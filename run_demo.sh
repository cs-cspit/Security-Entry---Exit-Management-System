#!/bin/bash

echo "============================================================"
echo "YOLO SECURITY SYSTEM - LAUNCHER"
echo "============================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo ""
    echo "Please create it first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated"
echo ""

# Check if OpenCV is installed
python3 -c "import cv2" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ OpenCV not installed in virtual environment"
    echo ""
    echo "Installing required packages..."
    pip install opencv-python numpy pyyaml
    pip install torch torchvision
    pip install ultralytics
    echo ""
fi

# Check for YOLO models
echo "🔍 Checking for YOLO models..."

if [ -f "yolov8n-face.pt" ]; then
    echo "✅ YOLOv8-face model found"
else
    echo "⚠️  YOLOv8-face model not found"
    echo "   Will use MediaPipe or Haar Cascade as fallback"
    echo ""
    echo "   To get better face detection accuracy:"
    echo "   1. Run: python download_yolo_face.py"
    echo "   2. Or: pip install mediapipe"
    echo ""
fi

if [ -f "yolo11n.pt" ]; then
    echo "✅ YOLOv11 model found"
else
    echo "ℹ️  YOLOv11 model will auto-download on first run"
fi

echo ""
echo "============================================================"
echo "STARTING DEMO"
echo "============================================================"
echo ""
echo "📹 Controls:"
echo "   'q' or ESC - Quit"
echo "   'e' - Register person at entry"
echo "   'r' - Reset system"
echo ""
echo "============================================================"
echo ""

# Run the demo
python3 demo_yolo_cameras.py

EXIT_CODE=$?

echo ""
echo "============================================================"
echo "DEMO ENDED"
echo "============================================================"
echo ""

# Deactivate virtual environment
deactivate

exit $EXIT_CODE
