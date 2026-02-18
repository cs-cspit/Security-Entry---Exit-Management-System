#!/usr/bin/env python3
"""
EMERGENCY DEBUG SCRIPT - False Positive Detection
Tests why different people are matching to same ID
"""

import sys
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detectors.hybrid_face_detector import HybridFaceDetector
from detectors.yolov11_body_detector import YOLOv11BodyDetector
from multi_modal_reid import MultiModalReID


def test_two_people():
    """Test if two different people match incorrectly."""
    print("=" * 80)
    print("EMERGENCY FALSE POSITIVE DEBUG TEST")
    print("=" * 80)
    print()
    print("This script will help diagnose why different people match to same ID")
    print()

    # Initialize detectors
    print("🔧 Initializing detectors...")
    try:
        face_detector = HybridFaceDetector(
            model_path="yolov8n-face.pt", confidence_threshold=0.5, device="auto"
        )
        body_detector = YOLOv11BodyDetector(
            model_path="yolo11n.pt", confidence_threshold=0.5, device="auto"
        )
        print("✅ Detectors initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize detectors: {e}")
        return

    # Initialize re-ID with CURRENT thresholds
    reid_system = MultiModalReID(
        face_weight=0.6,
        body_weight=0.4,
        similarity_threshold=0.65,
        confidence_gap=0.05,
        body_only_threshold=0.60,
    )
    print()

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return

    print("=" * 80)
    print("TEST PROCEDURE:")
    print("=" * 80)
    print()
    print("STEP 1: Register Person A (YOU)")
    print("  - Position yourself in front of camera")
    print("  - Press 'r' to register as Person A")
    print()
    print("STEP 2: Register Person B (YOUR FRIEND)")
    print("  - Have your friend stand in front of camera")
    print("  - Press 'r' again to register as Person B")
    print()
    print("STEP 3: Test Matching")
    print("  - Person A appears → Press SPACE to test")
    print("  - Person B appears → Press SPACE to test")
    print("  - System will show if they match to correct ID")
    print()
    print("Press 'q' to quit")
    print("=" * 80)
    print()

    registered_people = {}
    person_counter = 0

    test_mode = False
    test_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display_frame = frame.copy()

        # Detect faces and bodies
        face_detections = face_detector.detect(frame)
        body_detections = body_detector.detect(frame)

        # Draw detections
        for x, y, w, h, conf in face_detections:
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            cv2.putText(
                display_frame,
                f"Face: {conf:.2f}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                2,
            )

        for x, y, w, h, conf in body_detections:
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (255, 150, 0), 2)
            cv2.putText(
                display_frame,
                f"Body: {conf:.2f}",
                (x, y + h + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 150, 0),
                2,
            )

        # Show status
        status_y = 30
        cv2.putText(
            display_frame,
            f"Registered: {len(registered_people)}",
            (10, status_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            display_frame,
            "Press 'r' to register | SPACE to test | 'q' to quit",
            (10, status_y + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        cv2.imshow("Emergency Debug - False Positive Test", display_frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("r"):
            # Register current person
            if len(body_detections) > 0 and len(face_detections) > 0:
                person_counter += 1
                person_id = f"TEST_P{person_counter:03d}"

                # Take first detection
                face_bbox = face_detections[0]
                body_bbox = body_detections[0]

                # Extract features
                fx, fy, fw, fh, _ = face_bbox
                bx, by, bw, bh, _ = body_bbox

                face_features = face_detector.extract_face_features(
                    frame, (fx, fy, fw, fh)
                )
                body_features = body_detector.extract_body_features(
                    frame, (bx, by, bw, bh)
                )

                # Create profile
                profile = reid_system.create_person_profile(
                    person_id=person_id,
                    face_features=face_features,
                    body_features=body_features,
                    face_bbox=(fx, fy, fw, fh),
                    body_bbox=(bx, by, bw, bh),
                )

                registered_people[person_id] = profile

                print("\n" + "=" * 80)
                print(f"✅ REGISTERED: {person_id}")
                print("=" * 80)
                print(f"Face bbox: ({fx}, {fy}, {fw}, {fh})")
                print(f"Body bbox: ({bx}, {by}, {bw}, {bh})")
                print(f"Face features shape: {face_features.shape}")
                print(
                    f"Body features keys: {list(body_features.keys()) if body_features else 'None'}"
                )
                print()

                # Show feature statistics
                print("📊 Feature Statistics:")
                if face_features is not None and len(face_features) > 0:
                    print(f"   Face histogram mean: {np.mean(face_features):.4f}")
                    print(f"   Face histogram std: {np.std(face_features):.4f}")
                    print(f"   Face histogram max: {np.max(face_features):.4f}")

                if body_features:
                    for key, feat in body_features.items():
                        if isinstance(feat, np.ndarray) and len(feat) > 0:
                            print(f"   {key} mean: {np.mean(feat):.4f}")
                            print(f"   {key} std: {np.std(feat):.4f}")

                print("=" * 80)
                print()

            else:
                print("❌ No face or body detected - move closer and try again")

        elif key == ord(" "):
            # Test matching
            if len(registered_people) == 0:
                print("⚠️ No registered people - press 'r' to register first")
                continue

            if len(body_detections) > 0:
                test_count += 1
                face_bbox = face_detections[0] if len(face_detections) > 0 else None
                body_bbox = body_detections[0]

                # Extract features
                bx, by, bw, bh, _ = body_bbox
                body_features = body_detector.extract_body_features(
                    frame, (bx, by, bw, bh)
                )

                face_features = None
                if face_bbox:
                    fx, fy, fw, fh, _ = face_bbox
                    face_features = face_detector.extract_face_features(
                        frame, (fx, fy, fw, fh)
                    )

                # Create query profile
                query_profile = reid_system.create_person_profile(
                    person_id="QUERY",
                    face_features=face_features,
                    body_features=body_features,
                    face_bbox=(fx, fy, fw, fh) if face_bbox else None,
                    body_bbox=(bx, by, bw, bh),
                )

                print("\n" + "=" * 80)
                print(f"🔍 MATCHING TEST #{test_count}")
                print("=" * 80)
                print(f"Query has face: {face_features is not None}")
                print(f"Query has body: {body_features is not None}")
                print()

                # Test against ALL registered people
                print("📊 SIMILARITY SCORES AGAINST ALL REGISTERED PEOPLE:")
                print("-" * 80)

                for pid, profile in registered_people.items():
                    similarity, details = reid_system.compare_profiles(
                        query_profile, profile, mode="auto"
                    )

                    face_sim = details.get("face_similarity", 0.0)
                    body_sim = details.get("body_similarity", 0.0)
                    mode_used = details.get("mode_used", "N/A")

                    print(f"\n{pid}:")
                    print(f"  Combined similarity: {similarity:.4f}")
                    print(f"  Face similarity:     {face_sim:.4f}")
                    print(f"  Body similarity:     {body_sim:.4f}")
                    print(f"  Mode used:           {mode_used}")

                    # Check thresholds
                    if body_sim >= reid_system.body_only_threshold:
                        print(
                            f"  ✅ Body matches (>= {reid_system.body_only_threshold})"
                        )
                    else:
                        print(
                            f"  ❌ Body doesn't match (< {reid_system.body_only_threshold})"
                        )

                    if similarity >= reid_system.similarity_threshold:
                        print(
                            f"  ✅ Combined matches (>= {reid_system.similarity_threshold})"
                        )
                    else:
                        print(
                            f"  ❌ Combined doesn't match (< {reid_system.similarity_threshold})"
                        )

                print()
                print("-" * 80)

                # Use is_match to see what system decides
                matched_id, best_sim, match_details = reid_system.is_match(
                    query_profile, registered_people, mode="auto"
                )

                print()
                print("🎯 FINAL DECISION:")
                if matched_id:
                    print(f"  ✅ MATCHED to: {matched_id}")
                    print(f"  Similarity: {best_sim:.4f}")
                    print(f"  Reason: {match_details.get('reason', 'N/A')}")
                    print(
                        f"  Matching mode: {match_details.get('matching_mode', 'N/A')}"
                    )
                    print(
                        f"  Threshold used: {match_details.get('threshold_used', 'N/A'):.4f}"
                    )
                    print()
                    print("🚨 CHECK: Is this the CORRECT person?")
                    print("   If this matched to WRONG person → FALSE POSITIVE BUG!")
                else:
                    print(f"  ❌ NO MATCH (similarity: {best_sim:.4f})")
                    print(f"  Reason: {match_details.get('reason', 'N/A')}")
                    print()
                    print("✅ Correctly rejected as unknown person")

                print("=" * 80)
                print()

            else:
                print("❌ No body detected - move into frame and try again")

    cap.release()
    cv2.destroyAllWindows()

    # Final summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Registered people: {len(registered_people)}")
    print(f"Tests performed: {test_count}")
    print()
    print("CRITICAL QUESTIONS:")
    print("1. Did Person A match to their own ID? (Should: YES)")
    print("2. Did Person B match to their own ID? (Should: YES)")
    print("3. Did Person A match to Person B's ID? (Should: NO)")
    print("4. Did Person B match to Person A's ID? (Should: NO)")
    print()
    print("If ANY of questions 3 or 4 is YES → FALSE POSITIVE BUG EXISTS!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    try:
        test_two_people()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback

        traceback.print_exc()
