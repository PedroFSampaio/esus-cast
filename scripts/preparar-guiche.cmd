@echo off
setlocal
set "RAIZ=%~dp0.."
if not exist "%RAIZ%\.venv\Scripts\python.exe" (
    python -m venv "%RAIZ%\.venv" || exit /b 1
)
"%RAIZ%\.venv\Scripts\python.exe" -m pip install -r "%RAIZ%\sender-windows\requirements-guiche.txt" %*
