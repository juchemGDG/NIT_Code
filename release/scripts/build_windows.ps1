$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot/../..").Path
$ReleaseDir = Join-Path $RootDir "release"
$OutDir = Join-Path $RootDir "release/downloads/windows"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

python -m pip install --upgrade pip
python -m pip install -r "$RootDir/requirements.txt" -r "$RootDir/release/requirements-build.txt"

pyinstaller "$RootDir/release/pyinstaller.spec" --noconfirm --clean

$DistDir = Join-Path $RootDir "dist/NIT_Code"
$ZipPath = Join-Path $OutDir "NIT_Code-windows.zip"

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

Compress-Archive -Path "$DistDir/*" -DestinationPath $ZipPath

Write-Host "Windows-ZIP erstellt: $ZipPath"

# ──────────────────────────────────────────────────────────────────────────────
# Installer (Setup.exe) via Inno Setup
# Versionsnummer aus nit_code/config.py (einzige Quelle der Wahrheit) lesen und
# an das .iss-Skript durchreichen.
# ──────────────────────────────────────────────────────────────────────────────
$Version = (python -c "import sys; sys.path.insert(0, r'$RootDir'); from nit_code.config import APP_VERSION; print(APP_VERSION)").Trim()
Write-Host "App-Version: $Version"

# ISCC.exe finden: erst PATH, dann Standard-Installationspfade.
$Iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )) {
        if ($candidate -and (Test-Path $candidate)) { $Iscc = $candidate; break }
    }
}

if (-not $Iscc) {
    Write-Warning "Inno Setup (ISCC.exe) nicht gefunden - Setup.exe wird uebersprungen. Nur das ZIP wurde erstellt."
} else {
    & $Iscc "/DAppVersion=$Version" (Join-Path $ReleaseDir "installer.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup Compiler ist mit Fehlercode $LASTEXITCODE fehlgeschlagen."
    }
    Write-Host "Windows-Installer erstellt: $(Join-Path $OutDir 'NIT_Code-Setup.exe')"
}
