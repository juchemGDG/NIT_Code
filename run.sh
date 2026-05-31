#!/bin/bash
# NIT PyEd – Linux/macOS Starter
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Erstelle virtuelle Umgebung ..."
    python3 -m venv .venv
    echo "Installiere Abhängigkeiten ..."
    .venv/bin/pip install -r requirements.txt
fi

.venv/bin/python start.py "$@"
