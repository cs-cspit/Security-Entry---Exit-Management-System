#!/usr/bin/env python3
"""
SIMPLE ROOM CAMERA TEST - Multi-Person Detection
================================================

USE CASE: Test with MacBook webcam ONLY
- Detects ALL people in the room simultaneously
- Each person gets identified with OSNet + clothing features
- Shows KNOWN (green) vs UNKNOWN (red) people
- Simple and straightforward

WORKFLOW:
1. Stand in front of camera alone
2. Press 'r' to register yourself as Person 1
3. Have friend join you in frame
4. Press 'r' again to register them as Person 2
5. System will now show BOTH of you with different IDs in real-time

CONTROLS:
  r = Register NEW person (whoever is biggest in frame)
  q = Quit
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


def extract_face_histogram(frame, bbox):
    """Extract simple color histogram from face region."""
    x, y, w, h = bbox
    if w <= 0 or h <= 0 or y + h > frame.shape[0] or x + w > frame.shape[1]:
        return None

    face_img = frame[y : y + h, x : x + w]
    if face_img.size == 0:
        return None

    face_hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist(
        [face_hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256]
    )
    hist = hist.flatten()
    hist = hist / (np.sum(hist) + 1e-6)
    return hist


def main():
    print("\n" + "=" * 70)
    print("  SIMPLE MULTI-PERSON ROOM CAMERA TEST")
    print("=" * 70)
    print("\n✅ Using MacBook webcam to detect MULTIPLE people at once")
    print("✅ Each person gets unique ID based on OSNet + clothing features")
    print("✅ GREEN box = Known person | RED box = Unknown person\n")

    # Initialize with STRICT thresholds to prevent false positives
    print("🔧 Loading models...")
    face_detector = HybridFaceDetector()
    body_detector = YOLOv11BodyDetector()
    reid = EnhancedMultiModalReID(
        similarity_threshold=0.75,  # STRICT but not too harsh
        confidence_gap=0.20,  # LARGE GAP - must be clearly best match
        body_only_threshold=0.70,  # STRICT for body-only
        osnet_weight=0.70,  # INCREASE OSNet importance
        clothing_weight=0.10,  # REDUCE clothing (it's matching white tops!)
        face_weight=0.15,  # Face is less reliable with angles
        skin_weight=0.05,  # Minimal skin weight
    )
    print("✅ Models loaded with STRICT matching thresholds!\n")

    # Open camera
    print("📷 Opening MacBook built-in camera...")
    cap = cv2.VideoCapture(1)  # Index 1 = MacBook built-in camera
    if not cap.isOpened():
        print("❌ Cannot open camera! Trying index 0...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Cannot open camera! Check permissions.")
            return

    # Set lower resolution for better performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    print("✅ Camera ready! (320x240 for SPEED)\n")

    print("=" * 70)
    print("INSTRUCTIONS:")
    print("  1. Stand alone in frame → Press 'r' to register yourself")
    print("  2. Have friend join → Press 'r' to register them")
    print("  3. System will identify BOTH of you simultaneously!")
    print("  4. Press 'q' to quit")
    print("=" * 70 + "\n")

    person_count = 0
    frame_skip = 0  # Process every 3rd frame for speed
    last_display = None  # Cache last processed display frame
    last_detections = []  # Cache last detections

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Process detections every 3rd frame only (huge speed boost!)
        frame_skip += 1
        should_process = frame_skip % 3 == 0

        if not should_process:
            # Just show cached display and handle keys
            if last_display is not None:
                cv2.imshow("Room Camera - Multi-Person Test", last_display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("\n👋 Stopping...")
                break
            continue

        # Resize frame for MUCH faster processing (160x120!)
        small_frame = cv2.resize(frame, (160, 120))
        display = frame.copy()

        # Draw FPS counter
        cv2.putText(
            display,
            f"Processing every 3rd frame | Detection: 160x120",
            (10, display.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (100, 100, 100),
            1,
        )

        # Detect everyone in frame
        # Detect on smaller frame for speed
        # faces: List of (x, y, w, h, confidence)
        # bodies: List of (x, y, w, h, confidence)
        faces_small = face_detector.detect(small_frame)
        bodies_small = body_detector.detect(small_frame)

        # Scale detections back to original frame size
        scale_x = frame.shape[1] / small_frame.shape[1]
        scale_y = frame.shape[0] / small_frame.shape[0]

        faces = [
            (
                int(x * scale_x),
                int(y * scale_y),
                int(w * scale_x),
                int(h * scale_y),
                conf,
            )
            for x, y, w, h, conf in faces_small
        ]
        bodies = [
            (
                int(x * scale_x),
                int(y * scale_y),
                int(w * scale_x),
                int(h * scale_y),
                conf,
            )
            for x, y, w, h, conf in bodies_small
        ]

        # Process each body detection
        identified_people = []

        for body_tuple in bodies:
            bx, by, bw, bh, body_conf = body_tuple

            # Find face that overlaps with this body (if any)
            matching_face = None
            for face_tuple in faces:
                fx, fy, fw, fh, face_conf = face_tuple
                # Check if face is in upper part of body
                if fx >= bx and fx + fw <= bx + bw and fy >= by and fy < by + bh // 2:
                    matching_face = face_tuple
                    break

            # Try to identify this person
            person_id = None
            similarity = 0.0
            debug_info = None

            if matching_face:
                # Have face + body
                fx, fy, fw, fh, face_conf = matching_face
                face_bbox = (fx, fy, fw, fh)
                body_bbox = (bx, by, bw, bh)

                face_hist = extract_face_histogram(frame, face_bbox)
                if face_hist is not None:
                    person_id, similarity, debug_info = reid.match_person(
                        image=frame,
                        face_features=face_hist,
                        face_bbox=face_bbox,
                        body_bbox=body_bbox,
                        mode="auto",
                    )

                # PRINT DEBUG INFO - face+body
                if debug_info and "all_scores" in debug_info:
                    print(f"\n{'=' * 70}")
                    print(f"🔍 MATCH ATTEMPT (face+body) - Frame {frame_skip}")

                    # Sort by combined score to see ranking
                    ranked = []
                    for pid in debug_info["all_scores"]:
                        scores = debug_info["all_scores"][pid]
                        osnet_score = scores.get("osnet") or 0.0
                        clothing_score = scores.get("clothing") or 0.0
                        face_score = scores.get("face") or 0.0
                        skin_score = scores.get("skin") or 0.0
                        combined = (
                            osnet_score * reid.osnet_weight
                            + clothing_score * reid.clothing_weight
                            + face_score * reid.face_weight
                            + skin_score * reid.skin_weight
                        )
                        ranked.append(
                            (
                                pid,
                                combined,
                                osnet_score,
                                clothing_score,
                                face_score,
                                skin_score,
                            )
                        )

                    ranked.sort(key=lambda x: x[1], reverse=True)

                    for i, (pid, combined, osnet, cloth, face, skin) in enumerate(
                        ranked
                    ):
                        match_str = "✅ MATCHED" if pid == person_id else "❌ Rejected"
                        print(f"\n{match_str}: {pid} (combined: {combined:.3f})")
                        print(
                            f"   OSNet:    {osnet:.3f} × {reid.osnet_weight:.2f} = {osnet * reid.osnet_weight:.3f}"
                        )
                        print(
                            f"   Clothing: {cloth:.3f} × {reid.clothing_weight:.2f} = {cloth * reid.clothing_weight:.3f}"
                        )
                        print(
                            f"   Face:     {face:.3f} × {reid.face_weight:.2f} = {face * reid.face_weight:.3f}"
                        )
                        print(
                            f"   Skin:     {skin:.3f} × {reid.skin_weight:.2f} = {skin * reid.skin_weight:.3f}"
                        )

                        # Show registered person's clothing for comparison
                        if pid in reid.people and reid.people[pid].get("clothing"):
                            colors = reid.people[pid]["clothing"].get(
                                "dominant_colors", []
                            )[:2]
                            print(f"   Registered colors: {colors}")

                if not person_id:
                    print(
                        f"\n⚠️ NO MATCH - Below threshold (0.75) or gap too small (0.20)"
                    )
                else:
                    print(
                        f"\n✅ FINAL MATCH: {person_id} with similarity {similarity:.3f}"
                    )
                print(f"{'=' * 70}\n")
            else:
                # Body only
                body_bbox = (bx, by, bw, bh)
                person_id, similarity, debug_info = reid.match_person(
                    image=frame,
                    face_features=None,
                    face_bbox=None,
                    body_bbox=body_bbox,
                    mode="body_only",
                )

                # PRINT DEBUG INFO - body only
                if debug_info and "all_scores" in debug_info:
                    print(f"\n{'=' * 70}")
                    print(f"🔍 MATCH ATTEMPT (body only) - Frame {frame_skip}")

                    # Sort by combined score
                    ranked = []
                    for pid in debug_info["all_scores"]:
                        scores = debug_info["all_scores"][pid]
                        osnet_score = scores.get("osnet") or 0.0
                        clothing_score = scores.get("clothing") or 0.0
                        combined = (
                            osnet_score * reid.osnet_weight
                            + clothing_score * reid.clothing_weight
                        )
                        ranked.append((pid, combined, osnet_score, clothing_score))

                    ranked.sort(key=lambda x: x[1], reverse=True)

                    for pid, combined, osnet, cloth in ranked:
                        match_str = "✅ MATCHED" if pid == person_id else "❌ Rejected"
                        print(f"\n{match_str}: {pid} (combined: {combined:.3f})")
                        print(
                            f"   OSNet:    {osnet:.3f} × {reid.osnet_weight:.2f} = {osnet * reid.osnet_weight:.3f}"
                        )
                        print(
                            f"   Clothing: {cloth:.3f} × {reid.clothing_weight:.2f} = {cloth * reid.clothing_weight:.3f}"
                        )

                        # Show registered person's clothing
                        if pid in reid.people and reid.people[pid].get("clothing"):
                            colors = reid.people[pid]["clothing"].get(
                                "dominant_colors", []
                            )[:2]
                            print(f"   Registered colors: {colors}")

                if not person_id:
                    print(f"\n⚠️ NO MATCH - Below threshold (0.70) or gap too small")
                else:
                    print(
                        f"\n✅ FINAL MATCH: {person_id} with similarity {similarity:.3f}"
                    )
                print(f"{'=' * 70}\n")

            identified_people.append(
                {
                    "body": body_tuple,
                    "face": matching_face,
                    "person_id": person_id,
                    "similarity": similarity,
                }
            )

        # Draw boxes for each person
        known = 0
        unknown = 0

        for person in identified_people:
            # Determine color and label
            if person["person_id"]:
                color = (0, 255, 0)  # GREEN = Known
                label = person["person_id"]
                confidence_text = f" ({person['similarity']:.2f})"
                known += 1
            else:
                color = (0, 0, 255)  # RED = Unknown
                label = "UNKNOWN"
                confidence_text = ""
                unknown += 1

            # Draw body box
            bx, by, bw, bh, body_conf = person["body"]
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), color, 3)

            # Draw label
            label_text = label + confidence_text
            cv2.putText(
                display,
                label_text,
                (bx, by - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                color,
                3,
            )

            # Draw face box if present
            if person["face"]:
                fx, fy, fw, fh, face_conf = person["face"]
                cv2.rectangle(display, (fx, fy), (fx + fw, fy + fh), color, 2)

        # Status overlay
        cv2.rectangle(display, (0, 0), (750, 110), (0, 0, 0), -1)
        cv2.putText(
            display,
            f"Registered: {len(reid.people)} | Detected: {len(identified_people)}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            display,
            f"Known: {known} | Unknown: {unknown} | Threshold: 0.75",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0) if known > 0 else (255, 255, 255),
            2,
        )
        cv2.putText(
            display,
            "R: Register (stand closest) | Q: Quit",
            (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            2,
        )
        cv2.putText(
            display,
            f"OSNet weight: 70% | Clothing: 10%",
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (150, 150, 150),
            1,
        )

        # Cache this display frame
        last_display = display
        cv2.imshow("Room Camera - Multi-Person Test", display)

        key = cv2.waitKey(1) & 0xFF

        # Register person
        if key == ord("r"):
            if len(faces) > 0 and len(bodies) > 0:
                person_count += 1
                person_id = f"PERSON_{person_count}"

                # Register the largest person
                largest_face = max(faces, key=lambda f: f[2] * f[3])  # w * h
                largest_body = max(bodies, key=lambda b: b[2] * b[3])  # w * h

                fx, fy, fw, fh, face_conf = largest_face
                bx, by, bw, bh, body_conf = largest_body

                face_bbox = (fx, fy, fw, fh)
                body_bbox = (bx, by, bw, bh)

                face_hist = extract_face_histogram(frame, face_bbox)

                if face_hist is not None:
                    print(f"\n⏳ Registering {person_id}...")
                    print(f"   (Extracting OSNet features - takes 2-3 seconds)")
                    success = reid.register_person(
                        person_id=person_id,
                        image=frame,
                        face_features=face_hist,
                        face_bbox=face_bbox,
                        body_bbox=body_bbox,
                        metadata={"name": f"Person {person_count}"},
                    )

                    if success:
                        print(f"✅ Registered: {person_id}")
                        features = reid.people[person_id]

                        # Show what we extracted
                        if features.get("clothing"):
                            colors = features["clothing"].get("dominant_colors", [])[:3]
                            pattern = features["clothing"].get("pattern", "unknown")
                            print(f"   Clothing: {colors} | Pattern: {pattern}")

                        if features.get("osnet") is not None:
                            osnet_norm = np.linalg.norm(features["osnet"])
                            print(
                                f"   OSNet: {features['osnet'].shape} (norm={osnet_norm:.2f})"
                            )

                        if features.get("skin_tone") is not None:
                            skin = features["skin_tone"]
                            print(
                                f"   Skin: H={skin[0]:.0f} S={skin[1]:.0f} V={skin[2]:.0f}"
                            )

                        print(f"   Total registered: {len(reid.people)}\n")
                    else:
                        print(f"❌ Failed to register {person_id}")
            else:
                print("⚠️  Need face + body in frame to register!")

        # Quit
        elif key == ord("q"):
            print("\n👋 Stopping...")
            break

    cap.release()
    cv2.destroyAllWindows()

    print("\n" + "=" * 70)
    print(f"SESSION COMPLETE!")
    print(f"  People registered: {len(reid.people)}")
    if reid.people:
        print("\n  Registered IDs:")
        for pid in reid.people.keys():
            print(f"    - {pid}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
