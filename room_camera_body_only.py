#!/usr/bin/env python3
"""
ROOM CAMERA - BODY-ONLY MULTI-PERSON DETECTION
================================================

For distant room cameras where faces are NOT clearly visible.
Uses ONLY body features:
- OSNet body embeddings
- Hair color (top of body)
- Skin tone (from visible body parts)
- Upper clothing colors
- Lower clothing colors

NO FACE DETECTION - purely body-based identification.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detectors.yolov11_body_detector import YOLOv11BodyDetector
from features.body_only_analyzer import BodyOnlyAnalyzer
from features.osnet_extractor import OSNetExtractor


class RoomCameraBodyOnlyReID:
    """
    Body-only re-identification for room camera.
    Uses OSNet + hair + skin + clothing features.
    """

    def __init__(
        self,
        osnet_weight: float = 0.40,
        hair_weight: float = 0.20,
        skin_weight: float = 0.15,
        clothing_weight: float = 0.25,
        similarity_threshold: float = 0.70,
    ):
        """Initialize body-only re-ID system."""
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

        print("🔧 Initializing BODY-ONLY Re-ID system...")
        self.osnet = OSNetExtractor()
        self.body_analyzer = BodyOnlyAnalyzer()

        self.people = {}  # person_id -> features

        print(f"✅ Body-only Re-ID initialized:")
        print(f"   OSNet weight: {self.osnet_weight:.2f}")
        print(f"   Hair weight: {self.hair_weight:.2f}")
        print(f"   Skin weight: {self.skin_weight:.2f}")
        print(f"   Clothing weight: {self.clothing_weight:.2f}")
        print(f"   Threshold: {self.similarity_threshold:.2f}")

    def register_person(
        self, person_id: str, frame: np.ndarray, body_bbox: tuple
    ) -> bool:
        """Register a person using body-only features."""
        try:
            print(f"   Extracting OSNet features...")
            # OSNet features
            osnet_features = self.osnet.extract_features(frame, body_bbox)
            if osnet_features is None:
                print(f"   ❌ Failed to extract OSNet features")
                return False

            print(f"   Extracting hair, skin, clothing...")
            # Body features (hair, skin, clothing)
            body_features = self.body_analyzer.extract_features(frame, body_bbox)

            self.people[person_id] = {
                "osnet": osnet_features,
                "body_features": body_features,
                "body_bbox": body_bbox,
            }

            return True

        except Exception as e:
            print(f"   ❌ Registration failed: {e}")
            return False

    def match_person(
        self, frame: np.ndarray, body_bbox: tuple
    ) -> tuple[str, float, dict]:
        """
        Match a person using body-only features.

        Returns:
            (person_id, similarity, debug_info)
        """
        if len(self.people) == 0:
            return None, 0.0, {}

        # Extract features
        try:
            osnet_features = self.osnet.extract_features(frame, body_bbox)
            if osnet_features is None:
                return None, 0.0, {}

            osnet_query = osnet_features
            body_query = self.body_analyzer.extract_features(frame, body_bbox)

        except Exception as e:
            print(f"⚠️ Feature extraction failed: {e}")
            return None, 0.0, {}

        # Compare with all registered people
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
                body_query["hair_color"], person_data["body_features"]["hair_color"]
            )

            # Skin similarity
            skin_sim = self._compare_skin(
                body_query["skin_tone"], person_data["body_features"]["skin_tone"]
            )

            # Clothing similarity (upper + lower combined)
            upper_sim = self._compare_clothing(
                body_query["upper_clothing"],
                person_data["body_features"]["upper_clothing"],
            )
            lower_sim = self._compare_clothing(
                body_query["lower_clothing"],
                person_data["body_features"]["lower_clothing"],
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

        # Check threshold
        if best_score >= self.similarity_threshold:
            return best_pid, best_score, {"all_scores": all_scores}
        else:
            return None, best_score, {"all_scores": all_scores}

    def _compare_hair(self, hair1: dict, hair2: dict) -> float:
        """Compare hair colors."""
        if not hair1 or not hair2:
            return 0.5

        if hair1.get("dominant_color") is None or hair2.get("dominant_color") is None:
            return 0.5  # Neutral score if hair not detected

        # Exact match
        if hair1["dominant_color"] == hair2["dominant_color"]:
            return 1.0

        # HSV comparison
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
            return 0.5  # Neutral score

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

        if not cloth1.get("dominant_colors") or not cloth2.get("dominant_colors"):
            return 0.5

        colors1 = set(cloth1["dominant_colors"])
        colors2 = set(cloth2["dominant_colors"])
        common = len(colors1.intersection(colors2))
        total = len(colors1.union(colors2))
        return common / total if total > 0 else 0.0


def main():
    print("\n" + "=" * 70)
    print("  ROOM CAMERA - BODY-ONLY MULTI-PERSON DETECTION")
    print("=" * 70)
    print("\n✅ Uses ONLY body features (no face detection)")
    print("✅ Hair color + Skin tone + Clothing + OSNet")
    print("✅ GREEN = Registered | RED = Unknown\n")

    # Initialize
    body_detector = YOLOv11BodyDetector()
    reid = RoomCameraBodyOnlyReID()
    print()

    # Open camera
    print("📷 Opening camera...")
    cap = cv2.VideoCapture(1)  # Try index 1 first (MacBook built-in)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)  # Fallback to 0
        if not cap.isOpened():
            print("❌ Cannot open camera!")
            return

    # Lower resolution for speed
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("✅ Camera ready!\n")

    print("=" * 70)
    print("CONTROLS:")
    print("  R - Register person (whoever is biggest in frame)")
    print("  S - Show registered people summary")
    print("  C - Clear all registrations")
    print("  Q - Quit")
    print("=" * 70 + "\n")

    person_count = 0
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        display = frame.copy()

        # Detect bodies
        bodies = body_detector.detect(frame)

        # Process each body
        detected = []
        for body_tuple in bodies:
            bx, by, bw, bh, conf = body_tuple
            body_bbox = (bx, by, bw, bh)

            # Try to match
            person_id, similarity, debug_info = reid.match_person(frame, body_bbox)

            detected.append(
                {
                    "bbox": body_bbox,
                    "conf": conf,
                    "person_id": person_id,
                    "similarity": similarity,
                }
            )

            # Print match info
            if person_id and frame_count % 30 == 0:  # Print every 30 frames
                print(f"\n🔍 Match: {person_id} (similarity: {similarity:.3f})")
                if "all_scores" in debug_info and person_id in debug_info["all_scores"]:
                    scores = debug_info["all_scores"][person_id]
                    print(f"   OSNet: {scores['osnet']:.3f}")
                    print(f"   Hair: {scores['hair']:.3f}")
                    print(f"   Skin: {scores['skin']:.3f}")
                    print(f"   Clothing: {scores['clothing']:.3f}")

        # Draw detections
        known = 0
        unknown = 0
        for person in detected:
            bx, by, bw, bh = person["bbox"]

            if person["person_id"]:
                color = (0, 255, 0)  # GREEN
                label = f"{person['person_id']} ({person['similarity']:.2f})"
                known += 1
            else:
                color = (0, 0, 255)  # RED
                label = "UNKNOWN"
                unknown += 1

            # Draw box
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), color, 3)
            cv2.putText(
                display,
                label,
                (bx, by - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )

        # Status overlay
        cv2.rectangle(display, (0, 0), (700, 110), (0, 0, 0), -1)
        cv2.putText(
            display,
            f"Registered: {len(reid.people)} | Detected: {len(detected)}",
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
            "R: Register | S: Summary | C: Clear | Q: Quit",
            (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            2,
        )
        cv2.putText(
            display,
            "BODY-ONLY: Hair + Skin + Clothing + OSNet",
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (150, 150, 150),
            1,
        )

        cv2.imshow("Room Camera - Body Only", display)

        key = cv2.waitKey(1) & 0xFF

        # Register
        if key == ord("r"):
            if len(bodies) > 0:
                person_count += 1
                person_id = f"PERSON_{person_count}"

                # Get largest body
                largest = max(bodies, key=lambda b: b[2] * b[3])
                bx, by, bw, bh, conf = largest
                body_bbox = (bx, by, bw, bh)

                print(f"\n⏳ Registering {person_id}...")
                success = reid.register_person(person_id, frame, body_bbox)

                if success:
                    print(f"✅ Registered {person_id}")
                    features = reid.people[person_id]["body_features"]

                    # Show what was extracted
                    hair = features["hair_color"]
                    print(
                        f"   Hair: {hair['dominant_color']} (conf: {hair['confidence']:.2f})"
                    )

                    skin = features["skin_tone"]
                    if skin["hsv_mean"]:
                        print(f"   Skin: {skin['percentage'] * 100:.1f}% detected")

                    upper = features["upper_clothing"]
                    print(f"   Upper: {upper['dominant_colors'][:2]}")

                    lower = features["lower_clothing"]
                    print(f"   Lower: {lower['dominant_colors'][:2]}")
                    print()
                else:
                    print(f"❌ Failed to register {person_id}")
            else:
                print("⚠️ No person detected in frame!")

        # Show summary
        elif key == ord("s"):
            print("\n" + "=" * 70)
            print("REGISTERED PEOPLE SUMMARY")
            print("=" * 70)
            if len(reid.people) == 0:
                print("  No one registered yet.")
            else:
                for pid, data in reid.people.items():
                    features = data["body_features"]
                    print(f"\n📋 {pid}:")
                    print(f"   Hair: {features['hair_color']['dominant_color']}")
                    if features["skin_tone"]["hsv_mean"]:
                        print(
                            f"   Skin detected: {features['skin_tone']['percentage'] * 100:.1f}%"
                        )
                    print(
                        f"   Upper: {features['upper_clothing']['dominant_colors'][:2]}"
                    )
                    print(
                        f"   Lower: {features['lower_clothing']['dominant_colors'][:2]}"
                    )
            print("=" * 70 + "\n")

        # Clear
        elif key == ord("c"):
            reid.people.clear()
            person_count = 0
            print("🗑️ Cleared all registrations\n")

        # Quit
        elif key == ord("q"):
            print("\n👋 Stopping...")
            break

    cap.release()
    cv2.destroyAllWindows()

    print("\n" + "=" * 70)
    print(f"SESSION COMPLETE")
    print(f"  Total registered: {len(reid.people)}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
