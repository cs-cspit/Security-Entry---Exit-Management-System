#!/usr/bin/env python3
"""
YOLO26 Complete Three-Camera Security System
============================================
Ultimate implementation with Entry, Exit, and Room cameras using YOLO26-pose
for unified person detection, tracking, and re-identification.

Features:
✅ YOLO26-pose unified detection (single model for detection + pose)
✅ Multi-modal re-ID: OSNet + Hair + Skin + Clothing
✅ Entry gate: Auto-register people entering
✅ Room camera: Track authorized people, detect velocity, trajectory
✅ Exit gate: Match and exit people, calculate duration
✅ Real-time velocity tracking with color-coded indicators
✅ Unauthorized entry detection
✅ Session management with database persistence

Controls:
    E - Force register at entry (auto-register is default)
    D - Toggle debug output
    C - Clear all registrations
    Q - Quit and export session data
    S - Show statistics
"""

import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from alert_manager import AlertLevel, AlertManager, AlertType
    from cross_camera_adapter import CrossCameraAdapter
    from detectors.yolo26_body_detector import YOLO26BodyDetector
    from enhanced_database import EnhancedDatabase
    from features.body_only_analyzer import BodyOnlyAnalyzer
    from features.face_recognition import FaceRecognitionExtractor
    from features.osnet_extractor import OSNetExtractor
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print(
        "\n💡 Make sure you're in the project directory and have installed dependencies:"
    )
    print("   pip install ultralytics opencv-python numpy torch torchvision")
    sys.exit(1)


