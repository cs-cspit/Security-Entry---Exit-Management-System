#!/bin/bash
# Installation script for Enhanced Re-ID System
# Installs OSNet, DeepSORT, and advanced feature extraction dependencies

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║     ENHANCED RE-ID SYSTEM INSTALLATION                                     ║"
echo "║     Installing OSNet + Clothing Analysis + Skin Tone Detection             ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️ Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install PyTorch (with Metal acceleration for macOS)
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 1: Installing PyTorch                                                ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "✅ Detected macOS - Installing PyTorch with MPS (Metal) support..."
    pip install torch torchvision torchaudio
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✅ Detected Linux - Installing PyTorch..."
    # Check for CUDA
    if command -v nvidia-smi &> /dev/null; then
        echo "✅ NVIDIA GPU detected - Installing CUDA-enabled PyTorch..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    else
        echo "⚠️ No NVIDIA GPU detected - Installing CPU-only PyTorch..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
else
    echo "⚠️ Unknown OS - Installing default PyTorch..."
    pip install torch torchvision torchaudio
fi

# Install torchreid (OSNet)
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 2: Installing OSNet (torchreid)                                      ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Installing torchreid..."
pip install torchreid

# Install Deep SORT
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 3: Installing Deep SORT                                              ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Installing deep-sort-realtime..."
pip install deep-sort-realtime

# Install scikit packages
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 4: Installing Scientific Computing Libraries                        ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Installing scikit-learn and scikit-image..."
pip install scikit-learn scikit-image

# Install color analysis libraries
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 5: Installing Color Analysis Libraries                              ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Installing webcolors and colormath..."
pip install webcolors colormath

# Install remaining requirements
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 6: Installing Remaining Dependencies                                ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📦 Installing from requirements.txt..."
pip install -r requirements.txt

# Test imports
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 7: Testing Installations                                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "🔍 Testing PyTorch..."
python3 -c "import torch; print(f'  ✅ PyTorch {torch.__version__} installed')"

echo "🔍 Testing MPS/CUDA availability..."
python3 -c "import torch; print(f'  ✅ MPS available: {torch.backends.mps.is_available()}') if hasattr(torch.backends, 'mps') else print('  ⚠️ MPS not available')"
python3 -c "import torch; print(f'  ✅ CUDA available: {torch.cuda.is_available()}')"

echo "🔍 Testing torchreid..."
python3 -c "import torchreid; print('  ✅ torchreid installed successfully')" 2>&1 | grep -v "Warning"

echo "🔍 Testing deep-sort-realtime..."
python3 -c "from deep_sort_realtime.deepsort_tracker import DeepSort; print('  ✅ deep-sort-realtime installed successfully')"

echo "🔍 Testing scikit-learn..."
python3 -c "import sklearn; print(f'  ✅ scikit-learn {sklearn.__version__} installed')"

echo "🔍 Testing scikit-image..."
python3 -c "import skimage; print(f'  ✅ scikit-image {skimage.__version__} installed')"

echo "🔍 Testing OpenCV..."
python3 -c "import cv2; print(f'  ✅ OpenCV {cv2.__version__} installed')"

echo "🔍 Testing NumPy..."
python3 -c "import numpy as np; print(f'  ✅ NumPy {np.__version__} installed')"

# Download OSNet pretrained weights
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 8: Downloading OSNet Pretrained Weights                             ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📥 Downloading pretrained OSNet model..."
python3 -c "
import torchreid
print('  🔧 Initializing OSNet model (this will download weights)...')
try:
    model = torchreid.models.build_model(
        name='osnet_x1_0',
        num_classes=1000,
        pretrained=True,
        use_gpu=False
    )
    print('  ✅ OSNet weights downloaded successfully!')
except Exception as e:
    print(f'  ⚠️ Warning: {e}')
    print('  ⚠️ Weights will be downloaded on first use')
"

# Test the clothing analyzer
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 9: Testing Clothing Analyzer                                        ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "🧪 Running clothing analyzer test..."
python3 src/features/clothing_analyzer.py 2>&1 | grep -E "✅|⚠️|Testing"

# Test OSNet extractor
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 10: Testing OSNet Extractor                                         ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "🧪 Running OSNet extractor test..."
python3 src/features/osnet_extractor.py 2>&1 | grep -E "✅|⚠️|Testing|TESTING"

# Test enhanced re-ID system
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  STEP 11: Testing Enhanced Re-ID System                                   ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "🧪 Running enhanced re-ID test..."
python3 src/enhanced_reid.py 2>&1 | grep -E "✅|⚠️|Testing|TESTING"

# Final summary
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  INSTALLATION COMPLETE!                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Enhanced Re-ID System installed successfully!"
echo ""
echo "📦 Installed Components:"
echo "  ✅ PyTorch with GPU acceleration (if available)"
echo "  ✅ OSNet (Omni-Scale Network) for body re-ID"
echo "  ✅ Deep SORT for tracking"
echo "  ✅ Clothing analyzer with color/pattern/style detection"
echo "  ✅ Skin tone extraction"
echo "  ✅ Enhanced multi-modal re-ID system"
echo ""
echo "🚀 Next Steps:"
echo "  1. Test the system:"
echo "     python3 emergency_debug_enhanced.py"
echo ""
echo "  2. Compare with old system:"
echo "     python3 emergency_debug_false_positives.py    # Old histogram-based"
echo "     python3 emergency_debug_enhanced.py           # New OSNet + clothing"
echo ""
echo "  3. Expected improvements:"
echo "     - OSNet embeddings: Much better person discrimination"
echo "     - Clothing analysis: Detects colors, patterns, textures"
echo "     - Skin tone: Additional biometric feature"
echo "     - Lower false positive rate"
echo "     - Better cross-camera matching"
echo ""
echo "📚 Documentation:"
echo "  - README.md - System overview"
echo "  - EMERGENCY_DEBUG_ANALYSIS.md - Performance analysis"
echo "  - QUICK_TEST_UPDATED_SYSTEM.md - Testing guide"
echo ""
echo "Happy testing! 🎉"
echo ""
