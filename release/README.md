# Release-Builds (macOS / Windows / Linux)

Dieser Ordner enthaelt alles, um automatisch downloadbare Pakete zu bauen.

## Zielartefakte

- macOS: `NIT_Code-macos.dmg`
- Windows: `NIT_Code-windows.zip` und `NIT_Code.exe`
- Linux: `NIT_Code-linux-x86_64.tar.gz`

## Lokal bauen

Voraussetzungen: Python 3.11+ und Plattform-spezifische Build-Umgebung.

- Linux:
  - `bash release/scripts/build_linux.sh`
- macOS:
  - `bash release/scripts/build_macos.sh`
- Windows (PowerShell):
  - `pwsh -File release/scripts/build_windows.ps1`

Die fertigen Dateien landen in `release/downloads/<plattform>/`.

## GitHub Actions

Die Workflow-Datei liegt in `.github/workflows/release-build.yml` und baut die Artefakte automatisch fuer alle drei Plattformen:

- manuell per `workflow_dispatch`
- automatisch bei Tags wie `v1.2.3`

Bei Tag-Builds werden die Dateien zusaetzlich als GitHub-Release-Assets hochgeladen.
