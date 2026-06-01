"""Konsolenbereich: Shell + Programmausgaben + Fehler-Links."""
import re
import sys
import os
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QSplitter, QTabWidget,
)

from .config import THEME


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
            # Stdout und Stderr parallel in kleinen Chunks lesen (kein Warten auf \n)
            def read_stream(stream, kind):
                while True:
                    chunk = stream.read(256)
                    if not chunk:
                        break
                    self.output.emit(chunk.decode("utf-8", errors="replace"), kind)
                stream.close()

            t_out = threading.Thread(target=read_stream, args=(self._proc.stdout, "stdout"))
            t_err = threading.Thread(target=read_stream, args=(self._proc.stderr, "stderr"))
            t_out.start()
            t_err.start()
            t_out.join()
            t_err.join()
            self._proc.wait()
            self.finished_run.emit(self._proc.returncode)
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

            # Auf "OK" warten
            ok = ser.read(2)
            if ok != b"OK":
                extra = ser.read(256)
                self.output.emit(
                    f"⚠  REPL Fehler: {(ok + extra)!r}\n", "stderr"
                )
                self.finished_run.emit(1)
                ser.close()
                return

            # Ausgabe lesen bis ersten \x04 (stdout beendet)
            stdout_done = False
            stderr_buf  = b""
            rc          = 0

            while not self._abort:
                chunk = ser.read(256)
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
        self._current_cmd: list = [sys.executable, "-i"]
        self._text_ready.connect(self._do_append)
        self._setup_ui()
        self._start_shell([sys.executable, "-i"])  # Standard: Python REPL

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

        btn_clear = QPushButton("Leeren")
        btn_clear.setFixedWidth(70)
        btn_clear.setStyleSheet(self._btn_style())
        btn_clear.clicked.connect(self.output.clear)
        input_row.addWidget(btn_clear)

        layout.addLayout(input_row)

    def _btn_style(self):
        return (
            f"QPushButton {{ background:{THEME['bg_panel']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:4px; padding:3px 8px; }}"
            f"QPushButton:hover {{ background:{THEME['accent']}; color:#fff; }}"
        )

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_runner: ProcessRunner | None = None
        self._shell_is_micropython = False
        self._shell_pending_cmd: list | None = None
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
        self.tabs.addTab(output_container, "Ausgabe")

        # Tab 2: Shell
        self.shell = ShellWidget()
        self.tabs.addTab(self.shell, "Shell")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)

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

    # Delegations-Methoden
    def append_output(self, text: str):
        self.output_console.append_output(text)
        self.tabs.setCurrentIndex(0)

    def append_error(self, text: str):
        self.output_console.append_error(text)
        self.tabs.setCurrentIndex(0)

    def append_info(self, text: str):
        self.output_console.append_info(text)

    def append_success(self, text: str):
        self.output_console.append_success(text)

    def clear_output(self):
        self.output_console.clear_output()

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
            cmd = [sys.executable, "-m", "mpremote", "connect", port]
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
            exe = python_exec or sys.executable
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
