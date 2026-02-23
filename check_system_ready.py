#!/usr/bin/env python3
"""
System Readiness Checker
Verifies that your system is ready for Enhanced Re-ID installation
"""

import platform
import subprocess
import sys
from pathlib import Path


def print_header(text):
    """Print section header."""
    print()
    print("=" * 80)
    print(f"  {text}")
    print("=" * 80)
    print()


def check_python_version():
    """Check Python version."""
    print("🔍 Checking Python version...")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print(f"   Python version: {version_str}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"   ❌ Python 3.8+ required (you have {version_str})")
        return False
    else:
        print(f"   ✅ Python version OK")
        return True


def check_pip():
    """Check if pip is available."""
    print()
    print("🔍 Checking pip...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"   pip version: {result.stdout.strip()}")
        print(f"   ✅ pip is available")
        return True
    except subprocess.CalledProcessError:
        print(f"   ❌ pip not found")
        return False


def check_disk_space():
    """Check available disk space."""
    print()
    print("🔍 Checking disk space...")
    try:
        import shutil

        total, used, free = shutil.disk_usage(".")
        free_gb = free / (1024**3)
        print(f"   Free space: {free_gb:.2f} GB")

        if free_gb < 2.0:
            print(f"   ⚠️ Low disk space (need ~2 GB, have {free_gb:.2f} GB)")
            return False
        else:
            print(f"   ✅ Sufficient disk space")
            return True
    except Exception as e:
        print(f"   ⚠️ Could not check disk space: {e}")
        return True  # Continue anyway


def check_venv():
    """Check if virtual environment exists and is activated."""
    print()
    print("🔍 Checking virtual environment...")

    # Check if venv directory exists
    venv_path = Path("venv")
    if not venv_path.exists():
        print(f"   ⚠️ Virtual environment not found at ./venv")
        print(f"   💡 Create it with: python3 -m venv venv")
        return False
    else:
        print(f"   ✅ Virtual environment exists at ./venv")

    # Check if currently activated
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print(f"   ✅ Virtual environment is activated")
        return True
    else:
        print(f"   ⚠️ Virtual environment not activated")
        print(f"   💡 Activate it with: source venv/bin/activate")
        return False


def check_existing_packages():
    """Check which required packages are already installed."""
    print()
    print("🔍 Checking existing packages...")

    packages = {
        "opencv-python": "cv2",
        "numpy": "numpy",
        "torch": "torch",
        "torchvision": "torchvision",
        "torchreid": "torchreid",
        "ultralytics": "ultralytics",
        "scikit-learn": "sklearn",
        "scikit-image": "skimage",
    }

    installed = []
    missing = []

    for package_name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"   ✅ {package_name}")
            installed.append(package_name)
        except ImportError:
            print(f"   ❌ {package_name} (not installed)")
            missing.append(package_name)

    print()
    print(f"   Installed: {len(installed)}/{len(packages)}")
    print(f"   Missing: {len(missing)}/{len(packages)}")

    return len(missing) == 0


def check_gpu_availability():
    """Check if GPU/MPS acceleration is available."""
    print()
    print("🔍 Checking GPU/MPS availability...")

    try:
        import torch

        # Check CUDA (NVIDIA)
        if torch.cuda.is_available():
            print(f"   ✅ CUDA available")
            print(f"      Device: {torch.cuda.get_device_name(0)}")
            print(f"      CUDA version: {torch.version.cuda}")
            return True

        # Check MPS (Apple Silicon)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print(f"   ✅ MPS (Metal) available")
            print(f"      Apple Silicon acceleration enabled")
            return True

        print(f"   ⚠️ No GPU acceleration available (will use CPU)")
        print(f"      Performance will be slower but system will work")
        return True  # CPU is OK, just slower

    except ImportError:
        print(f"   ⚠️ PyTorch not installed yet (can't check GPU)")
        return True


def check_camera():
    """Check if camera is accessible."""
    print()
    print("🔍 Checking camera access...")

    try:
        import cv2

        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print(
                    f"   ✅ Camera accessible (resolution: {frame.shape[1]}x{frame.shape[0]})"
                )
                return True
            else:
                print(f"   ⚠️ Camera opened but couldn't read frame")
                return False
        else:
            print(f"   ⚠️ Could not open camera (index 0)")
            return False
    except ImportError:
        print(f"   ⚠️ OpenCV not installed yet (can't check camera)")
        return True  # Will check after installation
    except Exception as e:
        print(f"   ⚠️ Camera check failed: {e}")
        return False


def check_file_structure():
    """Check if essential files exist."""
    print()
    print("🔍 Checking project file structure...")

    essential_files = [
        "requirements.txt",
        "install_enhanced_reid.sh",
        "emergency_debug_enhanced.py",
        "src/enhanced_reid.py",
        "src/features/osnet_extractor.py",
        "src/features/clothing_analyzer.py",
        "src/detectors/hybrid_face_detector.py",
        "src/detectors/yolov11_body_detector.py",
    ]

    all_exist = True
    for file_path in essential_files:
        path = Path(file_path)
        if path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (missing)")
            all_exist = False

    if all_exist:
        print(f"   ✅ All essential files present")
    else:
        print(f"   ⚠️ Some files missing - re-extract the project")

    return all_exist


def main():
    """Run all system checks."""
    print_header("SYSTEM READINESS CHECK FOR ENHANCED RE-ID")

    print("This script will verify that your system is ready for:")
    print("  • Enhanced Re-ID installation")
    print("  • OSNet deep learning features")
    print("  • Advanced clothing analysis")
    print("  • Real-time person re-identification")
    print()
    print("Running checks...")

    # Run all checks
    checks = {
        "Python Version": check_python_version(),
        "pip": check_pip(),
        "Disk Space": check_disk_space(),
        "Virtual Environment": check_venv(),
        "Existing Packages": check_existing_packages(),
        "GPU/MPS": check_gpu_availability(),
        "Camera": check_camera(),
        "File Structure": check_file_structure(),
    }

    # Print summary
    print_header("CHECK SUMMARY")

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    for name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status:12} {name}")

    print()
    print(f"  Score: {passed}/{total} checks passed")
    print()

    # Recommendations
    if passed == total:
        print("🎉 ALL CHECKS PASSED!")
        print()
        print("Your system is ready for Enhanced Re-ID installation.")
        print()
        print("Next steps:")
        print("  1. Run: ./install_enhanced_reid.sh")
        print("  2. Test: python3 emergency_debug_enhanced.py")
        print()
    elif passed >= total - 2:
        print("⚠️ MOSTLY READY (minor issues)")
        print()
        print("Your system should work, but fix warnings if possible.")
        print()
        print("You can proceed with installation:")
        print("  ./install_enhanced_reid.sh")
        print()
    else:
        print("❌ NOT READY (critical issues)")
        print()
        print("Please fix the failed checks before proceeding:")
        print()

        if not checks["Python Version"]:
            print("  • Install Python 3.8 or later")

        if not checks["pip"]:
            print("  • Install pip: python3 -m ensurepip")

        if not checks["Virtual Environment"]:
            print("  • Create venv: python3 -m venv venv")
            print("  • Activate: source venv/bin/activate")

        if not checks["Disk Space"]:
            print("  • Free up at least 2 GB of disk space")

        if not checks["File Structure"]:
            print("  • Re-extract the project or check file paths")

        print()

    # System info
    print()
    print("=" * 80)
    print("  SYSTEM INFORMATION")
    print("=" * 80)
    print()
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Machine: {platform.machine()}")
    print(f"  Processor: {platform.processor()}")
    print(f"  Python: {sys.version}")
    print()

    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
