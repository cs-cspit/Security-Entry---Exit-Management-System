#!/usr/bin/env python3
"""
System Comparison Script
Compare old histogram-based system vs new OSNet+Clothing system side-by-side
"""

import sys
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detectors.hybrid_face_detector import HybridFaceDetector
from detectors.yolov11_body_detector import YOLOv11BodyDetector


def print_header(text):
    """Print section header."""
    print()
    print("=" * 80)
    print(f"  {text}")
    print("=" * 80)
    print()


def compare_systems():
    """Compare old and new re-ID systems."""
    print_header("SYSTEM COMPARISON - OLD VS NEW")

    print("This script will compare:")
    print()
    print("  📊 OLD SYSTEM:")
    print("     - Color histograms (RGB/HSV)")
    print("     - Simple shape features")
    print("     - No pattern detection")
    print()
    print("  🚀 NEW SYSTEM:")
    print("     - OSNet deep embeddings (512-dim)")
    print("     - Clothing analysis (colors, patterns, textures)")
    print("     - Skin tone detection")
    print("     - Multi-modal fusion")
    print()

    # Initialize detectors (shared by both systems)
    print("🔧 Initializing detectors...")
    try:
        face_detector = HybridFaceDetector(
            model_path="yolov8n-face.pt", confidence_threshold=0.5, device="auto"
        )
        body_detector = YOLOv11BodyDetector(
            model_path="yolo11n.pt", confidence_threshold=0.5, device="auto"
        )
        print("✅ Detectors initialized")
    except Exception as e:
        print(f"❌ Failed to initialize detectors: {e}")
        return

    # Initialize OLD system
    print()
    print("📊 Initializing OLD system (histogram-based)...")
    try:
        from multi_modal_reid import MultiModalReID

        old_system = MultiModalReID(
            face_weight=0.6,
            body_weight=0.4,
            similarity_threshold=0.65,
            confidence_gap=0.05,
            body_only_threshold=0.60,
        )
        print("✅ Old system initialized")
        old_available = True
    except Exception as e:
        print(f"⚠️ Old system failed: {e}")
        old_available = False

    # Initialize NEW system
    print()
    print("🚀 Initializing NEW system (OSNet + Clothing)...")
    try:
        from enhanced_reid import EnhancedMultiModalReID

        new_system = EnhancedMultiModalReID(
            osnet_weight=0.35,
            clothing_weight=0.25,
            face_weight=0.30,
            skin_weight=0.10,
            similarity_threshold=0.70,
            confidence_gap=0.15,
            body_only_threshold=0.65,
            use_osnet=True,
        )
        print("✅ New system initialized")
        new_available = True
    except Exception as e:
        print(f"⚠️ New system failed: {e}")
        new_available = False

    if not old_available and not new_available:
        print()
        print("❌ Both systems failed to initialize. Cannot compare.")
        return

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return

    print()
    print_header("TEST PROCEDURE")
    print("STEP 1: Register Person A (YOU)")
    print("  - Press 'r' to register in both systems")
    print()
    print("STEP 2: Register Person B (YOUR FRIEND)")
    print("  - Press 'r' again to register in both systems")
    print()
    print("STEP 3: Compare Matching")
    print("  - Press SPACE when Person A appears")
    print("  - Press SPACE when Person B appears")
    print("  - System will show side-by-side comparison")
    print()
    print("Press 'q' to quit")
    print("=" * 80)
    print()

    registered_count = 0
    match_count = 0

    # Statistics tracking
    stats = {
        "old": {"matches": 0, "rejections": 0, "ambiguous": 0},
        "new": {"matches": 0, "rejections": 0, "ambiguous": 0},
    }

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()

        # Detect face and body
        faces = face_detector.detect_faces(frame)
        bodies = body_detector.detect_bodies(frame)

        # Draw detections
        for face in faces:
            x, y, w, h = face["bbox"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)

        for body in bodies:
            x, y, w, h = body["bbox"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # Instructions
        cv2.putText(
            display,
            f"Registered: {registered_count} | Tests: {match_count}",
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

        cv2.imshow("System Comparison", display)

        key = cv2.waitKey(1) & 0xFF

        # Register person
        if key == ord("r") and len(faces) > 0 and len(bodies) > 0:
            registered_count += 1
            person_id = f"TEST_P{registered_count:03d}"

            print()
            print_header(f"REGISTERING: {person_id}")

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

            # Extract body features for old system
            bx, by, bw, bh = body["bbox"]
            body_img = frame[by : by + bh, bx : bx + bw]

            # Register in old system
            if old_available:
                try:
                    old_body_features = old_system._extract_body_features(body_img)
                    old_system.people[person_id] = {
                        "face_features": face_hist,
                        "body_features": old_body_features,
                        "face_bbox": face["bbox"],
                        "body_bbox": body["bbox"],
                    }
                    print(f"  📊 OLD: Registered {person_id}")
                except Exception as e:
                    print(f"  ⚠️ OLD: Registration failed: {e}")

            # Register in new system
            if new_available:
                try:
                    new_system.register_person(
                        person_id=person_id,
                        image=frame,
                        face_features=face_hist,
                        face_bbox=face["bbox"],
                        body_bbox=body["bbox"],
                        metadata={"name": f"Person {registered_count}"},
                    )
                    print(f"  🚀 NEW: Registered {person_id}")
                except Exception as e:
                    print(f"  ⚠️ NEW: Registration failed: {e}")

        # Match person
        elif key == ord(" ") and len(faces) > 0 and len(bodies) > 0:
            match_count += 1

            print()
            print_header(f"MATCHING TEST #{match_count}")

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

            # Extract body features
            bx, by, bw, bh = body["bbox"]
            body_img = frame[by : by + bh, bx : bx + bw]

            print()
            print("=" * 80)
            print("  📊 OLD SYSTEM RESULTS")
            print("=" * 80)

            # Match in old system
            if old_available:
                try:
                    old_body_features = old_system._extract_body_features(body_img)
                    old_person_id, old_sim, old_info = old_system.match_person(
                        face_features=face_hist,
                        body_features=old_body_features,
                        mode="auto",
                    )

                    if old_person_id:
                        print(f"  ✅ MATCHED: {old_person_id}")
                        print(f"  Similarity: {old_sim:.4f}")
                        stats["old"]["matches"] += 1
                    else:
                        print(f"  ❌ NO MATCH")
                        print(f"  Reason: {old_info.get('reason', 'unknown')}")
                        if old_info.get("reason") == "ambiguous_match":
                            stats["old"]["ambiguous"] += 1
                        else:
                            stats["old"]["rejections"] += 1

                    print(
                        f"  Gap: {old_info.get('confidence_gap', 0):.4f} "
                        f"(threshold: {old_system.confidence_gap:.2f})"
                    )
                except Exception as e:
                    print(f"  ⚠️ Matching failed: {e}")

            print()
            print("=" * 80)
            print("  🚀 NEW SYSTEM RESULTS")
            print("=" * 80)

            # Match in new system
            if new_available:
                try:
                    new_person_id, new_sim, new_info = new_system.match_person(
                        image=frame,
                        face_features=face_hist,
                        face_bbox=face["bbox"],
                        body_bbox=body["bbox"],
                        mode="auto",
                    )

                    if new_person_id:
                        print(f"  ✅ MATCHED: {new_person_id}")
                        print(f"  Similarity: {new_sim:.4f}")
                        stats["new"]["matches"] += 1

                        # Print detailed scores
                        if (
                            "all_scores" in new_info
                            and new_person_id in new_info["all_scores"]
                        ):
                            scores = new_info["all_scores"][new_person_id]
                            if scores.get("osnet"):
                                print(f"    - OSNet: {scores['osnet']:.4f}")
                            if scores.get("clothing"):
                                print(f"    - Clothing: {scores['clothing']:.4f}")
                            if scores.get("face"):
                                print(f"    - Face: {scores['face']:.4f}")
                    else:
                        print(f"  ❌ NO MATCH")
                        print(f"  Reason: {new_info.get('reason', 'unknown')}")
                        if new_info.get("reason") == "ambiguous_match":
                            stats["new"]["ambiguous"] += 1
                        else:
                            stats["new"]["rejections"] += 1

                    print(
                        f"  Gap: {new_info.get('confidence_gap', 0):.4f} "
                        f"(threshold: {new_system.confidence_gap:.2f})"
                    )
                except Exception as e:
                    print(f"  ⚠️ Matching failed: {e}")

            print()
            print("=" * 80)

        # Quit
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    # Print final statistics
    print()
    print_header("COMPARISON SUMMARY")
    print(f"Total people registered: {registered_count}")
    print(f"Total matching tests: {match_count}")
    print()

    if match_count > 0:
        print("📊 OLD SYSTEM (Histogram-based):")
        print(
            f"  Matches:    {stats['old']['matches']} ({stats['old']['matches'] / match_count * 100:.1f}%)"
        )
        print(
            f"  Rejections: {stats['old']['rejections']} ({stats['old']['rejections'] / match_count * 100:.1f}%)"
        )
        print(
            f"  Ambiguous:  {stats['old']['ambiguous']} ({stats['old']['ambiguous'] / match_count * 100:.1f}%)"
        )
        print()

        print("🚀 NEW SYSTEM (OSNet + Clothing):")
        print(
            f"  Matches:    {stats['new']['matches']} ({stats['new']['matches'] / match_count * 100:.1f}%)"
        )
        print(
            f"  Rejections: {stats['new']['rejections']} ({stats['new']['rejections'] / match_count * 100:.1f}%)"
        )
        print(
            f"  Ambiguous:  {stats['new']['ambiguous']} ({stats['new']['ambiguous'] / match_count * 100:.1f}%)"
        )
        print()

        # Compute improvement
        old_rate = stats["old"]["matches"] / match_count * 100 if match_count > 0 else 0
        new_rate = stats["new"]["matches"] / match_count * 100 if match_count > 0 else 0
        improvement = new_rate - old_rate

        print("📈 IMPROVEMENT:")
        if improvement > 0:
            print(f"  ✅ New system: +{improvement:.1f}% better match rate")
        elif improvement < 0:
            print(f"  ⚠️ New system: {improvement:.1f}% worse match rate")
        else:
            print(f"  ➖ No difference in match rate")

        old_ambiguous_rate = (
            stats["old"]["ambiguous"] / match_count * 100 if match_count > 0 else 0
        )
        new_ambiguous_rate = (
            stats["new"]["ambiguous"] / match_count * 100 if match_count > 0 else 0
        )
        ambiguous_improvement = old_ambiguous_rate - new_ambiguous_rate

        if ambiguous_improvement > 0:
            print(
                f"  ✅ New system: {ambiguous_improvement:.1f}% fewer ambiguous cases"
            )
        elif ambiguous_improvement < 0:
            print(
                f"  ⚠️ New system: {abs(ambiguous_improvement):.1f}% more ambiguous cases"
            )

    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        compare_systems()
    except KeyboardInterrupt:
        print("\n⚠️ Comparison interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
