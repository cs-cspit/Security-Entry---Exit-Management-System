#!/usr/bin/env python3
"""
Debug Second Camera Connection Script
=====================================
Dedicated script to help troubleshoot and connect the second phone camera.

This script will:
1. Detect all available cameras
2. Show detailed information about each
3. Provide step-by-step guidance for connecting the second phone
4. Test each camera individually
5. Help identify which camera is which

Usage:
    python scripts/debug_second_camera.py
"""

import sys
import time
from datetime import datetime

import cv2


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num, description):
    """Print a step instruction."""
    print(f"\n[STEP {step_num}] {description}")
    print("-" * 70)


def detect_all_cameras(max_index=10):
    """
    Detect all available cameras with detailed information.

    Returns:
        List of dictionaries with camera information
    """
    print_header("CAMERA DETECTION")
    print("Scanning for cameras (this may take a moment)...")

    cameras = []

    for index in range(max_index):
        print(f"\nTrying camera index {index}...", end=" ")
        cap = cv2.VideoCapture(index)

        if cap.isOpened():
            # Try to read a frame
            ret, frame = cap.read()

            if ret and frame is not None:
                # Get properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                backend = cap.getBackendName()

                print("✅ FOUND")

                camera_info = {
                    "index": index,
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "backend": backend,
                    "working": True,
                }

                cameras.append(camera_info)

                # Print details
                print(f"   Resolution: {width}x{height}")
                print(f"   Frame Rate: {fps:.1f} FPS")
                print(f"   Backend: {backend}")
            else:
                print("❌ Opens but cannot read frames")
        else:
            print("❌ Not available")

        cap.release()

    return cameras


def display_camera_summary(cameras):
    """Display summary of detected cameras."""
    print_header(f"SUMMARY: {len(cameras)} CAMERA(S) DETECTED")

    if not cameras:
        print("\n❌ NO CAMERAS DETECTED!")
        print("\nThis could mean:")
        print("  1. No cameras are connected")
        print("  2. Camera permissions are denied")
        print("  3. Another app is using all cameras")
        return

    print("\nDetected Cameras:")
    for cam in cameras:
        print(f"\n  📹 Camera {cam['index']}:")
        print(f"     Resolution: {cam['width']}x{cam['height']}")
        print(f"     FPS: {cam['fps']:.1f}")
        print(f"     Backend: {cam['backend']}")

    print()


