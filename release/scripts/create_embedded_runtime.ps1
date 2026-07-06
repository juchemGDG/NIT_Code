param(
    [switch]$Force,
    [switch]$SkipRequirements,
    [string]$Requirements = ""
)

# Erzeugt eine mitlieferbare Python-Runtime im Projektordner: python_runtime/
#
# WICHTIG: Frueher wurde hier ein venv erzeugt (python -m venv). Ein venv ist
# NICHT relocatable: pyvenv.cfg verweist auf das Basis-Python des Build-
# Rechners; auf Nutzer-Rechnern ohne dieses Python startet der Interpreter
# nicht (bzw. auf macOS/Linux ist er nur ein toter Symlink). Darum wird jetzt
# python-build-standalone verwendet: ein vollstaendig eigenstaendiges,
# verschiebbares CPython (inkl. tkinter und pip) von
# https://github.com/astral-sh/python-build-standalone
#
# Ergebnis-Layout (von nit_code/config.py und start.py erwartet):
#   python_runtime/python/python.exe

$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot/../..").Path
$RuntimeDir = Join-Path $RootDir "python_runtime"
if ($Requirements) {
    $ReqFile = $Requirements
} else {
    $ReqFile = Join-Path $RootDir "release/requirements-runtime.txt"
}

# Gepinnte Version von python-build-standalone (per Umgebungsvariable uebersteuerbar).
$PbsRelease = if ($env:PBS_RELEASE) { $env:PBS_RELEASE } else { "20260623" }
$PbsPythonVersion = if ($env:PBS_PYTHON_VERSION) { $env:PBS_PYTHON_VERSION } else { "3.12.13" }

switch ($env:PROCESSOR_ARCHITECTURE) {
    "AMD64" { $ArchTag = "x86_64" }
    "ARM64" { $ArchTag = "aarch64" }
    default { throw "Nicht unterstuetzte Architektur: $($env:PROCESSOR_ARCHITECTURE)" }
}

$Asset = "cpython-$PbsPythonVersion+$PbsRelease-$ArchTag-pc-windows-msvc-install_only.tar.gz"
$Url = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsRelease/$Asset"

if (-not $SkipRequirements -and -not (Test-Path $ReqFile)) {
    throw "requirements-Datei nicht gefunden: $ReqFile"
}

if (Test-Path $RuntimeDir) {
    if ($Force) {
        Write-Host "Loesche bestehendes python_runtime/ ..."
        Remove-Item $RuntimeDir -Recurse -Force
    } else {
        throw "$RuntimeDir existiert bereits. Mit -Force ueberschreiben."
    }
}

$Tarball = Join-Path ([System.IO.Path]::GetTempPath()) $Asset
try {
    Write-Host "Lade $Asset ..."
    Invoke-WebRequest -Uri $Url -OutFile $Tarball

    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    Write-Host "Entpacke nach $RuntimeDir ..."
    tar -xzf $Tarball -C $RuntimeDir    # entpackt als python_runtime/python/
    if ($LASTEXITCODE -ne 0) {
        throw "Entpacken fehlgeschlagen."
    }
} finally {
    if (Test-Path $Tarball) {
        Remove-Item $Tarball -Force
    }
}

$RuntimePy = Join-Path $RuntimeDir "python/python.exe"
if (-not (Test-Path $RuntimePy)) {
    throw "Runtime-Python wurde nicht korrekt erstellt: $RuntimePy"
}

# Ohne dies "sieht" pip Pakete aus dem User-Site-Verzeichnis des Build-
# Rechners und installiert sie dann NICHT in die Runtime.
$env:PYTHONNOUSERSITE = "1"

# pip sicherstellen (install_only-Builds bringen pip i. d. R. schon mit)
& $RuntimePy -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    & $RuntimePy -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "ensurepip fehlgeschlagen."
    }
}
Write-Host "Upgrade pip in python_runtime ..."
& $RuntimePy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip-Upgrade fehlgeschlagen."
}

if (-not $SkipRequirements) {
    Write-Host "Installiere Runtime-Pakete aus $ReqFile ..."
    & $RuntimePy -m pip install -r $ReqFile
    if ($LASTEXITCODE -ne 0) {
        throw "Installation der Runtime-Pakete fehlgeschlagen."
    }
} else {
    Write-Host "Ueberspringe Paket-Installation (-SkipRequirements)."
}

& $RuntimePy -c "import platform, sys, tkinter; print('Fertig. Runtime-Interpreter:', sys.executable); print('Python-Version:', sys.version.split()[0]); print('Architektur:', platform.machine()); print('tkinter: verfuegbar (Tk', tkinter.TkVersion, ')')"
Write-Host "Runtime bereit unter: $RuntimeDir"
