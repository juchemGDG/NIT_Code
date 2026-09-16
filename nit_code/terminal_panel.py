"""Eingebettetes Terminal mit echtem PTY + ANSI-Rendering (pyte).

Warum nicht die bestehende ``ShellWidget`` (siehe ``console_panel.py``)?
Die dort verwendete Strategie – ``TERM=dumb`` setzen und ANSI-Escape-Sequenzen
per Regex herausfiltern – funktioniert nur für Programme, die zeilenweise in
den Terminal-Scrollback schreiben (Python-REPL, mpremote-REPL). Vollbild-TUIs
wie ``claude`` zeichnen ihren Bildschirm dagegen aktiv per Cursor-Bewegung neu
(Alternate-Screen-Buffer, Farben, neu positionierte Eingabezeile). Ohne echte
Terminal-Emulation ergäbe das Escape-Stripping nur wirren, sich wiederholenden
Text.

``pyte`` übernimmt die Emulation: Es interpretiert den Bytestrom wie ein
echtes Terminal und hält einen Bildschirmpuffer (Zeichen + Cursor-Position +
Farbattribute je Zelle), den ``TerminalWidget`` zellenweise zeichnet.

Nur Unix (macOS/Linux) – Windows hat kein natives PTY, das bräuchte
``pywinpty``/ConPTY. Siehe ``pty_available()``.
"""
from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import threading
from pathlib import Path

try:
    # Unix-only Standardmodule. Der Import darf auf Windows nicht scheitern,
    # sonst crasht schon der bloße ``import terminal_panel`` die ganze App.
    # Aufrufer müssen vorher pty_available() prüfen – auf Windows bleiben
    # fcntl/termios dann einfach ungenutzt.
    import fcntl
    import termios
except ImportError:  # Windows
    fcntl = None
    termios = None

import pyte
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QFontMetrics, QKeyEvent, QPainter, QResizeEvent,
    QWheelEvent,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .config import THEME


def pty_available() -> bool:
    """True, wenn diese Plattform ein Unix-PTY hat (macOS/Linux, nicht Windows)."""
    return sys.platform != "win32"


_cached_login_path: str | None = None


def resolve_login_shell_path() -> str:
    """PATH wie in einem frisch geöffneten Terminal – NICHT das knappe PATH,
    mit dem macOS grafische Apps startet.

    Aus dem Terminal per ./run.sh gestartet erbt der Prozess die volle
    Shell-PATH (inkl. Homebrew, pyenv, und dem Installationsort der
    claude-CLI). Ein per Doppelklick/Dock gestartetes .app-Bundle – also
    genau das Release-Paket – bekommt von launchd dagegen nur ein absolutes
    Minimal-PATH (``/usr/bin:/bin:/usr/sbin:/sbin``) ohne alle drei. Deshalb
    findet ``shutil.which("claude")`` die CLI im Dev-Modus, im Release-Bundle
    aber nicht – obwohl beide Male derselbe Rechner mit derselben Installation
    gemeint ist.

    Lösung: die Login-Shell selbst nach ihrem PATH fragen (``-l`` lädt
    .zprofile/.zshrc bzw. .bash_profile, genau wie ein neues Terminal-Fenster
    es täte). Ergebnis wird gecacht, da das einen kurzlebigen Shell-Start
    kostet (~100–300 ms).
    """
    global _cached_login_path
    if _cached_login_path is not None:
        return _cached_login_path
    shell = os.environ.get("SHELL") or "/bin/zsh"
    path = ""
    try:
        result = subprocess.run(
            [shell, "-ilc", 'echo -n "$PATH"'],
            capture_output=True, text=True, timeout=5,
        )
        path = result.stdout.strip()
    except Exception:
        pass
    _cached_login_path = path or os.environ.get("PATH", "")
    return _cached_login_path


def find_claude_binary() -> str | None:
    """Sucht die claude-CLI robust – auch mit dem knappen launchd-PATH eines
    per Doppelklick gestarteten .app-Bundles (siehe resolve_login_shell_path()).
    """
    found = shutil.which("claude")
    if found:
        return found
    home = Path.home()
    for candidate in (
        home / ".local" / "bin" / "claude",
        home / ".claude" / "local" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
    ):
        if candidate.exists():
            return str(candidate)
    return shutil.which("claude", path=resolve_login_shell_path())


