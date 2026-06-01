@echo off
REM NIT_Code – Windows Starter
cd /d "%~dp0"

if not exist ".venv" (
    echo Erstelle virtuelle Umgebung ...
    python -m venv .venv
    echo Installiere Abhaengigkeiten ...
    .venv\Scripts\pip install -r requirements.txt
)

.venv\Scripts\python start.py %*
