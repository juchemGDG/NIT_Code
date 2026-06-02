#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT_DIR/release/downloads/linux"

mkdir -p "$OUT_DIR"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/release/requirements-build.txt"

pyinstaller "$ROOT_DIR/release/pyinstaller.spec" --noconfirm --clean

tar -C "$ROOT_DIR/dist" -czf "$OUT_DIR/NIT_Code-linux-x86_64.tar.gz" "NIT_Code"

echo "Linux-Paket erstellt: $OUT_DIR/NIT_Code-linux-x86_64.tar.gz"
