#!/usr/bin/env bash
# Veroeffentlicht den Release-Entwurf des aktuellen Tags.
#
# Laeuft erst, wenn alle Plattform-Builds ihre Pakete angehaengt haben - so
# wird nie ein halbfertiges Release oeffentlich sichtbar.
set -euo pipefail

TAG="${GITHUB_REF_NAME:?GITHUB_REF_NAME nicht gesetzt}"
REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY nicht gesetzt}"

echo "Assets am Release $TAG:"
gh release view "$TAG" --repo "$REPO" --json assets \
   --jq '.assets[] | "  \(.name)  \(.size) Bytes"'

gh release edit "$TAG" --repo "$REPO" --draft=false --latest
echo "Release $TAG veroeffentlicht."
