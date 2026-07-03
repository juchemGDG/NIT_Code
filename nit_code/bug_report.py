"""Dialog „Fehler melden" (Hilfe-Menü).

Sammelt eine Fehlerbeschreibung, hängt automatisch den aktuellen Code und die
Konsolenausgabe an, prüft eine einfache Rechen-Abfrage (Bot-/Versehen-Bremse)
und schickt alles per HTTPS-POST an ``BUG_REPORT_URL``. Ein kleines Server-Skript
(siehe ``server/bugreport.php``) leitet den Bericht als E-Mail weiter – es liegen
also keine Mail-Zugangsdaten im Programm.
"""
import platform
import random
from datetime import datetime

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QLineEdit,
    QPushButton, QCheckBox, QMessageBox,
)

from .config import (
    BUG_REPORT_URL, BUG_REPORT_EMAIL, APP_NAME, APP_VERSION, THEME,
)
from .net_hints import with_network_hint


class BugReportWorker(QThread):
    """Schickt den Fehlerbericht als JSON per HTTPS-POST (im Hintergrund)."""
    done = pyqtSignal(bool, str)   # (erfolg, fehlermeldung)

    def __init__(self, url: str, payload: dict):
        super().__init__()
        self.url = url
        self.payload = payload

    def run(self):
        try:
            resp = requests.post(self.url, json=self.payload, timeout=20)
            if 200 <= resp.status_code < 300:
                self.done.emit(True, "")
            else:
                self.done.emit(False, "Server antwortete mit Status "
                               f"{resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            self.done.emit(False, with_network_hint(e))


class BugReportDialog(QDialog):
    def __init__(self, code: str = "", console: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fehler melden")
        self.setMinimumSize(560, 600)
        self._code = code or ""
        self._console = console or ""
        self._worker: BugReportWorker | None = None
        # Einfache Rechen-Abfrage statt echtem Captcha (Desktop-App, offline).
        self._a = random.randint(2, 9)
        self._b = random.randint(2, 9)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(9)

        intro = QLabel(
            "Beschreibe möglichst genau, was du gemacht hast und was schiefging. "
            "Der aktuelle Code und die Konsolenausgabe werden auf Wunsch mitgeschickt."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel("Fehlerbeschreibung:"))
        self._desc = QTextEdit()
        self._desc.setPlaceholderText("Was ist passiert? Was hattest du erwartet?")
        self._desc.setMinimumHeight(120)
        layout.addWidget(self._desc)

        row = QHBoxLayout()
        row.addWidget(QLabel("Deine E-Mail (optional, für Rückfragen):"))
        self._email = QLineEdit()
        self._email.setPlaceholderText("name@schule.de")
        row.addWidget(self._email, 1)
        layout.addLayout(row)

        self._attach = QCheckBox("Aktuellen Code und Konsolenausgabe anhängen")
        self._attach.setChecked(True)
        self._attach.toggled.connect(self._update_preview)
        layout.addWidget(self._attach)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(150)
        layout.addWidget(self._preview)
        self._update_preview()

        cap = QHBoxLayout()
        cap.addWidget(QLabel(f"Sicherheitsfrage: Was ist {self._a} + {self._b}?"))
        self._captcha = QLineEdit()
        self._captcha.setFixedWidth(80)
        cap.addWidget(self._captcha)
        cap.addStretch()
        layout.addLayout(cap)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        btns = QHBoxLayout()
        btns.addStretch()
        self._btn_send = QPushButton("Senden")
        self._btn_send.setStyleSheet(
            f"background:{THEME['accent']}; color:white; font-weight:bold;"
            " border:none; border-radius:5px; padding:7px 18px;"
        )
        self._btn_send.clicked.connect(self._send)
        btns.addWidget(self._btn_send)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _update_preview(self):
        if self._attach.isChecked():
            self._preview.setVisible(True)
            self._preview.setPlainText(
                "--- Code ---\n" + (self._code or "(kein Code)") +
                "\n\n--- Konsole ---\n" + (self._console or "(keine Ausgabe)")
            )
        else:
            self._preview.setVisible(False)

    def _send(self):
        desc = self._desc.toPlainText().strip()
        if not desc:
            QMessageBox.warning(self, "Beschreibung fehlt",
                                "Bitte beschreibe den Fehler kurz.")
            return
        answer = self._captcha.text().strip()
        if answer != str(self._a + self._b):
            QMessageBox.warning(self, "Sicherheitsfrage",
                                "Die Antwort auf die Rechenaufgabe stimmt nicht.")
            return
        if not BUG_REPORT_URL:
            QMessageBox.warning(self, "Kein Ziel konfiguriert",
                                "Es ist keine Melde-Adresse (BUG_REPORT_URL) hinterlegt.")
            return

        payload = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "platform": platform.platform(),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "description": desc,
            "email": self._email.text().strip(),
            "code": self._code if self._attach.isChecked() else "",
            "console": self._console if self._attach.isChecked() else "",
        }

        self._btn_send.setEnabled(False)
        self._status.setText("Sende Bericht …")
        self._worker = BugReportWorker(BUG_REPORT_URL, payload)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, err: str):
        if ok:
            QMessageBox.information(
                self, "Danke!",
                f"Dein Fehlerbericht wurde an {BUG_REPORT_EMAIL} gesendet. Danke!"
            )
            self.accept()
        else:
            self._btn_send.setEnabled(True)
            self._status.setText("")
            QMessageBox.critical(
                self, "Senden fehlgeschlagen",
                "Der Bericht konnte nicht gesendet werden:\n\n" + err +
                f"\n\nDu kannst ihn auch direkt an {BUG_REPORT_EMAIL} mailen."
            )
