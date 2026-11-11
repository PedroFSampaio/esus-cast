@echo off
setlocal
set "RAIZ=%~dp0.."
if not exist "%RAIZ%\.venv\Scripts\python.exe" (
    echo Execute scripts\preparar-windows.cmd primeiro.
    exit /b 1
)
"%RAIZ%\.venv\Scripts\python.exe" "%RAIZ%\sender-windows\sender.py" %*
