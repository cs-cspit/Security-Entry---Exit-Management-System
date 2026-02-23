#!/usr/bin/env python3
"""
MULTI-PERSON ROOM MONITORING TEST
Tests enhanced re-ID with MULTIPLE people simultaneously in the frame

USE CASE: MacBook webcam as ROOM CAMERA
- Detects ALL people in frame at once
- Shows each person's ID and similarity score
- Color-coded boxes: GREEN = known, RED = unknown
- Real-time tracking and identification

CONTROLS:
  'r' - Register NEW person (whoever is largest in frame)
  's' - Show registered people summary
  'c' - Clear all registered people
  'q' - Quit
"""

import sys
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detectors.hybrid_face_detector import HybridFaceDetector
from detectors.yolov11_body_detector import YOLOv11BodyDetector
from enhanced_reid import EnhancedMultiModalReID


def draw_bbox_with_label(frame, bbox, label, color, confidence=None):
    """Draw bounding box with label and optional confidence."""
    x, y, w, h = bbox

    # Draw rectangle
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

    # Prepare label text
    if confidence is not None:
        text = f"{label} ({confidence:.2f})"
    else:
        text = label

    # Calculate text size for background
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    # Draw background rectangle for text
    cv2.rectangle(
        frame, (x, y - text_h - baseline - 10), (x + text_w + 10, y), color, -1
    )

    # Draw text
    cv2.putText(
        frame,
        text,
        (x + 5, y - baseline - 5),
        font,
        font_scale,
        (255, 255, 255),
        thickness,
    )


def match_face_to_body(faces, bodies, iou_threshold=0.3):
    """
    Match faces to bodies based on spatial overlap.
    Returns list of (face, body) pairs.
    """
    pairs = []
    used_faces = set()
    used_bodies = set()

    # Calculate IoU for all face-body combinations
    matches = []
    for i, face in enumerate(faces):
        fx, fy, fw, fh = face["bbox"]
        for j, body in enumerate(bodies):
            bx, by, bw, bh = body["bbox"]

            # Calculate intersection
            x1 = max(fx, bx)
            y1 = max(fy, by)
            x2 = min(fx + fw, bx + bw)
            y2 = min(fy + fh, by + bh)

            if x2 > x1 and y2 > y1:
                intersection = (x2 - x1) * (y2 - y1)
                face_area = fw * fh
                body_area = bw * bh
                union = face_area + body_area - intersection
                iou = intersection / union if union > 0 else 0

                # Also check if face is roughly in upper part of body
                face_center_y = fy + fh / 2
                body_top_third = by + bh / 3

                if iou > iou_threshold or (
                    face_center_y < body_top_third and iou > 0.1
                ):
                    matches.append((i, j, iou))

    # Sort by IoU descending
    matches.sort(key=lambda x: x[2], reverse=True)

    # Greedily assign matches
    for face_idx, body_idx, iou in matches:
        if face_idx not in used_faces and body_idx not in used_bodies:
            pairs.append((faces[face_idx], bodies[body_idx]))
            used_faces.add(face_idx)
            used_bodies.add(body_idx)

    # Add unmatched faces (face only)
    for i, face in enumerate(faces):
        if i not in used_faces:
            pairs.append((face, None))

    # Add unmatched bodies (body only)
    for j, body in enumerate(bodies):
        if j not in used_bodies:
            pairs.append((None, body))

    return pairs


def extract_face_features(frame, bbox):
    """Extract simple histogram features from face region."""
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return None

    face_img = frame[y : y + h, x : x + w]
    if face_img.size == 0:
        return None

    face_hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
    face_hist = cv2.calcHist(
        [face_hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256]
    )
    face_hist = face_hist.flatten()
    face_hist = face_hist / (np.sum(face_hist) + 1e-6)
    return face_hist


