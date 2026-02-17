#!/bin/bash

echo "============================================================"
echo "YOLO SECURITY SYSTEM - QUICK START"
echo "============================================================"
echo ""

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed!"
    echo "Please install Python 3.8 or later."
    exit 1
fi

print_success "Python 3 found: $(python3 --version)"
echo ""

# Check/create virtual environment
if [ ! -d "venv" ]; then
    print_warning "Virtual environment not found. Creating one..."
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

print_success "Virtual environment activated"
echo ""

# Check if dependencies are installed
echo "============================================================"
echo "CHECKING DEPENDENCIES"
echo "============================================================"
echo ""

DEPS_INSTALLED=true

python3 << 'EOF'
import sys
try:
    import cv2
    print("✅ OpenCV installed")
except ImportError:
    print("❌ OpenCV not installed")
    sys.exit(1)

try:
    import torch
    print("✅ PyTorch installed")
except ImportError:
    print("❌ PyTorch not installed")
    sys.exit(1)

try:
    import ultralytics
    print("✅ Ultralytics YOLO installed")
except ImportError:
    print("❌ Ultralytics YOLO not installed")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    DEPS_INSTALLED=false
fi

echo ""

# Install dependencies if needed
if [ "$DEPS_INSTALLED" = false ]; then
    echo "============================================================"
    echo "INSTALLING DEPENDENCIES"
    echo "============================================================"
    echo ""

    print_warning "Some dependencies are missing. Installing..."
    echo ""

    # Run installation script
    if [ -f "install_yolo.sh" ]; then
        bash install_yolo.sh
    else
        echo "📦 Installing core dependencies..."
        pip install --upgrade pip
        pip install opencv-python numpy pyyaml

        echo ""
        echo "📦 Installing PyTorch..."
        if [[ "$OSTYPE" == "darwin"* ]] && [[ $(uname -m) == "arm64" ]]; then
            print_success "Detected Apple Silicon Mac"
            pip install torch torchvision
        else
            pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
        fi

        echo ""
        echo "📦 Installing Ultralytics YOLO..."
        pip install ultralytics

        echo ""
        echo "📦 Installing optional dependencies..."
        pip install Pillow scipy matplotlib
    fi

    print_success "Dependencies installed"
    echo ""
fi

# Check for YOLO models
echo "============================================================"
echo "CHECKING YOLO MODELS"
echo "============================================================"
echo ""

MODELS_OK=true

# Check YOLOv8-face
if [ -f "yolov8n-face.pt" ]; then
    FILE_SIZE=$(du -h "yolov8n-face.pt" | cut -f1)
    print_success "YOLOv8n-face model found ($FILE_SIZE)"
else
    print_warning "YOLOv8n-face model not found"
    MODELS_OK=false
fi

# Check YOLOv11
if [ -f "yolo11n.pt" ]; then
    FILE_SIZE=$(du -h "yolo11n.pt" | cut -f1)
    print_success "YOLOv11n model found ($FILE_SIZE)"
else
    print_warning "YOLOv11n model will auto-download on first run"
fi

echo ""

# Download YOLOv8-face if needed
if [ "$MODELS_OK" = false ]; then
    echo "============================================================"
    echo "DOWNLOADING YOLO MODELS"
    echo "============================================================"
    echo ""

    if [ -f "download_yolo_face.py" ]; then
        python3 download_yolo_face.py

        if [ $? -eq 0 ]; then
            print_success "Models downloaded successfully"
        else
            print_error "Model download failed"
            echo ""
            echo "MANUAL STEPS:"
            echo "1. Visit: https://github.com/derronqi/yolov8-face"
            echo "2. Download 'yolov8n-face.pt' from Releases"
            echo "3. Place it in this directory"
            echo ""
            read -p "Press Enter when you've downloaded the model, or Ctrl+C to exit..."
        fi
    else
        print_error "Download script not found"
        echo ""
        echo "MANUAL DOWNLOAD REQUIRED:"
        echo "1. Visit: https://github.com/derronqi/yolov8-face"
        echo "2. Download 'yolov8n-face.pt' from Releases"
        echo "3. Place it in this directory"
        echo ""
        echo "OR"
        echo ""
        echo "1. Visit: https://huggingface.co/Bingsu/yolov8n-face"
        echo "2. Download 'yolov8n-face.pt'"
        echo "3. Place it in this directory"
        echo ""
        read -p "Press Enter when you've downloaded the model, or Ctrl+C to exit..."
    fi

    echo ""
fi

# Final check
if [ ! -f "yolov8n-face.pt" ]; then
    print_error "YOLOv8n-face model still not found!"
    echo ""
    echo "The system cannot run without this model."
    echo "Please download it manually and run this script again."
    exit 1
fi

# Check for demo script
echo "============================================================"
echo "READY TO RUN"
echo "============================================================"
echo ""

if [ ! -f "demo_yolo_cameras.py" ]; then
    print_error "Demo script not found: demo_yolo_cameras.py"
    exit 1
fi

print_success "All dependencies installed"
print_success "All models ready"
print_success "Demo script found"
echo ""

echo "============================================================"
echo "STARTING YOLO SECURITY SYSTEM"
echo "============================================================"
echo ""

echo "🎥 Initializing cameras..."
echo "📹 This will open windows for Entry, Room, and Exit cameras"
echo ""
echo "CONTROLS:"
echo "  'q' or ESC - Quit"
echo "  'r' - Reset system"
echo "  Click on Entry camera - Register person"
echo ""
echo "============================================================"
echo ""

# Run the demo
python3 demo_yolo_cameras.py

echo ""
echo "============================================================"
echo "SESSION ENDED"
echo "============================================================"
echo ""

# Deactivate virtual environment
deactivate

print_success "Thank you for using the YOLO Security System!"
echo ""