def _pick_monospace_font(point_size: int) -> QFont:
    """Echte feste Zeichenbreite ist Pflicht (zellenweises Zeichnen), anders als bei
    QTextEdit reicht ein bloßer Familienname-Wunsch nicht: ``QFont("A, B, C")`` behandelt
    Qt NICHT als CSS-Fallback-Liste, sondern sucht wörtlich nach der Familie "A, B, C" –
    ist die nicht installiert, springt Qt auf einen beliebigen (oft proportionalen) Ersatz,
    und das feste Spaltenraster reißt (Buchstaben laufen auseinander/übereinander).
    """
    preferred = ["JetBrains Mono", "Fira Code", "Cascadia Mono", "Consolas", "Menlo",
                 "DejaVu Sans Mono"]
    available = set(QFontDatabase.families())
    for name in preferred:
        if name in available:
            font = QFont(name, point_size)
            font.setFixedPitch(True)
            return font
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(point_size)
    return font


# ── ANSI-Namen → Hex (pyte löst 16-Farben-Codes in diese Namen auf; 256-Farben
#    und Truecolor liefert pyte bereits als fertigen Hex-String) ────────────
_ANSI_COLORS = {
    "black": "45475a", "red": "f38ba8", "green": "a6e3a1", "brown": "f9e2af",
    "blue": "89b4fa", "magenta": "cba6f7", "cyan": "89dceb", "white": "bac2de",
    "brightblack": "6c7086", "brightred": "fab0c4", "brightgreen": "c8f5c3",
    "brightbrown": "fff0b3", "brightblue": "b4cdfc", "brightmagenta": "ddc4fb",
    "bfightmagenta": "ddc4fb",  # Tippfehler in pyte.graphics.BG_AIXTERM, defensiv mit abgefangen
    "brightcyan": "b7ecf5", "brightwhite": "e4e6f5",
}


class _Screen(pyte.HistoryScreen):
    """HistoryScreen mit Fix für eine pyte-0.8.2-Falle.

    Moderne Shells/Readline-Konfigurationen senden häufig private-markierte
    CSI-Sequenzen, die auf 'm' enden (z. B. ``CSI > 4 ; 2 m`` – XTerms
    „modifyOtherKeys"). pyte leitet die dann mit ``private=True`` an
    ``select_graphic_rendition`` (SGR) weiter, dessen Signatur dieses Keyword
    gar nicht kennt → ``TypeError`` und Absturz des ganzen Streams. Hier
    abfangen und ignorieren (es betrifft nur Terminal-Modi, keine sichtbare
    Darstellung).
    """

    def select_graphic_rendition(self, *attrs, **kwargs):
        if kwargs.get("private"):
            return
        super().select_graphic_rendition(*attrs)


def _resolve_color(value: str, default_hex: str) -> QColor:
    if value == "default":
        return QColor(f"#{default_hex}")
    hexval = _ANSI_COLORS.get(value, value)  # sonst bereits fertiger Hex-String
    color = QColor(f"#{hexval}")
    return color if color.isValid() else QColor(f"#{default_hex}")


# ── Tastatur → Terminal-Bytes ───────────────────────────────────────────────
_KEY_SEQUENCES = {
    Qt.Key.Key_Up: b"\x1b[A",
    Qt.Key.Key_Down: b"\x1b[B",
    Qt.Key.Key_Right: b"\x1b[C",
    Qt.Key.Key_Left: b"\x1b[D",
    Qt.Key.Key_Home: b"\x1b[H",
    Qt.Key.Key_End: b"\x1b[F",
    Qt.Key.Key_Insert: b"\x1b[2~",
    Qt.Key.Key_Delete: b"\x1b[3~",
    Qt.Key.Key_PageUp: b"\x1b[5~",
    Qt.Key.Key_PageDown: b"\x1b[6~",
    Qt.Key.Key_Backspace: b"\x7f",
    Qt.Key.Key_Tab: b"\t",
    Qt.Key.Key_Backtab: b"\x1b[Z",
    Qt.Key.Key_Escape: b"\x1b",
    Qt.Key.Key_Return: b"\r",
    Qt.Key.Key_Enter: b"\r",
}


