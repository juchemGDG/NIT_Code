"""Gemeinsamer Ollama-Streaming-Worker für Tutor- (Infi) und Coder-Panel.

Streamt eine Chat-Antwort token-weise über ``/api/chat``. Läuft hinter einem
passwortgeschützten Schul-Proxy (siehe ``config.ollama_web_password``), wird
bei 401/403 automatisch erst mit Bearer-, dann mit Basic-Auth erneut versucht –
dieselbe Reihenfolge wie beim Modell-Abruf im Einstellungs-Dialog.
"""
import base64
import json

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from .config import ollama_web_password


class OllamaStreamWorker(QThread):
    token_ready    = pyqtSignal(str)      # einzelner Token-Chunk
    response_done  = pyqtSignal()         # Antwort vollständig (immer emittiert)
    error_occurred = pyqtSignal(str)      # Fehlermeldung

    def __init__(self, url: str, model: str, messages: list,
                 temperature: float | None = None, parent=None):
        super().__init__(parent)
        self._url         = url.rstrip("/")
        self._model       = model
        self._messages    = messages
        self._temperature = temperature

    def _header_variants(self) -> list[dict]:
        """Auth-Varianten in Versuchsreihenfolge: ohne, Bearer, Basic."""
        variants: list[dict] = [{}]
        password = ollama_web_password()
        if password:
            variants.append({"Authorization": f"Bearer {password}"})
            creds = base64.b64encode(f":{password}".encode()).decode()
            variants.append({"Authorization": f"Basic {creds}"})
        return variants

    def run(self):
        endpoint = f"{self._url}/api/chat"
        payload = {
            "model":    self._model,
            "messages": self._messages,
            "stream":   True,
        }
        if self._temperature is not None:
            payload["options"] = {"temperature": self._temperature}

        try:
            last_status = None
            for headers in self._header_variants():
                with requests.post(
                    endpoint, json=payload, stream=True,
                    timeout=120, headers=headers,
                ) as resp:
                    last_status = resp.status_code
                    if resp.status_code in (401, 403):
                        continue   # nächste Auth-Variante versuchen
                    if resp.status_code != 200:
                        self.error_occurred.emit(
                            f"Ollama antwortet mit Status {resp.status_code}.\n"
                            f'Ist das Modell "{self._model}" geladen?'
                        )
                        return
                    self._stream_response(resp)
                    return
            self.error_occurred.emit(
                f"Ollama antwortet mit Status {last_status}.\n"
                "Zugangsdaten des Ollama-Proxys prüfen "
                "(NIT_OLLAMA_PASSWORD bzw. ollama_password-Datei)."
            )
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                "Keine Verbindung zu Ollama.\n"
                "Bitte Ollama starten: ollama serve"
            )
        except Exception as exc:
            self.error_occurred.emit(f"Fehler: {exc}")
        finally:
            self.response_done.emit()

    def _stream_response(self, resp):
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            content = data.get("message", {}).get("content", "")
            if content:
                self.token_ready.emit(content)
            if data.get("done"):
                break
