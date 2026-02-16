#!/usr/bin/env python3
"""
Simple Camera Test Script
==========================
Non-interactive camera detection and preview.
"""

import sys

import cv2

print("\n" + "=" * 60)
print("SIMPLE CAMERA TEST")
print("=" * 60)

# Test cameras 0-5
cameras = []
for i in range(6):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            print(f"\n✅ Camera {i}:")
            print(f"   Resolution: {w}x{h}")
            print(f"   FPS: {fps:.1f}")
            cameras.append({"index": i, "cap": cap, "w": w, "h": h})
        else:
            cap.release()
    else:
        cap.release()

print(f"\n{'-' * 60}")
print(f"Total cameras detected: {len(cameras)}")
print(f"{'-' * 60}")

if len(cameras) < 2:
    print("\n❌ Need at least 2 cameras!")
    print("   Make sure both phones are connected via Iriun.")
    for cam in cameras:
        cam["cap"].release()
    sys.exit(1)

print("\n📹 Opening preview windows...")
print("Press 'q' to quit\n")

# Preview loop
try:
    frame_count = 0
    while True:
        for cam_info in cameras:
            ret, frame = cam_info["cap"].read()
            if ret:
                # Resize for display
                frame = cv2.resize(frame, (640, 480))

                # Add label
                cv2.putText(
                    frame,
                    f"Camera {cam_info['index']}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                )

                cv2.imshow(f"Camera {cam_info['index']}", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            print("\n✅ Closing...")
            break

        frame_count += 1
        if frame_count % 100 == 0:
            print(f"Frame {frame_count}...")

except KeyboardInterrupt:
    print("\n\n⚠️  Interrupted")

finally:
    for cam_info in cameras:
        cam_info["cap"].release()
    cv2.destroyAllWindows()

print("\n" + "=" * 60)
print("CAMERA ASSIGNMENT RECOMMENDATION:")
print("=" * 60)
if len(cameras) >= 3:
    print("\n✅ 3 cameras detected - PERFECT!")
    print("\n   Suggested mapping:")
    print("   - Camera 0 (MacBook webcam) → ROOM camera")
    print("   - Camera 1 (Phone 1) → ENTRY camera")
    print("   - Camera 2 (Phone 2) → EXIT camera")
elif len(cameras) == 2:
    print("\n⚠️  Only 2 cameras detected")
    print("\n   Current 2-camera setup (working):")
    print("   - Camera 0 → One gate")
    print("   - Camera 1 → Other gate")
    print("\n   For 3-camera system, connect the second phone.")
else:
    print("\n✅ 1 camera")

print("=" * 60 + "\n")