class _PtyProcess(QObject):
    """Startet einen Befehl an einem echten PTY und liest ihn im Hintergrund-Thread.

    Signale werden aus dem Lese-Thread heraus emittiert; Qt stellt sicher, dass
    verbundene Slots trotzdem im GUI-Thread ausgeführt werden (Queued Connection).
    """

    data_ready = pyqtSignal(bytes)
    finished_run = pyqtSignal(int)
    start_failed = pyqtSignal(str)

    def __init__(self, cmd: list[str], cwd: str | None, cols: int, rows: int, parent=None):
        super().__init__(parent)
        self._cmd = cmd
        self._cwd = cwd
        self._cols = cols
        self._rows = rows
        self._master_fd: int | None = None
        self._proc: subprocess.Popen | None = None
        self._terminating = False

    def start(self):
        import pty
        try:
            master_fd, slave_fd = pty.openpty()
            self._set_size(slave_fd, self._rows, self._cols)
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            # Gleicher Grund wie in find_claude_binary(): ohne das erhielte
            # `claude` selbst nur das knappe launchd-PATH und fände darin
            # aufgerufene Tools (git, python3, …) im Release-Bundle nicht.
            env["PATH"] = resolve_login_shell_path()
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                cwd=self._cwd, env=env, close_fds=True,
                preexec_fn=os.setsid,  # eigene Prozessgruppe → sauberes terminate()
            )
        except Exception as exc:
            self.start_failed.emit(str(exc))
            return
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        self._master_fd = master_fd
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._wait_loop, daemon=True).start()

    def _read_loop(self):
        import select
        while True:
            fd = self._master_fd
            if fd is None:
                break
            try:
                ready, _, _ = select.select([fd], [], [], 0.05)
                if not ready:
                    continue
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            self.data_ready.emit(data)

    def _wait_loop(self):
        if self._proc is None:
            return
        rc = self._proc.wait()
        if self._terminating:
            # Absichtlich beendet (z. B. Panel gewechselt/geschlossen) – kein
            # "Prozess beendet"-Signal mehr nötig, und self ist zu diesem
            # Zeitpunkt evtl. schon von Qt zerstört worden.
            return
        try:
            self.finished_run.emit(rc)
        except RuntimeError:
            pass  # Qt-Objekt wurde parallel bereits zerstört

    def write(self, data: bytes):
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, data)
            except OSError:
                pass

    def resize(self, rows: int, cols: int):
        self._rows, self._cols = rows, cols
        if self._master_fd is not None:
            self._set_size(self._master_fd, rows, cols)

    @staticmethod
    def _set_size(fd: int, rows: int, cols: int):
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def terminate(self):
        self._terminating = True
        if self._proc and self._proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._proc.pid), 15)
            except Exception:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None


