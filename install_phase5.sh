#!/bin/bash
# Phase 5: Face Recognition Integration - Installation Script
# Installs InsightFace and dependencies

set -e

echo "=============================================="
echo "  PHASE 5: Face Recognition Integration"
echo "  Installing InsightFace and dependencies"
echo "=============================================="
echo ""

# Check Python version
echo "🔍 Checking Python version..."
python3 --version || { echo "❌ Python 3 not found!"; exit 1; }

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  No virtual environment detected"
    echo "   Recommended: Create and activate a venv first"
    echo "   python3 -m venv venv && source venv/bin/activate"
    read -p "   Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install InsightFace
echo ""
echo "📦 Installing InsightFace..."
pip install insightface>=0.7.3

# Install ONNX Runtime (required by InsightFace)
echo ""
echo "📦 Installing ONNX Runtime..."
pip install onnxruntime>=1.16.0

# Install additional dependencies
echo ""
echo "📦 Installing additional dependencies..."
pip install albumentations>=1.3.1

# Verify installation
echo ""
echo "✅ Verifying installation..."
python3 -c "import insightface; print(f'InsightFace version: {insightface.__version__}')" || { echo "❌ InsightFace import failed!"; exit 1; }
python3 -c "import onnxruntime; print(f'ONNX Runtime version: {onnxruntime.__version__}')" || { echo "❌ ONNX Runtime import failed!"; exit 1; }

# Test face recognition module
echo ""
echo "🧪 Testing face recognition module..."
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
from features.face_recognition import FaceRecognitionExtractor
print('✅ Face recognition module loaded successfully')
" || { echo "❌ Face recognition module test failed!"; exit 1; }

echo ""
echo "=============================================="
echo "  ✅ PHASE 5 INSTALLATION COMPLETE!"
echo "=============================================="
echo ""
echo "📋 What was installed:"
echo "   ✅ insightface (face detection & recognition)"
echo "   ✅ onnxruntime (model inference)"
echo "   ✅ albumentations (image preprocessing)"
echo ""
echo "📝 Next steps:"
echo "   1. Run the system: python3 yolo26_complete_system.py"
echo "   2. Test face recognition: python3 src/features/face_recognition.py"
echo "   3. Press 'F' in system to toggle face recognition"
echo ""
echo "ℹ️  Models will be downloaded automatically on first run (~100MB)"
echo "   Location: ~/.insightface/models/"
echo ""
echo "🎯 Face Recognition Features:"
echo "   - Entry gate: Captures face during registration"
echo "   - Exit gate: Face-first matching (60% weight)"
echo "   - Fallback to body features if face not detected"
echo "   - 512D face embeddings (ArcFace model)"
echo "   - Typical threshold: 0.45 for same person"
echo ""
