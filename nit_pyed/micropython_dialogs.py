"""MicroPython-Dialoge: Flash-Dialog & Bibliotheks-Manager."""
import os
import threading
from pathlib import Path

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QFileDialog, QTextEdit,
    QGroupBox, QRadioButton, QLineEdit, QListWidget,
    QListWidgetItem, QSplitter, QMessageBox, QCheckBox,
)
from PyQt6.QtGui import QFont, QColor

from .config import THEME, SUPPORTED_BOARDS, LIB_REPO_API, LIB_REPO_RAW

# ──────────────────────────────────────────────────────────────────────────────
# Hilfsstil
# ──────────────────────────────────────────────────────────────────────────────
def _dialog_style():
    return f"""
        QDialog, QWidget {{
            background: {THEME['bg_mid']};
            color: {THEME['text']};
        }}
        QGroupBox {{
            border: 1px solid {THEME['border']};
            border-radius: 6px;
            margin-top: 8px;
            padding: 8px;
            color: {THEME['text_dim']};
            font-size: 11px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            color: {THEME['accent']};
        }}
        QComboBox, QLineEdit {{
            background: {THEME['bg_dark']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QComboBox::drop-down {{ border: none; }}
        QPushButton {{
            background: {THEME['bg_panel']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 5px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background: {THEME['accent']};
            color: white;
            border: 1px solid {THEME['accent']};
        }}
        QPushButton:disabled {{
            background: {THEME['bg_dark']};
            color: {THEME['text_dim']};
        }}
        QListWidget {{
            background: {THEME['bg_dark']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background: {THEME['accent']};
            color: white;
        }}
        QTextEdit {{
            background: {THEME['terminal_bg']};
            color: {THEME['terminal_text']};
            border: 1px solid {THEME['border']};
            border-radius: 4px;
            font-family: 'JetBrains Mono', Consolas, monospace;
            font-size: 11px;
        }}
        QProgressBar {{
            background: {THEME['bg_dark']};
            border: 1px solid {THEME['border']};
            border-radius: 4px;
            height: 10px;
        }}
        QProgressBar::chunk {{
            background: {THEME['accent']};
            border-radius: 4px;
        }}
        QRadioButton {{ color: {THEME['text']}; spacing: 6px; }}
        QCheckBox {{ color: {THEME['text']}; spacing: 6px; }}
        QLabel {{ color: {THEME['text']}; }}
    """


