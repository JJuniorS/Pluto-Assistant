@echo off
rem Inicia o Pluto Assistant sem janela de console (fica só na bandeja).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Criando ambiente virtual e instalando dependencias...
    python -m venv .venv || goto :fail
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
)
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:fail
echo.
echo Falha na instalacao. Verifique se o Python 3.11+ esta instalado e no PATH.
pause
exit /b 1
