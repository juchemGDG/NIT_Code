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

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                env=self.env,
                text=True,
                bufsize=1,
            )
            # Stdout und Stderr parallel lesen
            def read_stream(stream, kind):
                for line in stream:
                    self.output.emit(line, kind)
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
# Konsolenausgabe-Widget
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_idx = 0
        self._proc: subprocess.Popen | None = None
        self._setup_ui()
        self._start_shell()

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

    def _start_shell(self):
        shell = os.environ.get("SHELL", "/bin/bash") if sys.platform != "win32" else "cmd.exe"
        try:
            self._proc = subprocess.Popen(
                [shell],
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
            self._append(f"Shell konnte nicht gestartet werden: {e}\n", THEME["error"])

    def _read_output(self):
        if not self._proc:
            return
        for line in self._proc.stdout:
            self._append(line, THEME["terminal_text"])

    def _append(self, text: str, color: str):
        from PyQt6.QtCore import QMetaObject, Qt
        # Thread-sicherer Aufruf
        from PyQt6.QtCore import QMetaObject
        QMetaObject.invokeMethod(
            self,
            "_do_append",
            Qt.ConnectionType.QueuedConnection,
            *[],
        )
        # Direkte Methode über Signal
        self._bridge_append(text, color)

    def _bridge_append(self, text: str, color: str):
        from PyQt6.QtCore import QMetaObject, Qt
        # Nutze das Main-Thread-Event via Closure
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._do_append(text, color))

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
        self._do_append(f"$ {cmd}\n", THEME["accent"])
        if self._proc and self._proc.poll() is None:
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
        self.output_console = OutputConsole()
        self.output_console.error_link_clicked.connect(self.error_link_clicked)
        self.tabs.addTab(self.output_console, "Ausgabe")

        # Tab 2: Shell
        self.shell = ShellWidget()
        self.tabs.addTab(self.shell, "Shell")

        layout.addWidget(self.tabs)

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
