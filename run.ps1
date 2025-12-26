# Ultimate Download Machine Launcher
# PowerShell Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ultimate Download Machine Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Red
    pause
    exit 1
}

# Check if .env file exists
Write-Host ""
Write-Host "Checking environment configuration..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Write-Host "✗ .env file not found!" -ForegroundColor Red
    Write-Host "Creating .env template..." -ForegroundColor Yellow
    "BRAVE_API_KEY=your_api_key_here" | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✓ Created .env file" -ForegroundColor Green
    Write-Host "Please edit .env and add your Brave API key, then run this script again." -ForegroundColor Yellow
    pause
    exit 1
} else {
    Write-Host "✓ .env file found" -ForegroundColor Green
}

# Check/Install requirements
Write-Host ""
Write-Host "Checking dependencies..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Write-Host "Installing/updating requirements..." -ForegroundColor Yellow
    pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
        pause
        exit 1
    }
} else {
    Write-Host "⚠ requirements.txt not found, skipping..." -ForegroundColor Yellow
}

# Start the server
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting Server..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server will start at: http://localhost:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Wait a moment then open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:5000"

# Run the server
python server.py
