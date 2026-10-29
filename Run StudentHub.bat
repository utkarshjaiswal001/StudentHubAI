@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo StudentHub's virtual environment was not found.
    echo Create it first or run the app with your installed Python.
    pause
    exit /b 1
)

echo Starting StudentHub AI...
start "StudentHub AI server" cmd /k ""%CD%\.venv\Scripts\python.exe" "%CD%\app.py""
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000/"