class TerminalWidget(QWidget):
    """Zeichnet einen ``pyte``-Bildschirmpuffer zellenweise; leitet Tastatur an den PTY weiter."""

    finished_run = pyqtSignal(int)
    start_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._font = _pick_monospace_font(11)
        self._metrics = QFontMetrics(self._font)
        self._cell_w = max(1, self._metrics.horizontalAdvance("M"))
        self._cell_h = max(1, self._metrics.height())
        self._cols, self._rows = 80, 24
        self._screen = _Screen(self._cols, self._rows, history=5000, ratio=0.1)
        self._stream = pyte.ByteStream(self._screen)
        self._pty: _PtyProcess | None = None
        self._paged_up = False
        self._pending = bytearray()
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(16)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.timeout.connect(self.update)
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._toggle_cursor_blink)
        self._blink_timer.start()
        self._cursor_visible_blink = True

    # ── Prozess-Lebenszyklus ────────────────────────────────────────────────
    def start(self, cmd: list[str], cwd: str | None = None):
        """Startet ``cmd`` (z. B. ``["claude"]``) im Ordner ``cwd``."""
        self.stop()
        self._screen.reset()
        self._pty = _PtyProcess(cmd, cwd, self._cols, self._rows, parent=self)
        self._pty.data_ready.connect(self._on_data)
        self._pty.finished_run.connect(self._on_finished)
        self._pty.start_failed.connect(self._on_start_failed)
        self._pty.start()

    def stop(self):
        if self._pty is not None:
            self._pty.terminate()
            self._pty = None

    def is_running(self) -> bool:
        return self._pty is not None

    def _on_finished(self, rc: int):
        self._pty = None
        self.finished_run.emit(rc)

    def _on_start_failed(self, message: str):
        # Prozess (z. B. `claude`) konnte gar nicht erst gestartet werden
        # (Binary fehlt/PATH) – sonst würde is_running() fälschlich True
        # bleiben und ein erneuter start()-Versuch stillschweigend nichts tun.
        self._pty = None
        self.start_failed.emit(message)

    # ── Eingehende Daten ─────────────────────────────────────────────────────
    def _on_data(self, data: bytes):
        if self._paged_up:
            self._snap_to_bottom()
        try:
            self._stream.feed(data)
        except Exception as exc:
            # pyte (0.8.2, kaum noch gepflegt) kennt nicht jede moderne
            # Escape-Sequenz und kann dabei abstürzen (siehe _Screen oben für
            # einen bekannten Fall). Lieber diesen Chunk verwerfen als das
            # ganze Terminal-Widget mitreißen.
            print(f"[terminal_panel] pyte-Fehler beim Verarbeiten der Ausgabe: {exc}", file=sys.stderr)
        if not self._repaint_timer.isActive():
            self._repaint_timer.start()

    def _snap_to_bottom(self):
        history = self._screen.history
        while history.position < history.size and history.bottom:
            self._screen.next_page()
            history = self._screen.history
        self._paged_up = False

    # ── Zeichnen ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(THEME["terminal_bg"]))
        painter.setFont(self._font)
        default_fg = THEME["terminal_text"].lstrip("#")
        default_bg = THEME["terminal_bg"].lstrip("#")

        buffer = self._screen.buffer
        for y in range(self._rows):
            row = buffer[y]
            x = 0
            while x < self._cols:
                char = row[x]
                # Doppelbreite Zeichen (CJK/Emoji) belegen intern eine Folgezelle
                # mit leerem data – die überspringen wir beim Zeichnen nicht extra,
                # QFontMetrics rechnet die Breite über den Text selbst.
                fg = _resolve_color(char.fg, default_fg)
                bg = _resolve_color(char.bg, default_bg)
                if char.reverse:
                    fg, bg = bg, fg
                cell_rect_w = self._cell_w
                if bg.name() != f"#{default_bg}":
                    painter.fillRect(x * self._cell_w, y * self._cell_h,
                                      cell_rect_w, self._cell_h, bg)
                if char.data and char.data != " ":
                    font = QFont(self._font)
                    font.setBold(char.bold)
                    font.setItalic(char.italics)
                    font.setUnderline(char.underscore)
                    font.setStrikeOut(char.strikethrough)
                    painter.setFont(font)
                    painter.setPen(fg)
                    painter.drawText(
                        x * self._cell_w, y * self._cell_h + self._metrics.ascent(),
                        char.data,
                    )
                x += 1

        cursor = self._screen.cursor
        if not cursor.hidden and self._cursor_visible_blink and not self._paged_up:
            painter.fillRect(
                cursor.x * self._cell_w, cursor.y * self._cell_h,
                self._cell_w, self._cell_h,
                QColor(THEME["accent"]) if THEME.get("accent") else QColor("#7c6af7"),
            )
            under = buffer[cursor.y][cursor.x]
            if under.data and under.data != " ":
                painter.setPen(QColor(THEME["terminal_bg"]))
                painter.drawText(
                    cursor.x * self._cell_w, cursor.y * self._cell_h + self._metrics.ascent(),
                    under.data,
                )

    def _toggle_cursor_blink(self):
        self._cursor_visible_blink = not self._cursor_visible_blink
        self.update()

    # ── Größenanpassung ───────────────────────────────────────────────────
    def resizeEvent(self, event: QResizeEvent):
        cols = max(10, self.width() // self._cell_w)
        rows = max(4, self.height() // self._cell_h)
        if (cols, rows) != (self._cols, self._rows):
            self._cols, self._rows = cols, rows
            self._screen.resize(rows, cols)
            if self._pty is not None:
                self._pty.resize(rows, cols)
        super().resizeEvent(event)

    # ── Tastatur ─────────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        if self._pty is None:
            return
        key = event.key()
        mods = event.modifiers()

        # Bild-hoch/-runter mit Umschalt: lokaler Scrollback statt an den
        # Kindprozess weiterleiten (der bekäme sonst z. B. bei vim/less die
        # normale Seiten-Navigation doppelt gemeldet).
        if mods & Qt.KeyboardModifier.ShiftModifier and key in (
            Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
        ):
            if key == Qt.Key.Key_PageUp:
                self._screen.prev_page()
                self._paged_up = True
            else:
                self._screen.next_page()
                if self._screen.history.position >= self._screen.history.size:
                    self._paged_up = False
            self.update()
            return

        if mods & Qt.KeyboardModifier.ControlModifier and Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            self._pty.write(bytes([key - Qt.Key.Key_A + 1]))
            return

        if key in _KEY_SEQUENCES:
            self._pty.write(_KEY_SEQUENCES[key])
            return

        text = event.text()
        if text:
            self._pty.write(text.encode("utf-8"))

    def wheelEvent(self, event: QWheelEvent):
        steps = event.angleDelta().y() // 120
        if steps == 0:
            return
        if steps > 0:
            for _ in range(steps):
                self._screen.prev_page()
            self._paged_up = True
        else:
            for _ in range(-steps):
                self._screen.next_page()
            if self._screen.history.position >= self._screen.history.size:
                self._paged_up = False
        self.update()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


class ClaudeTerminalPanel(QWidget):
    """Kopfzeile (Ordner/Status) + eingebettetes Terminal für ``claude``.

    Bewusst NICHT über ``settings_dialog.tutor_mode`` erreichbar – dieses Panel
    ist nur per verstecktem Tastenkürzel in main_window.py zugänglich (siehe
    dortigen Kommentar). Kein Menüpunkt, keine sichtbare Einstellung.
    """

    process_exited = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        self._header_label = QLabel("🤖  Claude Code")
        header_layout.addWidget(self._header_label)
        header_layout.addStretch()
        layout.addWidget(header)

        self._terminal = TerminalWidget()
        self._terminal.finished_run.connect(self._on_finished)
        self._terminal.start_failed.connect(self._on_start_failed)
        layout.addWidget(self._terminal, 1)

        self._header = header
        self.refresh_theme()

    def start_claude(self, folder: str):
        """Startet ``claude`` im angegebenen Ordner – falls nicht schon aktiv."""
        if self._terminal.is_running():
            return
        claude_path = find_claude_binary()
        if not claude_path:
            self._header_label.setText("🤖  Claude Code  –  claude-CLI nicht gefunden")
            return
        self._header_label.setText(f"🤖  Claude Code  –  {folder}")
        # Absoluten Pfad übergeben statt des bloßen Namens "claude": subprocess
        # löst Kommandos sonst wieder über das eigene (evtl. knappe) PATH auf.
        self._terminal.start([claude_path], cwd=folder)
        self._terminal.setFocus()

    def stop(self):
        self._terminal.stop()

    def is_running(self) -> bool:
        return self._terminal.is_running()

    def focus_terminal(self):
        self._terminal.setFocus()

    def _on_finished(self, rc: int):
        self._header_label.setText(f"🤖  Claude Code  –  beendet (Code {rc})")
        self.process_exited.emit(rc)

    def _on_start_failed(self, message: str):
        self._header_label.setText(f"🤖  Claude Code  –  Start fehlgeschlagen: {message}")

    def refresh_theme(self):
        self._header.setStyleSheet(
            f"background:{THEME['bg_panel']}; border-bottom:1px solid {THEME['border']};"
        )
        self._header_label.setStyleSheet(f"color:{THEME['text']}; font-weight:bold;")
