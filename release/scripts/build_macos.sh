#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT_DIR/release/downloads/macos"
# Eingebettete Python-Runtime ist standardmaessig dabei; INCLUDE_RUNTIME=0 schaltet ab.
INCLUDE_RUNTIME="${INCLUDE_RUNTIME:-1}"

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

DMG_PATH="$OUT_DIR/NIT_Code-macos.dmg"
APP_PATH="$ROOT_DIR/dist/NIT_Code.app"

if [[ "$INCLUDE_RUNTIME" == "1" ]]; then
  echo "Erzeuge eingebettete Runtime (python_runtime/) ..."
  bash "$ROOT_DIR/release/scripts/create_embedded_runtime.sh" --force
  # Nach Contents/Resources, NICHT Contents/MacOS: dort behandelt codesign
  # die Runtime-Ordner als "nested code" und bricht ab ("bundle format
  # unrecognized ... In subcomponent: .../include/python3.12"). Unter
  # Resources wird sie nur als Daten versiegelt; nit_code/config.py sucht
  # dort ebenfalls. ditto statt cp -R: erhaelt Zeitstempel/Metadaten.
  echo "Kopiere python_runtime ins App-Bundle ..."
  rm -rf "$APP_PATH/Contents/Resources/python_runtime"
  ditto "$ROOT_DIR/python_runtime" "$APP_PATH/Contents/Resources/python_runtime"

  # WICHTIG: Runtime-Check VOR dem Signieren und ohne Bytecode-Schreiben –
  # sonst schreibt Python .pyc-Dateien ins bereits versiegelte Bundle und
  # die Signatur ist beim Nutzer kaputt ("a sealed resource is missing or
  # invalid" -> macOS meldet die App als "beschaedigt").
  echo "Pruefe gebuendelte Runtime (Python + pip) ..."
  BUNDLED_PY="$APP_PATH/Contents/Resources/python_runtime/python/bin/python3"
  PYTHONDONTWRITEBYTECODE=1 "$BUNDLED_PY" --version
  PYTHONDONTWRITEBYTECODE=1 "$BUNDLED_PY" -m pip --version

  # Das Hineinkopieren bricht das Resources-Siegel der Ad-hoc-Signatur –
  # Bundle neu signieren (ohne --deep: die inneren Binaries hat PyInstaller
  # bereits signiert, nur das Siegel muss neu) und streng verifizieren.
  echo "Signiere App-Bundle neu (ad hoc) ..."
  codesign --force -s - "$APP_PATH"
  codesign --verify --deep --strict "$APP_PATH"
fi

hdiutil create \
  -volname "NIT_Code" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

# -y erhält Symlinks (App-Bundle und Runtime enthalten welche); aus dist/
# heraus packen, damit im Archiv nicht der komplette Build-Pfad landet.
rm -f "$OUT_DIR/NIT_Code-macos-app.zip"
(cd "$ROOT_DIR/dist" && zip -ryq "$OUT_DIR/NIT_Code-macos-app.zip" "NIT_Code.app")

echo "macOS-Pakete erstellt: $DMG_PATH und NIT_Code-macos-app.zip"
