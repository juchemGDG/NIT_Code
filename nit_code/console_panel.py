"""Konsolenbereich: Shell + Programmausgaben + Fehler-Links."""
import re
import sys
import os
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QSplitter, QTabWidget,
)

from .config import THEME, python_executable, tool_command


# ──────────────────────────────────────────────────────────────────────────────
# Signal-Brücke für Thread-sichere Ausgaben
# ──────────────────────────────────────────────────────────────────────────────
class _OutputBridge(QObject):
    append_text = pyqtSignal(str, str)   # (text, style)  style ∈ stdout|stderr|info|error


class ProcessRunner(QThread):
    """Führt einen Subprozess aus und leitet stdout/stderr weiter."""
    output = pyqtSignal(str, str)   # (text, kind)
    finished_run = pyqtSignal(int)  # return-code

    def __init__(self, cmd: list, cwd: str | None = None, env=None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self._proc = None

    def send_input(self, text: str):
        """Sendet Text an stdin des laufenden Prozesses (binärer Stream)."""
        if self._proc and self._proc.poll() is None and self._proc.stdin:
            try:
                self._proc.stdin.write((text + "\n").encode("utf-8"))
                self._proc.stdin.flush()
            except Exception:
                pass

    def run(self):
        import codecs
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=self.cwd,
                env=self.env,
                bufsize=0,   # unbuffered – damit input()-Prompts sofort erscheinen
            )
            # Stdout und Stderr parallel in größeren Chunks lesen. Ein
            # inkrementeller UTF-8-Decoder verhindert, dass Mehrbyte-Zeichen
            # (Umlaute, ², €, Emojis) an Chunk-Grenzen zerschnitten werden.
            def read_stream(stream, kind):
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                try:
                    while True:
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        text = decoder.decode(chunk)
                        if text:
                            self.output.emit(text, kind)
                    rest = decoder.decode(b"", final=True)
                    if rest:
                        self.output.emit(rest, kind)
                except (OSError, ValueError):
                    pass   # Pipe wurde geschlossen / Prozess beendet
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass

            # Daemon-Threads: blockieren das Programmende nicht, falls eine vom
            # Schülerprogramm gestartete Subprozess-/Thread-Instanz das Pipe-Ende
            # offen hält.
            t_out = threading.Thread(target=read_stream, args=(self._proc.stdout, "stdout"), daemon=True)
            t_err = threading.Thread(target=read_stream, args=(self._proc.stderr, "stderr"), daemon=True)
            t_out.start()
            t_err.start()
            # Auf den ECHTEN Prozess-Exit warten (nicht auf Pipe-EOF). So wird
            # 'Programm beendet' auch dann gemeldet, wenn ein geerbtes Pipe-Ende
            # in einem Kindprozess offen bleibt – sonst „hängt“ die Ausführung.
            rc = self._proc.wait()
            # Restausgabe (z. B. Traceback) noch einsammeln, aber nicht ewig warten.
            t_out.join(timeout=1.5)
            t_err.join(timeout=1.5)
            self.finished_run.emit(rc)
        except Exception as e:
            self.output.emit(f"Fehler beim Starten: {e}\n", "stderr")
            self.finished_run.emit(-1)

    def terminate_process(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


# ──────────────────────────────────────────────────────────────────────────────
# MicroPython-Runner: interaktiver Raw-REPL via pyserial
# ──────────────────────────────────────────────────────────────────────────────
class MicroPythonRunner(QThread):
    """Führt ein MicroPython-Skript über Raw-REPL (pyserial) aus.
    Unterstützt bidirektionales stdin/stdout – input() funktioniert.
    """
    output       = pyqtSignal(str, str)   # (text, kind)
    finished_run = pyqtSignal(int)

    def __init__(self, port: str, script_path: str):
        super().__init__()
        self._port        = port
        self._script_path = script_path
        self._serial      = None
        self._abort       = False

    def send_input(self, text: str):
        """Schickt Benutzereingabe an den Controller."""
        if self._serial and self._serial.is_open:
            try:
                self._serial.write((text + "\r\n").encode("utf-8"))
            except Exception:
                pass

    def terminate_process(self):
        """Unterbricht laufendes Programm sicher (doppeltes Ctrl+C + Raw-REPL-Exit)."""
        self._abort = True
        if self._serial and self._serial.is_open:
            try:
                # Doppeltes Ctrl+C: unterbricht auch Endlosschleifen zuverlässig
                self._serial.write(b"\x03\x03")
            except Exception:
                pass

    def run(self):
        import serial
        import time as _t
        try:
            ser = serial.Serial(self._port, 115200, timeout=0.1)
            self._serial = ser

            # Laufendes Programm unterbrechen
            ser.write(b"\x03\x03")
            _t.sleep(0.3)
            ser.reset_input_buffer()

            # Raw-REPL aktivieren (Ctrl+A)
            ser.write(b"\x01")
            if not self._read_until(ser, b">", timeout=4.0):
                self.output.emit("⚠  Raw-REPL konnte nicht gestartet werden.\n", "stderr")
                self.finished_run.emit(1)
                ser.close()
                return

            # Skript übertragen + ausführen (Ctrl+D)
            with open(self._script_path, "rb") as f:
                code = f.read()
            ser.write(code + b"\x04")

            # Auf "OK" warten. Je nach Skriptgröße (z. B. I2C-Programme mit
            # mehreren NIT-Bibliotheken) braucht der Controller dafür spürbar
            # länger als ein einzelner read() – deshalb bis zu 5 s sammeln,
            # aber genau 2 Bytes lesen, um keine Programmausgabe zu verschlucken.
            ok       = b""
            deadline = _t.time() + 5.0
            while len(ok) < 2 and _t.time() < deadline:
                ok += ser.read(2 - len(ok))
            if ok != b"OK":
                extra = ser.read(256)
                self.output.emit(
                    f"⚠  Der Controller hat den Programmstart nicht bestätigt "
                    f"(Antwort: {(ok + extra)!r}).\n"
                    f"   Bitte Controller über '↻' neu verbinden oder kurz "
                    f"aus- und wieder einstecken und erneut starten.\n",
                    "stderr",
                )
                self.finished_run.emit(1)
                ser.close()
                return

            # Ausgabe lesen bis ersten \x04 (stdout beendet)
            stdout_done = False
            stderr_buf  = b""
            rc          = 0

            while not self._abort:
                # Wird der Controller während des Laufs abgezogen, meldet
                # pyserial entweder einen Fehler oder der Port ist geschlossen –
                # dann sauber abbrechen statt endlos auf Daten zu warten.
                if not ser.is_open:
                    self.output.emit(
                        "\n⚠  Verbindung zum Controller verloren "
                        "(abgezogen?).\n", "stderr")
                    rc = 1
                    break
                try:
                    chunk = ser.read(256)
                except (OSError, serial.SerialException) as exc:
                    self.output.emit(
                        f"\n⚠  Verbindung zum Controller unterbrochen: {exc}\n",
                        "stderr")
                    rc = 1
                    break
                if not chunk:
                    continue

                if not stdout_done:
                    if b"\x04" in chunk:
                        i    = chunk.index(b"\x04")
                        head = chunk[:i]
                        if head:
                            self.output.emit(head.decode("utf-8", errors="replace"), "stdout")
                        stdout_done = True
                        stderr_buf  = chunk[i + 1:]
                    else:
                        self.output.emit(chunk.decode("utf-8", errors="replace"), "stdout")
                else:
                    stderr_buf += chunk
                    if b"\x04" in stderr_buf:
                        i   = stderr_buf.index(b"\x04")
                        err = stderr_buf[:i].decode("utf-8", errors="replace").strip()
                        if err and "KeyboardInterrupt" not in err:
                            self.output.emit(err + "\n", "stderr")
                            rc = 1
                        break

            try:
                ser.write(b"\x02")   # Zurück in normalen REPL (Ctrl+B)
            except Exception:
                pass
            ser.close()
            self.finished_run.emit(rc)

        except Exception as exc:
            self.output.emit(f"⚠  Verbindungsfehler: {exc}\n", "stderr")
            self.finished_run.emit(1)

    @staticmethod
    def _read_until(ser, needle: bytes, timeout: float) -> bool:
        import time as _t
        buf      = b""
        deadline = _t.time() + timeout
        while _t.time() < deadline:
            data = ser.read(64)
            if data:
                buf += data
                if needle in buf:
                    return True
        return False
# ──────────────────────────────────────────────────────────────────────────────
_ERROR_PATTERN = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)'
)


