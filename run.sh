#!/bin/bash
# NIT_Code – Linux/macOS Starter
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Python-Executable ermitteln ─────────────────────────────────────────────
# Auf Apple Silicon (arm64): nativen ARM64-Python suchen, Rosetta vermeiden
find_python() {
    if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
        # Bevorzugte Kandidaten: Homebrew ARM64, dann Python.org universal
        for candidate in \
            /opt/homebrew/bin/python3 \
            /opt/homebrew/opt/python@3.13/bin/python3 \
            /opt/homebrew/opt/python@3.12/bin/python3 \
            /opt/homebrew/opt/python@3.11/bin/python3 \
            /usr/local/bin/python3 \
            python3; do
            if command -v "$candidate" &>/dev/null; then
                ARCH=$("$candidate" -c "import platform; print(platform.machine())" 2>/dev/null)
                if [[ "$ARCH" == "arm64" ]]; then
                    echo "$candidate"
                    return
                fi
            fi
        done
        # Letzter Ausweg: arch -arm64 erzwingen
        echo "arch -arm64 $(command -v python3)"
    else
        echo "python3"
    fi
}

PYTHON=$(find_python)
echo "Verwende Python: $PYTHON ($($PYTHON -c 'import platform; print(platform.machine())' 2>/dev/null))"

if [ ! -d ".venv" ]; then
    echo "Erstelle virtuelle Umgebung (.venv) ..."
    $PYTHON -m venv .venv
    echo "Installiere Abhängigkeiten ..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

PYTHONPATH="$SCRIPT_DIR" .venv/bin/python start.py "$@"
