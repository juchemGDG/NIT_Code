#!/usr/bin/env bash
# Haengt die gebauten Pakete eines Ordners an das Release des aktuellen Tags.
#
# Ersetzt den frueheren Umweg ueber Actions-Artefakte (upload-artifact +
# download-artifact): deren Speicherkontingent lief voll und liess den ganzen
# Release-Build scheitern. Das Release wird als ENTWURF angelegt; erst
# publish_release.sh veroeffentlicht es, wenn alle Plattformen fertig sind.
set -euo pipefail

DIR="${1:?Ordner mit den Paketen fehlt}"
TAG="${GITHUB_REF_NAME:?GITHUB_REF_NAME nicht gesetzt}"
REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY nicht gesetzt}"

shopt -s nullglob
files=("$DIR"/*)
shopt -u nullglob
if [ ${#files[@]} -eq 0 ]; then
  echo "Keine Dateien in $DIR gefunden." >&2
  exit 1
fi

# Die Plattform-Jobs laufen parallel: Der erste legt den Entwurf an, die
# anderen scheitern hier folgenlos und laden anschliessend nur noch hoch.
if ! gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  gh release create "$TAG" --repo "$REPO" --draft \
     --title "$TAG" --generate-notes || true
fi

# Kurz warten, falls ein paralleler Job den Entwurf gerade erst anlegt.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

echo "Lade ${#files[@]} Datei(en) aus $DIR an Release $TAG:"
printf '  %s\n' "${files[@]}"
gh release upload "$TAG" "${files[@]}" --repo "$REPO" --clobber
