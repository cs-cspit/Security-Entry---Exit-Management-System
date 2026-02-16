#!/usr/bin/env python3
"""
Camera Detection Script
=======================
Detects all available cameras and displays their feed.
Helps identify which camera index corresponds to which physical camera.

Usage:
    python scripts/detect_cameras.py
"""

import sys
from datetime import datetime

import cv2


def detect_cameras(max_cameras=10):
    """
    Scan for available cameras and display their properties.

    Args:
        max_cameras: Maximum number of camera indices to test

    Returns:
        List of available camera indices
    """
    print("\n" + "=" * 60)
    print("CAMERA DETECTION SCRIPT")
    print("=" * 60)
    print(f"\nScanning camera indices 0-{max_cameras - 1}...\n")

    available_cameras = []

    for index in range(max_cameras):
        cap = cv2.VideoCapture(index)

        if cap.isOpened():
            # Try to read a frame
            ret, frame = cap.read()

            if ret:
                # Get camera properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)

                print(f"✅ Camera {index} FOUND:")
                print(f"   - Resolution: {width}x{height}")
                print(f"   - FPS: {fps:.1f}")
                print(f"   - Backend: {cap.getBackendName()}")

                available_cameras.append(
                    {"index": index, "width": width, "height": height, "fps": fps}
                )

            cap.release()

    if not available_cameras:
        print("❌ No cameras detected!")
        return []

    print(f"\n{'=' * 60}")
    print(f"Total cameras found: {len(available_cameras)}")
    print(f"{'=' * 60}\n")

    return available_cameras