# ──────────────────────────────────────────────────────────────────────────────
# Flash-Worker
# ──────────────────────────────────────────────────────────────────────────────
class FlashWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    done = pyqtSignal(bool, str)

    def __init__(self, board: str, port: str, firmware_path: str):
        super().__init__()
        self.board = board
        self.port = port
        self.firmware_path = firmware_path

    def run(self):
        import subprocess, sys
        self.log.emit(f"Flashe {self.board} auf {self.port} ...\n")
        self.progress.emit(10)
        board_info = SUPPORTED_BOARDS.get(self.board, {})
        flash_cmd = board_info.get("flash_cmd", "esp32")
        baud = board_info.get("baud", 115200)

        if flash_cmd == "esp32":
            cmd = [
                sys.executable, "-m", "esptool",
                "--chip", "esp32",
                "--port", self.port,
                "--baud", str(baud),
                "write_flash", "-z", "0x1000",
                self.firmware_path,
            ]
        elif flash_cmd == "rp2":
            # Pico: Firmware per Drag-and-Drop (UF2) oder picotool
            self.log.emit(
                "Hinweis: Für den Raspberry Pi Pico bitte den Pico im BOOTSEL-Modus "
                "anschließen und die UF2-Datei manuell auf das Laufwerk kopieren,\n"
                "oder picotool verwenden.\n"
            )
            self.done.emit(True, "Manuelle Installation erforderlich.")
            return
        elif flash_cmd == "microbit":
            # micro:bit: Drag-and-Drop HEX
            self.log.emit(
                "Hinweis: Für den micro:bit bitte die HEX-Datei auf das MICROBIT-Laufwerk kopieren.\n"
            )
            self.done.emit(True, "Manuelle Installation erforderlich.")
            return
        else:
            cmd = [sys.executable, "-m", "esptool", "--port", self.port,
                   "write_flash", "0x0", self.firmware_path]

        try:
            self.progress.emit(30)
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self.log.emit(line)
            proc.wait()
            self.progress.emit(100)
            if proc.returncode == 0:
                self.done.emit(True, "Flash erfolgreich!")
            else:
                self.done.emit(False, f"Fehler (Code {proc.returncode})")
        except FileNotFoundError:
            self.done.emit(False, "esptool nicht gefunden. Bitte installieren: pip install esptool")
        except Exception as e:
            self.done.emit(False, str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Download-Worker für Firmware
# ──────────────────────────────────────────────────────────────────────────────
class FirmwareDownloader(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    done = pyqtSignal(bool, str)   # (success, filepath_or_error)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url = url
        self.dest = dest

    def run(self):
        try:
            self.log.emit(f"Lade Firmware von {self.url} ...\n")
            resp = requests.get(self.url, stream=True, timeout=30)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(self.dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.progress.emit(int(downloaded / total * 100))
            self.done.emit(True, self.dest)
        except Exception as e:
            self.done.emit(False, str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Flash-Dialog
# ──────────────────────────────────────────────────────────────────────────────
class FlashDialog(QDialog):
    def __init__(self, board: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MicroPython flashen")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(_dialog_style())
        self._board = board
        self._firmware_path: str | None = None
        self._worker: FlashWorker | None = None
        self._downloader: FirmwareDownloader | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Board-Info
        info = QLabel(f"Board: <b>{SUPPORTED_BOARDS.get(self._board, {}).get('label', self._board)}</b>")
        info.setStyleSheet(f"color:{THEME['accent']}; font-size:13px;")
        layout.addWidget(info)

        # Serieller Port
        port_group = QGroupBox("Serieller Port")
        pg = QHBoxLayout(port_group)
        self._port_combo = QComboBox()
        self._refresh_ports()
        pg.addWidget(self._port_combo)
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedWidth(32)
        btn_refresh.clicked.connect(self._refresh_ports)
        pg.addWidget(btn_refresh)
        layout.addWidget(port_group)

        # Firmware-Quelle
        fw_group = QGroupBox("Firmware-Quelle")
        fg = QVBoxLayout(fw_group)
        self._rb_local = QRadioButton("Lokale .bin Datei")
        self._rb_local.setChecked(True)
        self._rb_online = QRadioButton("Von micropython.org herunterladen")
        fg.addWidget(self._rb_local)
        fg.addWidget(self._rb_online)

        # Lokale Datei
        local_row = QHBoxLayout()
        self._local_path = QLineEdit()
        self._local_path.setPlaceholderText("Pfad zur .bin Datei ...")
        local_row.addWidget(self._local_path)
        btn_browse = QPushButton("Durchsuchen")
        btn_browse.clicked.connect(self._browse_firmware)
        local_row.addWidget(btn_browse)
        fg.addLayout(local_row)

        # Online-URL
        self._online_url = QLineEdit()
        board_page = SUPPORTED_BOARDS.get(self._board, {}).get("download_page", "")
        self._online_url.setPlaceholderText(
            f"https://micropython.org/download/{board_page}/"
        )
        self._online_url.setText(
            f"https://micropython.org/download/{board_page}/"
        )
        fg.addWidget(QLabel("Download-URL (.bin direkt):"))
        fg.addWidget(self._online_url)
        layout.addWidget(fw_group)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

        # Fortschritt
        self._progress = QProgressBar()
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_flash = QPushButton("Jetzt flashen")
        self._btn_flash.setStyleSheet(
            f"background:{THEME['accent']}; color:white; font-weight:bold;"
            f" border:none; border-radius:5px; padding:7px 18px;"
        )
        self._btn_flash.clicked.connect(self._start_flash)
        btn_row.addWidget(self._btn_flash)
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _refresh_ports(self):
        import serial.tools.list_ports
        self._port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            self._port_combo.addItem("Kein Gerät gefunden")
        else:
            for p in ports:
                self._port_combo.addItem(p)

    def _browse_firmware(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Firmware wählen", str(Path.home()), "Firmware (*.bin *.hex *.uf2)"
        )
        if path:
            self._local_path.setText(path)
            self._firmware_path = path

    def _log_append(self, text: str):
        self._log.append(text.rstrip())

    def _start_flash(self):
        port = self._port_combo.currentText()
        if "Kein" in port:
            QMessageBox.warning(self, "Kein Port", "Bitte einen seriellen Port auswählen.")
            return

        if self._rb_online.isChecked():
            url = self._online_url.text().strip()
            if not url.endswith(".bin"):
                QMessageBox.information(
                    self, "Hinweis",
                    "Bitte die direkte .bin-Download-URL von micropython.org eingeben.\n"
                    "Öffne die Download-Seite im Browser und kopiere den Link zur .bin Datei."
                )
                return
            dest = str(Path.home() / "micropython_firmware.bin")
            self._downloader = FirmwareDownloader(url, dest)
            self._downloader.log.connect(self._log_append)
            self._downloader.progress.connect(self._progress.setValue)
            self._downloader.done.connect(
                lambda ok, r: self._after_download(ok, r, port)
            )
            self._btn_flash.setEnabled(False)
            self._downloader.start()
        else:
            fw = self._local_path.text().strip()
            if not fw or not os.path.isfile(fw):
                QMessageBox.warning(self, "Datei fehlt", "Bitte eine gültige Firmware-Datei wählen.")
                return
            self._do_flash(port, fw)

    def _after_download(self, ok: bool, result: str, port: str):
        self._btn_flash.setEnabled(True)
        if ok:
            self._log_append(f"Download abgeschlossen: {result}\n")
            self._do_flash(port, result)
        else:
            self._log_append(f"Download fehlgeschlagen: {result}\n")

    def _do_flash(self, port: str, fw: str):
        self._worker = FlashWorker(self._board, port, fw)
        self._worker.log.connect(self._log_append)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.done.connect(self._on_flash_done)
        self._btn_flash.setEnabled(False)
        self._worker.start()

    def _on_flash_done(self, ok: bool, msg: str):
        self._btn_flash.setEnabled(True)
        self._log_append(f"\n{'✓ ' if ok else '✗ '}{msg}\n")
        if ok:
            QMessageBox.information(self, "Fertig", msg)
        else:
            QMessageBox.critical(self, "Fehler", msg)


# ──────────────────────────────────────────────────────────────────────────────
# Bibliotheks-Worker
# ──────────────────────────────────────────────────────────────────────────────
class LibInstallWorker(QThread):
    log = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, files: list[dict], port: str):
        super().__init__()
        self.files = files   # [{"name": ..., "download_url": ...}]
        self.port = port

    def run(self):
        import subprocess, sys, tempfile
        for finfo in self.files:
            name = finfo["name"]
            url = finfo["download_url"]
            self.log.emit(f"Lade {name} herunter ...\n")
            try:
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                with tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(name)[1], delete=False
                ) as tmp:
                    tmp.write(resp.content)
                    tmp_path = tmp.name

                self.log.emit(f"Übertrage {name} auf Controller ({self.port}) ...\n")
                result = subprocess.run(
                    [sys.executable, "-m", "mpremote", "connect", self.port,
                     "cp", tmp_path, f":{name}"],
                    capture_output=True, text=True, timeout=30
                )
                os.unlink(tmp_path)
                if result.returncode == 0:
                    self.log.emit(f"✓ {name} erfolgreich übertragen.\n")
                else:
                    self.log.emit(f"✗ Fehler bei {name}: {result.stderr}\n")
                    self.done.emit(False, f"Fehler bei {name}")
                    return
            except Exception as e:
                self.log.emit(f"✗ Ausnahme bei {name}: {e}\n")
                self.done.emit(False, str(e))
                return
        self.done.emit(True, "Alle Bibliotheken übertragen.")


# ──────────────────────────────────────────────────────────────────────────────
# Bibliotheks-Manager-Dialog
# ──────────────────────────────────────────────────────────────────────────────
class LibraryManagerDialog(QDialog):
    def __init__(self, port: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT Bibliotheken")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(_dialog_style())
        self._port = port
        self._files: list[dict] = []
        self._worker: LibInstallWorker | None = None
        self._setup_ui()
        self._fetch_libs()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        lbl = QLabel("Bibliotheken aus <b>NIT_Bibliotheken</b> (GitHub)")
        lbl.setStyleSheet(f"color:{THEME['accent']}; font-size:13px;")
        layout.addWidget(lbl)

        # Port
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Serieller Port:"))
        self._port_combo = QComboBox()
        self._refresh_ports()
        if self._port:
            idx = self._port_combo.findText(self._port)
            if idx >= 0:
                self._port_combo.setCurrentIndex(idx)
        port_row.addWidget(self._port_combo)
        btn_ref = QPushButton("↻")
        btn_ref.setFixedWidth(32)
        btn_ref.clicked.connect(self._refresh_ports)
        port_row.addWidget(btn_ref)
        port_row.addStretch()
        layout.addLayout(port_row)

        # Splitter: Dateiliste | Vorschau
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Verfügbare Dateien:"))
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._list.currentItemChanged.connect(self._on_select)
        ll.addWidget(self._list)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Vorschau:"))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        rl.addWidget(self._preview)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        layout.addWidget(self._log)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_install = QPushButton("Ausgewählte installieren")
        self._btn_install.setStyleSheet(
            f"background:{THEME['accent']}; color:white; font-weight:bold;"
            f" border:none; border-radius:5px; padding:7px 18px;"
        )
        self._btn_install.clicked.connect(self._install_selected)
        self._btn_install.setEnabled(False)
        btn_row.addWidget(self._btn_install)
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _refresh_ports(self):
        import serial.tools.list_ports
        self._port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            self._port_combo.addItem("Kein Gerät")
        else:
            for p in ports:
                self._port_combo.addItem(p)

    def _fetch_libs(self):
        self._log.append("Lade Dateiliste von GitHub ...")

        def fetch():
            try:
                resp = requests.get(LIB_REPO_API, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._populate_list(data))
            except Exception as e:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._log.append(f"Fehler: {e}"))

        threading.Thread(target=fetch, daemon=True).start()

    def _populate_list(self, data: list):
        self._files = [f for f in data if f.get("type") == "file"]
        self._list.clear()
        for f in self._files:
            item = QListWidgetItem(f["name"])
            item.setData(Qt.ItemDataRole.UserRole, f)
            self._list.addItem(item)
        self._btn_install.setEnabled(True)
        self._log.append(f"{len(self._files)} Dateien gefunden.")

    def _on_select(self, current, _):
        if not current:
            return
        finfo = current.data(Qt.ItemDataRole.UserRole)
        if not finfo:
            return

        def fetch_preview():
            try:
                url = finfo.get("download_url", "")
                if url:
                    resp = requests.get(url, timeout=10)
                    content = resp.text[:3000]
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self._preview.setPlainText(content))
            except Exception as e:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._preview.setPlainText(f"Vorschau nicht verfügbar: {e}"))

        threading.Thread(target=fetch_preview, daemon=True).start()

    def _install_selected(self):
        selected = [item.data(Qt.ItemDataRole.UserRole)
                    for item in self._list.selectedItems()
                    if item.data(Qt.ItemDataRole.UserRole)]
        if not selected:
            QMessageBox.information(self, "Nichts ausgewählt",
                                    "Bitte mindestens eine Datei auswählen.")
            return
        port = self._port_combo.currentText()
        if "Kein" in port:
            QMessageBox.warning(self, "Kein Port",
                                "Bitte einen seriellen Port auswählen.")
            return
        self._worker = LibInstallWorker(selected, port)
        self._worker.log.connect(lambda t: self._log.append(t.rstrip()))
        self._worker.done.connect(self._on_install_done)
        self._btn_install.setEnabled(False)
        self._worker.start()

    def _on_install_done(self, ok: bool, msg: str):
        self._btn_install.setEnabled(True)
        self._log.append(f"\n{'✓ ' if ok else '✗ '}{msg}")
        if ok:
            QMessageBox.information(self, "Fertig", msg)
        else:
            QMessageBox.critical(self, "Fehler", msg)
