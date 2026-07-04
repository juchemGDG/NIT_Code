#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/python_runtime"
REQ_FILE="$ROOT_DIR/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FORCE=0
SKIP_REQUIREMENTS=0

usage() {
  cat <<'EOF'
Erzeugt eine mitlieferbare Python-Runtime im Projektordner: python_runtime/

Nutzung:
  bash release/scripts/create_embedded_runtime.sh [--force] [--skip-requirements] [--python <pfad|name>]

Optionen:
  --force              Bestehendes python_runtime/ vor dem Erzeugen loeschen.
  --skip-requirements  Nur Runtime + pip erstellen, keine Projektabhaengigkeiten installieren.
  --python <...>       Basis-Python setzen (Standard: python3 oder PYTHON_BIN).
  -h, --help           Hilfe anzeigen.

Beispiele:
  bash release/scripts/create_embedded_runtime.sh --force
  bash release/scripts/create_embedded_runtime.sh --python /usr/bin/python3.12
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --skip-requirements)
      SKIP_REQUIREMENTS=1
      shift
      ;;
    --python)
      if [[ $# -lt 2 ]]; then
        echo "Fehler: --python braucht einen Wert" >&2
        exit 2
      fi
      PYTHON_BIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unbekannte Option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Fehler: Python nicht gefunden: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Fehler: requirements.txt nicht gefunden unter $REQ_FILE" >&2
  exit 1
fi

if [[ -d "$RUNTIME_DIR" ]]; then
  if [[ "$FORCE" -eq 1 ]]; then
    echo "Loesche bestehendes python_runtime/ ..."
    rm -rf "$RUNTIME_DIR"
  else
    echo "Fehler: $RUNTIME_DIR existiert bereits (nutze --force zum Ueberschreiben)." >&2
    exit 1
  fi
fi

echo "Erzeuge Runtime mit: $PYTHON_BIN"
"$PYTHON_BIN" -m venv "$RUNTIME_DIR"

RUNTIME_PY="$RUNTIME_DIR/bin/python"
if [[ ! -x "$RUNTIME_PY" ]]; then
  echo "Fehler: Runtime-Python wurde nicht korrekt erstellt: $RUNTIME_PY" >&2
  exit 1
fi

echo "Upgrade pip/setuptools/wheel in python_runtime ..."
"$RUNTIME_PY" -m pip install --upgrade pip setuptools wheel

if [[ "$SKIP_REQUIREMENTS" -eq 0 ]]; then
  echo "Installiere Projektabhaengigkeiten aus requirements.txt ..."
  "${RUNTIME_PY}" -m pip install -r "$REQ_FILE"
else
  echo "Ueberspringe requirements-Installation (--skip-requirements)."
fi

echo
"$RUNTIME_PY" - <<'PY'
import platform
import sys
print('Fertig. Runtime-Interpreter:', sys.executable)
print('Python-Version:', sys.version.split()[0])
print('Architektur:', platform.machine())
PY

echo "Runtime bereit unter: $RUNTIME_DIR"
