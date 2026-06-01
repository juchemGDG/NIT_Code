#!/usr/bin/env python3
"""NIT_Code - Python & MicroPython Editor für den Unterricht
Startskript: Erstellt .venv falls nötig und startet den Editor.
"""
import sys
import os
import subprocess
import venv
import platform
from pathlib import Path

VENV_DIR = Path(__file__).parent / ".venv"
REQ_FILE = Path(__file__).parent / "requirements.txt"


def _is_arm_mac() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _current_python_arch() -> str:
    return platform.machine()


def create_venv():
    print("Erstelle virtuelle Umgebung (.venv) ...")
    if _is_arm_mac() and _current_python_arch() != "arm64":
        # Rosetta-Prozess – venv über nativen ARM64-Python erstellen
        arm_python = _find_arm_python()
        if arm_python:
            subprocess.check_call([arm_python, "-m", "venv", str(VENV_DIR)])
            return
    venv.create(VENV_DIR, with_pip=True)


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


def pip_install():
    pip = VENV_DIR / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
    print("Installiere Abhängigkeiten ...")
    subprocess.check_call([str(pip), "install", "--upgrade", "pip"])
    subprocess.check_call([str(pip), "install", "-r", str(REQ_FILE)])


def run_editor():
    python = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    project_dir = str(Path(__file__).parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = project_dir
    os.execve(str(python), [str(python), "-m", "nit_pyed.main"] + sys.argv[1:], env)


def main():
    if not VENV_DIR.exists():
        create_venv()
        pip_install()
    else:
        # Prüfen ob Pakete installiert sind
        python = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        try:
            subprocess.check_call(
                [str(python), "-c", "import PyQt6"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            pip_install()
    run_editor()


if __name__ == "__main__":
    main()
