#!/bin/bash

echo "============================================================"
echo "YOLO26-BASED SECURITY SYSTEM INSTALLATION"
echo "============================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.8 or later."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if we're in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  WARNING: Not in a virtual environment!"
    echo ""
    echo "It's recommended to use a virtual environment."
    echo "To create and activate one:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate  # On macOS/Linux"
    echo "  venv\\Scripts\\activate     # On Windows"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "============================================================"
echo "INSTALLING DEPENDENCIES"
echo "============================================================"
echo ""

# Core dependencies
echo "📦 Installing core dependencies..."
pip install --upgrade pip
pip install opencv-python numpy pyyaml

# YOLO dependencies
echo ""
echo "📦 Installing YOLO dependencies (PyTorch + Ultralytics)..."
echo "⏳ This may take a few minutes..."
echo ""

# Check if Mac with Apple Silicon (M1/M2/M3)
if [[ "$OSTYPE" == "darwin"* ]] && [[ $(uname -m) == "arm64" ]]; then
    echo "🍎 Detected Apple Silicon Mac - installing optimized PyTorch..."
    pip install torch torchvision
else
    echo "💻 Installing PyTorch (CPU version)..."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
fi

echo ""
echo "📦 Installing Ultralytics YOLO..."
pip install ultralytics

# Optional dependencies
echo ""
echo "📦 Installing optional dependencies..."
pip install Pillow scipy matplotlib

echo ""
echo "============================================================"
echo "DOWNLOADING YOLO MODELS"
echo "============================================================"
echo ""

# Create a test script to download models
cat > /tmp/download_models.py << 'EOF'
#!/usr/bin/env python3
"""Download YOLO26 model (unified detection + pose)."""
import sys
try:
    from ultralytics import YOLO

    print("📥 Downloading YOLO26n-pose model (unified body + face + pose)...")
    print("   This is the single model used for ALL detection tasks:")
    print("   - Person / body detection")
    print("   - Face localisation (via pose keypoints)")
    print("   - Pose estimation (17 COCO keypoints)")
    print("   - Hair / clothing / body re-ID features")
    model = YOLO("yolo26n-pose.pt")
    print("✅ YOLO26n-pose model ready!")

    print("\n✅ All models ready!")

except Exception as e:
    print(f"\n⚠️  Could not pre-download models: {e}")
    print("   Models will auto-download on first run.")
    sys.exit(0)
EOF

python3 /tmp/download_models.py
rm /tmp/download_models.py

echo ""
echo "============================================================"
echo "VERIFYING INSTALLATION"
echo "============================================================"
echo ""

# Verify imports
python3 << 'EOF'
import sys

def check_import(module_name, display_name=None):
    if display_name is None:
        display_name = module_name
    try:
        __import__(module_name)
        print(f"✅ {display_name}")
        return True
    except ImportError:
        print(f"❌ {display_name} - FAILED")
        return False

print("Checking dependencies:")
all_ok = True
all_ok &= check_import("cv2", "OpenCV")
all_ok &= check_import("numpy", "NumPy")
all_ok &= check_import("torch", "PyTorch")
all_ok &= check_import("torchvision", "TorchVision")
all_ok &= check_import("ultralytics", "Ultralytics YOLO")
all_ok &= check_import("yaml", "PyYAML")

if all_ok:
    print("\n✅ All dependencies installed successfully!")
    sys.exit(0)
else:
    print("\n❌ Some dependencies failed to install")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Installation verification failed!"
    echo "Please check the error messages above."
    exit 1
fi

echo ""
echo "============================================================"
echo "INSTALLATION COMPLETE!"
echo "============================================================"
echo ""
echo "🎉 You're ready to use the YOLO26-based system!"
echo ""
echo "To run the system:"
echo "  python yolo26_complete_system.py"
echo ""
echo "📚 For more information, see:"
echo "  - README.md"
echo "  - FRONTEND_INTEGRATION.md"
echo "  - requirements_yolo.txt"
echo ""
echo "============================================================"
echo ""
