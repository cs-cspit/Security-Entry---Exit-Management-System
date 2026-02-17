#!/bin/bash

# Three-Camera Security System Runner Script
# ===========================================
# Activates virtual environment and runs the system

echo ""
echo "============================================================"
echo "THREE-CAMERA SECURITY MONITORING SYSTEM"
echo "============================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "demo_three_cameras.py" ]; then
    echo "❌ Error: demo_three_cameras.py not found!"
    echo "   Please run this script from the project root directory."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv

    echo "Installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    echo ""
    echo "✅ Virtual environment created and dependencies installed!"
    echo ""
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Check if opencv is installed
python -c "import cv2" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  OpenCV not found. Installing dependencies..."
    pip install -r requirements.txt
fi

echo "✅ Environment ready!"
echo ""
echo "🎥 Starting three-camera system..."
echo ""
echo "Controls:"
echo "  - Press 'e' to register person at ENTRY camera"
echo "  - Press 'x' to test detection at EXIT camera"
echo "  - Press 'q' to quit and save session data"
echo ""
echo "============================================================"
echo ""

# Run the system
python demo_three_cameras.py

# Exit status
exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ System exited normally"
else
    echo "⚠️  System exited with code: $exit_code"
fi
echo ""

exit $exit_code
