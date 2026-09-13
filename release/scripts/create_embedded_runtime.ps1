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

# "_stripped"-Variante: gleiche Runtime, aber ohne Debug-Symbole - spart
# spuerbar Groesse ohne Funktionsverlust fuer Schueler-Programme.
$Asset = "cpython-$PbsPythonVersion+$PbsRelease-$ArchTag-pc-windows-msvc-install_only_stripped.tar.gz"
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

# Nicht benoetigte Anteile entfernen (Build-only-Tools/redundante Doku).
# tcl/tk bleibt erhalten: tkinter/turtle wird von Schueler-Programmen
# unterstuetzt (siehe nit_code/micropython_dialogs.py). include/libs fliegen
# raus, weil auf den Zielrechnern ohnehin kein C-Compiler vorhanden ist -
# pyserial/requests sind reine Python-Pakete, die nie kompiliert werden.
Write-Host "Entferne nicht benoetigte Runtime-Anteile ..."
$StdlibDir = & $RuntimePy -c "import sysconfig; print(sysconfig.get_path('stdlib'))"
foreach ($p in @(
    (Join-Path $RuntimeDir "python/include"),
    (Join-Path $RuntimeDir "python/libs"),
    (Join-Path $StdlibDir "idlelib"),
    (Join-Path $StdlibDir "ensurepip"),
    (Join-Path $StdlibDir "lib2to3")
)) {
    if (Test-Path $p) {
        Remove-Item $p -Recurse -Force
    }
}

# .pyc hash-basiert (PEP 552) neu erzeugen: mtime-basierte .pyc gelten nach
# Kopieren/Entpacken als veraltet und wuerden beim ersten Start neu
# geschrieben (auf macOS braeche das die App-Signatur; hier Konsistenz).
Write-Host "Kompiliere Bytecode (hash-basiert) ..."
& $RuntimePy -m compileall -f -q --invalidation-mode unchecked-hash -x "(bad_coding|badsyntax|lib2to3)" (Join-Path $RuntimeDir "python/Lib")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Bytecode-Kompilierung teilweise fehlgeschlagen (fahre fort)."
}

& $RuntimePy -c "import platform, sys, tkinter; print('Fertig. Runtime-Interpreter:', sys.executable); print('Python-Version:', sys.version.split()[0]); print('Architektur:', platform.machine()); print('tkinter: verfuegbar (Tk', tkinter.TkVersion, ')')"
Write-Host "Runtime bereit unter: $RuntimeDir"
