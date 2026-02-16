#!/usr/bin/env python3
"""
System Check Script
===================
Comprehensive pre-flight check for the Three-Camera Monitoring System.

This script verifies:
1. Python environment and dependencies
2. Camera availability and configuration
3. Database and file system
4. Required files and modules
5. System readiness

Usage:
    python scripts/system_check.py
"""

import os
import sys
from pathlib import Path

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(title):
    """Print formatted header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_check(name, status, message=""):
    """Print check result."""
    if status:
        print(f"{GREEN}✅{RESET} {name:<40} {GREEN}OK{RESET}")
        if message:
            print(f"   {message}")
    else:
        print(f"{RED}❌{RESET} {name:<40} {RED}FAILED{RESET}")
        if message:
            print(f"   {message}")
    return status


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    required = (3, 8)

    if version >= required:
        return print_check(
            "Python Version",
            True,
            f"Python {version.major}.{version.minor}.{version.micro}",
        )
    else:
        return print_check(
            "Python Version",
            False,
            f"Python {version.major}.{version.minor} (Required: 3.8+)",
        )


def check_opencv():
    """Check OpenCV installation."""
    try:
        import cv2

        version = cv2.__version__
        return print_check("OpenCV", True, f"Version {version}")
    except ImportError as e:
        return print_check(
            "OpenCV", False, f"Not installed. Run: pip install opencv-python"
        )


def check_numpy():
    """Check NumPy installation."""
    try:
        import numpy as np

        version = np.__version__
        return print_check("NumPy", True, f"Version {version}")
    except ImportError:
        return print_check("NumPy", False, "Not installed. Run: pip install numpy")


def check_pyyaml():
    """Check PyYAML installation."""
    try:
        import yaml

        return print_check("PyYAML", True)
    except ImportError:
        return print_check("PyYAML", False, "Not installed. Run: pip install pyyaml")


def check_cameras():
    """Check available cameras."""
    try:
        import cv2

        cameras_found = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cameras_found.append(i)
                cap.release()

        if len(cameras_found) >= 3:
            return print_check(
                "Camera Detection",
                True,
                f"Found {len(cameras_found)} cameras: {cameras_found}",
            )
        elif len(cameras_found) >= 2:
            return print_check(
                "Camera Detection",
                True,
                f"Found {len(cameras_found)} cameras (2-camera mode available)",
            )
        else:
            return print_check(
                "Camera Detection",
                False,
                f"Only {len(cameras_found)} camera(s) found. Need at least 2.",
            )
    except Exception as e:
        return print_check("Camera Detection", False, f"Error: {e}")


def check_file_exists(filepath, description):
    """Check if a file exists."""
    path = Path(filepath)
    if path.exists():
        size = path.stat().st_size
        return print_check(description, True, f"{filepath} ({size} bytes)")
    else:
        return print_check(description, False, f"{filepath} not found")


def check_directory_exists(dirpath, description):
    """Check if a directory exists."""
    path = Path(dirpath)
    if path.exists() and path.is_dir():
        return print_check(description, True, f"{dirpath}")
    else:
        return print_check(description, False, f"{dirpath} not found")


def check_module_import(module_path, description):
    """Check if a module can be imported."""
    try:
        # Add parent directory to path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Try to import
        if "/" in module_path:
            parts = module_path.replace(".py", "").split("/")
            module_name = ".".join(parts)
        else:
            module_name = module_path.replace(".py", "")

        __import__(module_name)
        return print_check(description, True, f"{module_path}")
    except Exception as e:
        return print_check(description, False, f"{module_path} - Error: {str(e)[:50]}")


def check_haarcascade():
    """Check Haar Cascade availability."""
    try:
        import cv2

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)

        if cascade.empty():
            return print_check(
                "Haar Cascade", False, "Failed to load cascade classifier"
            )
        else:
            return print_check("Haar Cascade", True, "Face detection model ready")
    except Exception as e:
        return print_check("Haar Cascade", False, f"Error: {e}")


def check_database_access():
    """Check database access and creation."""
    try:
        import sqlite3

        # Try to create a test database
        test_db = Path("data/test_check.db")
        test_db.parent.mkdir(exist_ok=True)

        conn = sqlite3.connect(str(test_db))
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
        conn.close()

        # Clean up
        if test_db.exists():
            test_db.unlink()

        return print_check("Database Access", True, "SQLite3 working correctly")
    except Exception as e:
        return print_check("Database Access", False, f"Error: {e}")


def main():
    """Run all system checks."""
    print(f"\n{BLUE}{'=' * 70}")
    print(f"  THREE-CAMERA SYSTEM - PRE-FLIGHT CHECK")
    print(f"{'=' * 70}{RESET}\n")

    results = []

    # Check Python Environment
    print_header("PYTHON ENVIRONMENT")
    results.append(check_python_version())
    results.append(check_opencv())
    results.append(check_numpy())
    results.append(check_pyyaml())

    # Check Hardware
    print_header("HARDWARE")
    results.append(check_cameras())

    # Check Required Files
    print_header("REQUIRED FILES")
    results.append(check_file_exists("demo_three_cameras.py", "Main Demo Script"))
    results.append(check_file_exists("demo_entry_room.py", "2-Camera Demo"))
    results.append(check_file_exists("src/enhanced_database.py", "Database Module"))
    results.append(check_file_exists("src/alert_manager.py", "Alert Manager"))
    results.append(check_file_exists("configs/system_config.yaml", "Configuration"))

    # Check Directories
    print_header("DIRECTORIES")
    results.append(check_directory_exists("src", "Source Directory"))
    results.append(check_directory_exists("scripts", "Scripts Directory"))
    results.append(check_directory_exists("configs", "Config Directory"))

    # Create data directory if missing
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(exist_ok=True)
        print(f"{GREEN}✅{RESET} Data Directory               {GREEN}CREATED{RESET}")
        print(f"   data/")
        results.append(True)
    else:
        results.append(check_directory_exists("data", "Data Directory"))

    # Check Module Imports
    print_header("MODULE IMPORTS")
    results.append(check_module_import("src/enhanced_database", "Enhanced Database"))
    results.append(check_module_import("src/alert_manager", "Alert Manager"))

    # Check Additional Components
    print_header("ADDITIONAL COMPONENTS")
    results.append(check_haarcascade())
    results.append(check_database_access())

    # Summary
    print_header("SUMMARY")

    total_checks = len(results)
    passed_checks = sum(results)
    failed_checks = total_checks - passed_checks

    print(f"Total Checks:  {total_checks}")
    print(f"{GREEN}Passed:        {passed_checks}{RESET}")
    if failed_checks > 0:
        print(f"{RED}Failed:        {failed_checks}{RESET}")
    else:
        print(f"Failed:        {failed_checks}")

    print(f"\n{'=' * 70}\n")

    if all(results):
        print(f"{GREEN}🎉 ALL CHECKS PASSED!{RESET}")
        print(f"\n{GREEN}✅ System is READY to run!{RESET}\n")
        print("Next steps:")
        print("  1. Ensure all cameras are connected")
        print("  2. Run: python demo_three_cameras.py")
        print("  3. Press 'e' to register at entry camera")
        print("  4. Test the system\n")
        return 0
    else:
        print(f"{RED}⚠️  SOME CHECKS FAILED{RESET}")
        print(f"\n{YELLOW}System may not work correctly.{RESET}\n")
        print("Recommendations:")

        if not results[0]:  # Python version
            print(f"  {RED}→{RESET} Upgrade Python to 3.8 or higher")

        if not results[1]:  # OpenCV
            print(f"  {RED}→{RESET} Install OpenCV: pip install opencv-python")

        if not results[2]:  # NumPy
            print(f"  {RED}→{RESET} Install NumPy: pip install numpy")

        if not results[4]:  # Cameras
            print(
                f"  {RED}→{RESET} Connect cameras and run: python scripts/detect_cameras.py"
            )

        # Check for missing files
        if not any(results[5:10]):
            print(f"  {RED}→{RESET} Some required files are missing")
            print(f"     Please ensure you're in the project root directory")

        print()
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⚠️  Check interrupted by user{RESET}\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}❌ ERROR: {e}{RESET}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
