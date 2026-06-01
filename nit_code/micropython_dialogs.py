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
    QListWidgetItem, QSplitter, QMessageBox, QCheckBox, QWidget,
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
            self._flash_pico()
            return
        elif flash_cmd == "microbit":
            self._flash_microbit()
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

    # ------------------------------------------------------------------
    # Pico: UF2 automatisch auf das BOOTSEL-Laufwerk kopieren
    # ------------------------------------------------------------------
    # Bekannte BOOTSEL-Laufwerksnamen für alle Pico-Varianten
    _PICO_VOLUME_PREFIXES = (
        "RPI-RP2",   # Pico 1 (RP2040)
        "RP2350",    # Pico 2 / Pico 2W (RP2350)
        "RPI-RP2W",  # mögliche Variante
    )

    def _find_pico_drive(self) -> str | None:
        """Sucht das BOOTSEL-Laufwerk (RPI-RP2, RP2350, ...)."""
        import sys, os
        candidates = []

        def _matches(name: str) -> bool:
            n = name.upper()
            return any(n.startswith(p) for p in self._PICO_VOLUME_PREFIXES)

        if sys.platform == "darwin":
            for name in os.listdir("/Volumes"):
                if _matches(name):
                    candidates.append(f"/Volumes/{name}")
        elif sys.platform == "win32":
            import string, ctypes
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                    label_buf = ctypes.create_unicode_buffer(261)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        drive, label_buf, 261, None, None, None, None, 0
                    )
                    if _matches(label_buf.value):
                        candidates.append(drive)
        else:
            import getpass
            for base in [f"/media/{getpass.getuser()}", "/media", "/run/media"]:
                if os.path.isdir(base):
                    for sub in os.listdir(base):
                        if _matches(sub):
                            candidates.append(os.path.join(base, sub))
                        subpath = os.path.join(base, sub)
                        if os.path.isdir(subpath):
                            for entry in os.listdir(subpath):
                                if _matches(entry):
                                    candidates.append(os.path.join(subpath, entry))
        return candidates[0] if candidates else None

    def _flash_pico(self):
        import shutil, time
        self.log.emit("Suche Raspberry Pi Pico im BOOTSEL-Modus ...\n")
        self.progress.emit(10)

        # Bis zu 20 Sekunden warten, damit Schüler den BOOTSEL noch drücken können
        drive = None
        for i in range(20):
            drive = self._find_pico_drive()
            if drive:
                break
            import os, sys
            # Aktuell gemountete Laufwerke anzeigen zur Diagnose
            if sys.platform == "darwin":
                volumes = os.listdir("/Volumes")
                self.log.emit(f"  Warte ... ({i+1}/20) – Laufwerke: {', '.join(volumes)}\n")
            else:
                self.log.emit(f"  Warte ... ({i+1}/20) – Pico im BOOTSEL-Modus anschließen!\n")
            self.progress.emit(10 + i)
            time.sleep(1)

        if not drive:
            self.done.emit(
                False,
                "Kein Pico im BOOTSEL-Modus gefunden!\n\n"
                "Bitte:\n"
                "1. BOOTSEL-Taste auf dem Pico gedrückt halten\n"
                "2. USB-Kabel anschließen\n"
                "3. Taste loslassen\n"
                "4. Erneut versuchen."
            )
            return

        self.log.emit(f"Pico gefunden: {drive}\n")
        self.progress.emit(50)

        fw = self.firmware_path
        if not fw.lower().endswith(".uf2"):
            self.done.emit(False, "Für den Raspberry Pi Pico wird eine .uf2-Datei benötigt!")
            return

        try:
            import os, sys, time, subprocess as _sp
            fw_size = os.path.getsize(fw)
            dest = os.path.join(drive, os.path.basename(fw))
            self.log.emit(f"Kopiere {os.path.basename(fw)} ({fw_size // 1024} KB) → {drive} ...\n")

            if sys.platform == "darwin":
                # macOS: Python open() hängt auf USB-FAT-Volumes (bekanntes Problem).
                # /bin/cp nutzt fcopyfile() auf Kernel-Ebene – zuverlässiger.
                self.log.emit("(macOS: verwende /bin/cp)\n")
                proc = _sp.Popen(
                    ["/bin/cp", fw, dest],
                    stderr=_sp.PIPE, stdout=_sp.PIPE
                )
                deadline = time.monotonic() + 90
                timed_out = False
                while proc.poll() is None:
                    if time.monotonic() > deadline:
                        proc.kill()
                        proc.wait()
                        timed_out = True
                        break
                    elapsed_frac = 1 - max(0, deadline - time.monotonic()) / 90
                    self.progress.emit(int(51 + elapsed_frac * 44))
                    time.sleep(0.4)

                if timed_out:
                    if not os.path.exists(drive):
                        # Pico hat sich neu gestartet → Laufwerk verschwunden = Erfolg
                        self.progress.emit(100)
                        self.log.emit("✓ Pico hat sich neu gestartet (Laufwerk verschwunden).\n")
                        self.done.emit(True, "Flash erfolgreich! Pico startet neu.")
                    else:
                        self.done.emit(False, "Zeitüberschreitung (90 s). Pico hat nicht reagiert.\n"
                                       "Bitte BOOTSEL-Modus erneut aktivieren und nochmal versuchen.")
                    return

                rc = proc.returncode
                stderr_out = proc.stderr.read().decode(errors="replace").strip()
                drive_still_there = os.path.exists(drive)

                if rc == 0 or not drive_still_there:
                    # rc=0: normaler Erfolg; Laufwerk weg: Pico hat sich nach dem Flash neu gestartet
                    self.progress.emit(100)
                    if not drive_still_there:
                        self.log.emit("✓ Pico hat sich neu gestartet (Laufwerk verschwunden).\n")
                    else:
                        self.log.emit("✓ Datei erfolgreich übertragen.\n")
                    self.log.emit("Pico startet automatisch neu mit der neuen Firmware.\n")
                    self.done.emit(True, "Flash erfolgreich! Pico startet neu.")
                else:
                    self.done.emit(False, f"Fehler beim Kopieren:\n{stderr_out or 'Unbekannter Fehler'}\n\n"
                                   "Bitte sicherstellen:\n"
                                   "• Pico ist im BOOTSEL-Modus (Laufwerk sichtbar im Finder)\n"
                                   "• Ausreichende Schreibrechte auf das Laufwerk")
            else:
                # Windows / Linux: chunk-weise kopieren
                CHUNK = 65536
                written = 0
                with open(fw, "rb") as src, open(dest, "wb") as dst:
                    while True:
                        chunk = src.read(CHUNK)
                        if not chunk:
                            break
                        dst.write(chunk)
                        written += len(chunk)
                        self.progress.emit(50 + int(written / fw_size * 45))
                    dst.flush()
                    os.fsync(dst.fileno())
                self.progress.emit(100)
                self.log.emit(f"✓ {written // 1024} KB übertragen.\n")
                self.log.emit("Pico startet automatisch neu mit der neuen Firmware.\n")
                self.done.emit(True, "Flash erfolgreich! Pico startet neu.")
        except Exception as e:
            self.done.emit(False, f"Fehler beim Kopieren: {e}\n\nBitte sicherstellen:\n"
                           "• Pico ist im BOOTSEL-Modus (Laufwerk sichtbar im Finder)\n"
                           "• Die .uf2-Datei ist nicht beschädigt\n"
                           "• Ausreichende Schreibrechte auf das Laufwerk")

    # ------------------------------------------------------------------
    # micro:bit: HEX automatisch auf das MICROBIT-Laufwerk kopieren
    # ------------------------------------------------------------------
    def _find_microbit_drive(self) -> str | None:
        import sys, os
        if sys.platform == "darwin":
            for name in os.listdir("/Volumes"):
                if name.upper() == "MICROBIT":
                    return f"/Volumes/{name}"
        elif sys.platform == "win32":
            import string, ctypes
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                label_buf = ctypes.create_unicode_buffer(261)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    drive, label_buf, 261, None, None, None, None, 0
                )
                if label_buf.value.upper() == "MICROBIT":
                    return drive
        else:
            import getpass
            for base in [f"/media/{getpass.getuser()}", "/media", "/run/media"]:
                if os.path.isdir(base):
                    for sub in os.listdir(base):
                        if sub.upper() == "MICROBIT":
                            return os.path.join(base, sub)
        return None

    def _flash_microbit(self):
        import shutil, time
        self.log.emit("Suche micro:bit ...\n")
        self.progress.emit(10)

        drive = None
        for i in range(15):
            drive = self._find_microbit_drive()
            if drive:
                break
            self.log.emit(f"  Warte ... ({i+1}/15) – micro:bit anschließen!\n")
            self.progress.emit(10 + i)
            time.sleep(1)

        if not drive:
            self.done.emit(False, "Kein micro:bit gefunden! Bitte anschließen.")
            return

        self.log.emit(f"micro:bit gefunden: {drive}\n")
        self.progress.emit(50)

        fw = self.firmware_path
        if not fw.lower().endswith(".hex"):
            self.done.emit(False, "Für den micro:bit wird eine .hex-Datei benötigt!")
            return

        try:
            import os
            dest = os.path.join(drive, os.path.basename(fw))
            self.log.emit(f"Kopiere {os.path.basename(fw)} → {drive} ...\n")
            shutil.copy2(fw, dest)
            self.progress.emit(100)
            self.done.emit(True, "Flash erfolgreich! micro:bit startet neu.")
        except Exception as e:
            self.done.emit(False, f"Fehler beim Kopieren: {e}")


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
    def __init__(self, board: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MicroPython flashen")
        self.setMinimumSize(520, 540)
        self.setStyleSheet(_dialog_style())
        self._board = board or list(SUPPORTED_BOARDS.keys())[0]
        self._flash_cmd = "esp32"
        self._is_uf2 = False
        self._firmware_path: str | None = None
        self._worker: FlashWorker | None = None
        self._downloader: FirmwareDownloader | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Board-Auswahl ──
        board_row = QHBoxLayout()
        board_lbl = QLabel("Board:")
        board_lbl.setStyleSheet(f"color:{THEME['text_dim']}; min-width:50px;")
        self._board_combo_dlg = QComboBox()
        for bid, binfo in SUPPORTED_BOARDS.items():
            self._board_combo_dlg.addItem(binfo["label"], bid)
        idx = self._board_combo_dlg.findData(self._board)
        if idx >= 0:
            self._board_combo_dlg.setCurrentIndex(idx)
        self._board_combo_dlg.currentIndexChanged.connect(self._on_board_changed)
        board_row.addWidget(board_lbl)
        board_row.addWidget(self._board_combo_dlg, 1)
        layout.addLayout(board_row)

        # ── Hinweis (dynamisch je nach Board) ──
        self._hint_lbl = QLabel()
        self._hint_lbl.setWordWrap(True)
        self._hint_lbl.setStyleSheet(
            f"background:{THEME['bg_panel']}; color:{THEME['info']};"
            f" border:1px solid {THEME['border']}; border-radius:5px; padding:8px;"
        )
        layout.addWidget(self._hint_lbl)

        # ── Serieller Port (nur für ESP32) ──
        self._port_group = QGroupBox("Serieller Port (nur für ESP32)")
        pg = QHBoxLayout(self._port_group)
        self._port_combo = QComboBox()
        self._refresh_ports()
        pg.addWidget(self._port_combo)
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedWidth(32)
        btn_refresh.clicked.connect(self._refresh_ports)
        pg.addWidget(btn_refresh)
        layout.addWidget(self._port_group)

        # ── Firmware-Quelle ──
        fw_group = QGroupBox("Firmware-Quelle")
        fg = QVBoxLayout(fw_group)
        self._rb_local = QRadioButton("Lokale Datei")
        self._rb_local.setChecked(True)
        self._rb_online = QRadioButton("Von micropython.org herunterladen")
        fg.addWidget(self._rb_local)
        fg.addWidget(self._rb_online)

        local_row = QHBoxLayout()
        self._local_path = QLineEdit()
        local_row.addWidget(self._local_path)
        btn_browse = QPushButton("Durchsuchen")
        btn_browse.clicked.connect(self._browse_firmware)
        local_row.addWidget(btn_browse)
        fg.addLayout(local_row)

        self._url_lbl = QLabel()
        fg.addWidget(self._url_lbl)
        self._online_url = QLineEdit()
        fg.addWidget(self._online_url)
        layout.addWidget(fw_group)

        # ── Log ──
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

        # ── Fortschritt ──
        self._progress = QProgressBar()
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # ── Buttons ──
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

        # Initiales UI-Update
        self._update_board_ui()

    def _on_board_changed(self, index: int):
        self._board = self._board_combo_dlg.itemData(index)
        self._update_board_ui()

    def _update_board_ui(self):
        """Aktualisiert alle board-abhängigen UI-Elemente dynamisch."""
        board_info = SUPPORTED_BOARDS.get(self._board, {})
        self._flash_cmd = board_info.get("flash_cmd", "esp32")
        self._is_uf2 = self._flash_cmd in ("rp2", "microbit")

        if self._flash_cmd == "rp2":
            self._hint_lbl.setText(
                "💡 <b>Pico:</b> BOOTSEL-Taste gedrückt halten, USB einstecken, "
                "Taste loslassen – das Programm kopiert die Firmware automatisch!"
            )
            self._hint_lbl.setVisible(True)
        elif self._flash_cmd == "microbit":
            self._hint_lbl.setText(
                "💡 <b>micro:bit:</b> Gerät anschließen – "
                "die HEX-Datei wird automatisch übertragen!"
            )
            self._hint_lbl.setVisible(True)
        else:
            self._hint_lbl.setVisible(False)

        self._port_group.setVisible(not self._is_uf2)

        ext = ".uf2" if self._flash_cmd == "rp2" else ".hex" if self._flash_cmd == "microbit" else ".bin"
        self._local_path.setPlaceholderText(f"Pfad zur {ext} Datei ...")
        board_page = board_info.get("download_page", "")
        url = f"https://micropython.org/download/{board_page}/"
        self._online_url.setText(url)
        self._url_lbl.setText(f"Download-URL ({ext} direkt):")

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
        flash_cmd = getattr(self, "_flash_cmd", "esp32")
        if flash_cmd == "rp2":
            file_filter = "UF2-Firmware (*.uf2);;Alle Dateien (*)"
        elif flash_cmd == "microbit":
            file_filter = "HEX-Firmware (*.hex);;Alle Dateien (*)"
        else:
            file_filter = "BIN-Firmware (*.bin);;Alle Dateien (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Firmware wählen", str(Path.home()), file_filter
        )
        if path:
            self._local_path.setText(path)
            self._firmware_path = path

    def _log_append(self, text: str):
        self._log.append(text.rstrip())

    def _start_flash(self):
        board_info = SUPPORTED_BOARDS.get(self._board, {})
        flash_cmd = board_info.get("flash_cmd", "esp32")
        port = self._port_combo.currentText() if not self._is_uf2 else "n/a"
        if not self._is_uf2 and "Kein" in port:
            QMessageBox.warning(self, "Kein Port", "Bitte einen seriellen Port auswählen.")
            return

        if self._rb_online.isChecked():
            url = self._online_url.text().strip()
            ext = ".uf2" if self._flash_cmd == "rp2" else ".hex" if self._flash_cmd == "microbit" else ".bin"
            if not any(url.endswith(e) for e in (".bin", ".uf2", ".hex")):
                QMessageBox.information(
                    self, "Hinweis",
                    f"Bitte die direkte {ext}-Download-URL von micropython.org eingeben.\n"
                    "Öffne die Download-Seite im Browser und kopiere den direkten Download-Link."
                )
                return
            dest = str(Path.home() / f"micropython_firmware{ext}")
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
        self._btn_flash.setText("Flashe …")
        self._worker.start()

    def _on_flash_done(self, ok: bool, msg: str):
        self._btn_flash.setEnabled(True)
        self._btn_flash.setText("Jetzt flashen")
        self._log_append(f"\n{'✓ ' if ok else '✗ '}{msg}\n")
        if ok:
            QMessageBox.information(self, "Fertig", msg)
        else:
            box = QMessageBox(self)
            box.setWindowTitle("Fehler")
            box.setIcon(QMessageBox.Icon.Critical)
            box.setText(msg)
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            box.exec()


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
            if finfo.get("type") == "dir":
                # Unterordner: .py-Dateien (keine Beispiele) holen und installieren
                dir_name = finfo["name"]
                self.log.emit(f"📁 Lade Bibliothek '{dir_name}' ...\n")
                try:
                    resp = requests.get(finfo["url"], timeout=10)
                    resp.raise_for_status()
                    dir_contents = resp.json()
                    # Bibliotheks-Dateien: .py ohne 'beispiel'
                    lib_files = [
                        f for f in dir_contents
                        if f.get("type") == "file"
                        and f["name"].endswith(".py")
                        and not f["name"].lower().startswith("beispiel")
                    ]
                    if not lib_files:
                        lib_files = [f for f in dir_contents
                                     if f.get("type") == "file" and f["name"].endswith(".py")]
                except Exception as e:
                    self.log.emit(f"✗ Fehler beim Laden von '{dir_name}': {e}\n")
                    self.done.emit(False, str(e))
                    return
            else:
                lib_files = [finfo]

            for file_info in lib_files:
                name = file_info["name"]
                url = file_info["download_url"]
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
# Hilfworker für HTTP-Requests (thread-sicher via pyqtSignal)
# ──────────────────────────────────────────────────────────────────────────────
class _HttpWorker(QThread):
    result = pyqtSignal(object)   # beliebige Python-Objekte
    error  = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            resp = requests.get(self._url, timeout=12)
            resp.raise_for_status()
            self.result.emit(resp.json())
        except Exception as e:
            self.error.emit(str(e))


