#!/usr/bin/env python3
"""
YOLO26 Ultimate System Readiness Check
======================================
Verifies all dependencies and models before running the complete system.
"""

import sys
from pathlib import Path

print("\n" + "=" * 70)
print("  🔍 YOLO26 ULTIMATE SYSTEM READINESS CHECK")
print("=" * 70 + "\n")

checks_passed = 0
checks_failed = 0
warnings = 0

# Check 1: Python version
print("1️⃣  Checking Python version...")
if sys.version_info >= (3, 8):
    print(
        f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    checks_passed += 1
else:
    print(f"   ❌ Python {sys.version_info.major}.{sys.version_info.minor} (need 3.8+)")
    checks_failed += 1

# Check 2: Core dependencies
print("\n2️⃣  Checking core dependencies...")
core_deps = {
    "cv2": "opencv-python",
    "numpy": "numpy",
    "torch": "torch",
    "torchvision": "torchvision",
    "PIL": "pillow",
    "yaml": "pyyaml",
}

for module, package in core_deps.items():
    try:
        __import__(module)
        print(f"   ✅ {package}")
        checks_passed += 1
    except ImportError:
        print(f"   ❌ {package} - Install: pip install {package}")
        checks_failed += 1

# Check 3: Ultralytics (YOLO)
print("\n3️⃣  Checking Ultralytics YOLO...")
try:
    import ultralytics
    from ultralytics import YOLO

    version = getattr(ultralytics, "__version__", "unknown")
    print(f"   ✅ ultralytics {version}")
    checks_passed += 1
except ImportError:
    print("   ❌ ultralytics - Install: pip install ultralytics")
    checks_failed += 1

# Check 4: torchreid (OSNet)
print("\n4️⃣  Checking torchreid (for OSNet)...")
try:
    import torchreid

    print("   ✅ torchreid")
    checks_passed += 1
except ImportError:
    print("   ⚠️  torchreid not found - Install: pip install torchreid")
    print("      (System will use fallback features)")
    warnings += 1

# Check 5: PyTorch device support
print("\n5️⃣  Checking PyTorch acceleration...")
try:
    import torch

    if torch.cuda.is_available():
        print("   ✅ CUDA GPU available")
        print(f"      Device: {torch.cuda.get_device_name(0)}")
    elif torch.backends.mps.is_available():
        print("   ✅ Apple MPS (Metal) available")
        print("      Device: Apple Silicon GPU")
    else:
        print("   ⚠️  CPU only (no GPU acceleration)")
        print("      System will work but may be slower")
        warnings += 1
    checks_passed += 1
except Exception as e:
    print(f"   ❌ Error checking device: {e}")
    checks_failed += 1

# Check 6: YOLO26 model
print("\n6️⃣  Checking YOLO26-pose model...")
model_path = Path("yolo26n-pose.pt")
if model_path.exists():
    size_mb = model_path.stat().st_size / (1024 * 1024)
    print(f"   ✅ yolo26n-pose.pt ({size_mb:.1f} MB)")
    checks_passed += 1
else:
    print("   ⚠️  yolo26n-pose.pt not found")
    print("      Model will auto-download on first run (~6MB)")
    warnings += 1

# Check 7: Project structure
print("\n7️⃣  Checking project structure...")
required_dirs = ["src", "data"]
required_files = ["yolo26_complete_system.py"]

all_present = True
for dir_name in required_dirs:
    dir_path = Path(dir_name)
    if dir_path.exists():
        print(f"   ✅ {dir_name}/ directory")
    else:
        print(f"   ❌ {dir_name}/ directory missing")
        all_present = False

for file_name in required_files:
    file_path = Path(file_name)
    if file_path.exists():
        print(f"   ✅ {file_name}")
    else:
        print(f"   ❌ {file_name} missing")
        all_present = False

if all_present:
    checks_passed += 1
else:
    checks_failed += 1

# Check 8: Camera availability
print("\n8️⃣  Checking camera availability...")
try:
    import cv2

    available_cameras = []
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available_cameras.append(i)
            cap.release()

    if len(available_cameras) >= 3:
        print(f"   ✅ Found {len(available_cameras)} cameras: {available_cameras}")
        print("      Perfect for three-camera system!")
    elif len(available_cameras) > 0:
        print(f"   ⚠️  Found {len(available_cameras)} camera(s): {available_cameras}")
        print("      System needs 3 cameras for full operation")
        print("      (Available cameras will be reused)")
        warnings += 1
    else:
        print("   ❌ No cameras found")
        print("      Check camera connections")
        checks_failed += 1
    checks_passed += 1
except Exception as e:
    print(f"   ❌ Error checking cameras: {e}")
    checks_failed += 1

# Check 9: Data directory permissions
print("\n9️⃣  Checking data directory...")
data_dir = Path("data")
if not data_dir.exists():
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        print("   ✅ Created data/ directory")
        checks_passed += 1
    except Exception as e:
        print(f"   ❌ Cannot create data/ directory: {e}")
        checks_failed += 1
else:
    # Check write permissions
    test_file = data_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print("   ✅ data/ directory writable")
        checks_passed += 1
    except Exception as e:
        print(f"   ❌ data/ directory not writable: {e}")
        checks_failed += 1

# Check 10: System modules
print("\n🔟  Checking system modules...")
sys.path.insert(0, str(Path("src")))

modules_to_check = [
    ("detectors.yolo26_body_detector", "YOLO26BodyDetector"),
    ("features.osnet_extractor", "OSNetExtractor"),
    ("features.body_only_analyzer", "BodyOnlyAnalyzer"),
    ("enhanced_database", "EnhancedDatabase"),
    ("alert_manager", "AlertManager"),
]

all_modules_ok = True
for module_name, class_name in modules_to_check:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"   ✅ {module_name}.{class_name}")
    except Exception as e:
        print(f"   ❌ {module_name}.{class_name} - {e}")
        all_modules_ok = False

if all_modules_ok:
    checks_passed += 1
else:
    checks_failed += 1

# Summary
print("\n" + "=" * 70)
print("  📊 SUMMARY")
print("=" * 70)
print(f"✅ Checks passed: {checks_passed}")
print(f"❌ Checks failed: {checks_failed}")
print(f"⚠️  Warnings: {warnings}")
print("=" * 70)

if checks_failed == 0:
    print("\n🎉 ALL SYSTEMS GO!")
    print("   Your system is ready to run!")
    print("\n   Next step:")
    print("   ./RUN_ULTIMATE_SYSTEM.sh")
    print("\n   Or directly:")
    print("   python3 yolo26_complete_system.py")
elif checks_failed <= 2 and warnings <= 2:
    print("\n⚠️  MOSTLY READY")
    print("   System should work with minor issues")
    print("   Check warnings above and fix if needed")
    print("\n   Try running:")
    print("   python3 yolo26_complete_system.py")
else:
    print("\n❌ NOT READY")
    print("   Please fix the failed checks above")
    print("\n   Common fixes:")
    print("   • pip install ultralytics opencv-python torch torchvision")
    print("   • pip install torchreid")
    print("   • Check camera connections")

print("\n" + "=" * 70 + "\n")

sys.exit(0 if checks_failed == 0 else 1)
