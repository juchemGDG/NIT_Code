# main.py
# Laeuft nach boot.py. Startet einen Webserver, der
#  1) die Blockly-/Editor-Oberflaeche aus /www ausliefert
#  2) per POST /api/run Python-Code entgegennimmt und ihn in einem
#     Hintergrund-Thread ausfuehrt – print-Ausgaben und Fehler werden
#     abgefangen und in einem Ringpuffer gesammelt
#  3) per GET /api/output?since=N neue Ausgabezeilen liefert (die Weboberflaeche
#     pollt diesen Endpunkt und zeigt sie in der Konsole)
#  4) per POST /api/stop das laufende Programm durch einen Reset beendet
#
# Der Webserver bleibt waehrend der Ausfuehrung erreichbar (eigener Thread).
# Hinweis: Der ESP32-C3 hat nur einen Kern – ein Nutzerprogramm mit einer
# reinen Endlosschleife OHNE sleep kann den Webserver ausbremsen. In der Praxis
# enthalten Schuelerprogramme fast immer ein time.sleep(_ms), das anderen
# Tasks Rechenzeit gibt.

import uasyncio as asyncio
import os
import sys
import io
import json
import _thread
import machine
import network

STATIC_DIR = "/www"
CODE_FILE = "/user_code.py"
MAX_LINES = 800   # Ringpuffer-Groesse fuer Konsolenausgaben

MIME_TYPES = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}

# ── Konsolen-Ausgabepuffer (thread-sicher) ────────────────────────────────
_out_lock = _thread.allocate_lock()
_out_lines = []     # gesammelte Ausgabezeilen
_out_base = 0       # wie viele Zeilen vorne bereits verworfen wurden
_running = False     # laeuft gerade ein Nutzerprogramm?


def _append(text):
    global _out_base
    with _out_lock:
        _out_lines.append(text)
        if len(_out_lines) > MAX_LINES:
            drop = len(_out_lines) - MAX_LINES
            del _out_lines[:drop]
            _out_base += drop


def _reset_output():
    global _out_base
    with _out_lock:
        _out_lines.clear()
        _out_base = 0


def _snapshot(since):
    """Liefert (neue_zeilen, gesamtzahl) ab absolutem Index ``since``."""
    with _out_lock:
        total = _out_base + len(_out_lines)
        start = since - _out_base
        if start < 0:
            start = 0
        return _out_lines[start:], total


def _user_print(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    _append(sep.join(str(a) for a in args) + end)


def _run_code(code):
    """Fuehrt den Nutzercode aus (im Hintergrund-Thread)."""
    global _running
    _running = True
    try:
        g = {"__name__": "__main__", "print": _user_print}
        exec(code, g)
    except Exception as e:
        buf = io.StringIO()
        sys.print_exception(e, buf)
        _append(buf.getvalue())
    finally:
        _running = False


# ── HTTP-Hilfen ───────────────────────────────────────────────────────────
def guess_mime(path):
    for ext, mime in MIME_TYPES.items():
        if path.endswith(ext):
            return mime
    return "application/octet-stream"


async def send_file(writer, path):
    try:
        size = os.stat(path)[6]
    except OSError:
        writer.write(b"HTTP/1.0 404 Not Found\r\nConnection: close\r\n\r\nNot found")
        await writer.drain()
        return
    mime = guess_mime(path)
    header = ("HTTP/1.0 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
              "Connection: close\r\n\r\n").format(mime, size)
    writer.write(header.encode())
    await writer.drain()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()


async def send_text(writer, body, status="200 OK", mime="text/plain"):
    if isinstance(body, str):
        body = body.encode()
    header = ("HTTP/1.0 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
              "Connection: close\r\n\r\n").format(status, mime, len(body))
    writer.write(header.encode())
    writer.write(body)
    await writer.drain()


async def read_headers(reader):
    headers = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b""):
            break
        if b":" in line:
            k, _, v = line.decode().partition(":")
            headers[k.strip().lower()] = v.strip()
    return headers


async def read_body(reader, n):
    body = b""
    while len(body) < n:
        chunk = await reader.read(n - len(body))
        if not chunk:
            break
        body += chunk
    return body


async def reset_soon():
    await asyncio.sleep_ms(300)
    machine.reset()


# ── Request-Handler ───────────────────────────────────────────────────────
async def handle_client(reader, writer):
    try:
        request_line = await reader.readline()
        if not request_line:
            return
        parts = request_line.decode().split()
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1]
        headers = await read_headers(reader)
        content_length = int(headers.get("content-length", 0))

        if method == "GET" and path.startswith("/api/output"):
            since = 0
            if "?" in path:
                for kv in path.split("?", 1)[1].split("&"):
                    if kv.startswith("since="):
                        try:
                            since = int(kv[6:])
                        except ValueError:
                            since = 0
            lines, total = _snapshot(since)
            payload = json.dumps({"lines": lines, "next": total, "running": _running})
            await send_text(writer, payload, mime="application/json")

        elif method == "GET" and path == "/api/info":
            try:
                ssid = network.WLAN(network.AP_IF).config("essid")
            except Exception:
                ssid = ""
            await send_text(writer, json.dumps({"ssid": ssid}), mime="application/json")

        elif method == "GET":
            if path == "/":
                path = "/index.html"
            await send_file(writer, STATIC_DIR + path)

        elif method == "POST" and path == "/api/run":
            body = await read_body(reader, content_length)
            code = body.decode("utf-8")
            if _running:
                await send_text(writer, "Es laeuft bereits ein Programm – erst Stopp.",
                                status="409 Conflict")
            else:
                _reset_output()
                try:
                    with open(CODE_FILE, "w") as f:
                        f.write(code)
                except OSError:
                    pass
                _thread.start_new_thread(_run_code, (code,))
                await send_text(writer, "OK")

        elif method == "POST" and path == "/api/stop":
            await send_text(writer, "OK - Board startet neu")
            asyncio.create_task(reset_soon())

        else:
            await send_text(writer, "Not found", status="404 Not Found")

    except Exception as e:
        print("Fehler im Request-Handler:", e)
    finally:
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Webserver laeuft: http://<AP-IP>/  (Standard: 192.168.4.1)")
    async with server:
        await server.wait_closed()


asyncio.run(main())
