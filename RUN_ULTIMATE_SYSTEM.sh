#!/bin/bash

# YOLO26 Complete Security System Launcher
# ========================================

clear
echo "=========================================================================="
echo "  🚀 YOLO26 COMPLETE SECURITY SYSTEM LAUNCHER"
echo "=========================================================================="
echo ""
echo "This script will:"
echo "  ✅ Check Python environment"
echo "  ✅ Verify all dependencies"
echo "  ✅ Download required YOLO26 models"
echo "  ✅ Detect available cameras"
echo "  ✅ Launch the complete three-camera system"
echo ""
echo "Features:"
echo "  🎯 Entry gate with auto-registration"
echo "  🎯 Room monitoring with velocity tracking"
echo "  🎯 Exit gate with session tracking"
echo "  🎯 Real-time re-identification using OSNet + body features"
echo "  🎯 Unauthorized entry detection"
echo "  🎯 Complete database logging"
echo ""
echo "=========================================================================="
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check Python
echo "🔍 Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "✅ Found: $PYTHON_VERSION"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_VERSION=$(python --version 2>&1)
    echo "✅ Found: $PYTHON_VERSION"
else
    echo "❌ Python not found!"
    echo "   Please install Python 3.8 or higher"
    exit 1
fi
echo ""

# Check virtual environment
echo "🔍 Checking virtual environment..."
if [ -d "venv" ]; then
    echo "✅ Virtual environment found"
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  No virtual environment found"
    echo "   Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    echo "✅ Virtual environment created and activated"
fi
echo ""

# Install/check dependencies
echo "🔍 Checking dependencies..."
pip install --quiet --upgrade pip > /dev/null 2>&1

REQUIRED_PACKAGES=(
    "ultralytics>=8.3.0"
    "opencv-python>=4.8.0"
    "numpy>=1.24.0"
    "torch>=2.0.0"
    "torchvision>=0.15.0"
    "pillow>=10.0.0"
    "pyyaml>=6.0"
)

echo "📦 Installing/verifying required packages..."
for package in "${REQUIRED_PACKAGES[@]}"; do
    echo "   • $package"
done

pip install --quiet "${REQUIRED_PACKAGES[@]}" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ All dependencies installed"
else
    echo "⚠️  Some dependencies may have issues"
    echo "   Continuing anyway..."
fi
echo ""

# Check for YOLO26 model
echo "🔍 Checking YOLO26-pose model..."
if [ -f "yolo26n-pose.pt" ]; then
    echo "✅ YOLO26-pose model found"
else
    echo "⚠️  YOLO26-pose model not found"
    echo "   The model will auto-download on first run"
    echo "   This may take a few minutes..."
fi
echo ""

# Check for OSNet dependencies
echo "🔍 Checking OSNet dependencies..."
if $PYTHON_CMD -c "import torchreid" &> /dev/null; then
    echo "✅ torchreid installed"
else
    echo "📦 Installing torchreid for OSNet..."
    pip install --quiet torchreid > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ torchreid installed successfully"
    else
        echo "⚠️  torchreid installation had issues"
        echo "   System will use fallback features"
    fi
fi
echo ""

# Detect cameras
echo "🎥 Detecting available cameras..."
CAMERA_COUNT=$($PYTHON_CMD -c "
import cv2
count = 0
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, _ = cap.read()
        if ret:
            count += 1
        cap.release()
print(count)
" 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ Found $CAMERA_COUNT camera(s)"

    if [ "$CAMERA_COUNT" -lt 3 ]; then
        echo ""
        echo "⚠️  WARNING: Less than 3 cameras detected!"
        echo "   The system requires 3 cameras for full operation:"
        echo "     1. Entry gate"
        echo "     2. Room monitoring"
        echo "     3. Exit gate"
        echo ""
        echo "   Available cameras will be reused for missing views."
        echo ""
        read -p "   Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled by user"
            exit 1
        fi
    fi
else
    echo "⚠️  Could not detect cameras (will try anyway)"
fi
echo ""

# Create data directory if needed
if [ ! -d "data" ]; then
    echo "📁 Creating data directory..."
    mkdir -p data
    echo "✅ Data directory created"
    echo ""
fi

# Final check
echo "=========================================================================="
echo "  🎬 READY TO LAUNCH!"
echo "=========================================================================="
echo ""
echo "System Controls:"
echo "  E - Force register person at entry gate"
echo "  D - Toggle debug output (show detailed matching scores)"
echo "  C - Clear all registrations and restart"
echo "  S - Show statistics (people inside, exited, velocities)"
echo "  Q - Quit and export session data"
echo ""
echo "Expected Behavior:"
echo "  1. Entry Gate: People are AUTO-REGISTERED when detected"
echo "  2. Room: Authorized people shown in GREEN with velocity tracking"
echo "  3. Room: Unauthorized people shown in RED with alerts"
echo "  4. Exit Gate: People matched and session closed with statistics"
echo ""
echo "Velocity Indicators:"
echo "  GREEN:  < 1.0 m/s (walking slowly)"
echo "  ORANGE: 1.0-2.0 m/s (fast walking)"
echo "  RED:    > 2.0 m/s (running - triggers alert)"
echo ""
echo "=========================================================================="
echo ""
read -p "Press ENTER to launch the system..."
echo ""

# Launch the system
echo "🚀 Launching YOLO26 Complete Security System..."
echo ""

$PYTHON_CMD yolo26_complete_system.py

# Check exit status
EXIT_CODE=$?
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ System exited normally"
elif [ $EXIT_CODE -eq 130 ]; then
    echo "⚠️  System interrupted by user (Ctrl+C)"
else
    echo "❌ System exited with error code: $EXIT_CODE"
fi

echo ""
echo "=========================================================================="
echo "  Session Complete"
echo "=========================================================================="
echo ""
echo "Data saved to:"
echo "  • Database: data/yolo26_complete_system.db"
echo "  • Alerts:   data/yolo26_system_alerts.log"
echo ""
echo "Thank you for using YOLO26 Security System!"
echo ""
