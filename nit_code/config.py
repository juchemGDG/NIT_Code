"""Konstanten und Konfiguration für NIT_Code."""
import shutil
import sys
from pathlib import Path


def python_executable() -> str:
    """Liefert einen echten Python-Interpreter zum Starten von Subprozessen.

    WICHTIG: In einem PyInstaller-Bundle ist ``sys.executable`` die App selbst
    (z. B. ``NIT_Code.app/Contents/MacOS/NIT_Code``) und KEIN Python-Interpreter.
    Würde man sie als Interpreter starten (``[sys.executable, "-i"]`` o. ä.),
    ignoriert der Bootloader die Argumente und startet die GUI rekursiv neu –
    eine Endlosschleife / Fork-Bomb, die den Rechner zum Absturz bringen kann.

    Im Frozen-Modus wird daher der System-Python gesucht; im normalen Modus
    der venv-Python bzw. der laufende Interpreter.
    """
    if getattr(sys, "frozen", False):
        found = shutil.which("python3") or shutil.which("python")
        return found or ("python" if sys.platform == "win32" else "python3")
    venv_py = Path(__file__).resolve().parents[1] / ".venv" / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def tool_command(module: str) -> list[str]:
    """Befehl, um ein mitgeliefertes Tool (``mpremote``/``esptool``) zu starten.

    Im Frozen-Modus ruft sich die App selbst als Dispatcher auf
    (``[sys.executable, "-m", module]`` – siehe ``release/launcher.py``), weil
    der System-Python das Modul i. d. R. NICHT enthält
    (``No module named mpremote``). Die Module sind ins PyInstaller-Bundle
    eingepackt und werden vom Launcher in-process ausgeführt.

    Im Dev-Modus wird der venv-/aktuelle Python verwendet.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "-m", module]
    return [python_executable(), "-m", module]


APP_NAME = "NIT_Code"
APP_VERSION = "1.3.2"

# GitHub-Repository für Bibliotheken
LIB_REPO_API = "https://api.github.com/repos/juchemGDG/NIT_Bibliotheken/contents"
LIB_REPO_RAW = "https://raw.githubusercontent.com/juchemGDG/NIT_Bibliotheken/main"

# MicroPython Download-Seite
MICROPYTHON_DOWNLOAD_BASE = "https://micropython.org/download/"

SUPPORTED_BOARDS = {
    "ESP32": {
        "label": "ESP32",
        "download_page": "ESP32_GENERIC",
        "flash_cmd": "esp32",
        "baud": 115200,
    },
    "micro:bit": {
        "label": "micro:bit v2",
        "download_page": "MICROBIT",
        "flash_cmd": "microbit",
        "baud": 115200,
    },
    "RPI Pico 2": {
        "label": "Raspberry Pi Pico 2",
        "download_page": "RPI_PICO2",
        "flash_cmd": "rp2",
        "baud": 115200,
    },
    "RPI Pico 2W": {
        "label": "Raspberry Pi Pico 2W",
        "download_page": "RPI_PICO2W",
        "flash_cmd": "rp2",
        "baud": 115200,
    },
}

# KI-Tutor (Ollama)
TUTOR_DEFAULT_URL    = "http://localhost:11434"
TUTOR_DEFAULT_MODEL  = "llama3.2"
OLLAMA_WEB_PASSWORD  = "geheim"

# AIS-Chat (schulischer Web-Chatbot)
AIS_CHAT_URL = "https://app.ais-chat.schule"


def is_ollama_available() -> bool:
    """True wenn das ollama-Kommando im PATH gefunden wird."""
    return shutil.which("ollama") is not None


# ── Themes ───────────────────────────────────────────────────────────────────

_DARK_THEME: dict[str, str] = {
    "bg_dark":       "#1e1e2e",
    "bg_mid":        "#252535",
    "bg_panel":      "#2a2a3e",
    "bg_editor":     "#1a1a2a",
    "accent":        "#7c6af7",
    "accent_hover":  "#9d8fff",
    "text":          "#cdd6f4",
    "text_dim":      "#6c7086",
    "success":       "#a6e3a1",
    "error":         "#f38ba8",
    "warning":       "#fab387",
    "info":          "#89dceb",
    "selection":     "#3d3d5c",
    "border":        "#313244",
    "terminal_bg":   "#11111b",
    "terminal_text": "#cdd6f4",
}

_LIGHT_THEME: dict[str, str] = {          # Eclipse-klassisch
    "bg_dark":       "#f5f5f5",
    "bg_mid":        "#eeeeee",
    "bg_panel":      "#e8e8e8",
    "bg_editor":     "#ffffff",
    "accent":        "#3b6ea5",
    "accent_hover":  "#7f0055",            # Eclipse-Schlüsselwort-Lila
    "text":          "#1a1a1a",
    "text_dim":      "#3f7f5f",            # Eclipse-Kommentar-Grün
    "success":       "#2a00ff",            # Eclipse-String-Blau
    "error":         "#cc0000",
    "warning":       "#00627a",            # Zahlen: Blaugrün
    "info":          "#0000c0",            # Klassen/Funktionen: Dunkelblau
    "selection":     "#cce0f5",
    "border":        "#c8c8c8",
    "terminal_bg":   "#ffffff",
    "terminal_text": "#1a1a1a",
}

THEMES: dict[str, dict[str, str]] = {
    "modern_dark":   _DARK_THEME,
    "classic_light": _LIGHT_THEME,
}

THEME: dict[str, str] = dict(_LIGHT_THEME)  # aktives Theme (veränderlich), Standard: hell


def set_theme(name: str) -> None:
    """Aktives Theme in-place aktualisieren (alle Referenzen auf THEME sehen die Änderung)."""
    THEME.update(THEMES.get(name, _DARK_THEME))