class OutputConsole(QTextEdit):
    """Zeigt Programmausgaben an. Fehler-Links klickbar (rot, unterstrichen)."""

    error_link_clicked = pyqtSignal(str, int)   # (dateipfad, zeilennummer)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 11))
        self.setStyleSheet(
            f"background:{THEME['terminal_bg']}; color:{THEME['terminal_text']};"
            f" border:none; padding:4px;"
        )
        self._links: dict[str, tuple[str, int]] = {}   # anchor → (file, line)

    def append_output(self, text: str):
        """Normale Ausgabe (weiß)."""
        self._append_colored(text, THEME["terminal_text"])

    def append_error(self, text: str):
        """Fehlerausgabe: Traceback-Zeilen werden als klickbare Links dargestellt."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        for line in text.splitlines(keepends=True):
            m = _ERROR_PATTERN.search(line)
            if m:
                filepath = m.group("file")
                lineno = int(m.group("line"))
                anchor = f"err_{filepath}_{lineno}"
                self._links[anchor] = (filepath, lineno)

                # Zeile vor dem Match normal ausgeben
                pre = line[:m.start()]
                if pre:
                    fmt = QTextCharFormat()
                    fmt.setForeground(QColor(THEME["error"]))
                    cursor.insertText(pre, fmt)

                # Match als klickbaren Link
                fmt_link = QTextCharFormat()
                fmt_link.setForeground(QColor(THEME["error"]))
                fmt_link.setFontUnderline(True)
                fmt_link.setAnchor(True)
                fmt_link.setAnchorHref(anchor)
                cursor.insertText(m.group(0), fmt_link)

                # Rest der Zeile
                post = line[m.end():]
                if post:
                    fmt2 = QTextCharFormat()
                    fmt2.setForeground(QColor(THEME["error"]))
                    cursor.insertText(post, fmt2)
            else:
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(THEME["error"]))
                cursor.insertText(line, fmt)

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_info(self, text: str):
        self._append_colored(text, THEME["info"])

    def append_success(self, text: str):
        self._append_colored(text, THEME["success"])

    def _append_colored(self, text: str, color: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def refresh_theme(self):
        self.setStyleSheet(
            f"background:{THEME['terminal_bg']}; color:{THEME['terminal_text']};"
            f" border:none; padding:4px;"
        )

    def clear_output(self):
        self.clear()
        self._links.clear()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        anchor = self.anchorAt(event.pos())
        if anchor and anchor in self._links:
            filepath, lineno = self._links[anchor]
            self.error_link_clicked.emit(filepath, lineno)


# ──────────────────────────────────────────────────────────────────────────────
# Shell-Widget (interaktive Eingabe)
# ──────────────────────────────────────────────────────────────────────────────
class ShellWidget(QWidget):
    """Einfache interaktive Shell mit Eingabezeile und Ausgabebereich."""

    # Thread-sicheres Signal: aus Hintergrund-Thread emittierbar
    _text_ready = pyqtSignal(str, str)   # (text, color)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_idx = 0
        self._proc: subprocess.Popen | None = None
        self._master_fd: int | None = None   # PTY master (Unix)
        self._current_cmd: list = [python_executable(), "-i"]
        self._text_ready.connect(self._do_append)
        self._setup_ui()
        # In PyInstaller-Bundles ist sys.executable die App-EXE, kein Python-Interpreter.
        # Die Shell wird dann über set_shell_mode() mit dem System-Python gestartet.
        if not getattr(sys, 'frozen', False):
            self._start_shell([python_executable(), "-i"])  # Standard: Python REPL

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 11))
        self.output.setStyleSheet(
            f"background:{THEME['terminal_bg']}; color:{THEME['terminal_text']};"
            f" border:none; padding:4px;"
        )
        layout.addWidget(self.output)

        # Eingabezeile
        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)
        input_row.setSpacing(4)

        self._prompt_label = QLabel("$")
        self._prompt_label.setStyleSheet(
            f"color:{THEME['accent']}; font-family:monospace; font-size:12px;"
        )
        input_row.addWidget(self._prompt_label)

        self._input = QLineEdit()
        self._input.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px; padding:3px 6px;"
            f" font-family:'JetBrains Mono', 'Fira Code', Consolas, monospace; font-size:11px;"
        )
        self._input.returnPressed.connect(self._send_command)
        self._input.installEventFilter(self)
        input_row.addWidget(self._input)

        self._btn_clear = QPushButton("Leeren")
        self._btn_clear.setFixedWidth(70)
        self._btn_clear.setStyleSheet(self._btn_style())
        self._btn_clear.clicked.connect(self.output.clear)
        input_row.addWidget(self._btn_clear)

        layout.addLayout(input_row)

    def _btn_style(self):
        return (
            f"QPushButton {{ background:{THEME['bg_panel']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px; padding:3px 8px; }}"
            f"QPushButton:hover {{ background:{THEME['accent']}; color:#fff; }}"
        )

    def refresh_theme(self):
        self.output.setStyleSheet(
            f"background:{THEME['terminal_bg']}; color:{THEME['terminal_text']};"
            f" border:none; padding:4px;"
        )
        self._prompt_label.setStyleSheet(
            f"color:{THEME['accent']}; font-family:monospace; font-size:12px;"
        )
        self._input.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px; padding:3px 6px;"
            f" font-family:'JetBrains Mono', 'Fira Code', Consolas, monospace; font-size:11px;"
        )
        self._btn_clear.setStyleSheet(self._btn_style())

    def restart(self, cmd: list):
        """Beendet den aktuellen Prozess und startet neu mit neuem Befehl."""
        self._current_cmd = cmd
        self._kill_proc()
        self.output.clear()
        self._start_shell(cmd)

    def stop(self):
        """Beendet den Prozess ohne Neustart (Port freigeben)."""
        self._kill_proc()

    def resume(self):
        """Startet den zuletzt verwendeten Befehl neu."""
        if self._current_cmd:
            self._start_shell(self._current_cmd)

    def _kill_proc(self):
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._proc = None

    def _start_shell(self, cmd: list):
        """Startet cmd als interaktiven Prozess (PTY auf Unix, PIPE auf Windows)."""
        try:
            if sys.platform != "win32":
                # Unix/macOS: PTY damit readline/REPL korrekt funktioniert
                import pty, termios, fcntl, struct
                master_fd, slave_fd = pty.openpty()
                try:
                    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ,
                                struct.pack("HHHH", 24, 80, 0, 0))
                except Exception:
                    pass
                env = os.environ.copy()
                env["TERM"] = "dumb"          # readline ohne Cursor-Escape-Seq.
                env["PYTHONUNBUFFERED"] = "1"
                self._proc = subprocess.Popen(
                    cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    cwd=Path.home(),
                    env=env,
                )
                os.close(slave_fd)
                self._master_fd = master_fd
                t = threading.Thread(target=self._read_pty, daemon=True)
                t.start()
            else:
                self._proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=Path.home(),
                )
                t = threading.Thread(target=self._read_output, daemon=True)
                t.start()
        except Exception as e:
            self._append(f"Prozess konnte nicht gestartet werden: {e}\n", THEME["error"])

    def _read_pty(self):
        """Liest kontinuierlich vom PTY-Master (Unix/macOS)."""
        import select, re as _re
        while True:
            # Lokale Kopie sichert gegen Race mit _kill_proc (setzt master_fd = None)
            fd = self._master_fd
            if fd is None or self._proc is None or self._proc.poll() is not None:
                break
            try:
                r, _, _ = select.select([fd], [], [], 0.1)
                if r:
                    data = os.read(fd, 4096)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        # ANSI/VT100-Escape-Sequenzen entfernen
                        text = _re.sub(r'\x1b\[[\x20-\x3f]*[\x40-\x7e]', '', text)
                        text = _re.sub(r'\x1b\][^\x07]*\x07', '', text)
                        text = _re.sub(r'\x1b[^[\]]', '', text)
                        text = _re.sub(r'\r(?!\n)', '', text)
                        text = text.replace('\r\n', '\n')
                        self._bridge_append(text, THEME["terminal_text"])
            except (OSError, TypeError):
                break

    def _read_output(self):
        if not self._proc:
            return
        for line in self._proc.stdout:
            self._append(line, THEME["terminal_text"])

    def _append(self, text: str, color: str):
        """Thread-sicher: aus Hintergrund-Thread aufrufbar."""
        self._text_ready.emit(text, color)

    def _bridge_append(self, text: str, color: str):
        """Alias für _append (Kompatibilität)."""
        self._text_ready.emit(text, color)

    def _do_append(self, text: str, color: str):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _send_command(self):
        cmd = self._input.text().strip()
        if not cmd:
            return
        self._history.append(cmd)
        self._hist_idx = len(self._history)
        if self._master_fd is not None:
            # PTY: schreiben → bash echot den Befehl selbst zurück
            try:
                os.write(self._master_fd, (cmd + "\n").encode())
            except OSError as e:
                self._do_append(f"Fehler: {e}\n", THEME["error"])
        elif self._proc and self._proc.poll() is None:
            self._do_append(f"$ {cmd}\n", THEME["accent"])
            try:
                self._proc.stdin.write(cmd + "\n")
                self._proc.stdin.flush()
            except Exception as e:
                self._do_append(f"Fehler: {e}\n", THEME["error"])
        self._input.clear()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up and self._history:
                self._hist_idx = max(0, self._hist_idx - 1)
                self._input.setText(self._history[self._hist_idx])
                return True
            if key == Qt.Key.Key_Down:
                self._hist_idx = min(len(self._history), self._hist_idx + 1)
                if self._hist_idx < len(self._history):
                    self._input.setText(self._history[self._hist_idx])
                else:
                    self._input.clear()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Kombiniertes Konsolenpanel
# ──────────────────────────────────────────────────────────────────────────────
class ConsolePanel(QWidget):
    """Konsolenpanel mit Tabs: Ausgabe + Shell."""

    error_link_clicked = pyqtSignal(str, int)
    explain_requested  = pyqtSignal()   # „Infi erklärt diesen Fehler"-Knopf gedrückt

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_runner: ProcessRunner | None = None
        self._shell_is_micropython = False
        self._shell_pending_cmd: list | None = None
        # Gepufferte Programmausgabe: viele kleine print()-Chunks werden
        # gesammelt und nur alle 40 ms gebündelt eingefügt. Das verhindert,
        # dass der GUI-Thread bei ausgabeintensiven Programmen (Schleifen mit
        # vielen print()) durch zehntausende Einzel-Updates einfriert.
        self._pending: list[tuple[str, str]] = []   # (text, kind) kind ∈ out|err
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(40)
        self._flush_timer.timeout.connect(self._flush_pending)
        # Serial Plotter (nur bei Bedarf eingeblendet, siehe set_plotter_visible).
        self._plot = None
        self._plot_active = False
        self._plot_config: dict | None = None   # Achsen-Standardwerte aus den Einstellungen
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: none;
                background: {THEME['terminal_bg']};
            }}
            QTabBar::tab {{
                background: {THEME['bg_panel']};
                color: {THEME['text_dim']};
                padding: 5px 14px;
                border: none;
                border-right: 1px solid {THEME['border']};
            }}
            QTabBar::tab:selected {{
                background: {THEME['terminal_bg']};
                color: {THEME['text']};
                border-bottom: 2px solid {THEME['accent']};
            }}
            """
        )

        # Tab 1: Ausgabe
        output_container = QWidget()
        oc_layout = QVBoxLayout(output_container)
        oc_layout.setContentsMargins(0, 0, 0, 0)
        oc_layout.setSpacing(0)
        self.output_console = OutputConsole()
        self.output_console.error_link_clicked.connect(self.error_link_clicked)
        oc_layout.addWidget(self.output_console)

        # Eingabezeile für laufende Programme (input()-Unterstützung)
        self._input_bar = QWidget()
        self._input_bar.setVisible(False)
        inp_row = QHBoxLayout(self._input_bar)
        inp_row.setContentsMargins(4, 2, 4, 4)
        inp_row.setSpacing(4)
        self._input_prompt = QLabel("➜")
        self._input_prompt.setStyleSheet(
            f"color:{THEME['accent']}; font-family:monospace; font-size:13px;"
        )
        inp_row.addWidget(self._input_prompt)
        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Eingabe hier tippen und Enter drücken …")
        self._input_field.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['accent']}; border-radius:4px; padding:3px 6px;"
            f" font-family:'JetBrains Mono', Consolas, monospace; font-size:11px;"
        )
        self._input_field.returnPressed.connect(self._send_input)
        inp_row.addWidget(self._input_field)
        oc_layout.addWidget(self._input_bar)

        # Leiste „Infi erklärt diesen Fehler" – erscheint nur nach einem Absturz,
        # wenn der KI-Tutor (Ollama) aktiv ist.
        self._explain_bar = QWidget()
        self._explain_bar.setVisible(False)
        ex_row = QHBoxLayout(self._explain_bar)
        ex_row.setContentsMargins(4, 2, 4, 4)
        ex_row.setSpacing(4)
        self._explain_btn = QPushButton("🤖  Infi erklärt diesen Fehler")
        self._explain_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._explain_btn.clicked.connect(self.explain_requested)
        ex_row.addWidget(self._explain_btn)
        ex_row.addStretch()
        oc_layout.addWidget(self._explain_bar)

        self.tabs.addTab(output_container, "Ausgabe")

        # Tab 2: Shell
        self.shell = ShellWidget()
        self.tabs.addTab(self.shell, "Shell")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)

    def refresh_theme(self):
        self.tabs.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: none;
                background: {THEME['terminal_bg']};
            }}
            QTabBar::tab {{
                background: {THEME['bg_panel']};
                color: {THEME['text_dim']};
                padding: 5px 14px;
                border: none;
                border-right: 1px solid {THEME['border']};
            }}
            QTabBar::tab:selected {{
                background: {THEME['terminal_bg']};
                color: {THEME['text']};
                border-bottom: 2px solid {THEME['accent']};
            }}
            """
        )
        self._input_prompt.setStyleSheet(
            f"color:{THEME['accent']}; font-family:monospace; font-size:13px;"
        )
        self._input_field.setStyleSheet(
            f"background:{THEME['bg_dark']}; color:{THEME['text']};"
            f" border:1px solid {THEME['accent']}; border-radius:4px; padding:3px 6px;"
            f" font-family:'JetBrains Mono', Consolas, monospace; font-size:11px;"
        )
        self._explain_btn.setStyleSheet(
            f"QPushButton {{ background:{THEME['accent']}; color:#fff; border:none;"
            f" border-radius:4px; padding:5px 12px; font-size:12px; }}"
            f"QPushButton:hover {{ background:{THEME['accent_hover']}; }}"
        )
        self.output_console.refresh_theme()
        self.shell.refresh_theme()
        if self._plot is not None:
            self._plot.refresh_theme()

    def _on_tab_changed(self, index: int):
        """mpremote-REPL erst starten wenn Shell-Tab aktiv wird."""
        if index == 1 and self._shell_pending_cmd:
            self.shell.restart(self._shell_pending_cmd)
            self._shell_pending_cmd = None
        elif index != 1 and self._shell_is_micropython:
            # Shell-Tab verlassen → Port freigeben
            self.shell.stop()

    def _send_input(self):
        text = self._input_field.text()
        self._input_field.clear()
        # Eingabe im Ausgabefeld anzeigen (Echo)
        self.output_console.append_info(f"➜ {text}\n")
        if self._active_runner:
            self._active_runner.send_input(text)

    def set_active_runner(self, runner: ProcessRunner | None):
        """Verbindet Eingabezeile mit dem aktuell laufenden Prozess."""
        self._active_runner = runner
        self._input_bar.setVisible(runner is not None)
        if runner is not None:
            self.tabs.setCurrentIndex(0)
            self._input_field.setFocus()

    # ── Gepufferte Programmausgabe (hohe Frequenz) ──────────────────────────
    def append_program_output(self, text: str):
        """stdout eines laufenden Programms – gepuffert/gebündelt."""
        if self._plot_active and self._plot is not None:
            self._plot.feed(text)
        self._enqueue(text, "out")

    def append_program_error(self, text: str):
        """stderr eines laufenden Programms – gepuffert/gebündelt."""
        self._enqueue(text, "err")

    def _enqueue(self, text: str, kind: str):
        self._pending.append((text, kind))
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_pending(self):
        if not self._pending:
            self._flush_timer.stop()
            return
        pending = self._pending
        self._pending = []
        # stdout und stderr kommen über zwei getrennte Pipes/Threads und damit in
        # nicht garantierter Reihenfolge an (Race Condition – ein Traceback konnte
        # so VOR der zugehörigen Programmausgabe erscheinen). Innerhalb eines
        # Flush-Fensters geben wir deshalb erst die normale Ausgabe, dann die
        # Fehlerausgabe aus. Für den häufigsten Fall (Programm gibt etwas aus und
        # stürzt am Ende ab) ist die Reihenfolge damit immer korrekt.
        out_text = "".join(text for text, kind in pending if kind != "err")
        err_text = "".join(text for text, kind in pending if kind == "err")
        if out_text:
            self.output_console.append_output(out_text)
        if err_text:
            self.output_console.append_error(err_text)
        self._focus_output_tab()

    def _focus_output_tab(self):
        """Schaltet auf den Ausgabe-Tab – außer der Plotter ist gerade aktiv.

        So reißt neue Programmausgabe den Lernenden nicht aus dem Live-Graph.
        """
        if self._plot_active and self.tabs.currentWidget() is self._plot:
            return
        self.tabs.setCurrentIndex(0)

    def flush_now(self):
        """Restpuffer sofort ausgeben (z. B. bevor 'Programm beendet' erscheint)."""
        self._flush_pending()

    # Delegations-Methoden
    def append_output(self, text: str):
        self.output_console.append_output(text)
        self._focus_output_tab()

    def append_error(self, text: str):
        self.output_console.append_error(text)
        self._focus_output_tab()

    def append_info(self, text: str):
        self.output_console.append_info(text)

    def append_success(self, text: str):
        self.output_console.append_success(text)

    def append_hint(self, text: str):
        """Verständlicher Klartext-Hinweis zu einem Fehler (eigene Info-Farbe)."""
        self.output_console.append_info("\n" + text)
        self._focus_output_tab()

    def set_explain_visible(self, visible: bool):
        """Zeigt/versteckt den „Infi erklärt diesen Fehler"-Knopf."""
        self._explain_bar.setVisible(visible)

    def set_plot_defaults(self, config: dict):
        """Achsen-Standardwerte des Plotters setzen (aus den Einstellungen)."""
        self._plot_config = dict(config)
        if self._plot is not None:
            self._plot.apply_config(**config)

    def clear_output(self):
        self.output_console.clear_output()
        if self._plot is not None:
            self._plot.clear()   # bei jedem Programmstart frischer Graph

    def set_plotter_visible(self, visible: bool):
        """Blendet den Serial-Plotter-Tab bei Bedarf ein bzw. wieder aus.

        Solange er aus ist, fällt keinerlei Parsing-Aufwand an (siehe
        :meth:`append_program_output`). Die Plot-Instanz bleibt erhalten, sodass
        beim erneuten Einblenden die bisherigen Kurven nicht verloren gehen.
        """
        if visible:
            if self._plot is None:
                from .serial_plot import SerialPlot
                self._plot = SerialPlot()
                if self._plot_config:
                    self._plot.apply_config(**self._plot_config)
            if self.tabs.indexOf(self._plot) == -1:
                self.tabs.addTab(self._plot, "📈 Plotter")
            self._plot_active = True
            self.tabs.setCurrentWidget(self._plot)
        else:
            self._plot_active = False
            if self._plot is not None:
                idx = self.tabs.indexOf(self._plot)
                if idx != -1:
                    self.tabs.removeTab(idx)

    def pause_shell(self):
        """Port freigeben: Shell-Prozess beenden."""
        self.shell.stop()
        if self._shell_is_micropython:
            # Beim nächsten Tab-Klick neu starten
            self._shell_pending_cmd = self.shell._current_cmd

    def resume_shell(self):
        """Shell neu starten, aber nur wenn Shell-Tab gerade sichtbar ist."""
        if self._shell_is_micropython and self.tabs.currentIndex() == 1:
            self.shell.resume()

    def set_shell_mode(self, mode: str, port: str = "", python_exec: str = ""):
        """Setzt Shell-Modus. mpremote-REPL wird erst beim Tab-Klick gestartet."""
        if mode == "micropython" and port:
            cmd = [*tool_command("mpremote"), "connect", port]
            label = f"Shell  –  MicroPython REPL ({port})"
            self._shell_is_micropython = True
            self.shell.stop()                 # alten Prozess beenden
            self.shell._current_cmd = cmd     # für resume()
            if self.tabs.currentIndex() == 1:
                # Shell-Tab bereits aktiv → sofort starten
                self.shell.restart(cmd)
            else:
                # Lazy: erst beim nächsten Tab-Klick starten
                self._shell_pending_cmd = cmd
        else:
            exe = python_exec or python_executable()
            cmd = [exe, "-i"]
            label = "Shell  –  Python REPL"
            self._shell_is_micropython = False
            self._shell_pending_cmd = None
            self.shell.restart(cmd)
        self.tabs.setTabText(1, label)

    def set_font_size(self, size: int):
        """Schriftgröße der Konsole und Shell ändern."""
        font = QFont("JetBrains Mono, Fira Code, Consolas, monospace", size)
        self.output_console.setFont(font)   # OutputConsole ist selbst das QTextEdit
        self.shell.output.setFont(font)

    def set_scrollback_limit(self, lines: int):
        """Maximale Zeilenzahl im Output- und Shell-Puffer setzen."""
        self.output_console.document().setMaximumBlockCount(lines)
        self.shell.output.document().setMaximumBlockCount(lines)
