@echo off
cd /d "%~dp0\.."

set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Expected: %PYTHON%
    pause
    exit /b 1
)

echo Starting settings server...
echo.
"%PYTHON%" automatic_videos\settings_server.py

if errorlevel 1 (
    echo.
    echo ERROR: Settings server failed to start.
    echo Check that all dependencies are installed.
    pause
    exit /b 1
)
pause
