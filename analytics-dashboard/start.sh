#!/bin/bash
# ============================================================================
# SecureVision Analytics Dashboard — Startup Script
# ============================================================================
# Production-grade startup: no demo data, all analytics from real cameras.
#
# Pages served:
#   /          — Full analytics dashboard (charts, tables, history)
#   /monitor   — LIVE monitor (camera feeds + real-time analytics side-by-side)
#
# Usage:
#   chmod +x start.sh
#   ./start.sh
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║    SecureVision — Live Monitor & Analytics Dashboard    ║${RESET}"
echo -e "${CYAN}${BOLD}║              PRODUCTION MODE — Real Data Only           ║${RESET}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# --------------------------------------------------------------------------
# 1. Check for Python 3
# --------------------------------------------------------------------------
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PY_VER=$(python --version 2>&1 | awk '{print $2}' | cut -d. -f1)
    if [ "$PY_VER" = "3" ]; then
        PYTHON="python"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo -e "${RED}ERROR: Python 3 is required but was not found.${RESET}"
    echo "Please install Python 3.8+ from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$("$PYTHON" --version 2>&1)
echo -e "${GREEN}✓${RESET} Found ${PY_VERSION}"

# --------------------------------------------------------------------------
# 2. Use the existing parent project virtual environment
# --------------------------------------------------------------------------
VENV_DIR="$SCRIPT_DIR/../venv"

# Activate
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}✓${RESET} Using project virtual environment: ${BOLD}$VENV_DIR${RESET}"
    # Re-point PYTHON to the venv interpreter
    PYTHON="$VENV_DIR/bin/python"
else
    echo -e "${YELLOW}⚠${RESET} Parent venv not found at $VENV_DIR — using system Python"
fi

# --------------------------------------------------------------------------
# 3. Install any missing dashboard dependencies into the project venv
# --------------------------------------------------------------------------
echo -e "${YELLOW}→${RESET} Checking dependencies ..."

# Only install if not already present
"$PYTHON" -c "import flask; import flask_cors" 2>/dev/null || {
    echo -e "${YELLOW}→${RESET} Installing missing packages into project venv ..."
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
}

# Check for OpenCV (needed for camera bridge)
"$PYTHON" -c "import cv2" 2>/dev/null && {
    echo -e "${GREEN}✓${RESET} OpenCV available (camera streaming enabled)"
} || {
    echo -e "${YELLOW}⚠${RESET} OpenCV not found — camera streaming will not work"
    echo "  Install with: pip install opencv-python"
}

# Check for YOLO / torch (needed for full detection mode)
"$PYTHON" -c "import torch; from ultralytics import YOLO" 2>/dev/null && {
    echo -e "${GREEN}✓${RESET} YOLO + PyTorch available (FULL detection mode)"
} || {
    echo -e "${YELLOW}⚠${RESET} YOLO/PyTorch not found — will use LITE or RAW mode"
    echo "  Install with: pip install ultralytics torch torchvision"
}

echo -e "${GREEN}✓${RESET} All dependencies satisfied"

# --------------------------------------------------------------------------
# 4. Ensure data directory exists
# --------------------------------------------------------------------------
mkdir -p "$SCRIPT_DIR/data"
echo -e "${GREEN}✓${RESET} Data directory ready: ${BOLD}$SCRIPT_DIR/data/${RESET}"

# --------------------------------------------------------------------------
# 5. Clean up old demo database if it exists
# --------------------------------------------------------------------------
if [ -f "$SCRIPT_DIR/data/demo_security.db" ]; then
    echo -e "${YELLOW}→${RESET} Removing old demo database (no longer used) ..."
    rm -f "$SCRIPT_DIR/data/demo_security.db"
    echo -e "${GREEN}✓${RESET} Demo database removed"
fi

# --------------------------------------------------------------------------
# 6. Launch the Flask server
# --------------------------------------------------------------------------
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5050}"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${BOLD}PRODUCTION MODE — All data from real camera detections${RESET}"
echo ""
echo -e "  ${BOLD}Database:${RESET} $SCRIPT_DIR/data/live_security.db"
echo -e "  ${BOLD}Tables start EMPTY. Data flows in when cameras are active.${RESET}"
echo ""
echo -e "  ${BOLD}Pages:${RESET}"
echo -e "    📊 Dashboard:     ${GREEN}${BOLD}http://127.0.0.1:${PORT}/${RESET}"
echo -e "    📹 Live Monitor:  ${GREEN}${BOLD}http://127.0.0.1:${PORT}/monitor${RESET}"
echo ""
echo -e "  ${BOLD}How it works:${RESET}"
echo -e "    1. Open ${CYAN}/monitor${RESET} in your browser"
echo -e "    2. Click ${GREEN}\"Start Camera System\"${RESET} to connect cameras"
echo -e "    3. Camera detections flow into the dashboard in real-time"
echo -e "    4. Open ${CYAN}/${RESET} to see the full analytics dashboard"
echo ""
echo -e "  ${BOLD}Controls:${RESET}"
echo -e "    Start cameras:  POST http://127.0.0.1:${PORT}/api/bridge/start"
echo -e "    Stop cameras:   POST http://127.0.0.1:${PORT}/api/bridge/stop"
echo -e "    Reset all data: POST http://127.0.0.1:${PORT}/api/db/reset"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop the server."
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

"$PYTHON" "$SCRIPT_DIR/app.py"
