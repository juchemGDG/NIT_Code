#!/bin/bash
# NIT_Code – Linux/macOS Starter
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Mitgelieferte Python-Runtime bevorzugen (Hybrid-Modus).
find_bundled_python() {
    local runtime_dir="$SCRIPT_DIR/python_runtime"
    for candidate in \
        "$runtime_dir/bin/python3" \
        "$runtime_dir/bin/python" \
        "$runtime_dir/python/bin/python3" \
        "$runtime_dir/python/bin/python"; do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return
        fi
    done
}

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

PYTHON="$(find_bundled_python)"
if [[ -z "$PYTHON" ]]; then
    PYTHON=$(find_python)
fi
echo "Verwende Python: $PYTHON ($($PYTHON -c 'import platform; print(platform.machine())' 2>/dev/null))"

PYTHONPATH="$SCRIPT_DIR" "$PYTHON" "$SCRIPT_DIR/start.py" "$@"
