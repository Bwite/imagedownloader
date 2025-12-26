#!/bin/bash
# Ultimate Download Machine Launcher
# Bash Script for Linux/Mac/Git Bash/WSL

echo "========================================"
echo "  Ultimate Download Machine Launcher"
echo "========================================"
echo ""

# Check if Python is installed
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "✗ Python is not installed"
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
    PIP_CMD=pip3
else
    PYTHON_CMD=python
    PIP_CMD=pip
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo "✓ Found: $PYTHON_VERSION"
echo ""

# Check if .env file exists
echo "Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo "✗ .env file not found!"
    echo "Creating .env template..."
    echo "BRAVE_API_KEY=your_api_key_here" > .env
    echo "✓ Created .env file"
    echo "Please edit .env and add your Brave API key, then run this script again."
    exit 1
fi
echo "✓ .env file found"
echo ""

# Check/Install requirements
echo "Checking dependencies..."
if [ -f "requirements.txt" ]; then
    echo "Installing/updating requirements..."
    $PIP_CMD install -r requirements.txt --quiet
    if [ $? -eq 0 ]; then
        echo "✓ Dependencies installed"
    else
        echo "✗ Failed to install dependencies"
        exit 1
    fi
else
    echo "⚠ requirements.txt not found, skipping..."
fi
echo ""

# Start the server
echo "========================================"
echo "  Starting Server..."
echo "========================================"
echo ""
echo "Server will start at: http://localhost:5000"
echo "Press Ctrl+C to stop the server"
echo ""

# Wait a moment then open browser
sleep 2

# Open browser (different commands for different OS)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:5000 2>/dev/null &
elif [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5000 2>/dev/null &
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    start http://localhost:5000 2>/dev/null &
fi

# Run the server
$PYTHON_CMD server.py