def preview_cameras(camera_indices):
    """
    Show live preview from all detected cameras simultaneously.

    Args:
        camera_indices: List of camera index dictionaries
    """
    if not camera_indices:
        print("No cameras to preview!")
        return

    print("\n" + "=" * 60)
    print("CAMERA PREVIEW MODE")
    print("=" * 60)
    print("\nOpening all cameras for preview...")
    print("\nControls:")
    print("  - Press 'q' to quit")
    print("  - Press '0', '1', '2'... to label cameras")
    print("=" * 60 + "\n")

    # Open all cameras
    cameras = []
    for cam_info in camera_indices:
        cap = cv2.VideoCapture(cam_info["index"])
        if cap.isOpened():
            cameras.append(
                {
                    "index": cam_info["index"],
                    "capture": cap,
                    "label": f"Camera {cam_info['index']}",
                }
            )

    if not cameras:
        print("❌ Failed to open cameras!")
        return

    # Labels for user assignment
    camera_labels = {"0": "ENTRY", "1": "EXIT", "2": "ROOM"}

    print(f"✅ Opened {len(cameras)} camera(s)\n")

    frame_count = 0

    try:
        while True:
            frames = []

            # Read from all cameras
            for cam in cameras:
                ret, frame = cam["capture"].read()
                if ret:
                    # Resize for display
                    frame = cv2.resize(frame, (640, 480))

                    # Add camera label
                    cv2.putText(
                        frame,
                        cam["label"],
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 0),
                        2,
                    )

                    # Add index number
                    cv2.putText(
                        frame,
                        f"Index: {cam['index']}",
                        (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2,
                    )

                    # Add timestamp
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    cv2.putText(
                        frame,
                        timestamp,
                        (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                    )

                    frames.append(frame)
                else:
                    print(f"⚠️  Failed to read from camera {cam['index']}")

            if not frames:
                print("❌ No frames to display!")
                break

            # Display frames
            if len(frames) == 1:
                cv2.imshow("Camera 0", frames[0])
            elif len(frames) == 2:
                cv2.imshow("Camera 0", frames[0])
                cv2.imshow("Camera 1", frames[1])
            elif len(frames) == 3:
                cv2.imshow("Camera 0", frames[0])
                cv2.imshow("Camera 1", frames[1])
                cv2.imshow("Camera 2", frames[2])
            else:
                # More than 3 cameras - stack them
                for i, frame in enumerate(frames):
                    cv2.imshow(f"Camera {i}", frame)

            # Handle key press
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("\n✅ Exiting preview mode...")
                break
            elif key == ord("0") and len(cameras) > 0:
                cameras[0]["label"] = "ENTRY Camera"
                print("✅ Camera 0 labeled as ENTRY")
            elif key == ord("1") and len(cameras) > 1:
                cameras[1]["label"] = "EXIT Camera"
                print("✅ Camera 1 labeled as EXIT")
            elif key == ord("2") and len(cameras) > 2:
                cameras[2]["label"] = "ROOM Camera"
                print("✅ Camera 2 labeled as ROOM")
            elif key == ord("r"):
                # Reset labels
                for cam in cameras:
                    cam["label"] = f"Camera {cam['index']}"
                print("✅ Labels reset")

            frame_count += 1

            # Print status every 30 frames
            if frame_count % 30 == 0:
                print(f"📹 Displaying frames... (frame {frame_count})")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user (Ctrl+C)")

    finally:
        # Release all cameras
        for cam in cameras:
            cam["capture"].release()
        cv2.destroyAllWindows()

        print("\n" + "=" * 60)
        print("CAMERA PREVIEW CLOSED")
        print("=" * 60)

        # Print final camera assignments
        print("\n📋 Final Camera Assignments:")
        for cam in cameras:
            print(f"   Camera {cam['index']}: {cam['label']}")
        print()


def save_camera_config(cameras, filepath="configs/detected_cameras.txt"):
    """
    Save detected camera configuration to file.

    Args:
        cameras: List of camera info dictionaries
        filepath: Path to save configuration
    """
    try:
        with open(filepath, "w") as f:
            f.write("# Detected Camera Configuration\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for cam in cameras:
                f.write(f"Camera {cam['index']}:\n")
                f.write(f"  Resolution: {cam['width']}x{cam['height']}\n")
                f.write(f"  FPS: {cam['fps']:.1f}\n\n")

        print(f"✅ Camera configuration saved to: {filepath}")
    except Exception as e:
        print(f"❌ Failed to save configuration: {e}")


def main():
    """Main function."""
    print("\n🎥 Camera Detection & Preview Tool")
    print("For: Intelligence-Led Entry & Exit Management System")
    print()

    # Step 1: Detect cameras
    detected_cameras = detect_cameras(max_cameras=10)

    if not detected_cameras:
        print("\n❌ No cameras detected. Please check:")
        print("   1. Cameras are connected")
        print("   2. Iriun app is running (for phone cameras)")
        print("   3. Camera permissions are granted")
        sys.exit(1)

    # Step 2: Save configuration
    save_camera_config(detected_cameras)

    # Step 3: Ask user if they want to preview
    print("\n" + "=" * 60)
    response = input("Do you want to preview the cameras? (y/n): ").strip().lower()

    if response == "y" or response == "yes":
        preview_cameras(detected_cameras)
    else:
        print("\n✅ Camera detection complete!")
        print("\nDetected camera indices:")
        for cam in detected_cameras:
            print(f"   - Camera {cam['index']}: {cam['width']}x{cam['height']}")
        print("\nYou can now configure these in configs/system_config.yaml")

    print("\n" + "=" * 60)
    print("RECOMMENDED CONFIGURATION:")
    print("=" * 60)
    if len(detected_cameras) >= 3:
        print("\n✅ You have 3+ cameras! Suggested mapping:")
        print(f"   Camera 0 (MacBook): ROOM camera (monitoring)")
        print(f"   Camera 1 (Phone 1): ENTRY camera")
        print(f"   Camera 2 (Phone 2): EXIT camera")
    elif len(detected_cameras) == 2:
        print("\n⚠️  You have 2 cameras. Current 2-camera system will work.")
        print("   Need to connect 3rd camera for room monitoring.")
    else:
        print("\n⚠️  Only 1 camera detected.")
        print("   Need at least 2 cameras for entry/exit tracking.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
