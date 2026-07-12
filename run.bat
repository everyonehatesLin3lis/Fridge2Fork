@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed or not in PATH. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [FridgeAgent] Creating virtual environment - first run only...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" run.py %*
if errorlevel 1 pause
endlocal
