#!/usr/bin/env python3
"""
YOLO26 ROOM CAMERA TEST
Uses YOLO26-pose for unified person detection and tracking.
Extracts body, hair, skin, and clothing features from BODY ONLY.

NO SEPARATE FACE DETECTION - everything from YOLO26 pose model.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detectors.yolo26_body_detector import YOLO26BodyDetector
from features.body_only_analyzer import BodyOnlyAnalyzer
from features.osnet_extractor import OSNetExtractor


class YOLO26RoomReID:
    """
    Room camera re-identification using YOLO26 unified detection.
    Features: OSNet + hair + skin + clothing (all from body bbox).
    """

    def __init__(
        self,
        osnet_weight: float = 0.50,
        hair_weight: float = 0.15,
        skin_weight: float = 0.15,
        clothing_weight: float = 0.20,
        similarity_threshold: float = 0.70,
    ):
        """Initialize YOLO26-based room re-ID."""
        self.osnet_weight = osnet_weight
        self.hair_weight = hair_weight
        self.skin_weight = skin_weight
        self.clothing_weight = clothing_weight
        self.similarity_threshold = similarity_threshold

        # Normalize weights
        total = osnet_weight + hair_weight + skin_weight + clothing_weight
        self.osnet_weight /= total
        self.hair_weight /= total
        self.skin_weight /= total
        self.clothing_weight /= total

        print("🔧 Initializing YOLO26 Room Re-ID...")
        self.osnet = OSNetExtractor()
        self.body_analyzer = BodyOnlyAnalyzer()

        self.people = {}

        print(f"✅ YOLO26 Room Re-ID initialized:")
        print(f"   OSNet: {self.osnet_weight:.2f}")
        print(f"   Hair: {self.hair_weight:.2f}")
        print(f"   Skin: {self.skin_weight:.2f}")
        print(f"   Clothing: {self.clothing_weight:.2f}")
        print(f"   Threshold: {self.similarity_threshold:.2f}")

    def register_person(
        self, person_id: str, frame: np.ndarray, detection: dict
    ) -> bool:
        """Register person using YOLO26 detection."""
        try:
            body_bbox = detection["body_bbox"]

            print(f"   Extracting OSNet features...")
            osnet_features = self.osnet.extract_features(frame, body_bbox)
            if osnet_features is None:
                print(f"   ❌ OSNet extraction failed")
                return False

            print(f"   Extracting hair, skin, clothing...")
            body_features = self.body_analyzer.extract_features(frame, body_bbox)

            self.people[person_id] = {
                "osnet": osnet_features,
                "body_features": body_features,
                "body_bbox": body_bbox,
                "keypoints": detection.get("keypoints"),
            }

            return True

        except Exception as e:
            print(f"   ❌ Registration failed: {e}")
            return False

    def match_person(self, frame: np.ndarray, detection: dict) -> tuple:
        """Match person using YOLO26 detection."""
        if len(self.people) == 0:
            return None, 0.0, {}

        body_bbox = detection["body_bbox"]

        try:
            osnet_features = self.osnet.extract_features(frame, body_bbox)
            if osnet_features is None:
                return None, 0.0, {}

            osnet_query = osnet_features
            body_query = self.body_analyzer.extract_features(frame, body_bbox)

        except Exception as e:
            print(f"⚠️ Feature extraction failed: {e}")
            return None, 0.0, {}

        all_scores = {}

        for pid, person_data in self.people.items():
            # OSNet similarity
            osnet_registered = person_data["osnet"]
            osnet_sim = float(
                np.dot(osnet_query, osnet_registered)
                / (
                    np.linalg.norm(osnet_query) * np.linalg.norm(osnet_registered)
                    + 1e-6
                )
            )

            # Hair similarity
            hair_sim = self._compare_hair(
                body_query.get("hair_color", {}),
                person_data["body_features"].get("hair_color", {}),
            )

            # Skin similarity
            skin_sim = self._compare_skin(
                body_query.get("skin_tone", {}),
                person_data["body_features"].get("skin_tone", {}),
            )

            # Clothing similarity
            upper_sim = self._compare_clothing(
                body_query.get("upper_clothing", {}),
                person_data["body_features"].get("upper_clothing", {}),
            )
            lower_sim = self._compare_clothing(
                body_query.get("lower_clothing", {}),
                person_data["body_features"].get("lower_clothing", {}),
            )
            clothing_sim = (upper_sim + lower_sim) / 2.0

            # Combined score
            combined = (
                osnet_sim * self.osnet_weight
                + hair_sim * self.hair_weight
                + skin_sim * self.skin_weight
                + clothing_sim * self.clothing_weight
            )

            all_scores[pid] = {
                "osnet": osnet_sim,
                "hair": hair_sim,
                "skin": skin_sim,
                "clothing": clothing_sim,
                "combined": combined,
            }

        # Find best match
        best_pid = max(all_scores.keys(), key=lambda p: all_scores[p]["combined"])
        best_score = all_scores[best_pid]["combined"]

        # Confidence gap check (must be clearly best)
        sorted_scores = sorted(
            [s["combined"] for s in all_scores.values()], reverse=True
        )
        if len(sorted_scores) > 1:
            gap = sorted_scores[0] - sorted_scores[1]
            if gap < 0.15:  # Not clear enough
                return None, best_score, {"all_scores": all_scores, "gap": gap}

        if best_score >= self.similarity_threshold:
            return best_pid, best_score, {"all_scores": all_scores}
        else:
            return None, best_score, {"all_scores": all_scores}

    def _compare_hair(self, hair1: dict, hair2: dict) -> float:
        """Compare hair colors."""
        if not hair1 or not hair2:
            return 0.5

        if hair1.get("dominant_color") is None or hair2.get("dominant_color") is None:
            return 0.5

        if hair1["dominant_color"] == hair2["dominant_color"]:
            return 1.0

        if hair1.get("hsv_mean") and hair2.get("hsv_mean"):
            hsv1 = np.array(hair1["hsv_mean"])
            hsv2 = np.array(hair2["hsv_mean"])
            h_dist = min(abs(hsv1[0] - hsv2[0]), 180 - abs(hsv1[0] - hsv2[0]))
            s_dist = abs(hsv1[1] - hsv2[1])
            v_dist = abs(hsv1[2] - hsv2[2])
            total_dist = (
                (h_dist / 180) * 0.5 + (s_dist / 255) * 0.25 + (v_dist / 255) * 0.25
            )
            return 1.0 - total_dist

        return 0.5

    def _compare_skin(self, skin1: dict, skin2: dict) -> float:
        """Compare skin tones."""
        if not skin1 or not skin2:
            return 0.5

        if skin1.get("hsv_mean") is None or skin2.get("hsv_mean") is None:
            return 0.5

        hsv1 = np.array(skin1["hsv_mean"])
        hsv2 = np.array(skin2["hsv_mean"])
        h_dist = min(abs(hsv1[0] - hsv2[0]), 180 - abs(hsv1[0] - hsv2[0]))
        s_dist = abs(hsv1[1] - hsv2[1])
        v_dist = abs(hsv1[2] - hsv2[2])
        total_dist = (h_dist / 180) * 0.3 + (s_dist / 255) * 0.3 + (v_dist / 255) * 0.4
        return 1.0 - total_dist

    def _compare_clothing(self, cloth1: dict, cloth2: dict) -> float:
        """Compare clothing colors."""
        if not cloth1 or not cloth2:
            return 0.5

        colors1 = cloth1.get("dominant_colors", [])
        colors2 = cloth2.get("dominant_colors", [])

        if not colors1 or not colors2:
            return 0.5

        colors1_set = set(colors1)
        colors2_set = set(colors2)
        common = len(colors1_set.intersection(colors2_set))
        total = len(colors1_set.union(colors2_set))
        return common / total if total > 0 else 0.0


def main():
    print("\n" + "=" * 70)
    print("  YOLO26 ROOM CAMERA - MULTI-PERSON TEST")
    print("=" * 70)
    print("\n✅ Uses YOLO26-pose for unified detection")
    print("✅ Body + Hair + Skin + Clothing + OSNet")
    print("✅ NO separate face detector needed")
    print("✅ GREEN = Known | RED = Unknown\n")

    # Initialize
    print("🔧 Loading YOLO26...")
    detector = YOLO26BodyDetector(
        model_name="yolo26n-pose.pt", confidence_threshold=0.4
    )
    print()

    reid = YOLO26RoomReID()
    print()

    # Open camera
    print("📷 Opening camera...")
    cap = cv2.VideoCapture(1)  # MacBook built-in
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Cannot open camera!")
            return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("✅ Camera ready!\n")

    print("=" * 70)
    print("CONTROLS:")
    print("  R - Register person (biggest in frame)")
    print("  D - Toggle debug output")
    print("  C - Clear all registrations")
    print("  Q - Quit")
    print("=" * 70 + "\n")

    person_count = 0
    frame_count = 0
    debug_mode = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        display = frame.copy()

        # Detect all people with YOLO26
        detections = detector.detect(frame)

        # Match each detection
        matched = []
        for detection in detections:
            person_id, similarity, debug_info = reid.match_person(frame, detection)

            matched.append(
                {
                    "detection": detection,
                    "person_id": person_id,
                    "similarity": similarity,
                    "debug_info": debug_info,
                }
            )

            # Print debug info every 30 frames if enabled
            if debug_mode and person_id and frame_count % 30 == 0:
                print(f"\n🔍 Match: {person_id} ({similarity:.3f})")
                if "all_scores" in debug_info and person_id in debug_info["all_scores"]:
                    scores = debug_info["all_scores"][person_id]
                    print(
                        f"   OSNet: {scores['osnet']:.3f} × {reid.osnet_weight:.2f} = {scores['osnet'] * reid.osnet_weight:.3f}"
                    )
                    print(
                        f"   Hair:  {scores['hair']:.3f} × {reid.hair_weight:.2f} = {scores['hair'] * reid.hair_weight:.3f}"
                    )
                    print(
                        f"   Skin:  {scores['skin']:.3f} × {reid.skin_weight:.2f} = {scores['skin'] * reid.skin_weight:.3f}"
                    )
                    print(
                        f"   Cloth: {scores['clothing']:.3f} × {reid.clothing_weight:.2f} = {scores['clothing'] * reid.clothing_weight:.3f}"
                    )

        # Draw detections
        known = 0
        unknown = 0

        for match in matched:
            detection = match["detection"]
            person_id = match["person_id"]
            similarity = match["similarity"]

            bx, by, bw, bh = detection["body_bbox"]

            if person_id:
                color = (0, 255, 0)  # GREEN
                label = f"{person_id} ({similarity:.2f})"
                known += 1
            else:
                color = (0, 0, 255)  # RED
                label = "UNKNOWN"
                unknown += 1

            # Draw body box
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), color, 3)
            cv2.putText(
                display,
                label,
                (bx, by - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                color,
                2,
            )

            # Draw face box if available
            if detection["has_face"] and detection["face_bbox"]:
                fx, fy, fw, fh = detection["face_bbox"]
                cv2.rectangle(display, (fx, fy), (fx + fw, fy + fh), color, 2)

            # Draw keypoints
            if detection["keypoints"] is not None:
                kpts = detection["keypoints"]
                for kpt in kpts:
                    x, y, conf = kpt
                    if conf > 0.5:
                        cv2.circle(display, (int(x), int(y)), 3, color, -1)

        # Status overlay
        overlay_height = 130 if debug_mode else 110
        cv2.rectangle(display, (0, 0), (750, overlay_height), (0, 0, 0), -1)

        cv2.putText(
            display,
            f"Registered: {len(reid.people)} | Detected: {len(detections)}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            display,
            f"Known: {known} | Unknown: {unknown}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0) if known > 0 else (255, 255, 255),
            2,
        )
        cv2.putText(
            display,
            "R: Register | D: Debug | C: Clear | Q: Quit",
            (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            2,
        )
        cv2.putText(
            display,
            "YOLO26-pose: Body + Hair + Skin + Clothing",
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (150, 150, 150),
            1,
        )

        if debug_mode:
            cv2.putText(
                display,
                "DEBUG MODE: ON (console output enabled)",
                (10, 125),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 255),
                1,
            )

        cv2.imshow("YOLO26 Room Camera", display)

        key = cv2.waitKey(1) & 0xFF

        # Register
        if key == ord("r"):
            if len(detections) > 0:
                person_count += 1
                person_id = f"P{person_count:02d}"

                # Get largest detection
                largest = max(
                    detections, key=lambda d: d["body_bbox"][2] * d["body_bbox"][3]
                )

                print(f"\n⏳ Registering {person_id}...")
                success = reid.register_person(person_id, frame, largest)

                if success:
                    print(f"✅ Registered {person_id}")
                    features = reid.people[person_id]["body_features"]

                    hair = features.get("hair_color", {})
                    if hair.get("dominant_color"):
                        print(
                            f"   Hair: {hair['dominant_color']} (conf: {hair.get('confidence', 0):.2f})"
                        )

                    skin = features.get("skin_tone", {})
                    if skin.get("hsv_mean"):
                        print(
                            f"   Skin: {skin.get('percentage', 0) * 100:.1f}% detected"
                        )

                    upper = features.get("upper_clothing", {})
                    if upper.get("dominant_colors"):
                        print(f"   Upper: {upper['dominant_colors'][:2]}")

                    lower = features.get("lower_clothing", {})
                    if lower.get("dominant_colors"):
                        print(f"   Lower: {lower['dominant_colors'][:2]}")

                    print()
                else:
                    print(f"❌ Failed to register {person_id}\n")
            else:
                print("⚠️ No person detected!\n")

        # Toggle debug
        elif key == ord("d"):
            debug_mode = not debug_mode
            status = "ON" if debug_mode else "OFF"
            print(f"🔧 Debug mode: {status}\n")

        # Clear
        elif key == ord("c"):
            reid.people.clear()
            person_count = 0
            print("🗑️  Cleared all registrations\n")

        # Quit
        elif key == ord("q"):
            print("\n👋 Stopping...\n")
            break

    cap.release()
    cv2.destroyAllWindows()

    print("=" * 70)
    print(f"SESSION COMPLETE")
    print(f"  Total registered: {len(reid.people)}")
    print(f"  Frames processed: {frame_count}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback

        traceback.print_exc()
