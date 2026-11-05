@echo off
cd /d "%~dp0"
py -m kleinos
if errorlevel 1 pause
