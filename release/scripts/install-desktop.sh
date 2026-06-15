#!/usr/bin/env bash
# Registriert NIT_Code im Anwendungsmenü (GNOME, KDE, …), sodass es per Klick
# startbar ist. Aus dem entpackten NIT_Code-Ordner heraus ausführen:
#
#     ./install-desktop.sh
#
# Die .desktop-Datei wird mit absoluten Pfaden auf den AKTUELLEN Speicherort
# erzeugt. Wird der Ordner verschoben, das Skript einfach erneut ausführen.
set -euo pipefail

# Verzeichnis dieses Skripts = Ordner mit der NIT_Code-Binary.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXEC_PATH="$APP_DIR/NIT_Code"
ICON_PATH="$APP_DIR/_internal/nit_code/logo.png"

if [ ! -x "$EXEC_PATH" ]; then
    chmod +x "$EXEC_PATH" 2>/dev/null || true
fi

DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$DESKTOP_DIR/nit_code.desktop"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=NIT_Code
Comment=Python-IDE für den Informatikunterricht
Exec=$EXEC_PATH
Icon=$ICON_PATH
Terminal=false
Categories=Development;IDE;Education;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Menü-Datenbank aktualisieren, falls das Werkzeug vorhanden ist.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "NIT_Code wurde im Anwendungsmenü registriert:"
echo "  $DESKTOP_FILE"
echo "Es kann nun über das App-Menü gestartet werden."
