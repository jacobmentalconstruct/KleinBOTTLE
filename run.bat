@echo off
cd /d "%~dp0"
py -m src.app
if errorlevel 1 pause