def test_camera_individually(camera_index):
    """Test a specific camera with live preview."""
    print(f"\nTesting Camera {camera_index}...")

    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"❌ Failed to open camera {camera_index}")
        return False

    print(f"✅ Camera {camera_index} opened successfully")
    print("\nShowing live preview...")
    print("Controls:")
    print("  - Press 'q' to quit this camera test")
    print("  - Press 's' to take a snapshot")

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("❌ Failed to read frame")
                break

            # Add info overlay
            height, width = frame.shape[:2]

            # Info text
            cv2.putText(
                frame,
                f"Camera {camera_index}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )

            cv2.putText(
                frame,
                f"Resolution: {width}x{height}",
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            # FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed > 0:
                current_fps = frame_count / elapsed
                cv2.putText(
                    frame,
                    f"FPS: {current_fps:.1f}",
                    (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

            # Timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            cv2.putText(
                frame,
                timestamp,
                (10, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

            # Instructions
            cv2.putText(
                frame,
                "Press 'q' to quit | 's' to snapshot",
                (10, height - 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
            )

            # Display
            cv2.imshow(f"Camera {camera_index} Test", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print(f"\n✅ Camera {camera_index} test complete")
                break
            elif key == ord("s"):
                filename = f"camera_{camera_index}_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(filename, frame)
                print(f"📸 Snapshot saved: {filename}")

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")

    finally:
        cap.release()
        cv2.destroyAllWindows()

    return True


def guide_second_camera_setup():
    """Provide step-by-step guidance for connecting second camera."""
    print_header("SECOND PHONE CAMERA SETUP GUIDE")

    print("\nYou currently have fewer than 3 cameras detected.")
    print("Let's troubleshoot the second phone camera connection.\n")

    print_step(1, "Check Iriun App on Second Phone")
    print("   ✓ Is the Iriun app installed on your second phone?")
    print("   ✓ Is the Iriun app OPEN and running?")
    print("   ✓ Does it show 'Connected' or 'Waiting for connection'?")

    input("\nPress Enter when ready to continue...")

    print_step(2, "Check Iriun App on Mac")
    print("   ✓ Is the Iriun desktop app running on your Mac?")
    print("   ✓ Open Iriun on Mac - can you see BOTH phones listed?")
    print("   ✓ Do both phones show 'Connected' status?")

    input("\nPress Enter when ready to continue...")

    print_step(3, "Connection Method Check")
    print("\n   Which connection method are you using?")
    print("   1. USB connection (recommended)")
    print("   2. Wi-Fi connection")

    choice = input("\n   Enter 1 or 2: ").strip()

    if choice == "1":
        print("\n   USB CONNECTION CHECKLIST:")
        print("   ✓ Both phones physically connected via USB cable?")
        print("   ✓ Cables are working (try different ports)?")
        print("   ✓ 'Trust This Computer' accepted on iPhones?")
        print("   ✓ USB Debugging enabled on Android phones?")
        print("   ✓ USB Tethering enabled on Android phones?")
    else:
        print("\n   WI-FI CONNECTION CHECKLIST:")
        print("   ✓ Both phones on the same Wi-Fi network as Mac?")
        print("   ✓ Network name: _________________")
        print("   ✓ No VPN blocking local network connections?")
        print("   ✓ Firewall not blocking Iriun?")

    input("\nPress Enter when ready to continue...")

    print_step(4, "Restart Everything")
    print("\n   Let's do a complete restart:")
    print("   1. Close Iriun app on BOTH phones")
    print("   2. Close Iriun app on Mac")
    print("   3. Wait 5 seconds")
    print("   4. Open Iriun on Mac FIRST")
    print("   5. Wait for it to fully load")
    print("   6. Open Iriun on FIRST phone")
    print("   7. Wait for 'Connected' status")
    print("   8. Open Iriun on SECOND phone")
    print("   9. Wait for 'Connected' status")

    response = input("\nHave you completed the restart? (y/n): ").strip().lower()

    if response in ["y", "yes"]:
        print("\n✅ Great! Let's re-detect cameras...")
        return True
    else:
        print("\n⚠️  Please complete the restart steps, then run this script again.")
        return False


def show_simultaneous_preview(cameras):
    """Show all cameras simultaneously."""
    print_header("SIMULTANEOUS CAMERA PREVIEW")
    print("\nOpening all cameras...")
    print("\nControls:")
    print("  - Press 'q' to quit")
    print("  - Wave in front of each camera to identify them")

    # Open all cameras
    caps = []
    for cam in cameras:
        cap = cv2.VideoCapture(cam["index"])
        if cap.isOpened():
            caps.append({"index": cam["index"], "capture": cap})
            print(f"✅ Opened camera {cam['index']}")

    if not caps:
        print("❌ Failed to open any cameras")
        return

    print(f"\n✅ Showing {len(caps)} camera(s)")
    print("\n👋 Wave in front of each camera to identify them!")

    try:
        while True:
            frames = []

            for cam in caps:
                ret, frame = cam["capture"].read()
                if ret:
                    # Resize for display
                    frame = cv2.resize(frame, (640, 480))

                    # Add label
                    cv2.putText(
                        frame,
                        f"Camera {cam['index']}",
                        (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.2,
                        (0, 255, 0),
                        3,
                    )

                    # Add identification help
                    cv2.putText(
                        frame,
                        "Wave to identify!",
                        (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2,
                    )

                    frames.append((cam["index"], frame))

            # Display all frames
            for idx, frame in frames:
                cv2.imshow(f"Camera {idx}", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n⚠️  Preview interrupted")

    finally:
        for cam in caps:
            cam["capture"].release()
        cv2.destroyAllWindows()
        print("\n✅ Preview closed")


def main():
    """Main function."""
    print_header("SECOND CAMERA DEBUG TOOL")
    print("This tool will help you connect and identify your second phone camera.")
    print("\nDeveloped for: Three-Camera Security Monitoring System")

    # Detect cameras
    cameras = detect_all_cameras(max_index=10)

    # Display summary
    display_camera_summary(cameras)

    # Check if we need troubleshooting
    if len(cameras) < 3:
        print(f"\n⚠️  WARNING: Only {len(cameras)} camera(s) detected!")
        print("    Expected: 3 cameras (MacBook + 2 phones)")

        if len(cameras) == 0:
            print("\n❌ CRITICAL: No cameras detected at all!")
            print("\nPlease check:")
            print("  1. Camera permissions in System Preferences → Security → Camera")
            print("  2. No other apps using the cameras")
            print("  3. Restart your Mac")
            return 1

        print("\nWhat would you like to do?")
        print("  1. View troubleshooting guide")
        print("  2. Test existing cameras individually")
        print("  3. View all cameras simultaneously")
        print("  4. Exit")

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == "1":
            if guide_second_camera_setup():
                # Re-detect after troubleshooting
                print("\nRe-detecting cameras...")
                cameras = detect_all_cameras(max_index=10)
                display_camera_summary(cameras)

                if len(cameras) >= 3:
                    print("\n🎉 SUCCESS! All 3 cameras detected!")
                    print("You can now run: python demo_three_cameras.py")
                else:
                    print(f"\n⚠️  Still only {len(cameras)} camera(s) detected.")
                    print("Please check the troubleshooting guide or try again.")

        elif choice == "2":
            for cam in cameras:
                print(f"\n{'=' * 70}")
                response = input(f"Test Camera {cam['index']}? (y/n): ").strip().lower()
                if response in ["y", "yes"]:
                    test_camera_individually(cam["index"])

        elif choice == "3":
            show_simultaneous_preview(cameras)

        else:
            print("\n✅ Exiting...")

    else:
        # All 3 cameras detected!
        print("\n🎉 SUCCESS! All 3 cameras detected!")
        print("\nWhat would you like to do?")
        print("  1. Preview all cameras simultaneously")
        print("  2. Test each camera individually")
        print("  3. Run the three-camera demo")
        print("  4. Exit")

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == "1":
            show_simultaneous_preview(cameras)

        elif choice == "2":
            for cam in cameras:
                print(f"\n{'=' * 70}")
                response = input(f"Test Camera {cam['index']}? (y/n): ").strip().lower()
                if response in ["y", "yes"]:
                    test_camera_individually(cam["index"])

        elif choice == "3":
            print("\n✅ Ready to run three-camera system!")
            print("\nRun this command:")
            print("    python demo_three_cameras.py")
            print("\nRecommended camera mapping:")
            print(f"    Camera 0 → ENTRY")
            print(f"    Camera 1 → EXIT")
            print(f"    Camera 2 → ROOM")

        else:
            print("\n✅ Exiting...")

    print("\n" + "=" * 70)
    print("  DEBUG SESSION COMPLETE")
    print("=" * 70)
    print("\nSummary:")
    print(f"  Cameras detected: {len(cameras)}")

    if len(cameras) >= 3:
        print("  Status: ✅ READY FOR THREE-CAMERA SYSTEM")
        print("\n  Next steps:")
        print("    1. Run: python demo_three_cameras.py")
        print("    2. Press 'e' to register at entry")
        print("    3. Test the full system")
    elif len(cameras) == 2:
        print("  Status: ⚠️  CAN RUN TWO-CAMERA SYSTEM")
        print("\n  Next steps:")
        print("    1. Connect the third camera (see CAMERA_SETUP_GUIDE.md)")
        print("    2. Or run: python demo_entry_room.py (2-camera mode)")
    else:
        print("  Status: ❌ NEED MORE CAMERAS")
        print("\n  Next steps:")
        print("    1. Follow CAMERA_SETUP_GUIDE.md")
        print("    2. Re-run this script")

    print("\n" + "=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
