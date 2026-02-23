#!/usr/bin/env python3
"""
ENHANCED EMERGENCY DEBUG SCRIPT
Tests OSNet + Clothing Analysis + Skin Tone for Person Re-ID
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


def print_separator(char="=", length=80):
    """Print separator line."""
    print(char * length)


def print_header(text):
    """Print section header."""
    print_separator()
    print(f" {text}")
    print_separator()
    print()


def print_features_summary(features, person_id):
    """Print detailed summary of extracted features."""
    print_header(f"✅ REGISTERED: {person_id}")

    # Print bounding boxes
    if features.get("face_bbox"):
        print(f"Face bbox: {features['face_bbox']}")
    if features.get("body_bbox"):
        print(f"Body bbox: {features['body_bbox']}")

    # Print OSNet features
    if features.get("osnet") is not None:
        print(f"OSNet features shape: {features['osnet'].shape}")
        print(f"OSNet norm: {np.linalg.norm(features['osnet']):.4f}")
    else:
        print("OSNet features: Not available")

    # Print clothing features
    if features.get("clothing") is not None:
        clothing = features["clothing"]
        print(f"\n📊 Clothing Analysis:")
        print(f"   Upper colors: {clothing['upper_color_names']}")
        print(f"   Lower colors: {clothing['lower_color_names']}")
        print(
            f"   Upper pattern: {clothing['upper_pattern']['type']} "
            f"(confidence: {clothing['upper_pattern']['confidence']:.2f})"
        )
        print(
            f"   Lower pattern: {clothing['lower_pattern']['type']} "
            f"(confidence: {clothing['lower_pattern']['confidence']:.2f})"
        )
        print(f"   Upper brightness: {clothing['upper_brightness']:.1f}")
        print(f"   Lower brightness: {clothing['lower_brightness']:.1f}")

        # Print skin tone
        if clothing.get("skin_tone"):
            skin = clothing["skin_tone"]
            print(f"\n🎨 Skin Tone:")
            print(f"   Tone: {skin['tone']}")
            print(f"   HSV: H={skin['hue']}, S={skin['saturation']}, V={skin['value']}")
            print(f"   BGR: {skin['bgr']}")
        else:
            print(f"\n🎨 Skin Tone: Not detected")

        print(
            f"\n📐 Appearance signature shape: {clothing['appearance_signature'].shape}"
        )
    else:
        print("Clothing features: Not available")

    # Print face features
    if features.get("face") is not None:
        print(f"\n👤 Face features shape: {features['face'].shape}")
    else:
        print("\n👤 Face features: Not available")

    print_separator()
    print()


def print_matching_results(person_id, similarity, debug_info, match_count):
    """Print detailed matching test results."""
    print_header(f"🔍 MATCHING TEST #{match_count}")

    print(f"Query has face: {debug_info['all_scores'].get('face') is not None}")
    print(f"Query has OSNet: {debug_info['all_scores'].get('osnet') is not None}")
    print(f"Query has clothing: {debug_info['all_scores'].get('clothing') is not None}")
    print()

    print("📊 SIMILARITY SCORES AGAINST ALL REGISTERED PEOPLE:")
    print_separator("-")
    print()

    # Print scores for each registered person
    for pid, scores in debug_info["all_scores"].items():
        print(f"{pid}:")
        print(
            f"  Combined similarity: {debug_info['all_scores'][pid].get('combined', 0.0):.4f}"
        )

        if scores.get("osnet") is not None:
            print(f"  OSNet similarity:    {scores['osnet']:.4f}")
        else:
            print(f"  OSNet similarity:    N/A")

        if scores.get("clothing") is not None:
            print(f"  Clothing similarity: {scores['clothing']:.4f}")
            # Print detailed clothing breakdown
            if scores.get("clothing_details"):
                details = scores["clothing_details"]
                print(f"    - Upper color:  {details.get('upper_color', 0):.3f}")
                print(f"    - Lower color:  {details.get('lower_color', 0):.3f}")
                print(f"    - Color names:  {details.get('color_names', 0):.3f}")
                print(f"    - Pattern:      {details.get('pattern', 0):.3f}")
                print(f"    - Brightness:   {details.get('brightness', 0):.3f}")
                print(f"    - Skin tone:    {details.get('skin_tone', 0):.3f}")
        else:
            print(f"  Clothing similarity: N/A")

        if scores.get("face") is not None:
            print(f"  Face similarity:     {scores['face']:.4f}")
        else:
            print(f"  Face similarity:     N/A")

        print()

    print_separator("-")

    # Print matching decision
    mode = debug_info.get("mode", "unknown")
    best_match = debug_info.get("best_match", "N/A")
    best_sim = debug_info.get("best_similarity", 0.0)
    second_sim = debug_info.get("second_similarity", 0.0)
    gap = debug_info.get("confidence_gap", 0.0)
    threshold = debug_info.get("threshold", 0.0)

    print(
        f"🔍 Mode: {mode} | Best: {best_sim:.3f} | 2nd: {second_sim:.3f} | "
        f"Gap: {gap:.3f} | Threshold: {threshold:.3f}"
    )

    if gap < 0.15:
        print(
            f"⚠️ AMBIGUOUS: Best={best_match}({best_sim:.2f}) vs "
            f"2nd({second_sim:.2f}), gap={gap:.2f} < 0.15"
        )

    print()
    print("🎯 FINAL DECISION:")

    if person_id is not None:
        print(f"  ✅ MATCHED: {person_id}")
        print(f"  Similarity: {similarity:.4f}")
        print(f"  Reason: {debug_info.get('reason', 'match')}")
    else:
        print(f"  ❌ NO MATCH (similarity: {best_sim:.4f})")
        print(f"  Reason: {debug_info.get('reason', 'unknown')}")

    print_separator()
    print()


def test_enhanced_reid():
    """Test enhanced re-ID with OSNet and clothing features."""
    print_header("ENHANCED PERSON RE-IDENTIFICATION DEBUG TEST")

    print("This script tests the new enhanced re-ID system with:")
    print("  ✅ OSNet body embeddings (learned features)")
    print("  ✅ Clothing color, pattern, and style analysis")
    print("  ✅ Skin tone detection")
    print("  ✅ Face features (existing)")
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

    # Initialize enhanced re-ID system
    print("🔧 Initializing Enhanced Re-ID System...")
    reid_system = EnhancedMultiModalReID(
        osnet_weight=0.35,
        clothing_weight=0.25,
        face_weight=0.30,
        skin_weight=0.10,
        similarity_threshold=0.70,
        confidence_gap=0.15,
        body_only_threshold=0.65,
        use_osnet=True,
    )
    print()

    # Open webcam (MacBook built-in camera)
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return

    print_header("TEST PROCEDURE")
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
    print("  - System will show detailed similarity breakdown")
    print()
    print("EXPECTED RESULTS with Enhanced Features:")
    print("  ✅ OSNet should distinguish different people well")
    print("  ✅ Clothing colors should be clearly different")
    print("  ✅ Skin tone should provide additional confirmation")
    print("  ✅ Overall accuracy should be much better!")
    print()
    print("Press 'q' to quit")
    print_separator()
    print()

    registered_count = 0
    match_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()

        # Detect face and body
        faces = face_detector.detect(frame)
        bodies = body_detector.detect(frame)

        # Draw detections
        for face in faces:
            x, y, w, h = face["bbox"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                display,
                f"Face {face['confidence']:.2f}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        for body in bodies:
            x, y, w, h = body["bbox"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(
                display,
                f"Body {body['confidence']:.2f}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                2,
            )

        # Instructions
        cv2.putText(
            display,
            f"Registered: {registered_count} | Matches tested: {match_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        cv2.putText(
            display,
            "R: Register | SPACE: Match | Q: Quit",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        cv2.imshow("Enhanced Re-ID Debug", display)

        key = cv2.waitKey(1) & 0xFF

        # Register person
        if key == ord("r") and len(faces) > 0 and len(bodies) > 0:
            registered_count += 1
            person_id = f"TEST_P{registered_count:03d}"

            # Get largest face and body
            face = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
            body = max(bodies, key=lambda b: b["bbox"][2] * b["bbox"][3])

            # Extract face features (use histogram for now)
            fx, fy, fw, fh = face["bbox"]
            face_img = frame[fy : fy + fh, fx : fx + fw]
            face_hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
            face_hist = cv2.calcHist(
                [face_hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256]
            )
            face_hist = face_hist.flatten()
            face_hist = face_hist / (np.sum(face_hist) + 1e-6)

            # Register with enhanced features
            success = reid_system.register_person(
                person_id=person_id,
                image=frame,
                face_features=face_hist,
                face_bbox=face["bbox"],
                body_bbox=body["bbox"],
                metadata={"name": f"Person {registered_count}"},
            )

            if success:
                # Print feature summary
                features = reid_system.people[person_id]
                print_features_summary(features, person_id)

        # Match person
        elif key == ord(" ") and len(faces) > 0 and len(bodies) > 0:
            match_count += 1

            # Get largest face and body
            face = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
            body = max(bodies, key=lambda b: b["bbox"][2] * b["bbox"][3])

            # Extract face features
            fx, fy, fw, fh = face["bbox"]
            face_img = frame[fy : fy + fh, fx : fx + fw]
            face_hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
            face_hist = cv2.calcHist(
                [face_hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256]
            )
            face_hist = face_hist.flatten()
            face_hist = face_hist / (np.sum(face_hist) + 1e-6)

            # Match
            person_id, similarity, debug_info = reid_system.match_person(
                image=frame,
                face_features=face_hist,
                face_bbox=face["bbox"],
                body_bbox=body["bbox"],
                mode="auto",
            )

            # Add combined scores to debug info
            for pid in reid_system.people.keys():
                if pid in debug_info["all_scores"]:
                    # Compute combined score for display
                    scores = debug_info["all_scores"][pid]
                    combined = 0.0
                    total_weight = 0.0

                    if scores.get("osnet") is not None:
                        combined += scores["osnet"] * reid_system.osnet_weight
                        total_weight += reid_system.osnet_weight
                    if scores.get("clothing") is not None:
                        combined += scores["clothing"] * reid_system.clothing_weight
                        total_weight += reid_system.clothing_weight
                    if scores.get("face") is not None:
                        combined += scores["face"] * reid_system.face_weight
                        total_weight += reid_system.face_weight

                    if total_weight > 0:
                        combined = combined / total_weight

                    debug_info["all_scores"][pid]["combined"] = combined

            # Print results
            print_matching_results(person_id, similarity, debug_info, match_count)

        # Quit
        elif key == ord("q"):
            print("\n⚠️ Test interrupted by user")
            break

    cap.release()
    cv2.destroyAllWindows()

    # Print summary
    print()
    print_header("TEST SUMMARY")
    print(f"Total people registered: {registered_count}")
    print(f"Total matches tested: {match_count}")
    print()
    print("📊 Expected Improvements with Enhanced Features:")
    print("  ✅ OSNet embeddings: Much better discrimination than histograms")
    print("  ✅ Clothing analysis: Detects colors, patterns, styles")
    print("  ✅ Skin tone: Additional biometric feature")
    print("  ✅ Combined: Robust multi-modal re-identification")
    print()
    print("🔬 Key Differences from Basic System:")
    print("  - OSNet uses learned features (not just colors)")
    print("  - Can distinguish similar clothing by patterns/textures")
    print("  - Skin tone helps with face-occluded scenarios")
    print("  - More robust to lighting/camera changes")
    print_separator()


if __name__ == "__main__":
    try:
        test_enhanced_reid()
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
