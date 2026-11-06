@echo off
cd /d "%~dp0"

echo [KleinBOTTLE] Creating virtual environment...
py -m venv .venv
if errorlevel 1 (
    echo ERROR: Could not create venv. Is Python installed?
    pause
    exit /b 1
)

echo [KleinBOTTLE] Installing dependencies...
.venv\Scripts\pip install --upgrade pip -q
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency install failed.
    pause
    exit /b 1
)

echo.
echo Setup complete.  Run run.bat to start KleinBOTTLE.
pause