class _ReadmeWorker(QThread):
    text = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            resp = requests.get(self._url, timeout=12)
            resp.raise_for_status()
            self.text.emit(resp.text[:4000])
        except Exception as e:
            self.text.emit(f"(Vorschau nicht verfügbar: {e})")
class LibraryManagerDialog(QDialog):
    def __init__(self, port: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIT Bibliotheken")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(_dialog_style())
        self._port = port
        self._files: list[dict] = []
        self._worker: LibInstallWorker | None = None
        self._http_worker: _HttpWorker | None = None
        self._preview_worker: _HttpWorker | None = None
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
        self._http_worker = _HttpWorker(LIB_REPO_API, self)
        self._http_worker.result.connect(self._populate_list)
        self._http_worker.error.connect(lambda e: self._log.append(f"Fehler: {e}"))
        self._http_worker.start()

    def _populate_list(self, data: list):
        self._files = [
            f for f in data
            if f.get("type") == "dir" and not f["name"].startswith(".")
        ]
        self._list.clear()
        for f in self._files:
            item = QListWidgetItem(f["name"])
            item.setData(Qt.ItemDataRole.UserRole, f)
            self._list.addItem(item)
        if self._files:
            self._btn_install.setEnabled(True)
            self._log.append(f"{len(self._files)} Bibliotheken gefunden.")
        else:
            self._log.append("Keine Bibliotheken gefunden.")

    def _on_select(self, current, _):
        if not current:
            return
        finfo = current.data(Qt.ItemDataRole.UserRole)
        if not finfo or not finfo.get("url"):
            return
        # Verzeichnisinhalt laden und README / Dateiliste anzeigen
        self._preview_worker = _HttpWorker(finfo["url"], self)
        self._preview_worker.result.connect(self._show_preview)
        self._preview_worker.error.connect(
            lambda e: self._preview.setPlainText(f"Vorschau nicht verfügbar: {e}")
        )
        self._preview_worker.start()

    def _show_preview(self, dir_contents: list):
        readme = next(
            (f for f in dir_contents if f["name"].lower() == "readme.md"),
            None
        )
        if readme and readme.get("download_url"):
            w = _HttpWorker(readme["download_url"], self)
            w.result.connect(lambda _: None)   # JSON würde fehlschlagen
            # README ist kein JSON – separaten Worker für Text bauen
            self._readme_worker = _ReadmeWorker(readme["download_url"], self)
            self._readme_worker.text.connect(self._preview.setPlainText)
            self._readme_worker.start()
        else:
            py_files = [f["name"] for f in dir_contents if f["name"].endswith(".py")]
            self._preview.setPlainText(
                "Enthaltene Dateien:\n" + "\n".join(f"  • {n}" for n in py_files)
            )

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


# ──────────────────────────────────────────────────────────────────────────────
# pip-Paketmanager (lokaler Python-Modus)
# ──────────────────────────────────────────────────────────────────────────────

# Kuratierte Liste für Schüler/Einsteiger
_PIP_CATALOG: list[dict] = [
    # Daten & Mathematik
    {"name": "numpy",        "cat": "Daten & Mathematik", "desc": "Numerische Arrays und Matrizenrechnung"},
    {"name": "pandas",       "cat": "Daten & Mathematik", "desc": "Datenanalyse mit DataFrames"},
    {"name": "matplotlib",   "cat": "Daten & Mathematik", "desc": "Diagramme und Grafiken erstellen"},
    {"name": "scipy",        "cat": "Daten & Mathematik", "desc": "Wissenschaftliche Berechnungen"},
    {"name": "sympy",        "cat": "Daten & Mathematik", "desc": "Symbolische Mathematik (CAS)"},
    # Spiele & Grafik
    {"name": "pygame",       "cat": "Spiele & Grafik",    "desc": "2D-Spiele und Animationen programmieren"},
    {"name": "pyglet",       "cat": "Spiele & Grafik",    "desc": "OpenGL-Fenster und Multimedia"},
    {"name": "Pillow",       "cat": "Spiele & Grafik",    "desc": "Bilder öffnen, bearbeiten, speichern"},
    # Web & Netzwerk
    {"name": "requests",     "cat": "Web & Netzwerk",     "desc": "HTTP-Anfragen (APIs abrufen)"},
    {"name": "flask",        "cat": "Web & Netzwerk",     "desc": "Einfacher Webserver"},
    {"name": "beautifulsoup4","cat": "Web & Netzwerk",    "desc": "HTML/XML aus Webseiten auslesen"},
    {"name": "httpx",        "cat": "Web & Netzwerk",     "desc": "Moderner HTTP-Client"},
    # Maschinen­lernen & KI
    {"name": "scikit-learn", "cat": "KI & ML",            "desc": "Machine-Learning-Algorithmen"},
    {"name": "tensorflow",   "cat": "KI & ML",            "desc": "Deep Learning (Google)"},
    {"name": "torch",        "cat": "KI & ML",            "desc": "Deep Learning (PyTorch)"},
    {"name": "openai",       "cat": "KI & ML",            "desc": "OpenAI-API (ChatGPT, DALL·E …)"},
    # Hardware & Sensoren
    {"name": "pyserial",     "cat": "Hardware",           "desc": "Serielle Schnittstelle (COM/USB)"},
    {"name": "gpiozero",     "cat": "Hardware",           "desc": "GPIO-Pins am Raspberry Pi steuern"},
    {"name": "smbus2",       "cat": "Hardware",           "desc": "I²C-Kommunikation"},
    # Sonstiges
    {"name": "qrcode",       "cat": "Sonstiges",          "desc": "QR-Codes generieren"},
    {"name": "rich",         "cat": "Sonstiges",          "desc": "Bunte Terminal-Ausgaben"},
    {"name": "pyqt6",        "cat": "Sonstiges",          "desc": "Grafische Benutzeroberflächen (GUI)"},
    {"name": "pydantic",     "cat": "Sonstiges",          "desc": "Daten validieren und parsen"},
]


class _PipWorker(QThread):
    log    = pyqtSignal(str)
    done   = pyqtSignal(bool, str)

    def __init__(self, packages: list[str], action: str = "install", parent=None):
        super().__init__(parent)
        self._packages = packages
        self._action   = action   # "install" | "uninstall"

    def run(self):
        import subprocess, sys
        for pkg in self._packages:
            self.log.emit(f"{'Installiere' if self._action == 'install' else 'Deinstalliere'} {pkg} …\n")
            cmd = [sys.executable, "-m", "pip", self._action, pkg]
            if self._action == "uninstall":
                cmd.append("-y")
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                self.log.emit(r.stdout)
                if r.returncode == 0:
                    self.log.emit(f"✓ {pkg} erfolgreich.\n")
                else:
                    self.log.emit(r.stderr)
                    self.done.emit(False, f"Fehler bei {pkg}")
                    return
            except Exception as e:
                self.done.emit(False, str(e))
                return
        action_word = "installiert" if self._action == "install" else "deinstalliert"
        self.done.emit(True, f"Alle Pakete {action_word}.")


class PipManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Python-Pakete (pip)")
        self.setMinimumSize(700, 540)
        self.setStyleSheet(_dialog_style())
        self._worker: _PipWorker | None = None
        self._installed: set[str] = set()
        self._setup_ui()
        self._load_installed()

    # ── UI ────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        lbl = QLabel("📦  <b>Python-Pakete installieren / deinstallieren</b>")
        lbl.setStyleSheet(f"color:{THEME['accent']}; font-size:13px;")
        layout.addWidget(lbl)

        # Suche
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Paket suchen …")
        self._search.textChanged.connect(self._filter_list)
        search_row.addWidget(self._search)
        layout.addLayout(search_row)

        # Hauptbereich: Katalog-Liste | Details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Verfügbare Pakete:"))
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._list.currentItemChanged.connect(self._on_select)
        ll.addWidget(self._list)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Details:"))
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        rl.addWidget(self._detail)
        rl.addWidget(QLabel("Installierte Pakete:"))
        self._installed_list = QListWidget()
        self._installed_list.setMaximumHeight(130)
        self._installed_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        rl.addWidget(self._installed_list)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        layout.addWidget(self._log)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_install = QPushButton("⬇  Ausgewählte installieren")
        self._btn_install.setStyleSheet(
            f"background:{THEME['accent']}; color:white; font-weight:bold;"
            f" border:none; border-radius:5px; padding:7px 18px;"
        )
        self._btn_install.clicked.connect(self._install_selected)
        btn_row.addWidget(self._btn_install)
        self._btn_uninstall = QPushButton("🗑  Markierte deinstallieren")
        self._btn_uninstall.setStyleSheet(
            f"background:{THEME['bg_panel']}; color:{THEME['text']};"
            f" border:1px solid {THEME['border']}; border-radius:5px; padding:7px 18px;"
        )
        self._btn_uninstall.clicked.connect(self._uninstall_selected)
        btn_row.addWidget(self._btn_uninstall)
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._fill_catalog()

    def _fill_catalog(self, filter_text: str = ""):
        self._list.clear()
        ft = filter_text.lower()
        last_cat = ""
        for entry in _PIP_CATALOG:
            if ft and ft not in entry["name"].lower() and ft not in entry["desc"].lower():
                continue
            if entry["cat"] != last_cat and not ft:
                sep = QListWidgetItem(f"── {entry['cat']} ──")
                sep.setFlags(Qt.ItemFlag.NoItemFlags)
                sep.setForeground(QColor(THEME["text_dim"]))
                self._list.addItem(sep)
                last_cat = entry["cat"]
            item = QListWidgetItem(f"  {entry['name']}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)

    def _filter_list(self, text: str):
        self._fill_catalog(text)

    def _on_select(self, current, _):
        if not current:
            return
        entry = current.data(Qt.ItemDataRole.UserRole)
        if not entry:
            self._detail.clear()
            return
        status = "✓ installiert" if entry["name"].lower() in self._installed else "nicht installiert"
        self._detail.setPlainText(
            f"Paket:     {entry['name']}\n"
            f"Kategorie: {entry['cat']}\n"
            f"Status:    {status}\n\n"
            f"{entry['desc']}\n\n"
            f"PyPI: https://pypi.org/project/{entry['name']}/"
        )

    # ── Installierte Pakete laden ─────────────────────────────────────────
    def _load_installed(self):
        import subprocess, sys
        self._log.append("Lade installierte Pakete …")
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=columns"],
                capture_output=True, text=True, timeout=15,
            )
            lines = r.stdout.splitlines()[2:]   # Header überspringen
            self._installed = {line.split()[0].lower() for line in lines if line.strip()}
            self._installed_list.clear()
            for line in sorted(lines, key=lambda l: l.lower()):
                if line.strip():
                    self._installed_list.addItem(line.strip())
            self._log.append(f"{len(self._installed)} Pakete installiert.")
        except Exception as e:
            self._log.append(f"Fehler: {e}")

    # ── Aktionen ─────────────────────────────────────────────────────────
    def _get_selected_packages(self) -> list[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)["name"]
            for item in self._list.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole)
        ]

    def _install_selected(self):
        pkgs = self._get_selected_packages()
        # Auch manuell eingetippter Name aus Suchfeld, falls nicht in Liste
        typed = self._search.text().strip()
        if typed and typed not in pkgs and not self._list.selectedItems():
            pkgs = [typed]
        if not pkgs:
            QMessageBox.information(self, "Nichts ausgewählt",
                                    "Bitte Pakete in der Liste markieren.")
            return
        self._run_pip(pkgs, "install")

    def _uninstall_selected(self):
        pkgs = [item.text().split()[0]
                for item in self._installed_list.selectedItems()]
        if not pkgs:
            QMessageBox.information(self, "Nichts ausgewählt",
                                    "Bitte Pakete in der Liste installierter Pakete markieren.")
            return
        reply = QMessageBox.question(
            self, "Deinstallieren?",
            f"Folgende Pakete deinstallieren?\n{', '.join(pkgs)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._run_pip(pkgs, "uninstall")

    def _run_pip(self, packages: list[str], action: str):
        self._btn_install.setEnabled(False)
        self._btn_uninstall.setEnabled(False)
        self._worker = _PipWorker(packages, action, self)
        self._worker.log.connect(lambda t: self._log.append(t.rstrip()))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, msg: str):
        self._btn_install.setEnabled(True)
        self._btn_uninstall.setEnabled(True)
        self._log.append(f"\n{'✓' if ok else '✗'} {msg}")
        self._load_installed()
        if not ok:
            QMessageBox.critical(self, "Fehler", msg)

