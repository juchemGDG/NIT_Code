#!/usr/bin/env bash
set -euo pipefail

# Erzeugt eine mitlieferbare Python-Runtime im Projektordner: python_runtime/
#
# WICHTIG: Früher wurde hier ein venv erzeugt (python -m venv). Ein venv ist
# NICHT relocatable: auf macOS/Linux ist bin/python3 nur ein Symlink auf das
# Python des Build-Rechners, und pyvenv.cfg verweist auf dessen Pfad. Auf jedem
# anderen Rechner zeigt der Symlink ins Leere – die "eingebettete" Runtime
# existiert dort faktisch nicht und wurde deshalb in den Einstellungen weder
# angezeigt noch vorausgewählt.
#
# Darum wird jetzt python-build-standalone verwendet: ein vollständig
# eigenständiges, verschiebbares CPython (inkl. tkinter und pip) von
# https://github.com/astral-sh/python-build-standalone
#
# Ergebnis-Layout (von nit_code/config.py und start.py erwartet):
#   python_runtime/python/bin/python3

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/python_runtime"
REQ_FILE="$ROOT_DIR/release/requirements-runtime.txt"

# Gepinnte Version von python-build-standalone (per Umgebungsvariable übersteuerbar).
PBS_RELEASE="${PBS_RELEASE:-20260623}"
PBS_PYTHON_VERSION="${PBS_PYTHON_VERSION:-3.12.13}"

FORCE=0
SKIP_REQUIREMENTS=0

usage() {
  cat <<'EOF'
Erzeugt eine mitlieferbare, relocatable Python-Runtime: python_runtime/

Nutzung:
  bash release/scripts/create_embedded_runtime.sh [--force] [--skip-requirements] [--requirements <datei>]

Optionen:
  --force              Bestehendes python_runtime/ vor dem Erzeugen loeschen.
  --skip-requirements  Nur die Runtime bereitstellen, keine Pakete installieren.
  --requirements <..>  Alternative requirements-Datei (Standard:
                       release/requirements-runtime.txt).
  -h, --help           Hilfe anzeigen.

Umgebungsvariablen:
  PBS_RELEASE          Release-Tag von python-build-standalone (Standard: 20260623)
  PBS_PYTHON_VERSION   CPython-Version (Standard: 3.12.13)

Beispiele:
  bash release/scripts/create_embedded_runtime.sh --force
  PBS_PYTHON_VERSION=3.13.14 bash release/scripts/create_embedded_runtime.sh --force
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
    --requirements)
      if [[ $# -lt 2 ]]; then
        echo "Fehler: --requirements braucht einen Wert" >&2
        exit 2
      fi
      REQ_FILE="$2"
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

# Plattform/Architektur → python-build-standalone-Zielkennung
case "$(uname -s)" in
  Darwin) OS_TAG="apple-darwin" ;;
  Linux)  OS_TAG="unknown-linux-gnu" ;;
  *)
    echo "Fehler: Nicht unterstuetzte Plattform: $(uname -s)" >&2
    exit 1
    ;;
esac

case "$(uname -m)" in
  arm64|aarch64) ARCH_TAG="aarch64" ;;
  x86_64|amd64)  ARCH_TAG="x86_64" ;;
  *)
    echo "Fehler: Nicht unterstuetzte Architektur: $(uname -m)" >&2
    exit 1
    ;;
esac

ASSET="cpython-${PBS_PYTHON_VERSION}+${PBS_RELEASE}-${ARCH_TAG}-${OS_TAG}-install_only.tar.gz"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/${ASSET}"

if [[ -d "$RUNTIME_DIR" ]]; then
  if [[ "$FORCE" -eq 1 ]]; then
    echo "Loesche bestehendes python_runtime/ ..."
    rm -rf "$RUNTIME_DIR"
  else
    echo "Fehler: $RUNTIME_DIR existiert bereits (nutze --force zum Ueberschreiben)." >&2
    exit 1
  fi
fi

if [[ "$SKIP_REQUIREMENTS" -eq 0 && ! -f "$REQ_FILE" ]]; then
  echo "Fehler: requirements-Datei nicht gefunden: $REQ_FILE" >&2
  exit 1
fi

TMP_TARBALL="$(mktemp)"
trap 'rm -f "$TMP_TARBALL"' EXIT

echo "Lade $ASSET ..."
curl -fL --retry 3 -o "$TMP_TARBALL" "$URL"

mkdir -p "$RUNTIME_DIR"
echo "Entpacke nach $RUNTIME_DIR ..."
tar -xzf "$TMP_TARBALL" -C "$RUNTIME_DIR"    # entpackt als python_runtime/python/

RUNTIME_PY="$RUNTIME_DIR/python/bin/python3"
if [[ ! -x "$RUNTIME_PY" ]]; then
  echo "Fehler: Runtime-Python wurde nicht korrekt erstellt: $RUNTIME_PY" >&2
  exit 1
fi

# Ohne dies "sieht" pip Pakete aus ~/.local des Build-Rechners und
# installiert sie dann NICHT in die Runtime ("Requirement already satisfied").
export PYTHONNOUSERSITE=1

# pip sicherstellen (install_only-Builds bringen pip i. d. R. schon mit)
if ! "$RUNTIME_PY" -m pip --version >/dev/null 2>&1; then
  "$RUNTIME_PY" -m ensurepip --upgrade
fi
echo "Upgrade pip in python_runtime ..."
"$RUNTIME_PY" -m pip install --upgrade pip

if [[ "$SKIP_REQUIREMENTS" -eq 0 ]]; then
  echo "Installiere Runtime-Pakete aus $REQ_FILE ..."
  "$RUNTIME_PY" -m pip install -r "$REQ_FILE"
else
  echo "Ueberspringe Paket-Installation (--skip-requirements)."
fi

# .pyc-Dateien hash-basiert (PEP 552) neu erzeugen: Standard-.pyc sind
# mtime-basiert und gelten nach dem Kopieren/Entpacken auf anderen Rechnern
# als veraltet – Python schreibt sie dann beim ersten Import neu. Im macOS-
# App-Bundle wuerde genau das das Ressourcen-Siegel der Signatur brechen
# ("beschaedigt"-Dialog). Hash-basierte .pyc bleiben dauerhaft gueltig.
echo "Kompiliere Bytecode (hash-basiert) ..."
if ! "$RUNTIME_PY" -m compileall -f -q --invalidation-mode unchecked-hash \
    -x '(bad_coding|badsyntax|lib2to3)' "$RUNTIME_DIR/python/lib"; then
  echo "Warnung: Bytecode-Kompilierung teilweise fehlgeschlagen (fahre fort)." >&2
fi

echo
"$RUNTIME_PY" - <<'PY'
import platform
import sys
print('Fertig. Runtime-Interpreter:', sys.executable)
print('Python-Version:', sys.version.split()[0])
print('Architektur:', platform.machine())
try:
    import tkinter
    print('tkinter: verfuegbar (Tk', tkinter.TkVersion, ')')
except Exception as exc:
    print('tkinter: FEHLT –', exc)
PY

echo "Runtime bereit unter: $RUNTIME_DIR"
