#!/bin/bash
# Quick Test Runner for Basic Face Detection
# ============================================

echo ""
echo "=========================================="
echo "  Basic Face Detection Test"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "test_basic_face_detection.py" ]; then
    echo "ERROR: test_basic_face_detection.py not found!"
    echo "Please run this script from the project directory:"
    echo "  cd 'Security Entry & Exit Management System'"
    echo "  bash run_basic_test.sh"
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3 first."
    exit 1
fi

echo "Python version:"
python3 --version
echo ""

# Check if opencv-python is installed
echo "Checking dependencies..."
if python3 -c "import cv2" 2>/dev/null; then
    echo "✓ opencv-python is installed"
else
    echo "✗ opencv-python not found"
    echo ""
    echo "Installing opencv-python..."
    pip3 install opencv-python numpy
    echo ""
fi

if python3 -c "import numpy" 2>/dev/null; then
    echo "✓ numpy is installed"
else
    echo "✗ numpy not found"
    echo ""
    echo "Installing numpy..."
    pip3 install numpy
    echo ""
fi

echo ""
echo "=========================================="
echo "  Starting Face Detection..."
echo "=========================================="
echo ""
echo "Instructions:"
echo "  1. Show your face to the camera"
echo "  2. Each person gets a unique ID"
echo "  3. Press 'q' or Ctrl+C to exit"
echo ""
echo "Testing scenario:"
echo "  - Show 3 different faces"
echo "  - Should get exactly 3 unique IDs"
echo "  - (Not 10 or 20!)"
echo ""
echo "=========================================="
echo ""

# Run the test
python3 test_basic_face_detection.py

echo ""
echo "Test completed!"
echo ""
