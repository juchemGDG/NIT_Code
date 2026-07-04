#!/usr/bin/env python3
"""NIT_Code - Python & MicroPython Editor für den Unterricht.

Hybrid-Start:
- bevorzugt eine mitgelieferte Python-Runtime aus `python_runtime/`
- fällt sonst auf den aktuell gestarteten System-Interpreter zurück
- erstellt bei Bedarf eine virtuelle Umgebung und installiert Abhängigkeiten
"""
import sys
import os
import subprocess
import venv
import platform
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REQ_FILE = PROJECT_DIR / "requirements.txt"
RUNTIME_DIR = PROJECT_DIR / "python_runtime"


def _is_arm_mac() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _current_python_arch() -> str:
    return platform.machine()


def _user_data_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        return base / "NIT_Code"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/NIT_Code"
    return Path.home() / ".local/share/NIT_Code"


def _resolve_venv_dir() -> Path:
    local_venv = PROJECT_DIR / ".venv"
    if os.access(str(PROJECT_DIR), os.W_OK):
        return local_venv
    return _user_data_root() / ".venv"


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _bundled_python_candidates() -> list[Path]:
    if sys.platform == "win32":
        return [
            RUNTIME_DIR / "python.exe",
            RUNTIME_DIR / "Scripts/python.exe",
            RUNTIME_DIR / "python/python.exe",
        ]
    return [
        RUNTIME_DIR / "bin/python3",
        RUNTIME_DIR / "bin/python",
        RUNTIME_DIR / "python/bin/python3",
        RUNTIME_DIR / "python/bin/python",
    ]


def _find_bundled_python() -> Path | None:
    for candidate in _bundled_python_candidates():
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _select_base_python() -> Path:
    """Wählt den Basis-Interpreter für die Venv-Erzeugung.

    Modus über NIT_PYTHON_MODE:
    - auto (Standard): eingebettete Runtime bevorzugen, sonst System-Python
    - bundled: nur eingebettete Runtime verwenden (Fehler, falls nicht vorhanden)
    - system: immer aktuellen System-Interpreter verwenden
    """
    mode = os.environ.get("NIT_PYTHON_MODE", "auto").strip().lower()
    bundled = _find_bundled_python()

    if mode == "bundled":
        if bundled is None:
            raise RuntimeError(
                "NIT_PYTHON_MODE=bundled gesetzt, aber keine Runtime unter "
                f"{RUNTIME_DIR} gefunden."
            )
        return bundled

    if mode != "system" and bundled is not None:
        return bundled

    return Path(sys.executable)


def create_venv(venv_dir: Path, base_python: Path):
    print(f"Erstelle virtuelle Umgebung ({venv_dir}) ...")
    base_python = Path(base_python)
    if _is_arm_mac() and _current_python_arch() != "arm64" and base_python == Path(sys.executable):
        # Rosetta-Prozess – venv über nativen ARM64-Python erstellen
        arm_python = _find_arm_python()
        if arm_python:
            subprocess.check_call([arm_python, "-m", "venv", str(venv_dir)])
            return
    subprocess.check_call([str(base_python), "-m", "venv", str(venv_dir)])


def _find_arm_python() -> str | None:
    candidates = [
        "/opt/homebrew/bin/python3",
        "/opt/homebrew/opt/python@3.13/bin/python3",
        "/opt/homebrew/opt/python@3.12/bin/python3",
        "/opt/homebrew/opt/python@3.11/bin/python3",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                arch = subprocess.check_output(
                    [c, "-c", "import platform; print(platform.machine())"],
                    text=True,
                ).strip()
                if arch == "arm64":
                    return c
            except Exception:
                continue
    return None


def pip_install(venv_dir: Path):
    python = _venv_python(venv_dir)
    print("Installiere Abhängigkeiten ...")
    subprocess.check_call([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python), "-m", "pip", "install", "-r", str(REQ_FILE)])


def run_editor(venv_dir: Path):
    python = _venv_python(venv_dir)
    project_dir = str(PROJECT_DIR)
    env = os.environ.copy()
    env["PYTHONPATH"] = project_dir
    os.execve(str(python), [str(python), "-m", "nit_code.main"] + sys.argv[1:], env)


def main():
    venv_dir = _resolve_venv_dir()
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    base_python = _select_base_python()

    if not venv_dir.exists():
        create_venv(venv_dir, base_python)
        pip_install(venv_dir)
    else:
        # Prüfen ob Pakete installiert sind
        python = _venv_python(venv_dir)
        try:
            subprocess.check_call(
                [str(python), "-c", "import PyQt6; import PyQt6.QtWebEngineWidgets"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            pip_install(venv_dir)
    run_editor(venv_dir)


if __name__ == "__main__":
    main()
