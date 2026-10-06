#!/usr/bin/env bash
# Übernimmt die Web-App aus dem StatPlot-Repository in NIT_Code.
#
#   bash release/scripts/sync_statplot.sh ../StatPlot
#
# NIT_Code liefert StatPlot (Datenauswertung) mit und zeigt es offline über
# einen lokalen Server (nit_code/statplot_window.py). Nach Änderungen an
# StatPlot dieses Skript laufen lassen und das Ergebnis committen. Der Stand
# steht danach in nit_code/assets/statplot/VERSION.
set -euo pipefail

SRC="${1:?Pfad zum StatPlot-Repository angeben, z. B. ../StatPlot}"
STATIC="$SRC/web/static"
DEST="$(cd "$(dirname "$0")/../.." && pwd)/nit_code/assets/statplot"

[ -f "$STATIC/index.html" ] || { echo "Keine StatPlot-Web-App unter $STATIC gefunden." >&2; exit 1; }

# Vor dem Übernehmen: Rechentests von StatPlot (falls Node vorhanden)
if command -v node >/dev/null && [ -f "$SRC/tests/test_stats.js" ]; then
  node "$SRC/tests/test_stats.js"
fi

rm -rf "$DEST"
mkdir -p "$DEST/beispiele"
# Nur was die Seite zur Laufzeit braucht (ohne .htaccess, downloads/ und PNG-Icons –
# im iframe gibt es keinen Browser-Tab, und *.png ist hier ohnehin ignoriert)
cp "$STATIC"/index.html "$STATIC"/stats.js "$STATIC"/statplot.js "$STATIC"/statplot.css \
   "$STATIC"/favicon.svg "$DEST/"
cp "$STATIC"/beispiele/*.csv "$DEST/beispiele/"

STAND="$(git -C "$SRC" describe --tags --always --dirty 2>/dev/null || echo unbekannt)"
printf 'StatPlot %s\nQuelle: https://github.com/juchemGDG/StatPlot\nÜbernommen mit release/scripts/sync_statplot.sh – nicht von Hand ändern.\n' \
  "$STAND" > "$DEST/VERSION"
echo "StatPlot ($STAND) nach $DEST übernommen."
