@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m kleinos
) else (
    py -m kleinos
)
if errorlevel 1 pause
