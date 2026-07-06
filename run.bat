@echo off
REM NIT_Code – Windows Starter
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist "python_runtime\python.exe" set "PYTHON_EXE=python_runtime\python.exe"
if not exist "%PYTHON_EXE%" if exist "python_runtime\Scripts\python.exe" set "PYTHON_EXE=python_runtime\Scripts\python.exe"
if not exist "%PYTHON_EXE%" if exist "python_runtime\python\python.exe" set "PYTHON_EXE=python_runtime\python\python.exe"

echo Verwende Python: %PYTHON_EXE%
"%PYTHON_EXE%" start.py %*
