@echo off
setlocal
set "RAIZ=%~dp0.."
python -m venv "%RAIZ%\.venv" || exit /b 1
"%RAIZ%\.venv\Scripts\python.exe" -m pip install -r "%RAIZ%\sender-windows\requirements.txt" %*
