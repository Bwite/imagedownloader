@echo off
REM Ultimate Download Machine Launcher
REM Batch Script for Windows

echo ========================================
echo   Ultimate Download Machine Launcher
echo ========================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found
echo.

echo Checking environment configuration...
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Creating .env template...
    echo BRAVE_API_KEY=your_api_key_here > .env
    echo [OK] Created .env file
    echo Please edit .env and add your Brave API key, then run this script again.
    pause
    exit /b 1
)
echo [OK] .env file found
echo.

echo Checking dependencies...
if exist "requirements.txt" (
    echo Installing/updating requirements...
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
) else (
    echo [WARNING] requirements.txt not found, skipping...
)
echo.

echo ========================================
echo   Starting Server...
echo ========================================
echo.
echo Server will start at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

REM Wait a moment then open browser
timeout /t 2 /nobreak >nul
start http://localhost:5000

REM Run the server
python server.py
