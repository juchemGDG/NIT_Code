"""Konstanten und Konfiguration für NIT_Code."""
import shutil

APP_NAME = "NIT_Code"
APP_VERSION = "1.0.1"

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

# Farbschema (dunkel, modern)
# KI-Tutor (Ollama)
TUTOR_DEFAULT_URL   = "http://localhost:11434"
TUTOR_DEFAULT_MODEL = "llama3.2"


def is_ollama_available() -> bool:
    """True wenn das ollama-Kommando im PATH gefunden wird."""
    return shutil.which("ollama") is not None

THEME = {
    "bg_dark":        "#1e1e2e",
    "bg_mid":         "#252535",
    "bg_panel":       "#2a2a3e",
    "bg_editor":      "#1a1a2a",
    "accent":         "#7c6af7",
    "accent_hover":   "#9d8fff",
    "text":           "#cdd6f4",
    "text_dim":       "#6c7086",
    "success":        "#a6e3a1",
    "error":          "#f38ba8",
    "warning":        "#fab387",
    "info":           "#89dceb",
    "selection":      "#3d3d5c",
    "border":         "#313244",
    "terminal_bg":    "#11111b",
    "terminal_text":  "#cdd6f4",
}
