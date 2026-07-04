param(
    [switch]$Force,
    [switch]$SkipRequirements,
    [string]$Python = "python"
)

$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot/../..").Path
$RuntimeDir = Join-Path $RootDir "python_runtime"
$ReqFile = Join-Path $RootDir "requirements.txt"

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python nicht gefunden: $Python"
}

if (-not (Test-Path $ReqFile)) {
    throw "requirements.txt nicht gefunden: $ReqFile"
}

if (Test-Path $RuntimeDir) {
    if ($Force) {
        Write-Host "Loesche bestehendes python_runtime/ ..."
        Remove-Item $RuntimeDir -Recurse -Force
    } else {
        throw "$RuntimeDir existiert bereits. Mit -Force ueberschreiben."
    }
}

Write-Host "Erzeuge Runtime mit: $Python"
& $Python -m venv $RuntimeDir
if ($LASTEXITCODE -ne 0) {
    throw "venv-Erzeugung fehlgeschlagen."
}

$RuntimePy = Join-Path $RuntimeDir "Scripts/python.exe"
if (-not (Test-Path $RuntimePy)) {
    throw "Runtime-Python wurde nicht korrekt erstellt: $RuntimePy"
}

Write-Host "Upgrade pip/setuptools/wheel in python_runtime ..."
& $RuntimePy -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "pip-Upgrade fehlgeschlagen."
}

if (-not $SkipRequirements) {
    Write-Host "Installiere Projektabhaengigkeiten aus requirements.txt ..."
    & $RuntimePy -m pip install -r $ReqFile
    if ($LASTEXITCODE -ne 0) {
        throw "Installation der requirements fehlgeschlagen."
    }
} else {
    Write-Host "Ueberspringe requirements-Installation (-SkipRequirements)."
}

& $RuntimePy -c "import platform,sys; print('Fertig. Runtime-Interpreter:', sys.executable); print('Python-Version:', sys.version.split()[0]); print('Architektur:', platform.machine())"
Write-Host "Runtime bereit unter: $RuntimeDir"
