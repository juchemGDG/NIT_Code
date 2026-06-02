$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot/../..").Path
$OutDir = Join-Path $RootDir "release/downloads/windows"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

python -m pip install --upgrade pip
python -m pip install -r "$RootDir/requirements.txt" -r "$RootDir/release/requirements-build.txt"

pyinstaller "$RootDir/release/pyinstaller.spec" --noconfirm --clean

$DistDir = Join-Path $RootDir "dist/NIT_Code"
$ExePath = Join-Path $DistDir "NIT_Code.exe"
$ZipPath = Join-Path $OutDir "NIT_Code-windows.zip"

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

Compress-Archive -Path "$DistDir/*" -DestinationPath $ZipPath
Copy-Item $ExePath (Join-Path $OutDir "NIT_Code.exe") -Force

Write-Host "Windows-Pakete erstellt: $ZipPath und NIT_Code.exe"