def main():
    print("=" * 80)
    print(" MULTI-PERSON ROOM MONITORING TEST")
    print("=" * 80)
    print()
    print("This script demonstrates:")
    print("  ✅ Detecting MULTIPLE people simultaneously")
    print("  ✅ OSNet body embeddings for each person")
    print("  ✅ Clothing + Skin tone analysis")
    print("  ✅ Real-time identification")
    print("  ✅ Color-coded display (GREEN=known, RED=unknown)")
    print()
    print("=" * 80)
    print()

    # Initialize detectors
    print("🔧 Initializing detectors...")
    try:
        face_detector = HybridFaceDetector()
        body_detector = YOLOv11BodyDetector()
        reid_system = EnhancedMultiModalReID()
        print("✅ All systems initialized!")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return

    # Open camera
    print("🎥 Opening MacBook built-in camera...")
    cap = cv2.VideoCapture(1)  # Index 1 = MacBook built-in camera

    if not cap.isOpened():
        print("❌ Failed to open camera!")
        print("   Check camera permissions in System Preferences")
        return

    print("✅ Camera opened successfully!")
    print()

    # Print instructions
    print("=" * 80)
    print(" CONTROLS")
    print("=" * 80)
    print()
    print("  'r' - REGISTER new person (largest detection)")
    print("  's' - SHOW registered people summary")
    print("  'c' - CLEAR all registered people")
    print("  'q' - QUIT")
    print()
    print("=" * 80)
    print()
    print("🚀 Starting room monitoring...")
    print()

    registered_count = 0
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Failed to read frame")
            break

        frame_count += 1
        display = frame.copy()

        # Detect all faces and bodies
        faces = face_detector.detect(frame)
        bodies = body_detector.detect(frame)

        # Match faces to bodies
        person_detections = match_face_to_body(faces, bodies)

        # Process each detected person
        detected_people = []
        for face, body in person_detections:
            if face is None and body is None:
                continue

            # Try to identify this person
            person_info = {
                "face": face,
                "body": body,
                "person_id": None,
                "similarity": 0.0,
                "is_known": False,
            }

            # Extract features and match
            if face is not None and body is not None:
                # Have both face and body
                face_features = extract_face_features(frame, face["bbox"])

                if face_features is not None:
                    person_id, similarity, debug_info = reid_system.match_person(
                        image=frame,
                        face_features=face_features,
                        face_bbox=face["bbox"],
                        body_bbox=body["bbox"],
                        mode="auto",
                    )

                    person_info["person_id"] = person_id
                    person_info["similarity"] = similarity
                    person_info["is_known"] = person_id is not None

            elif body is not None:
                # Body only (no face visible)
                face_features = None
                person_id, similarity, debug_info = reid_system.match_person(
                    image=frame,
                    face_features=None,
                    face_bbox=None,
                    body_bbox=body["bbox"],
                    mode="body_only",
                )

                person_info["person_id"] = person_id
                person_info["similarity"] = similarity
                person_info["is_known"] = person_id is not None

            detected_people.append(person_info)

        # Draw all detections
        known_count = 0
        unknown_count = 0

        for person in detected_people:
            # Determine display info
            if person["is_known"]:
                color = (0, 255, 0)  # GREEN for known
                label = person["person_id"]
                confidence = person["similarity"]
                known_count += 1
            else:
                color = (0, 0, 255)  # RED for unknown
                label = "UNKNOWN"
                confidence = None
                unknown_count += 1

            # Draw face box if available
            if person["face"] is not None:
                draw_bbox_with_label(
                    display,
                    person["face"]["bbox"],
                    f"{label} (face)",
                    color,
                    confidence,
                )

            # Draw body box if available
            if person["body"] is not None:
                bbox = person["body"]["bbox"]
                x, y, w, h = bbox

                # Draw body rectangle
                cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)

                # Add body label at bottom of bbox
                body_label = f"{label} (body)"
                if confidence is not None:
                    body_label = f"{label} ({confidence:.2f})"

                cv2.putText(
                    display,
                    body_label,
                    (x, y + h + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

        # Display status bar
        status_bg_color = (50, 50, 50)
        cv2.rectangle(display, (0, 0), (display.shape[1], 100), status_bg_color, -1)

        cv2.putText(
            display,
            f"Registered: {len(reid_system.people)} | Detected: {len(detected_people)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            f"Known: {known_count} | Unknown: {unknown_count}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0) if known_count > 0 else (255, 255, 255),
            2,
        )

        cv2.putText(
            display,
            "R: Register | S: Summary | C: Clear | Q: Quit",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            2,
        )

        cv2.imshow("Multi-Person Room Monitor", display)

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF

        # Register largest person
        if key == ord("r"):
            if len(faces) > 0 and len(bodies) > 0:
                registered_count += 1
                person_id = f"ROOM_P{registered_count:03d}"

                # Get largest face and body
                face = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
                body = max(bodies, key=lambda b: b["bbox"][2] * b["bbox"][3])

                # Extract face features
                face_features = extract_face_features(frame, face["bbox"])

                if face_features is not None:
                    # Register
                    success = reid_system.register_person(
                        person_id=person_id,
                        image=frame,
                        face_features=face_features,
                        face_bbox=face["bbox"],
                        body_bbox=body["bbox"],
                        metadata={"name": f"Person {registered_count}"},
                    )

                    if success:
                        print(f"✅ Registered {person_id}")

                        # Print feature summary
                        features = reid_system.people[person_id]
                        if features.get("clothing"):
                            clothing = features["clothing"]
                            print(
                                f"   Clothing colors: {clothing.get('dominant_colors', [])[:3]}"
                            )
                            print(f"   Pattern: {clothing.get('pattern', 'N/A')}")
                        if features.get("skin_tone"):
                            skin = features["skin_tone"]
                            print(
                                f"   Skin tone: H={skin[0]:.0f} S={skin[1]:.0f} V={skin[2]:.0f}"
                            )
                        print()
                    else:
                        print(f"❌ Failed to register {person_id}")
            else:
                print("⚠️ Need both face and body to register!")

        # Show summary
        elif key == ord("s"):
            print()
            print("=" * 80)
            print(" REGISTERED PEOPLE SUMMARY")
            print("=" * 80)
            print()

            if len(reid_system.people) == 0:
                print("  No one registered yet. Press 'r' to register.")
            else:
                for person_id, features in reid_system.people.items():
                    print(f"📋 {person_id}:")

                    if features.get("clothing"):
                        clothing = features["clothing"]
                        colors = clothing.get("dominant_colors", [])[:3]
                        print(f"   Colors: {colors}")
                        print(f"   Pattern: {clothing.get('pattern', 'unknown')}")

                    if features.get("skin_tone") is not None:
                        skin = features["skin_tone"]
                        print(
                            f"   Skin: H={skin[0]:.0f}° S={skin[1]:.0f}% V={skin[2]:.0f}%"
                        )

                    if features.get("osnet") is not None:
                        print(
                            f"   OSNet: {features['osnet'].shape} (norm={np.linalg.norm(features['osnet']):.2f})"
                        )

                    print()

            print("=" * 80)
            print()

        # Clear all registered
        elif key == ord("c"):
            reid_system.people.clear()
            registered_count = 0
            print("🗑️  Cleared all registered people")
            print()

        # Quit
        elif key == ord("q"):
            print()
            print("👋 Stopping room monitoring...")
            break

    cap.release()
    cv2.destroyAllWindows()

    print()
    print("=" * 80)
    print(" SESSION SUMMARY")
    print("=" * 80)
    print(f"  Total frames processed: {frame_count}")
    print(f"  People registered: {len(reid_system.people)}")
    print()
    print("✅ Test complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
