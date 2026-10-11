@echo off
rem Inicia com console visivel para ver os logs em tempo real.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call run.bat
.venv\Scripts\python.exe main.py
pause
