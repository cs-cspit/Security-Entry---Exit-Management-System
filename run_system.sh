#!/bin/bash
# =============================================================================
# Security Entry & Exit Management System — Launch Script
# =============================================================================
#
# Camera setup for this project:
#   Entry  : iBall Face2Face CHD20.0 Webcam (720p HD, USB)
#   Room   : MacBook FaceTime HD (built-in)
#   Exit   : Redmi Note 11 via Iriun Webcam app (USB/WiFi)
#
# Default camera indices (macOS — built-in webcam is usually 0):
#   --entry 1   (iBall USB webcam)
#   --room  0   (MacBook built-in)
#   --exit  2   (Redmi via Iriun)
#
# Override if your setup differs:
#   bash run_system.sh --entry 2 --room 0 --exit 1
#
# To identify which index belongs to which camera:
#   bash run_system.sh --list-cameras
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
echo -e "  Entry  : iBall Face2Face CHD20.0 (720p HD, USB)  → default idx 1"
echo -e "  Room   : MacBook FaceTime HD (built-in)          → default idx 0"
echo -e "  Exit   : Redmi Note 11 via Iriun                 → default idx 2"
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

# ── YOLO model check ──────────────────────────────────────────────────────────
if [ ! -f "yolo26n-pose.pt" ]; then
    echo -e "${YELLOW}⚠️   yolo26n-pose.pt not found in project root.${NC}"
    echo    "    The system will attempt to download it on first run."
    echo ""
fi

# ── Controls reminder ────────────────────────────────────────────────────────
echo "🎮  Keyboard Controls:"
echo "      D  — Toggle debug output"
echo "      F  — Toggle face recognition (Phase 5)"
echo "      C  — Clear all registrations"
echo "      S  — Show statistics"
echo "      I  — Cross-camera adapter diagnostics"
echo "      +  — Increase room matching threshold"
echo "      -  — Decrease room matching threshold"
echo "      ]  — Increase exit matching threshold"
echo "      [  — Decrease exit matching threshold"
echo "      Q  — Quit and export session data"
echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo ""

# ── Launch ────────────────────────────────────────────────────────────────────
# Pass all script arguments straight through so callers can do:
#   bash run_system.sh --entry 2 --room 0 --exit 1
#   bash run_system.sh --list-cameras
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
