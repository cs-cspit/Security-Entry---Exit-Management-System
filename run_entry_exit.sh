#!/bin/bash
# Entry/Exit Tracking System Runner
# ==================================

echo ""
echo "=========================================="
echo "  Entry/Exit Tracking System"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "entry_exit_system.py" ]; then
    echo "ERROR: entry_exit_system.py not found!"
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    exit 1
fi

echo "✓ Python version:"
python3 --version
echo ""

# Check dependencies
echo "Checking dependencies..."
if python3 -c "import cv2" 2>/dev/null; then
    echo "✓ opencv-python is installed"
else
    echo "✗ Installing opencv-python..."
    pip3 install opencv-python numpy
fi

if python3 -c "import numpy" 2>/dev/null; then
    echo "✓ numpy is installed"
else
    echo "✗ Installing numpy..."
    pip3 install numpy
fi

echo ""
echo "=========================================="
echo "  Setup Checklist:"
echo "=========================================="
echo ""
echo "Before running, ensure:"
echo "  1. ✓ Mac webcam is working"
echo "  2. ✓ Iriun app running on phone"
echo "  3. ✓ Iriun app running on Mac"
echo "  4. ✓ Phone and Mac on same WiFi"
echo "  5. ✓ Camera permissions granted"
echo ""
echo "System will use:"
echo "  → Camera 1 = ENTRY (Phone via Iriun)"
echo "  → Camera 0 = EXIT (Mac webcam)"
echo ""
read -p "Press Enter to start scanning for cameras..."
echo ""

# Run the system
python3 entry_exit_system.py

echo ""
echo "Session ended!"
echo ""
