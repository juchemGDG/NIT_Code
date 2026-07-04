#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT_DIR/release/downloads/macos"
INCLUDE_RUNTIME="${INCLUDE_RUNTIME:-0}"

mkdir -p "$OUT_DIR"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/release/requirements-build.txt"

# logo.png → NIT_Code.icns
LOGO_PNG="$ROOT_DIR/nit_code/logo.png"
ICNS_PATH="$ROOT_DIR/release/NIT_Code.icns"
if [ -f "$LOGO_PNG" ]; then
  ICONSET_DIR="$(mktemp -d)/NIT_Code.iconset"
  mkdir -p "$ICONSET_DIR"
  for size in 16 32 128 256 512; do
    sips -z $size $size "$LOGO_PNG" --out "$ICONSET_DIR/icon_${size}x${size}.png" > /dev/null
    double=$((size * 2))
    sips -z $double $double "$LOGO_PNG" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" > /dev/null
  done
  iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"
  echo "Icon erstellt: $ICNS_PATH"
fi

pyinstaller "$ROOT_DIR/release/pyinstaller.spec" --noconfirm --clean

if [[ "$INCLUDE_RUNTIME" == "1" ]]; then
  echo "Erzeuge eingebettete Runtime (python_runtime/) ..."
  bash "$ROOT_DIR/release/scripts/create_embedded_runtime.sh" --force
  echo "Kopiere python_runtime ins App-Bundle ..."
  rm -rf "$ROOT_DIR/dist/NIT_Code.app/Contents/MacOS/python_runtime"
  cp -R "$ROOT_DIR/python_runtime" "$ROOT_DIR/dist/NIT_Code.app/Contents/MacOS/python_runtime"
fi

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
