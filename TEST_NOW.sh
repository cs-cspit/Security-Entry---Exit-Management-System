#!/bin/bash
# Quick Test Script for Updated System (Confidence Gap 0.12)

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║         EMERGENCY FIX - QUICK TEST SCRIPT                                  ║"
echo "║         Confidence Gap Adjusted: 0.20 → 0.12                               ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  OPTION 1: EMERGENCY DEBUG TEST (Recommended First)                       ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will test if Person A (you) now matches with 0.12 confidence gap"
echo ""
echo "Steps:"
echo "  1. Press 'r' when you appear → Register as Person A"
echo "  2. Press 'r' when friend appears → Register as Person B"
echo "  3. Press SPACE when Person A appears → Test matching"
echo "  4. Press SPACE when Person B appears → Test matching"
echo "  5. Press 'q' to quit"
echo ""
echo "Expected Results:"
echo "  ✅ Person A should match in ~70-80% of tests"
echo "  ✅ Person B should be rejected in ~90%+ of tests"
echo ""
read -p "Press ENTER to start Emergency Debug, or Ctrl+C to skip..."

python3 emergency_debug_false_positives.py

echo ""
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  OPTION 2: FULL THREE-CAMERA DEMO                                          ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "This runs the complete entry/room/exit camera system"
echo ""
echo "Steps:"
echo "  1. Entry Camera (Webcam 0): Press 'r' to register"
echo "  2. Room Camera (Webcam 1): Should recognize you"
echo "  3. Exit Camera (Webcam 2): Should detect your exit"
echo "  4. Have friend appear: Should be rejected as unknown"
echo "  5. Press 'q' to quit"
echo ""
read -p "Press ENTER to start Three-Camera Demo, or Ctrl+C to exit..."

python3 demo_yolo_cameras.py

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  TEST COMPLETE                                                             ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Please document your results:"
echo ""
echo "Person A (Registered User):"
echo "  - Total tests: ____"
echo "  - Matched correctly: ____  (Target: 70-80%)"
echo "  - Rejected incorrectly: ____  (Should be 20-30%)"
echo ""
echo "Person B (Unregistered):"
echo "  - Total tests: ____"
echo "  - Rejected correctly: ____  (Target: 90%+)"
echo "  - Matched incorrectly: ____  (Should be <10%)"
echo ""
echo "Next Steps:"
echo "  ✅ If results meet targets → System is ready!"
echo "  ⚠️  If too many false positives → Raise thresholds (see docs)"
echo "  ⚠️  If too many false negatives → Lower thresholds (see docs)"
echo ""
echo "Documentation:"
echo "  - EMERGENCY_FIX_SUMMARY.md          - Quick overview"
echo "  - EMERGENCY_DEBUG_ANALYSIS.md       - Detailed analysis"
echo "  - QUICK_TEST_UPDATED_SYSTEM.md      - Testing guide"
echo ""
