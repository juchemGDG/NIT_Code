#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT_DIR/release/downloads/macos"

mkdir -p "$OUT_DIR"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/release/requirements-build.txt"

pyinstaller "$ROOT_DIR/release/pyinstaller.spec" --noconfirm --clean

DMG_PATH="$OUT_DIR/NIT_Code-macos.dmg"
APP_PATH="$ROOT_DIR/dist/NIT_Code.app"

hdiutil create \
  -volname "NIT_Code" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

zip -r "$OUT_DIR/NIT_Code-macos-app.zip" "$APP_PATH"

echo "macOS-Pakete erstellt: $DMG_PATH und NIT_Code-macos-app.zip"