class YOLO26CompleteSystem:
    """
    Complete three-camera security system using YOLO26-pose.
    """

    def __init__(self, entry_idx=0, room_idx=2, exit_idx=1):
        """Initialize the complete system."""
        print("\n" + "=" * 70)
        print("  YOLO26 COMPLETE THREE-CAMERA SECURITY SYSTEM")
        print("=" * 70)
        print("✅ Unified YOLO26-pose detection (17 keypoints)")
        print("✅ Body + Hair + Skin + Clothing + OSNet re-identification")
        print("✅ Velocity tracking with real-time display")
        print("✅ Complete entry → room → exit pipeline\n")

        self.running = True
        self.entry_idx = entry_idx
        self.room_idx = room_idx
        self.exit_idx = exit_idx

        print(f"📹 Camera Assignment:")
        print(f"   Entry: Camera {entry_idx}")
        print(f"   Room:  Camera {room_idx}")
        print(f"   Exit:  Camera {exit_idx}")
        print()

        # System settings
        self.debug_mode = False
        self.auto_register = True
        self.pixels_per_meter = (
            100.0  # Calibration: pixels per meter (adjust for your camera)
        )

        # Initialize YOLO26 detector (shared across all cameras)
        print("🔧 Loading YOLO26-pose model...")
        self.detector = YOLO26BodyDetector(
            model_name="yolo26n-pose.pt", confidence_threshold=0.5, device="auto"
        )
        print()

        # Initialize feature extractors
        print("🔧 Loading feature extractors...")
        self.osnet = OSNetExtractor(device="auto")
        self.body_analyzer = BodyOnlyAnalyzer()

        # Initialize face recognition (Phase 5)
        print("🔧 Loading face recognition (InsightFace)...")
        try:
            self.face_recognizer = FaceRecognitionExtractor(
                model_name="buffalo_sc",  # Smaller, faster model
                det_size=(640, 640),
            )
            self.use_face_recognition = self.face_recognizer.is_initialized()
            if self.use_face_recognition:
                print("✅ Face recognition enabled!")
                print("   - Entry gate: Face + Body matching")
                print("   - Exit gate: Face-first matching (fallback to body)")
            else:
                print("⚠️  Face recognition disabled (initialization failed)")
        except Exception as e:
            print(f"⚠️  Face recognition not available: {e}")
            print("   System will use body-only matching")
            self.face_recognizer = None
            self.use_face_recognition = False

        # Initialize cross-camera adapter
        print("🔧 Loading cross-camera adapter...")
        self.cross_camera = CrossCameraAdapter()
        print()

        # Initialize database and alerts
        self.database = EnhancedDatabase("data/yolo26_complete_system.db")
        self.alert_manager = AlertManager(
            cooldown_seconds=5.0,
            console_output=True,
            file_logging=True,
            log_path="data/yolo26_system_alerts.log",
        )

        # Person registry
        self.registered_people = {}  # {person_id: profile}
        self.active_sessions = {}  # {person_id: session_info}
        self.person_status = {}  # {person_id: 'active' or 'exited'}
        self.person_counter = 0

        # Tracking data
        self.trajectories = defaultdict(list)  # {person_id: [(x, y, time), ...]}
        self.velocity_data = defaultdict(list)  # {person_id: [velocities]}
        self.last_detection_time = defaultdict(float)

        # Temporal smoothing - track last N frames for each detection
        self.detection_history = defaultdict(
            list
        )  # {detection_key: [(person_id, similarity), ...]}
        self.temporal_window = 3  # Require 3-frame majority
        self.stable_ids = {}  # {detection_key: person_id} - confirmed IDs

        # Entry cooldown (prevent duplicate registrations)
        self.entry_cooldown = {}
        self.entry_cooldown_seconds = (
            10.0  # Increased to prevent duplicate registrations
        )
        self.last_entry_person_bbox = None  # Track last registered person's bbox
        self.entry_area_threshold = 0.2  # 20% overlap = same person (more lenient)

        # Feature weights for matching (REBALANCED to prevent false positives)
        # OSNet is most discriminative, appearance features are weak across people
        self.osnet_weight = 0.70  # INCREASED - most important for person identity
        self.hair_weight = 0.05  # DECREASED - too similar across people
        self.skin_weight = 0.05  # DECREASED - too similar across people
        self.clothing_weight = 0.20

        # Hard OSNet minimum threshold - reject if OSNet alone is too low
        # This prevents matches based purely on appearance when body features don't match
        self.min_osnet_threshold = 0.50  # OSNet must be at least 0.50 for any match

        # Face recognition weights (Phase 5)
        self.face_weight = 0.60  # Face is most discriminative when available
        self.face_threshold = 0.45  # InsightFace threshold (0.4-0.5 typical)
        self.use_face_at_entry = True  # Always try to capture face at entry
        self.use_face_at_exit = True  # Face-first matching at exit

        # NOTE: Thresholds are now managed by CrossCameraAdapter!
        # These are fallback values only
        self.similarity_threshold = 0.38  # Fallback for room (managed by adapter)
        self.exit_threshold = 0.42  # Fallback for exit (managed by adapter)
        self.confidence_gap = 0.15  # Fallback confidence gap
        self.exit_confidence_gap = 0.10  # Fallback exit gap

        # Statistics
        self.stats = {
            "registered": 0,
            "inside": 0,
            "exited": 0,
            "unauthorized": 0,
            "total_detections": 0,
            "entry_detections": 0,
            "room_detections": 0,
            "exit_detections": 0,
        }

        # Open cameras
        self._init_cameras()

        # Signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        print("✅ System ready!\n")
        print("=" * 70)
        print("CONTROLS:")
        print("  E - Force register at entry")
        print("  D - Toggle debug output (extra verbose)")
        print("  C - Clear all registrations")
        print("  S - Show statistics")
        print("  I - Show cross-camera adapter info")
        print(
            "  F - Toggle face recognition (currently: {})".format(
                "ON" if self.use_face_recognition else "OFF"
            )
        )
        print("  + - Increase room threshold (+0.05)")
        print("  - - Decrease room threshold (-0.05)")
        print("  ] - Increase exit threshold (+0.05)")
        print("  [ - Decrease exit threshold (-0.05)")
        print("  Q - Quit and export data")
        print("=" * 70 + "\n")

    def _init_cameras(self):
        """Initialize camera connections with normalized resolution."""
        print("📹 Opening cameras...")

        # Target resolution — keeps all three cameras consistent for detection
        # and ensures overlay coordinates are correct.
        # iBall native: 1280x720 → normalized to 640x480
        # MacBook FaceTime HD: 1280x720 → normalized to 640x480
        # Redmi via Iriun: variable → normalized to 640x480
        self.FRAME_WIDTH = 640
        self.FRAME_HEIGHT = 480

        camera_info = [
            ("Entry Camera", self.entry_idx),
            ("Room  Camera", self.room_idx),
            ("Exit  Camera", self.exit_idx),
        ]

        self.cap_entry = cv2.VideoCapture(self.entry_idx)
        self.cap_room = cv2.VideoCapture(self.room_idx)
        self.cap_exit = cv2.VideoCapture(self.exit_idx)

        caps = [self.cap_entry, self.cap_room, self.cap_exit]

        all_ok = True
        for (label, _), cap in zip(camera_info, caps):
            if not cap.isOpened():
                print(f"   ❌ {label} — FAILED TO OPEN")
                all_ok = False
                continue

            # Request target resolution (camera will use nearest supported mode)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"   ✅ {label}")
            print(
                f"      Requested: {self.FRAME_WIDTH}x{self.FRAME_HEIGHT} | "
                f"Actual: {actual_w}x{actual_h}"
            )

        if all_ok:
            print("✅ All cameras opened successfully\n")
        else:
            print("⚠️  One or more cameras failed — check connections\n")

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n⚠️  Interrupt signal received...")
        self.running = False

    def register_person(
        self, person_id: str, frame: np.ndarray, detection: dict
    ) -> bool:
        """
        Register a new person with full feature extraction (Phase 5: includes face).
        """
        try:
            body_bbox = detection["body_bbox"]

            if self.debug_mode:
                print(f"   Extracting OSNet features...")

            osnet_features = self.osnet.extract_features(frame, body_bbox)
            if osnet_features is None:
                print(f"   ❌ OSNet extraction failed")
                return False

            # Update cross-camera adapter statistics (for entry camera)
            self.cross_camera.update_feature_stats("entry", osnet_features)

            if self.debug_mode:
                print(f"   Extracting hair, skin, clothing...")

            body_features = self.body_analyzer.extract_features(frame, body_bbox)

            # Phase 5: Extract face embedding at entry
            face_embedding = None
            if self.use_face_recognition and self.use_face_at_entry:
                if self.debug_mode:
                    print(f"   Extracting face embedding...")

                face_embedding = self.face_recognizer.extract_face_embedding(
                    frame, bbox=body_bbox, min_confidence=0.5
                )

                if face_embedding is not None:
                    print(f"   ✅ Face detected and embedded (512D)")
                else:
                    print(f"   ⚠️  No face detected (will use body-only matching)")

            # Store profile
            self.registered_people[person_id] = {
                "osnet": osnet_features,
                "body_features": body_features,
                "face_embedding": face_embedding,  # Phase 5: Store face
                "body_bbox": body_bbox,
                "keypoints": detection.get("keypoints"),
                "registered_at": datetime.now(),
            }

            return True

        except Exception as e:
            print(f"   ❌ Registration failed: {e}")
            return False

    def match_person(
        self, frame: np.ndarray, detection: dict, target_camera: str = "room"
    ) -> tuple:
        """
        Match a detected person against registered people (Phase 5: includes face).

        Args:
            frame: Current frame
            detection: Detection dictionary with body_bbox
            target_camera: Camera ID ('room', 'exit')

        Returns: (person_id, similarity, debug_info)
        """
        if not self.registered_people:
            return None, 0.0, {}

        body_bbox = detection["body_bbox"]

        try:
            # Phase 5: Extract face embedding if exit camera (face-first matching)
            face_query = None
            if (
                self.use_face_recognition
                and target_camera == "exit"
                and self.use_face_at_exit
            ):
                face_query = self.face_recognizer.extract_face_embedding(
                    frame, bbox=body_bbox, min_confidence=0.5
                )

                if self.debug_mode and face_query is not None:
                    print(f"   🔍 Face detected at exit - using face-first matching")

            # Extract query features
            osnet_query = self.osnet.extract_features(frame, body_bbox)
            if osnet_query is None:
                return None, 0.0, {}

            # Update cross-camera adapter statistics
            self.cross_camera.update_feature_stats(target_camera, osnet_query)

            body_query = self.body_analyzer.extract_features(frame, body_bbox)

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Feature extraction failed: {e}")
            return None, 0.0, {}

        # Compare with all registered people
        best_id = None
        best_score = 0.0
        second_best_score = 0.0
        all_scores = {}

        # Initialize debug_info dictionary
        debug_info = {
            "all_scores": {},
            "adaptive_threshold": 0.0,
            "adaptive_gap": 0.0,
            "reason": "",
            "gap": 0.0,
            "second_best": 0.0,
        }

        # Get adaptive threshold from cross-camera adapter
        adaptive_threshold, adaptive_gap = self.cross_camera.get_matching_params(
            "entry", target_camera
        )
        debug_info["adaptive_threshold"] = adaptive_threshold
        debug_info["adaptive_gap"] = adaptive_gap

        for person_id, person_data in self.registered_people.items():
            osnet_registered = person_data["osnet"]
            body_registered = person_data["body_features"]
            face_registered = person_data.get("face_embedding")  # Phase 5

            # Phase 5: Face matching (if available and at exit)
            face_sim = 0.0
            has_face_match = False
            if (
                face_query is not None
                and face_registered is not None
                and target_camera == "exit"
            ):
                # Face-first matching at exit
                face_sim = self.face_recognizer.compare_faces(
                    face_query, face_registered
                )
                has_face_match = True

                if self.debug_mode:
                    print(f"\n👤 Face Match for {person_id}: {face_sim:.3f}")
                    if face_sim >= self.face_threshold:
                        print(f"   ✅ Face match! (>{self.face_threshold:.2f})")
                    else:
                        print(f"   ❌ Face no match (<{self.face_threshold:.2f})")

            # OSNet similarity (PROPER cosine similarity - normalized dot product)
            dot_product = np.dot(osnet_query, osnet_registered)
            norm_query = np.linalg.norm(osnet_query)
            norm_registered = np.linalg.norm(osnet_registered)

            # DEBUG: Print raw values to diagnose
            if self.debug_mode:
                print(f"\n🔬 OSNet Debug for {person_id}:")
                print(f"   Dot product: {dot_product:.6f}")
                print(f"   Query norm: {norm_query:.6f}")
                print(f"   Registered norm: {norm_registered:.6f}")

            osnet_sim = float(dot_product / (norm_query * norm_registered + 1e-6))

            # Hair similarity
            hair_sim = self._compare_hair(
                body_query.get("hair_color", {}), body_registered.get("hair_color", {})
            )

            # Skin similarity
            skin_sim = self._compare_skin(
                body_query.get("skin_tone", {}), body_registered.get("skin_tone", {})
            )

            # Clothing similarity
            upper_sim = self._compare_clothing(
                body_query.get("upper_clothing", {}),
                body_registered.get("upper_clothing", {}),
            )
            lower_sim = self._compare_clothing(
                body_query.get("lower_clothing", {}),
                body_registered.get("lower_clothing", {}),
            )
            clothing_sim = (upper_sim + lower_sim) / 2.0

            # Phase 5: Weighted combination with face (if at exit and face available)
            if has_face_match and face_sim >= self.face_threshold:
                # Face match found - use face-dominant scoring
                total_score = face_sim * self.face_weight + osnet_sim * (
                    1.0 - self.face_weight
                )

                if self.debug_mode:
                    print(f"   Using FACE-DOMINANT scoring: {total_score:.3f}")
            else:
                # No face or face didn't match - use body-only scoring
                # HARD OSNET CHECK: Reject if OSNet similarity is too low
                if osnet_sim < self.min_osnet_threshold:
                    debug_info["all_scores"][person_id] = {
                        "osnet": osnet_sim,
                        "hair": hair_sim,
                        "skin": skin_sim,
                        "clothing": clothing_sim,
                        "face": face_sim if has_face_match else None,
                        "total": 0.0,
                        "rejected": f"OSNet too low ({osnet_sim:.3f} < {self.min_osnet_threshold:.3f})",
                    }
                    continue  # Skip this person entirely

                total_score = (
                    osnet_sim * self.osnet_weight
                    + hair_sim * self.hair_weight
                    + skin_sim * self.skin_weight
                    + clothing_sim * self.clothing_weight
                )

            # Apply cross-camera adjustment
            total_score = self.cross_camera.adjust_similarity_score(
                total_score,
                source_camera="entry",
                target_camera=target_camera,
                features_query=osnet_query,
                features_registered=osnet_registered,
            )

            all_scores[person_id] = {
                "osnet": osnet_sim,
                "hair": hair_sim,
                "skin": skin_sim,
                "clothing": clothing_sim,
                "face": face_sim if has_face_match else None,  # Phase 5
                "total": total_score,
            }

            if total_score > best_score:
                second_best_score = best_score  # Track second best
                best_score = total_score
                best_id = person_id
            elif total_score > second_best_score:
                second_best_score = total_score

        # Use CrossCameraAdapter to decide if match should be accepted
        should_match, reason = self.cross_camera.should_match(
            best_score=best_score,
            second_best_score=second_best_score,
            num_registered=len(self.registered_people),
            source_camera="entry",
            target_camera=target_camera,
        )

        if not should_match:
            return (
                None,
                best_score,
                {
                    "all_scores": all_scores,
                    "reason": reason,
                    "gap": best_score - second_best_score,
                    "second_best": second_best_score,
                    "adaptive_threshold": adaptive_threshold,
                    "adaptive_gap": adaptive_gap,
                },
            )

        return (
            best_id,
            best_score,
            {
                "all_scores": all_scores,
                "reason": "clear_match",
                "gap": best_score - second_best_score,
                "second_best": second_best_score,
                "adaptive_threshold": adaptive_threshold,
                "adaptive_gap": adaptive_gap,
            },
        )

    def _compare_hair(self, hair1: dict, hair2: dict) -> float:
        """Compare hair colors."""
        if not hair1 or not hair2:
            return 0.5

        color1 = hair1.get("dominant_color")
        color2 = hair2.get("dominant_color")

        if not color1 or not color2:
            return 0.5

        return 1.0 if color1 == color2 else 0.3

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

    def _calculate_velocity(self, person_id: str) -> float:
        """Calculate velocity from trajectory."""
        trajectory = self.trajectories.get(person_id, [])

        if len(trajectory) < 2:
            return 0.0

        # Use last two points
        (x1, y1, t1) = trajectory[-2]
        (x2, y2, t2) = trajectory[-1]

        time_delta = (t2 - t1).total_seconds()
        if time_delta < 0.001:
            return 0.0

        # Calculate pixel distance
        distance_pixels = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # Convert to meters
        distance_meters = distance_pixels / self.pixels_per_meter

        # Velocity in m/s
        velocity = distance_meters / time_delta

        return velocity

    def _get_detection_key(self, bbox):
        """Create a key for tracking detections across frames (area-based)."""
        bx, by, bw, bh = bbox
        # Use center and rough size for tracking
        center_x = bx + bw // 2
        center_y = by + bh // 2
        size = (bw * bh) // 100  # Rough size bucket
        return f"{center_x // 50}_{center_y // 50}_{size}"

    def _smooth_match(self, detection_key, person_id, similarity):
        """Apply temporal smoothing - require multiple frames to confirm match."""
        # Add to history
        history = self.detection_history[detection_key]
        history.append((person_id, similarity))

        # Keep only last N frames
        if len(history) > self.temporal_window:
            history.pop(0)

        # If we have enough frames, do majority vote
        if len(history) >= self.temporal_window:
            # Count votes for each person_id
            votes = defaultdict(int)
            for pid, sim in history:
                votes[pid] += 1

            # Find majority
            if votes:
                majority_id = max(votes, key=votes.get)
                majority_count = votes[majority_id]

                # Need at least 2 out of 3 frames
                if majority_count >= 2:
                    self.stable_ids[detection_key] = majority_id
                    return majority_id, True  # Confirmed

        # Not enough frames or no majority - return last stable ID if exists
        if detection_key in self.stable_ids:
            return self.stable_ids[detection_key], True

        # Return current match but marked as unconfirmed
        return person_id, False

    def _bbox_overlap(self, bbox1, bbox2):
        """Calculate IoU (Intersection over Union) between two bboxes."""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Calculate intersection
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)

        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0

        intersection = (xi2 - xi1) * (yi2 - yi1)
        union = w1 * h1 + w2 * h2 - intersection

        return intersection / union if union > 0 else 0.0

    def process_entry_camera(self, frame: np.ndarray) -> np.ndarray:
        """Process entry camera - auto-register new people."""
        display = frame.copy()
        current_time = time.time()

        # Detect people
        detections = self.detector.detect(frame)
        self.stats["entry_detections"] += len(detections)

        for detection in detections:
            body_bbox = detection["body_bbox"]
            bx, by, bw, bh = body_bbox

            # Draw pose keypoints and skeleton if available
            if detection.get("keypoints") is not None:
                keypoints = detection["keypoints"]

                # Draw skeleton connections first
                skeleton = [
                    (0, 1),
                    (0, 2),
                    (1, 3),
                    (2, 4),  # Head
                    (5, 6),
                    (5, 7),
                    (7, 9),
                    (6, 8),
                    (8, 10),  # Arms
                    (5, 11),
                    (6, 12),
                    (11, 12),  # Torso
                    (11, 13),
                    (13, 15),
                    (12, 14),
                    (14, 16),  # Legs
                ]

                for start_idx, end_idx in skeleton:
                    if start_idx < len(keypoints) and end_idx < len(keypoints):
                        x1, y1, conf1 = keypoints[start_idx]
                        x2, y2, conf2 = keypoints[end_idx]
                        if conf1 > 0.3 and conf2 > 0.3:
                            cv2.line(
                                display,
                                (int(x1), int(y1)),
                                (int(x2), int(y2)),
                                (0, 255, 255),
                                2,
                            )

                # Draw keypoints on top
                for i, (x, y, conf) in enumerate(keypoints):
                    if conf > 0.3:
                        color = (0, 255, 0) if conf > 0.7 else (0, 200, 200)
                        cv2.circle(display, (int(x), int(y)), 5, color, -1)
                        cv2.circle(display, (int(x), int(y)), 6, (255, 255, 255), 1)

            # Draw detection
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), (0, 255, 255), 2)

            # Check if this is same person as last registered (area-based cooldown)
            skip_registration = False
            if self.last_entry_person_bbox is not None:
                overlap = self._bbox_overlap(body_bbox, self.last_entry_person_bbox)
                time_since_last = current_time - self.entry_cooldown.get(
                    "last_registration", 0
                )

                if (
                    overlap > self.entry_area_threshold
                    and time_since_last < self.entry_cooldown_seconds
                ):
                    skip_registration = True
                    cv2.putText(
                        display,
                        "REGISTERED",
                        (bx, by - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2,
                    )

            # Auto-register if enabled and not in cooldown
            if self.auto_register and not skip_registration:
                self.person_counter += 1
                person_id = f"P{self.person_counter:03d}"

                print(f"\n⏳ Auto-registering {person_id} at entry...")
                success = self.register_person(person_id, frame, detection)

                if success:
                    self.entry_cooldown["last_registration"] = current_time
                    self.last_entry_person_bbox = body_bbox
                    self.stats["registered"] += 1

                    # Create session
                    session_id = f"SESSION_{person_id}_{int(current_time)}"
                    self.active_sessions[person_id] = {
                        "session_id": session_id,
                        "entry_time": datetime.now(),
                    }
                    self.person_status[person_id] = "active"
                    self.stats["inside"] += 1

                    # Pull extracted features from in-memory registry
                    registered_profile = self.registered_people[person_id]
                    face_embedding = registered_profile.get("face_embedding")
                    body_features = registered_profile.get("body_features")

                    # Add person to database FIRST (with face embedding),
                    # then record entry so the DB row already exists.
                    self.database.add_person(
                        person_id,
                        body_features=body_features,
                        face_embedding=face_embedding,
                    )
                    self.database.record_entry(person_id)

                    print(f"✅ Registered {person_id} at entry gate")

                    # Show extracted features
                    features = body_features or {}

                    hair = features.get("hair_color", {})
                    if hair.get("dominant_color"):
                        print(
                            f"   👤 Hair: {hair['dominant_color']} (conf: {hair.get('confidence', 0):.2f})"
                        )

                    skin = features.get("skin_tone", {})
                    if skin.get("hsv_mean"):
                        print(
                            f"   🎨 Skin: {skin.get('percentage', 0) * 100:.1f}% detected"
                        )

                    upper = features.get("upper_clothing", {})
                    if upper.get("dominant_colors"):
                        print(f"   👕 Upper: {upper['dominant_colors'][:2]}")

                    lower = features.get("lower_clothing", {})
                    if lower.get("dominant_colors"):
                        print(f"   👖 Lower: {lower['dominant_colors'][:2]}")

                    print()

                    # Show BIG notification with ID
                    cv2.rectangle(
                        display, (bx, by - 80), (bx + 200, by - 5), (0, 255, 0), -1
                    )
                    cv2.putText(
                        display,
                        f"REGISTERED: {person_id}",
                        (bx + 5, by - 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 0),
                        2,
                    )

                    # Show feature indicators
                    hair_color = features.get("hair_color", {}).get(
                        "dominant_color", "?"
                    )
                    upper_colors = features.get("upper_clothing", {}).get(
                        "dominant_colors", ["?"]
                    )
                    cv2.putText(
                        display,
                        f"Hair:{hair_color} Top:{upper_colors[0] if upper_colors else '?'}",
                        (bx + 5, by - 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 0),
                        1,
                    )

        # Status overlay — use actual frame width so it covers every camera resolution
        h_disp, w_disp = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w_disp, 80), (0, 0, 0), -1)
        cv2.putText(
            display,
            "ENTRY CAMERA",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        cv2.putText(
            display,
            f"Registered: {self.stats['registered']} | Inside: {self.stats['inside']}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0) if self.stats["registered"] > 0 else (255, 255, 255),
            2,
        )
        cv2.putText(
            display,
            f"Detections: {len(detections)} | Face-ID: {'ON' if self.use_face_recognition else 'OFF'}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 255, 255) if self.use_face_recognition else (200, 200, 200),
            1,
        )

        return display

    def process_room_camera(self, frame: np.ndarray) -> np.ndarray:
        """Process room camera - track authorized people, calculate velocity."""
        # Apply cross-camera preprocessing FIRST
        frame_preprocessed = self.cross_camera.preprocess_frame(frame, camera_id="room")

        display = frame_preprocessed.copy()
        current_time = datetime.now()

        # Detect people (on preprocessed frame)
        detections = self.detector.detect(frame_preprocessed)
        self.stats["room_detections"] += len(detections)
        self.stats["total_detections"] += len(detections)

        authorized_count = 0
        unauthorized_count = 0

        for detection in detections:
            body_bbox = detection["body_bbox"]
            bx, by, bw, bh = body_bbox
            center_x = bx + bw // 2
            center_y = by + bh // 2

            # ALWAYS print room detection status (even if not debug mode)
            print(f"\n🔍 ROOM: Person detected at ({bx}, {by}), size: {bw}x{bh}")

            # Match against registered people (with target_camera='room')
            person_id, similarity, debug_info = self.match_person(
                frame_preprocessed, detection, target_camera="room"
            )
            confirmed = True  # Always confirmed - no verification delay

            # Get adaptive threshold for display
            adaptive_threshold = debug_info.get(
                "adaptive_threshold", self.similarity_threshold
            )

            # Quick status print
            if person_id and person_id in self.active_sessions:
                print(f"   ✅ AUTHORIZED: {person_id} (score: {similarity:.3f})")
            elif person_id:
                print(f"   ⚠️  REGISTERED but NO SESSION: {person_id}")
            else:
                print(
                    f"   ❌ UNAUTHORIZED (best score: {similarity:.3f} < adaptive threshold: {adaptive_threshold:.3f})"
                )
                if similarity > 0.25:
                    print(f"   💡 Cross-camera domain shift detected! (entry→room)")
                    print(
                        f"   💡 Adaptive threshold: {adaptive_threshold:.3f}, Gap required: {debug_info.get('adaptive_gap', 0.08):.3f}"
                    )

            # Print matching scores ONLY when debug mode is ON (to reduce console spam)
            if self.debug_mode:
                print(f"\n🔍 ROOM DETECTION (DEBUG MODE):")
                print(f"   Body bbox: ({bx}, {by}, {bw}, {bh})")
                print(
                    f"   Adaptive threshold: {adaptive_threshold:.2f} | Adaptive gap: {debug_info.get('adaptive_gap', 0.08):.2f}"
                )
                print(f"   Camera pair: entry → room (HUGE domain shift expected!)")
                if not self.registered_people:
                    print(f"   ⚠️  NO REGISTERED PEOPLE YET!")
                else:
                    print(
                        f"   Testing against {len(self.registered_people)} registered people:"
                    )
                    for pid, scores in debug_info.get("all_scores", {}).items():
                        total = scores.get("total", 0)
                        osnet = scores.get("osnet", 0)
                        hair = scores.get("hair", 0)
                        skin = scores.get("skin", 0)
                        clothing = scores.get("clothing", 0)

                        # Check if rejected due to low OSNet
                        rejected = scores.get("rejected", None)
                        if rejected:
                            print(f"   {pid}: ❌ REJECTED - {rejected}")
                            continue

                        status = (
                            "✅ MATCH"
                            if total >= self.similarity_threshold
                            else "❌ BELOW"
                        )
                        gap = total - self.similarity_threshold
                        print(f"   {pid}: {total:.3f} {status} (gap: {gap:+.3f})")
                        print(
                            f"      OSNet: {osnet:.3f} × {self.osnet_weight:.2f} = {osnet * self.osnet_weight:.3f} {'← LOW!' if osnet < 0.60 else '✓'}"
                        )
                        print(
                            f"      Hair:  {hair:.3f} × {self.hair_weight:.2f} = {hair * self.hair_weight:.3f}"
                        )
                        print(
                            f"      Skin:  {skin:.3f} × {self.skin_weight:.2f} = {skin * self.skin_weight:.3f}"
                        )
                        print(
                            f"      Cloth: {clothing:.3f} × {self.clothing_weight:.2f} = {clothing * self.clothing_weight:.3f}"
                        )

                    if person_id:
                        gap = debug_info.get("gap", 0)
                        second = debug_info.get("second_best", 0)
                        print(f"   🎯 FINAL MATCH: {person_id} ({similarity:.3f})")
                        print(f"      Gap from 2nd best: {gap:.3f} (2nd: {second:.3f})")
                    else:
                        reason = debug_info.get("reason", "unknown")
                        if reason == "below_threshold":
                            print(
                                f"   ❌ NO MATCH: Best score {similarity:.3f} < threshold {self.similarity_threshold:.3f}"
                            )
                            if similarity > 0.60:
                                print(f"   💡 HINT: Close! Press - to lower threshold")
                        elif reason == "ambiguous":
                            gap = debug_info.get("gap", 0)
                            second = debug_info.get("second_best", 0)
                            print(
                                f"   ❌ NO MATCH: AMBIGUOUS! Best {similarity:.3f} vs 2nd {second:.3f} (gap: {gap:.3f})"
                            )
                            print(
                                f"   ⚠️  Multiple people too similar - can't distinguish!"
                            )
                print()
            else:
                # Print simplified summary when not in debug mode
                if person_id and person_id in self.active_sessions:
                    print(f"   Session: ACTIVE ✓")
                elif not person_id and similarity > 0.50:
                    print(f"   Hint: Score {similarity:.3f} is close. Lower threshold?")

            # ── Trajectory + velocity tracking for ALL detections ────────────
            # Track every person regardless of auth status so that crowd
            # behaviour, congestion and walking/running speeds are always
            # visible — essential for CISF threat analysis.
            track_key = (
                person_id if person_id else f"unauth_{center_x // 60}_{center_y // 60}"
            )
            self.trajectories[track_key].append((center_x, center_y, current_time))
            if len(self.trajectories[track_key]) > 60:
                self.trajectories[track_key].pop(0)

            velocity = self._calculate_velocity(track_key)
            self.velocity_data[track_key].append(velocity)

            # Always draw the trajectory tail
            self._draw_trajectory(display, track_key)

            # Velocity indicator (shown for every detection)
            velocity_text = f"{velocity:.2f} m/s"
            if velocity > 2.0:
                v_color = (0, 0, 255)  # RED - running
                velocity_text += " RUNNING!"
            elif velocity > 1.0:
                v_color = (0, 165, 255)  # ORANGE - fast walk
            else:
                v_color = (0, 255, 0)  # GREEN - normal

            cv2.putText(
                display,
                velocity_text,
                (bx, by + bh + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                v_color,
                1,
            )

            # Check if person has active session
            if person_id and person_id in self.active_sessions:
                # AUTHORIZED person with active session
                authorized_count += 1
                box_color = (0, 255, 0)  # GREEN
                label = f"{person_id} ({similarity:.2f})"

                # Store trajectory point in DB (only for registered persons)
                self.database.add_trajectory_point(
                    person_id, center_x, center_y, "room_camera", velocity=velocity
                )

                # Additional debug if enabled
                if self.debug_mode:
                    print(f"   📊 Session active, velocity={velocity:.2f} m/s")

            else:
                # UNAUTHORIZED detection
                unauthorized_count += 1
                self.stats["unauthorized"] += 1
                box_color = (0, 0, 255)  # RED
                label = f"UNAUTHORIZED ({similarity:.2f})"

                # Alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.CRITICAL,
                    message="Unauthorized person detected in room",
                    camera_source="room_camera",
                )

            # Draw pose keypoints and skeleton if available
            if detection.get("keypoints") is not None:
                keypoints = detection["keypoints"]

                # Draw skeleton connections first
                skeleton = [
                    (0, 1),
                    (0, 2),
                    (1, 3),
                    (2, 4),  # Head
                    (5, 6),
                    (5, 7),
                    (7, 9),
                    (6, 8),
                    (8, 10),  # Arms
                    (5, 11),
                    (6, 12),
                    (11, 12),  # Torso
                    (11, 13),
                    (13, 15),
                    (12, 14),
                    (14, 16),  # Legs
                ]

                for start_idx, end_idx in skeleton:
                    if start_idx < len(keypoints) and end_idx < len(keypoints):
                        x1, y1, conf1 = keypoints[start_idx]
                        x2, y2, conf2 = keypoints[end_idx]
                        if conf1 > 0.3 and conf2 > 0.3:
                            cv2.line(
                                display,
                                (int(x1), int(y1)),
                                (int(x2), int(y2)),
                                (0, 255, 255),
                                2,
                            )

                # Draw keypoints on top
                for i, (x, y, conf) in enumerate(keypoints):
                    if conf > 0.3:
                        kpt_color = (0, 255, 0) if conf > 0.7 else (0, 200, 200)
                        cv2.circle(display, (int(x), int(y)), 5, kpt_color, -1)
                        cv2.circle(display, (int(x), int(y)), 6, (255, 255, 255), 1)

            # Draw bbox and label (use box_color preserved from status check above)
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), box_color, 2)
            cv2.putText(
                display,
                label,
                (bx, by - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                box_color,
                2,
            )

        # Status overlay — use actual frame width
        h_disp, w_disp = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w_disp, 110), (0, 0, 0), -1)
        cv2.putText(
            display,
            "ROOM CAMERA",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2,
        )
        cv2.putText(
            display,
            f"Inside: {self.stats['inside']} | Authorized: {authorized_count}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0) if authorized_count > 0 else (255, 255, 255),
            2,
        )
        cv2.putText(
            display,
            f"Unauthorized: {unauthorized_count}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255) if unauthorized_count > 0 else (200, 200, 200),
            1,
        )
        cv2.putText(
            display,
            f"Detections: {len(detections)}",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (200, 200, 200),
            1,
        )

        if self.debug_mode:
            cv2.putText(
                display,
                "DEBUG MODE: ON",
                (10, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 255, 255),
                1,
            )

        return display

    def _draw_trajectory(self, frame: np.ndarray, person_id: str):
        """Draw trajectory path."""
        trajectory = self.trajectories.get(person_id, [])
        if len(trajectory) < 2:
            return

        points = [(int(x), int(y)) for x, y, _ in trajectory]

        # Draw lines
        for i in range(1, len(points)):
            thickness = max(1, int(3 * (i / len(points))))
            cv2.line(frame, points[i - 1], points[i], (0, 255, 255), thickness)

    def process_exit_camera(self, frame: np.ndarray) -> np.ndarray:
        """Process exit camera - match and close sessions."""
        # Apply cross-camera preprocessing FIRST
        frame_preprocessed = self.cross_camera.preprocess_frame(frame, camera_id="exit")

        display = frame_preprocessed.copy()
        current_time = datetime.now()

        # Detect people (on preprocessed frame)
        detections = self.detector.detect(frame_preprocessed)
        self.stats["exit_detections"] += len(detections)

        for detection in detections:
            body_bbox = detection["body_bbox"]
            bx, by, bw, bh = body_bbox

            # ALWAYS print exit detection status
            print(f"\n🚪 EXIT: Person detected at ({bx}, {by}), size: {bw}x{bh}")

            # Match against registered people (with target_camera='exit')
            person_id, similarity, debug_info = self.match_person(
                frame_preprocessed, detection, target_camera="exit"
            )

            # Get adaptive threshold for display
            adaptive_threshold = debug_info.get(
                "adaptive_threshold", self.exit_threshold
            )

            # Re-evaluate with EXIT-specific threshold (more lenient)
            original_person_id = person_id
            if (
                not person_id
                and self.registered_people
                and similarity >= self.exit_threshold
            ):
                # Original match_person rejected it, but it meets exit threshold
                # Find the best match that meets exit criteria
                best_id = None
                best_score = 0.0
                second_best_score = 0.0

                for pid, scores in debug_info.get("all_scores", {}).items():
                    total = scores.get("total", 0)
                    if total > best_score:
                        second_best_score = best_score
                        best_score = total
                        best_id = pid
                    elif total > second_best_score:
                        second_best_score = total

                # Check exit-specific gap
                if best_score >= self.exit_threshold:
                    if (
                        len(self.registered_people) == 1
                        or (best_score - second_best_score) >= self.exit_confidence_gap
                    ):
                        person_id = best_id
                        similarity = best_score
                        print(
                            f"   🔓 EXIT OVERRIDE: Accepting {person_id} (score: {best_score:.3f}, exit threshold: {self.exit_threshold:.2f})"
                        )

            # Quick status print
            if person_id and person_id in self.active_sessions:
                print(f"   ✅ VALID EXIT: {person_id} (score: {similarity:.3f})")
            elif person_id:
                print(f"   ⚠️  REGISTERED but NO ACTIVE SESSION: {person_id}")
            else:
                print(
                    f"   ❌ UNKNOWN PERSON (best score: {similarity:.3f} < adaptive threshold: {adaptive_threshold:.2f})"
                )
                if similarity > 0.50:
                    print(
                        f"   💡 Close to threshold! Press '[' to lower exit threshold"
                    )

            # Only print debug when match status changes or in debug mode
            if self.debug_mode or (not original_person_id and person_id):
                print(f"\n🚪 EXIT DETECTION:")
                print(
                    f"   Exit threshold: {self.exit_threshold:.2f} (room: {self.similarity_threshold:.2f})"
                )
                if not self.registered_people:
                    print(f"   ⚠️  NO REGISTERED PEOPLE YET!")
                else:
                    for pid, scores in debug_info.get("all_scores", {}).items():
                        total = scores.get("total", 0)
                        status = "✅" if total >= self.exit_threshold else "❌"
                        print(f"   {pid}: {total:.3f} {status}")
                    if person_id:
                        print(f"   🎯 MATCHED: {person_id} ({similarity:.3f})")
                    else:
                        print(f"   ❌ NO MATCH (best: {similarity:.3f})")
                print()

            if person_id and person_id in self.active_sessions:
                # Valid exit
                box_color = (0, 255, 0)  # GREEN
                label = f"{person_id} EXITING"

                # Close session
                session_info = self.active_sessions[person_id]
                entry_time = session_info["entry_time"]
                duration = (current_time - entry_time).total_seconds()

                # Calculate average velocity
                velocities = self.velocity_data.get(person_id, [0.0])
                avg_velocity = sum(velocities) / len(velocities)
                max_velocity = max(velocities) if velocities else 0.0

                # Record exit in database
                self.database.record_exit(person_id)

                # Update person record with velocity data and re-persist so
                # avg_velocity / max_velocity are not 0 in the database.
                # (record_exit persists before velocity is known, so we must
                # write it a second time after computing the values.)
                if person_id in self.database.people:
                    person = self.database.people[person_id]
                    person["avg_velocity"] = avg_velocity
                    person["max_velocity"] = max_velocity
                    self.database._persist_person_to_db(person)

                # Remove from active
                del self.active_sessions[person_id]
                self.person_status[person_id] = "exited"
                self.stats["inside"] -= 1
                self.stats["exited"] += 1

                print(f"\n✅ {person_id} exited")
                print(f"   Duration: {duration:.1f}s")
                print(f"   Avg velocity: {avg_velocity:.2f} m/s")
                print(f"   Max velocity: {max_velocity:.2f} m/s")

            elif person_id:
                # Person registered but no active session
                box_color = (0, 165, 255)  # ORANGE
                label = f"{person_id} NO SESSION"
            else:
                # Unknown person at exit
                box_color = (0, 0, 255)  # RED
                label = "UNKNOWN"

            # Draw pose keypoints and skeleton if available
            if detection.get("keypoints") is not None:
                keypoints = detection["keypoints"]

                # Draw skeleton connections first
                skeleton = [
                    (0, 1),
                    (0, 2),
                    (1, 3),
                    (2, 4),  # Head
                    (5, 6),
                    (5, 7),
                    (7, 9),
                    (6, 8),
                    (8, 10),  # Arms
                    (5, 11),
                    (6, 12),
                    (11, 12),  # Torso
                    (11, 13),
                    (13, 15),
                    (12, 14),
                    (14, 16),  # Legs
                ]

                for start_idx, end_idx in skeleton:
                    if start_idx < len(keypoints) and end_idx < len(keypoints):
                        x1, y1, conf1 = keypoints[start_idx]
                        x2, y2, conf2 = keypoints[end_idx]
                        if conf1 > 0.3 and conf2 > 0.3:
                            cv2.line(
                                display,
                                (int(x1), int(y1)),
                                (int(x2), int(y2)),
                                (0, 255, 255),
                                2,
                            )

                # Draw keypoints on top
                for i, (x, y, conf) in enumerate(keypoints):
                    if conf > 0.3:
                        kpt_color = (0, 255, 0) if conf > 0.7 else (0, 200, 200)
                        cv2.circle(display, (int(x), int(y)), 5, kpt_color, -1)
                        cv2.circle(display, (int(x), int(y)), 6, (255, 255, 255), 1)

            # Draw (use box_color preserved from status check above)
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), box_color, 2)
            cv2.putText(
                display,
                label,
                (bx, by - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                box_color,
                2,
            )

        # Status overlay — use actual frame width
        h_disp, w_disp = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w_disp, 90), (0, 0, 0), -1)
        cv2.putText(
            display,
            "EXIT CAMERA",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 255),
            2,
        )
        cv2.putText(
            display,
            f"Exited: {self.stats['exited']} | Still Inside: {self.stats['inside']}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )
        cv2.putText(
            display,
            f"Detections: {len(detections)} | Threshold: {self.exit_threshold:.2f} | Face-ID: {'ON' if self.use_face_recognition else 'OFF'}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 255, 255) if self.use_face_recognition else (200, 200, 200),
            1,
        )
        cv2.putText(
            display,
            f"Face matching: {'face-first (60%) + OSNet (40%)' if self.use_face_recognition else 'body-only OSNet (70%) + appearance (30%)'}",
            (10, 86),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.33,
            (180, 180, 180),
            1,
        )

        return display

    def show_statistics(self):
        """Print detailed statistics."""
        print("\n" + "=" * 70)
        print("  SYSTEM STATISTICS")
        print("=" * 70)
        print(f"Registered People:      {self.stats['registered']}")
        print(f"Currently Inside:       {self.stats['inside']}")
        print(f"Total Exited:           {self.stats['exited']}")
        print(f"Unauthorized Detections: {self.stats['unauthorized']}")
        print(f"\nCamera Detections:")
        print(f"  Entry:  {self.stats['entry_detections']}")
        print(f"  Room:   {self.stats['room_detections']}")
        print(f"  Exit:   {self.stats['exit_detections']}")
        print(f"  Total:  {self.stats['total_detections']}")
        print("\nActive Sessions:")
        for pid, session in self.active_sessions.items():
            duration = (datetime.now() - session["entry_time"]).total_seconds()
            print(f"  {pid}: {duration:.1f}s inside")
        print("=" * 70 + "\n")

    def run(self):
        """Main loop."""
        print("\n🚀 Starting system...\n")

        try:
            while self.running:
                # Read frames
                ret_entry, frame_entry = self.cap_entry.read()
                ret_room, frame_room = self.cap_room.read()
                ret_exit, frame_exit = self.cap_exit.read()

                if not (ret_entry and ret_room and ret_exit):
                    print("⚠️ Failed to read from cameras")
                    break

                # Normalize all frames to the target resolution before processing.
                # This ensures consistent coordinates for detection, feature
                # extraction, and overlay rendering across all three cameras.
                target = (self.FRAME_WIDTH, self.FRAME_HEIGHT)
                if (
                    frame_entry.shape[1] != self.FRAME_WIDTH
                    or frame_entry.shape[0] != self.FRAME_HEIGHT
                ):
                    frame_entry = cv2.resize(
                        frame_entry, target, interpolation=cv2.INTER_LINEAR
                    )
                if (
                    frame_room.shape[1] != self.FRAME_WIDTH
                    or frame_room.shape[0] != self.FRAME_HEIGHT
                ):
                    frame_room = cv2.resize(
                        frame_room, target, interpolation=cv2.INTER_LINEAR
                    )
                if (
                    frame_exit.shape[1] != self.FRAME_WIDTH
                    or frame_exit.shape[0] != self.FRAME_HEIGHT
                ):
                    frame_exit = cv2.resize(
                        frame_exit, target, interpolation=cv2.INTER_LINEAR
                    )

                # Process each camera
                display_entry = self.process_entry_camera(frame_entry)
                display_room = self.process_room_camera(frame_room)
                display_exit = self.process_exit_camera(frame_exit)

                # Show windows
                cv2.imshow("Entry Gate", display_entry)
                cv2.imshow("Room Monitoring", display_room)
                cv2.imshow("Exit Gate", display_exit)

                # Handle keys
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    print("\n⚠️  Quit requested...")
                    break
                elif key == ord("d"):
                    self.debug_mode = not self.debug_mode
                    print(f"\n🔧 Debug mode: {'ON' if self.debug_mode else 'OFF'}\n")
                elif key == ord("c"):
                    print("\n⚠️  Clearing all registrations...")
                    self.registered_people.clear()
                    self.active_sessions.clear()
                    self.trajectories.clear()
                    self.velocity_data.clear()
                    self.person_status.clear()
                    self.entry_cooldown.clear()
                    self.last_entry_person_bbox = None
                    self.detection_history.clear()
                    self.stable_ids.clear()
                    self.stats = {k: 0 for k in self.stats}
                    print("✅ All data cleared\n")
                elif key == ord("s"):
                    self.show_statistics()
                elif key == ord("+") or key == ord("="):
                    self.similarity_threshold = min(
                        0.90, self.similarity_threshold + 0.05
                    )
                    print(
                        f"\n🔧 ROOM Threshold INCREASED to {self.similarity_threshold:.2f} (stricter)\n"
                    )
                elif key == ord("-") or key == ord("_"):
                    self.similarity_threshold = max(
                        0.40, self.similarity_threshold - 0.05
                    )
                    print(
                        f"\n🔧 ROOM Threshold DECREASED to {self.similarity_threshold:.2f} (more lenient)\n"
                    )
                elif key == ord("]"):
                    self.exit_threshold = min(0.90, self.exit_threshold + 0.05)
                    print(
                        f"\n🔧 EXIT Threshold INCREASED to {self.exit_threshold:.2f} (stricter)\n"
                    )
                elif key == ord("["):
                    self.exit_threshold = max(0.40, self.exit_threshold - 0.05)
                    print(
                        f"\n🔧 EXIT Threshold DECREASED to {self.exit_threshold:.2f} (more lenient)\n"
                    )
                elif key == ord("e"):
                    print("\n⚠️  Manual registration mode not implemented for entry")
                    print("    (Auto-registration is active)\n")
                elif key == ord("i"):
                    # Show cross-camera adapter info
                    self.cross_camera.print_diagnostics()
                elif key == ord("f"):
                    # Toggle face recognition
                    if self.face_recognizer is not None:
                        self.use_face_recognition = not self.use_face_recognition
                        print(
                            f"\n🔧 Face recognition: {'ON' if self.use_face_recognition else 'OFF'}\n"
                        )
                    else:
                        print(
                            "\n⚠️  Face recognition not available (InsightFace not installed)\n"
                        )

        except Exception as e:
            print(f"\n❌ Error in main loop: {e}")
            import traceback

            traceback.print_exc()

        finally:
            print("\n🛑 Shutting down...")
            self.cleanup()

    def cleanup(self):
        """Cleanup resources."""
        print("📊 Exporting session data...")
        self.show_statistics()

        # Persist final trajectories and write last_session.json
        print("💾 Closing database (saving trajectories + session export)...")
        self.database.close()

        print("📹 Releasing cameras...")
        self.cap_entry.release()
        self.cap_room.release()
        self.cap_exit.release()

        cv2.destroyAllWindows()
        print("✅ Cleanup complete\n")


def _detect_available_cameras(max_index: int = 6) -> list:
    """Probe camera indices 0..max_index-1 and return those that produce frames."""
    available = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(i)
        cap.release()
    return available


def main():
    """
    Entry point with argparse-based camera assignment.

    Camera setup for this project:
      --entry   iBall Face2Face CHD20.0 Webcam (720p, USB)
      --room    MacBook FaceTime HD (built-in, usually index 0 on macOS)
      --exit    Redmi Note 11 via Iriun Webcam app (USB/WiFi)

    Run the helper script first if you are unsure which index maps to which camera:
        python scripts/detect_cameras.py

    Default indices (0=MacBook built-in, 1=iBall, 2=Iriun) are chosen for a
    typical macOS setup where the built-in webcam claims index 0 and USB cameras
    are assigned sequentially.  Override with --entry / --room / --exit if needed.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="YOLO26 Three-Camera Security System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Camera setup:
  --entry  Entry gate camera  (default index: 0)
  --room   Room monitor camera (default index: 2)
  --exit   Exit gate camera   (default index: 1)

Run  python scripts/detect_cameras.py  to identify camera indices.
        """,
    )
    parser.add_argument(
        "--entry",
        type=int,
        default=0,
        metavar="IDX",
        help="Camera index for Entry gate (default: 0)",
    )
    parser.add_argument(
        "--room",
        type=int,
        default=2,
        metavar="IDX",
        help="Camera index for Room monitor (default: 2)",
    )
    parser.add_argument(
        "--exit",
        type=int,
        default=1,
        metavar="IDX",
        help="Camera index for Exit gate (default: 1)",
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="Probe and list all available camera indices, then exit",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  YOLO26 COMPLETE SECURITY SYSTEM")
    print("=" * 70)

    if args.list_cameras:
        print("\n🔍 Probing camera indices 0-5 …")
        available = _detect_available_cameras()
        if available:
            print(f"✅ Found camera(s) at index(es): {available}")
        else:
            print("❌ No cameras detected.")
        return

    entry_idx = args.entry
    room_idx = args.room
    exit_idx = args.exit

    print(f"\n📹 Camera Assignment:")
    print(f"   Entry Camera : index {entry_idx}")
    print(f"   Room  Camera : index {room_idx}")
    print(f"   Exit  Camera : index {exit_idx}")
    print()
    print("💡 Tip: run with --list-cameras to identify indices,")
    print("         or override with --entry N --room N --exit N")
    print()

    # Create and run system
    system = YOLO26CompleteSystem(
        entry_idx=entry_idx, room_idx=room_idx, exit_idx=exit_idx
    )
    system.run()


if __name__ == "__main__":
    main()
