# main.py
# Laeuft nach boot.py. Startet einen einfachen Webserver, der
#  1) die Blockly-Oberflaeche aus /www ausliefert
#  2) per POST /api/upload generierten MicroPython-Code entgegennimmt,
#     als /user_code.py speichert und das Board neu startet
#  3) per POST /api/stop zurueck in den Programmiermodus wechselt
#     (naechster Boot fuehrt user_code.py NICHT aus)

import uasyncio as asyncio
import os
import machine

STATIC_DIR = "/www"
CODE_FILE = "/user_code.py"
RUN_FLAG = "/run_flag.txt"   # Existenz dieser Datei = "beim naechsten Boot ausfuehren"

MIME_TYPES = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}


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
    header = "HTTP/1.0 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n".format(mime, size)
    writer.write(header.encode())
    await writer.drain()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk:
                break
            writer.write(chunk)
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


async def restart_soon():
    await asyncio.sleep_ms(300)
    machine.reset()


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

        if method == "GET":
            if path == "/":
                path = "/index.html"
            await send_file(writer, STATIC_DIR + path)

        elif method == "POST" and path == "/api/upload":
            body = b""
            while len(body) < content_length:
                chunk = await reader.read(content_length - len(body))
                if not chunk:
                    break
                body += chunk
            code = body.decode("utf-8")
            with open(CODE_FILE, "w") as f:
                f.write(code)
            with open(RUN_FLAG, "w") as f:
                f.write("1")

            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK - Board startet neu und fuehrt den Code aus")
            await writer.drain()
            asyncio.create_task(restart_soon())

        elif method == "POST" and path == "/api/stop":
            try:
                os.remove(RUN_FLAG)
            except OSError:
                pass
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK - zurueck im Programmiermodus")
            await writer.drain()
            asyncio.create_task(restart_soon())

        else:
            writer.write(b"HTTP/1.0 404 Not Found\r\nConnection: close\r\n\r\nNot found")
            await writer.drain()

    except Exception as e:
        print("Fehler im Request-Handler:", e)
    finally:
        try:
            await writer.wait_closed()
        except Exception:
            pass


def should_run_user_code():
    try:
        os.stat(RUN_FLAG)
        os.stat(CODE_FILE)
        return True
    except OSError:
        return False


def run_user_code():
    print("Fuehre gespeicherten Blockly-Code aus (user_code.py) ...")
    try:
        import user_code  # fuehrt die Datei einmal aus
    except Exception as e:
        print("Fehler im Nutzercode:", e)
        # Bei Fehler zurueck in den Programmiermodus, damit man nicht ausgesperrt ist
        try:
            os.remove(RUN_FLAG)
        except OSError:
            pass


async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Webserver laeuft: http://<AP-IP>/  (Standard: 192.168.4.1)")
    async with server:
        await server.wait_closed()


if should_run_user_code():
    # Nutzercode blockiert hier bewusst (z.B. Endlosschleife mit Blinken).
    # Der Webserver startet danach nicht mehr - Reset-Taste oder Neustart
    # bringt das Board zurueck (RUN_FLAG wird dann erneut geprueft).
    run_user_code()
    # Falls der Nutzercode durchlaeuft (kein while True), zur Sicherheit
    # trotzdem den Server starten, damit man weiterarbeiten kann:
    asyncio.run(main())
else:
    asyncio.run(main())
