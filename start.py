#!/usr/bin/env python3
"""NIT PyEd - Python & MicroPython Editor für den Unterricht
Startskript: Erstellt .venv falls nötig und startet den Editor.
"""
import sys
import os
import subprocess
import venv
from pathlib import Path

VENV_DIR = Path(__file__).parent / ".venv"
REQ_FILE = Path(__file__).parent / "requirements.txt"


def create_venv():
    print("Erstelle virtuelle Umgebung (.venv) ...")
    venv.create(VENV_DIR, with_pip=True)


def pip_install():
    pip = VENV_DIR / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
    print("Installiere Abhängigkeiten ...")
    subprocess.check_call([str(pip), "install", "-r", str(REQ_FILE)])


def run_editor():
    python = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    editor_main = Path(__file__).parent / "nit_pyed" / "main.py"
    os.execv(str(python), [str(python), str(editor_main)] + sys.argv[1:])


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
