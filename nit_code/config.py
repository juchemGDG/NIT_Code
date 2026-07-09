"""Konstanten und Konfiguration für NIT_Code."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def python_executable() -> str:
    """Liefert einen echten Python-Interpreter zum Starten von Subprozessen.

    WICHTIG: In einem PyInstaller-Bundle ist ``sys.executable`` die App selbst
    (z. B. ``NIT_Code.app/Contents/MacOS/NIT_Code``) und KEIN Python-Interpreter.
    Würde man sie als Interpreter starten (``[sys.executable, "-i"]`` o. ä.),
    ignoriert der Bootloader die Argumente und startet die GUI rekursiv neu –
    eine Endlosschleife / Fork-Bomb, die den Rechner zum Absturz bringen kann.

    Im Frozen-Modus wird ein „guter" System-Python gesucht; im normalen Modus
    der venv-Python bzw. der laufende Interpreter.
    """
    if getattr(sys, "frozen", False):
        return _best_system_python()
    venv_py = _venv_python()
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _is_poor_macos_python(path: str) -> bool:
    """True für macOS-Pythons, die für den Unterricht ungeeignet sind.

    Der Command-Line-Tools-/System-Python bringt ein veraltetes Tk 8.5 mit
    (leere/abstürzende Tkinter-Fenster) und ist häufig „externally managed"
    (pip blockiert). python.org-/Homebrew-Pythons sind klar zu bevorzugen.
    """
    pl = path.lower()
    return (
        "/library/developer/commandlinetools" in pl
        or pl.startswith("/system/")
    )


_BEST_PYTHON_CACHE: str | None = None


def _best_system_python() -> str:
    """Bester verfügbarer System-Python (Frozen-Modus), Command-Line-Tools meidend."""
    global _BEST_PYTHON_CACHE
    if _BEST_PYTHON_CACHE:
        return _BEST_PYTHON_CACHE
    candidates = detect_python_interpreters()
    good = [c for c in candidates if not _is_poor_macos_python(c)]
    chosen = (
        good[0] if good
        else (candidates[0] if candidates else None)
        or shutil.which("python3") or shutil.which("python")
        or ("python" if sys.platform == "win32" else "python3")
    )
    _BEST_PYTHON_CACHE = chosen
    return chosen


def _venv_python() -> Path:
    """Pfad zum Python der projekteigenen .venv (Dev-Modus)."""
    return Path(__file__).resolve().parents[1] / ".venv" / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )


def _embedded_runtime_candidates() -> list[Path]:
    """Mögliche Interpreter-Pfade einer mitgelieferten Runtime.

    Dev-Modus: ``<project>/python_runtime/...``
    Frozen-Modus: neben der App-EXE bzw. im App-Bundle-Inhalt.
    """
    project_root = Path(__file__).resolve().parents[1]
    roots: list[Path] = [project_root / "python_runtime"]

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir / "python_runtime")
        # Falls Startpunkt innerhalb eines App-Bundles liegt, auch einen Level höher prüfen.
        roots.append(exe_dir.parent / "python_runtime")
        # macOS-App-Bundle: Contents/Resources als alternativer Ablageort.
        roots.append(exe_dir.parent / "Resources" / "python_runtime")

    if sys.platform == "win32":
        rels = [
            Path("python.exe"),
            Path("Scripts/python.exe"),
            Path("python/python.exe"),
        ]
    else:
        rels = [
            Path("bin/python3"),
            Path("bin/python"),
            Path("python/bin/python3"),
            Path("python/bin/python"),
        ]

    out: list[Path] = []
    for root in roots:
        for rel in rels:
            out.append(root / rel)
    return out


def embedded_python_executable() -> str | None:
    """Liefert den Pfad zum mitgelieferten Python-Interpreter, falls vorhanden."""
    for cand in _embedded_runtime_candidates():
        if cand.exists():
            return str(cand)
    return None


def preferred_python_interpreter() -> str | None:
    """Bevorzugter Interpreter für die UI-Auswahl (erster ermittelter Treffer)."""
    found = detect_python_interpreters()
    return found[0] if found else None


def detect_python_interpreters() -> list[str]:
    """Sucht mögliche Python-Interpreter auf dem System.

    Durchsucht PATH und plattformtypische Installationsorte. Liefert eine
    deduplizierte Liste echter Pfade (reale Ziele, keine Symlink-Dubletten).
    Die App selbst (Frozen-EXE) wird NIE vorgeschlagen – das würde beim Start
    eines Programms die GUI rekursiv neu öffnen (Fork-Bomb-Schutz).
    """
    found: list[str] = []
    seen_real: set[str] = set()

    def add(path: str | None):
        if not path:
            return
        try:
            p = Path(path)
            if not p.exists():
                return
            shown = str(p)
            real = str(p.resolve())
        except OSError:
            return
        if real in seen_real:
            return
        seen_real.add(real)
        found.append(shown)

    # 0. Mitgelieferte Runtime bevorzugt (Hybrid-Modus)
    for cand in _embedded_runtime_candidates():
        if cand.exists():
            add(str(cand))

    # 1. Projekteigene .venv (Dev-Modus) zuerst
    venv_py = _venv_python()
    if venv_py.exists():
        add(str(venv_py))

    # 2. Über PATH auffindbare Namen
    minor_names = [f"python3.{m}" for m in range(20, 7, -1)]
    if sys.platform == "win32":
        path_names = ["python.exe", "python3.exe", "python"]
    else:
        path_names = ["python3", "python", *minor_names]
    for name in path_names:
        add(shutil.which(name))

    # 3. Plattformtypische Installationsorte
    if sys.platform == "win32":
        # py-Launcher kennt alle registrierten Versionen
        py_launcher = shutil.which("py")
        if py_launcher:
            try:
                res = subprocess.run([py_launcher, "-0p"], capture_output=True,
                                     text=True, timeout=5)
                for line in res.stdout.splitlines():
                    for token in line.split():
                        if token.lower().endswith("python.exe"):
                            add(token)
            except Exception:
                pass
        bases: list[str] = []
        for env_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            val = os.environ.get(env_var)
            if val:
                bases.append(val)
        bases.append("C:\\")
        for base in bases:
            for pattern_base in (Path(base), Path(base) / "Programs" / "Python"):
                try:
                    for d in pattern_base.glob("Python3*"):
                        add(str(d / "python.exe"))
                except OSError:
                    pass
    else:
        search_dirs = [
            "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin",
            "/opt/local/bin", str(Path.home() / ".pyenv" / "shims"),
        ]
        macfw = Path("/Library/Frameworks/Python.framework/Versions")
        if macfw.exists():
            try:
                for ver in macfw.glob("3.*"):
                    search_dirs.append(str(ver / "bin"))
            except OSError:
                pass
        for d in search_dirs:
            for name in ["python3", "python", *minor_names]:
                add(str(Path(d) / name))

    # 4. Frozen-App-EXE niemals vorschlagen
    if getattr(sys, "frozen", False):
        try:
            self_exe = str(Path(sys.executable).resolve())
            found = [c for c in found if c != self_exe]
        except OSError:
            pass

    return found


def python_version_label(path: str) -> str:
    """Kurzbeschreibung (z. B. 'Python 3.12.3') eines Interpreters – leer bei Fehler."""
    try:
        res = subprocess.run([path, "--version"], capture_output=True,
                             text=True, timeout=5)
        return (res.stdout or res.stderr).strip()
    except Exception:
        return ""


def python_has_tkinter(path: str) -> bool:
    """Prüft, ob ein Interpreter tkinter importieren kann.

    Viele GUI-Programme im Unterricht brauchen tkinter. Es fehlt z. B. beim
    Homebrew-Python ohne ``python-tk`` oder ist beim macOS-System-Python defekt.
    """
    try:
        res = subprocess.run([path, "-c", "import tkinter"],
                             capture_output=True, text=True, timeout=8)
        return res.returncode == 0
    except Exception:
        return False


def asset_path(name: str) -> Path | None:
    """Findet eine Datei im assets-Ordner – im Dev- wie im PyInstaller-Bundle."""
    candidates = []
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "nit_code" / "assets" / name)
        candidates.append(Path(sys.executable).parent / "nit_code" / "assets" / name)
    candidates.append(Path(__file__).resolve().parent / "assets" / name)
    for p in candidates:
        if p.exists():
            return p
    return None


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
APP_VERSION = "1.8.8"

# GitHub-Repository für Bibliotheken
LIB_REPO_API = "https://api.github.com/repos/juchemGDG/NIT_Bibliotheken/contents"
LIB_REPO_RAW = "https://raw.githubusercontent.com/juchemGDG/NIT_Bibliotheken/main"

# MicroPython Download-Seite
MICROPYTHON_DOWNLOAD_BASE = "https://micropython.org/download/"

# Fehlerbericht ("Hilfe → Fehler melden"). Der Dialog schickt einen HTTPS-POST
# (JSON) an BUG_REPORT_URL; ein kleines Server-Skript (siehe server/bugreport.php)
# leitet ihn als E-Mail an BUG_REPORT_EMAIL weiter. So liegen KEINE Mail-
# Zugangsdaten im Programm. URL an den eigenen Endpoint anpassen.
BUG_REPORT_URL = "https://mint-checker.de/nitcode/nc-report-x7q3.php"
BUG_REPORT_EMAIL = "nitcode@mint-checker.de"

SUPPORTED_BOARDS = {
    # ESP-Familie: alle über esptool geflasht (flash_cmd "esp32"). Chip-Typ und
    # Bootloader-Offset unterscheiden sich je Variante – der originale ESP32 und
    # der S2 haben den Bootloader bei 0x1000, die neueren RISC-V-/S3-Chips bei 0x0.
    "ESP32": {
        "label": "ESP32",
        "download_page": "ESP32_GENERIC",
        "flash_cmd": "esp32",
        "chip": "esp32",
        "flash_offset": "0x1000",
        "baud": 115200,
    },
    "ESP32-C3": {
        "label": "ESP32-C3",
        "download_page": "ESP32_GENERIC_C3",
        "flash_cmd": "esp32",
        "chip": "esp32c3",
        "flash_offset": "0x0",
        "baud": 115200,
    },
    "ESP32-S3": {
        "label": "ESP32-S3",
        "download_page": "ESP32_GENERIC_S3",
        "flash_cmd": "esp32",
        "chip": "esp32s3",
        "flash_offset": "0x0",
        "baud": 115200,
    },
    "ESP32-C6": {
        "label": "ESP32-C6",
        "download_page": "ESP32_GENERIC_C6",
        "flash_cmd": "esp32",
        "chip": "esp32c6",
        "flash_offset": "0x0",
        "baud": 115200,
    },
    "ESP32-S2": {
        "label": "ESP32-S2",
        "download_page": "ESP32_GENERIC_S2",
        "flash_cmd": "esp32",
        "chip": "esp32s2",
        "flash_offset": "0x1000",
        "baud": 115200,
    },
    "micro:bit": {
        "label": "micro:bit (auto v1/v2)",
        "download_page": "MICROBIT_AUTO",
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
        "download_page": "RPI_PICO2_W",
        "flash_cmd": "rp2",
        "baud": 115200,
    },
}

# KI-Tutor (Ollama)
TUTOR_DEFAULT_URL    = "http://localhost:11434"
TUTOR_DEFAULT_MODEL  = "llama3.2"


def ollama_web_password() -> str:
    """Optionales Passwort für einen geschützten Ollama-Web-Proxy.

    Wird NICHT im Quellcode gespeichert (kein Klartext im Repository). Reihenfolge:
      1. Umgebungsvariable ``NIT_OLLAMA_PASSWORD``
      2. lokale, nicht versionierte Datei ``<config-dir>/nit_code/ollama_password``
      3. leer → es wird ohne Authentifizierung versucht (lokales Ollama braucht keine)

    Lokales Ollama (localhost) benötigt ohnehin kein Passwort; relevant ist dies
    nur für einen schulischen Reverse-Proxy mit Basic-/Bearer-Auth.
    """
    env = os.environ.get("NIT_OLLAMA_PASSWORD")
    if env:
        return env.strip()
    try:
        pw_file = _user_config_dir() / "ollama_password"
        if pw_file.exists():
            return pw_file.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _user_config_dir() -> Path:
    """Plattformabhängiges, nutzerspezifisches Konfigverzeichnis für NIT_Code."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "nit_code"

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
