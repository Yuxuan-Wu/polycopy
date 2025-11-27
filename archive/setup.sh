#!/bin/bash
# Setup script for Polymarket Copy Trading System

echo "=========================================="
echo "Polymarket Copy Trading System - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Create directories
echo ""
echo "Creating directories..."
mkdir -p data logs

# Make main.py executable
chmod +x main.py

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit config.yaml and add your monitored addresses"
echo "2. Run: python3 main.py"
echo ""
