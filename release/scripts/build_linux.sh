#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT_DIR/release/downloads/linux"
# Tarball-Name an die Build-Architektur koppeln (x86_64 bzw. aarch64), damit
# x86- und ARM-Pakete sich nicht gegenseitig überschreiben.
ARCH="$(uname -m)"

mkdir -p "$OUT_DIR"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/release/requirements-build.txt"

pyinstaller "$ROOT_DIR/release/pyinstaller.spec" --noconfirm --clean

# Desktop-Installer mit ins Bundle legen, damit Nutzer NIT_Code per
# ./install-desktop.sh ins Anwendungsmenü eintragen können.
cp "$ROOT_DIR/release/scripts/install-desktop.sh" "$ROOT_DIR/dist/NIT_Code/install-desktop.sh"
chmod +x "$ROOT_DIR/dist/NIT_Code/install-desktop.sh"

tar -C "$ROOT_DIR/dist" -czf "$OUT_DIR/NIT_Code-linux-${ARCH}.tar.gz" "NIT_Code"

echo "Linux-Paket erstellt: $OUT_DIR/NIT_Code-linux-${ARCH}.tar.gz"
