#!/bin/bash
# =============================================================================
# Security Entry & Exit Management System — Launch Script
# =============================================================================
#
# Camera setup for this project:
#   Entry  : Phone camera via DroidCam + OBS Virtual Camera
#   Room   : MacBook FaceTime HD (built-in)
#   Exit   : Redmi Note 11 via Iriun Webcam app (USB/WiFi)
#
# Default launch sources (from yolo26_complete_system.py):
#   --entry obs  (auto-detect OBS Virtual Camera / DroidCam feed)
#   --room  2    (numeric camera index)
#   --exit  1    (numeric camera index)
#
# Override if your setup differs:
#   bash run_system.sh --entry obs --room 0 --exit 2
#   bash run_system.sh --entry "http://PHONE_IP:4747/video" --room 0 --exit 2
#
# To identify which index belongs to which camera:
#   python scripts/detect_cameras.py
# =============================================================================

set -e

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Colour

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}  YOLO26 THREE-CAMERA SECURITY SYSTEM${NC}"
echo -e "${CYAN}=====================================================================${NC}"
echo ""
echo -e "  Entry  : Phone via DroidCam + OBS Virtual Cam    → default source 'obs'"
echo -e "  Room   : Room camera source                       → default idx 2"
echo -e "  Exit   : Exit camera source                       → default idx 1"
echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo ""

# ── Make sure we are in the project root ─────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "yolo26_complete_system.py" ]; then
    echo -e "${RED}❌  yolo26_complete_system.py not found.${NC}"
    echo    "    Please run this script from the project root directory."
    exit 1
fi

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️   Virtual environment not found — creating one…${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅  Created venv/${NC}"
    echo ""
fi

echo "🔄  Activating virtual environment…"
source venv/bin/activate

# ── Dependency check ──────────────────────────────────────────────────────────
echo "🔍  Checking core dependencies…"

MISSING=0

python -c "import cv2" 2>/dev/null       || { echo -e "${YELLOW}   ⚠️   opencv-python missing${NC}";  MISSING=1; }
python -c "import torch" 2>/dev/null     || { echo -e "${YELLOW}   ⚠️   torch missing${NC}";          MISSING=1; }
python -c "import ultralytics" 2>/dev/null || { echo -e "${YELLOW}   ⚠️   ultralytics missing${NC}";  MISSING=1; }
python -c "import torchreid" 2>/dev/null || { echo -e "${YELLOW}   ⚠️   torchreid missing${NC}";      MISSING=1; }

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}📦  Installing missing dependencies from requirements.txt …${NC}"
    pip install --upgrade pip -q
    pip install -r requirements.txt
    echo -e "${GREEN}✅  Dependencies installed.${NC}"
    echo ""
fi

# InsightFace (Phase 5 — face recognition)
python -c "import insightface" 2>/dev/null || {
    echo -e "${YELLOW}📦  InsightFace not found — installing Phase 5 dependencies…${NC}"
    pip install -r requirements_phase5.txt -q
    echo -e "${GREEN}✅  InsightFace installed.${NC}"
    echo ""
}

echo -e "${GREEN}✅  All dependencies satisfied.${NC}"
echo ""

# ── Ensure data/ directory exists ─────────────────────────────────────────────
mkdir -p data

# ── YOLO model check ──────────────────────────────────────────────────────
echo "🔍  Checking YOLO26 model suite…"

if [ -f "yolo26n-pose.pt" ]; then
    echo -e "${GREEN}   ✅  yolo26n-pose.pt (body detection + keypoints)${NC}"
else
    echo -e "${YELLOW}   ⚠️   yolo26n-pose.pt not found — will download on first run.${NC}"
fi

if [ -f "yolo26n-face.pt" ]; then
    echo -e "${GREEN}   ✅  yolo26n-face.pt (custom-trained face detector)${NC}"
elif [ -f "custom_models/yolo26_face_results/weights/best.pt" ]; then
    echo -e "${YELLOW}   ⚠️   yolo26n-face.pt not in root — copying from custom_models…${NC}"
    cp "custom_models/yolo26_face_results/weights/best.pt" "yolo26n-face.pt"
    echo -e "${GREEN}   ✅  yolo26n-face.pt copied successfully${NC}"
else
    echo -e "${RED}   ❌  No custom face model found — face detection will use generic COCO fallback.${NC}"
    echo    "       Place your trained model at yolo26n-face.pt or custom_models/yolo26_face_results/weights/best.pt"
fi

if [ -f "yolo26n-seg.pt" ]; then
    echo -e "${GREEN}   ✅  yolo26n-seg.pt (instance segmentation masks)${NC}"
else
    echo -e "${YELLOW}   ⚠️   yolo26n-seg.pt not found — clothing colour will use raw bbox crops.${NC}"
fi

if [ -f "yolo26n.pt" ]; then
    echo -e "${GREEN}   ✅  yolo26n.pt (body-level detection / OSNet)${NC}"
else
    echo -e "${YELLOW}   ⚠️   yolo26n.pt not found — will download on first run.${NC}"
fi

if [ -f "custom_models/yolov26n-threat_detection/weights/best.pt" ]; then
    echo -e "${GREEN}   ✅  yolov26n-threat_detection (room camera — guns/knives)${NC}"
else
    echo -e "${YELLOW}   ℹ️   Threat detection model not found (optional, for future use).${NC}"
fi

echo ""

# ── Controls reminder ────────────────────────────────────────────────────
echo "🎮  Keyboard Controls:"
echo "      D  — Toggle debug output"
echo "      F  — Toggle face recognition (Phase 5)"
echo "      C  — Clear all registrations"
echo "      S  — Show statistics"
echo "      I  — Cross-camera adapter diagnostics"
echo "      T  — Tracker diagnostics (ByteTrack)"
echo "      +  — Increase room matching threshold"
echo "      -  — Decrease room matching threshold"
echo "      ]  — Increase exit matching threshold"
echo "      [  — Decrease exit matching threshold"
echo "      Q  — Quit and export session data"
echo ""
echo "📊  Model Architecture (4-model YOLO26 suite):"
echo "      Pose:   yolo26n-pose.pt       → body bbox + 17 keypoints + ByteTrack"
echo "      Face:   yolo26n-face.pt       → custom-trained face detection (class 0 = face)"
echo "      Seg:    yolo26n-seg.pt        → pixel masks for clothing colour"
echo "      Body:   yolo26n.pt            → body-level detection / OSNet features"
echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo ""

# ── Launch ────────────────────────────────────────────────────────────────────
# Pass all script arguments straight through so callers can do:
#   bash run_system.sh --entry obs --room 0 --exit 2
#   bash run_system.sh --entry "http://PHONE_IP:4747/video" --room 0 --exit 2
#   python scripts/detect_cameras.py
python yolo26_complete_system.py "$@"

EXIT_CODE=$?
echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    echo -e "${GREEN}✅  System exited normally.${NC}"
else
    echo -e "${RED}⚠️   System exited with code: $EXIT_CODE${NC}"
fi
echo ""
exit "$EXIT_CODE"
