$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot/../..").Path
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

Write-Host "Windows-Paket erstellt: $ZipPath"
