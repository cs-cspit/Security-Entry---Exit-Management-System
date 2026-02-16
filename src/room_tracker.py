#!/usr/bin/env python3
"""
Room Tracker Module
===================
Phase 2: Room camera monitoring with person detection and re-identification.

Features:
- Multi-camera support (works with 2 or 3 cameras)
- Person detection using OpenCV Haar Cascade (YOLOv8 ready)
- Re-identification matching with entry gate UUIDs
- Unauthorized entry detection
- Real-time trajectory tracking
- Alert generation for security events

Camera Configuration:
- 2-Camera Mode: Entry + Exit (testing)
- 3-Camera Mode: Entry + Exit + Room (full system)
"""

import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from alert_manager import (
    AlertLevel,
    AlertManager,
    AlertType,
    create_running_alert,
    create_unauthorized_alert,
)
from enhanced_database import EnhancedDatabase, PersonState


class PersonDetector:
    """
    Person detection using OpenCV Haar Cascade.
    Can be upgraded to YOLOv8 in Phase 7.
    """

    def __init__(self, method="haar"):
        """
        Initialize person detector.

        Args:
            method: Detection method ("haar" or "yolo")
        """
        self.method = method

        if method == "haar":
            # Use face detection as proxy for person detection
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(cascade_path)

            if self.face_cascade.empty():
                raise RuntimeError("Failed to load Haar Cascade")

            # Also try full body detection
            try:
                body_cascade = cv2.data.haarcascades + "haarcascade_fullbody.xml"
                self.body_cascade = cv2.CascadeClassifier(body_cascade)
            except Exception:
                self.body_cascade = None

        elif method == "yolo":
            # TODO: Implement YOLOv8 in Phase 7
            raise NotImplementedError("YOLO detection coming in Phase 7")

    def detect(self, frame) -> List[Tuple[int, int, int, int]]:
        """
        Detect people in frame.

        Args:
            frame: Input image (BGR)

        Returns:
            List of bounding boxes [(x, y, w, h), ...]
        """
        if self.method == "haar":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces (primary method)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )

            # Convert to list of tuples
            detections = [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]

            # Optionally detect full bodies
            if self.body_cascade is not None:
                bodies = self.body_cascade.detectMultiScale(
                    gray, scaleFactor=1.05, minNeighbors=3, minSize=(80, 120)
                )

                # Add bodies that don't overlap with faces
                for bx, by, bw, bh in bodies:
                    overlap = False
                    for fx, fy, fw, fh in faces:
                        # Check if body contains face
                        if (
                            bx <= fx <= bx + bw
                            and by <= fy <= by + bh
                            and bx <= fx + fw <= bx + bw
                            and by <= fy + fh <= by + bh
                        ):
                            overlap = True
                            break

                    if not overlap:
                        detections.append((int(bx), int(by), int(bw), int(bh)))

            return detections

        return []


class SimpleMatcher:
    """
    Simple person matcher using color histograms.
    Will be upgraded to deep learning embeddings in Phase 7.
    """

    def __init__(self, similarity_threshold=0.6):
        """
        Initialize matcher.

        Args:
            similarity_threshold: Minimum similarity score (0-1)
        """
        self.similarity_threshold = similarity_threshold

    def extract_features(self, frame, bbox):
        """
        Extract features from detected person.

        Args:
            frame: Full frame (BGR)
            bbox: Bounding box (x, y, w, h)

        Returns:
            Feature vector (histogram)
        """
        x, y, w, h = bbox

        # Extract ROI
        roi = frame[y : y + h, x : x + w]

        if roi.size == 0:
            return None

        # Compute HSV histogram
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

        return hist

    def match(self, features1, features2):
        """
        Compare two feature vectors.

        Args:
            features1: First feature vector
            features2: Second feature vector

        Returns:
            Similarity score (0-1)
        """
        if features1 is None or features2 is None:
            return 0.0

        return cv2.compareHist(features1, features2, cv2.HISTCMP_CORREL)

    def find_best_match(self, query_features, database):
        """
        Find best match in database.

        Args:
            query_features: Query feature vector
            database: Dict of {person_id: {"histogram": features, ...}}

        Returns:
            Tuple of (best_person_id, similarity_score)
        """
        if not database:
            return None, 0.0

        best_id = None
        best_score = 0.0

        for person_id, person_data in database.items():
            if "histogram" not in person_data or person_data["histogram"] is None:
                continue

            score = self.match(query_features, person_data["histogram"])

            if score > best_score:
                best_score = score
                best_id = person_id

        if best_score >= self.similarity_threshold:
            return best_id, best_score

        return None, best_score


class RoomTracker:
    """
    Main room tracking system with person detection and re-identification.
    """

    def __init__(
        self,
        camera_index=0,
        camera_name="Room Camera",
        database=None,
        alert_manager=None,
        detector_method="haar",
        similarity_threshold=0.6,
    ):
        """
        Initialize room tracker.

        Args:
            camera_index: Camera device index
            camera_name: Descriptive name for camera
            database: EnhancedDatabase instance
            alert_manager: AlertManager instance
            detector_method: Person detection method
            similarity_threshold: Re-ID matching threshold
        """
        self.camera_index = camera_index
        self.camera_name = camera_name
        self.database = database or EnhancedDatabase()
        self.alert_manager = alert_manager or AlertManager()

        # Initialize detector and matcher
        self.detector = PersonDetector(method=detector_method)
        self.matcher = SimpleMatcher(similarity_threshold=similarity_threshold)

        # Tracking state
        self.tracked_people = {}  # {person_id: tracking_data}
        self.frame_count = 0
        self.start_time = datetime.now()

        # Statistics
        self.stats = {
            "total_detections": 0,
            "matched_people": 0,
            "unauthorized_people": 0,
            "alerts_triggered": 0,
        }

        # Open camera
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_index}")

    def process_frame(self, frame):
        """
        Process a single frame: detect people, match IDs, track trajectories.

        Args:
            frame: Input frame (BGR)

        Returns:
            Annotated frame with detections and IDs
        """
        self.frame_count += 1

        # Detect people
        detections = self.detector.detect(frame)
        self.stats["total_detections"] += len(detections)

        annotated_frame = frame.copy()

        for bbox in detections:
            x, y, w, h = bbox

            # Extract features
            features = self.matcher.extract_features(frame, bbox)

            if features is None:
                continue

            # Try to match with people inside (from entry gate)
            person_id, similarity = self._match_person(features)

            if person_id:
                # Matched with someone who entered through entry gate
                color = (0, 255, 0)  # Green
                label = f"{person_id[:8]} ({similarity:.2f})"
                self.stats["matched_people"] += 1

                # Update tracking
                self._update_tracking(person_id, bbox, frame)

            else:
                # Unauthorized entry detected!
                person_id = f"UNAUTH-{self.frame_count}"
                color = (0, 0, 255)  # Red
                label = f"UNAUTHORIZED"
                self.stats["unauthorized_people"] += 1

                # Record unauthorized entry
                self.database.record_unauthorized_entry(person_id, self.camera_name)

                # Create alert
                create_unauthorized_alert(
                    self.alert_manager, person_id, self.camera_name
                )
                self.stats["alerts_triggered"] += 1

            # Draw bounding box
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 2)

            # Draw label
            cv2.putText(
                annotated_frame,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        return annotated_frame

    def _match_person(self, features):
        """
        Match detected person with database of people who entered.

        Args:
            features: Extracted features

        Returns:
            Tuple of (person_id, similarity_score) or (None, 0.0)
        """
        # Get people currently inside (from entry gate)
        inside_people = self.database.inside_now

        if not inside_people:
            return None, 0.0

        # Build feature database
        feature_db = {}
        for person_id in inside_people.keys():
            if person_id in self.database.global_features:
                feature_db[person_id] = self.database.global_features[person_id]

        # Find best match
        return self.matcher.find_best_match(features, feature_db)

    def _update_tracking(self, person_id, bbox, frame):
        """
        Update trajectory tracking for a person.

        Args:
            person_id: Person identifier
            bbox: Bounding box (x, y, w, h)
            frame: Current frame
        """
        x, y, w, h = bbox
        center_x = x + w // 2
        center_y = y + h // 2

        # Calculate velocity if we have previous position
        velocity = 0.0
        if person_id in self.tracked_people:
            prev_data = self.tracked_people[person_id]
            if "last_pos" in prev_data and "last_time" in prev_data:
                prev_x, prev_y = prev_data["last_pos"]
                prev_time = prev_data["last_time"]

                # Calculate displacement
                dx = center_x - prev_x
                dy = center_y - prev_y
                distance = np.sqrt(dx**2 + dy**2)

                # Calculate time difference
                time_diff = (datetime.now() - prev_time).total_seconds()

                if time_diff > 0:
                    velocity = distance / time_diff  # pixels per second

        # Update tracking data
        self.tracked_people[person_id] = {
            "last_pos": (center_x, center_y),
            "last_time": datetime.now(),
            "velocity": velocity,
            "bbox": bbox,
        }

        # Add trajectory point to database
        self.database.add_trajectory_point(
            person_id, center_x, center_y, self.camera_name, velocity=velocity
        )

    def get_stats(self):
        """Get tracking statistics."""
        return {
            **self.stats,
            "frame_count": self.frame_count,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "people_tracked": len(self.tracked_people),
        }

    def release(self):
        """Release camera resources."""
        if self.cap:
            self.cap.release()


class MultiCameraSystem:
    """
    Multi-camera system controller for entry, exit, and room cameras.
    Works with 2 cameras (entry+exit) or 3 cameras (entry+exit+room).
    """

    def __init__(
        self,
        entry_camera_index=1,
        exit_camera_index=0,
        room_camera_index=None,
        database=None,
        alert_manager=None,
    ):
        """
        Initialize multi-camera system.

        Args:
            entry_camera_index: Entry gate camera index
            exit_camera_index: Exit gate camera index
            room_camera_index: Room camera index (None for 2-camera mode)
            database: EnhancedDatabase instance
            alert_manager: AlertManager instance
        """
        self.database = database or EnhancedDatabase()
        self.alert_manager = alert_manager or AlertManager()

        # Initialize cameras
        self.entry_camera_index = entry_camera_index
        self.exit_camera_index = exit_camera_index
        self.room_camera_index = room_camera_index

        # Camera names
        self.camera_names = {
            entry_camera_index: "ENTRY",
            exit_camera_index: "EXIT",
        }

        if room_camera_index is not None:
            self.camera_names[room_camera_index] = "ROOM"

        # Initialize room tracker if room camera available
        self.room_tracker = None
        if room_camera_index is not None:
            try:
                self.room_tracker = RoomTracker(
                    camera_index=room_camera_index,
                    camera_name="Room Camera",
                    database=self.database,
                    alert_manager=self.alert_manager,
                )
                print(f"✅ Room camera initialized (index {room_camera_index})")
            except Exception as e:
                print(f"⚠️  Failed to initialize room camera: {e}")
                self.room_tracker = None

        # Mode
        self.mode = "3-CAMERA" if self.room_tracker else "2-CAMERA"
        print(f"🎥 System mode: {self.mode}")

    def get_camera_name(self, index):
        """Get camera name by index."""
        return self.camera_names.get(index, f"Camera {index}")

    def is_room_camera_available(self):
        """Check if room camera is available."""
        return self.room_tracker is not None

    def process_room_frame(self, frame):
        """
        Process frame from room camera.

        Args:
            frame: Input frame

        Returns:
            Annotated frame
        """
        if self.room_tracker:
            return self.room_tracker.process_frame(frame)
        return frame

    def get_stats(self):
        """Get system statistics."""
        stats = {
            "mode": self.mode,
            "database_stats": self.database.get_stats(),
            "alert_stats": self.alert_manager.get_stats(),
        }

        if self.room_tracker:
            stats["room_tracker_stats"] = self.room_tracker.get_stats()

        return stats

    def cleanup(self):
        """Cleanup resources."""
        if self.room_tracker:
            self.room_tracker.release()
        self.database.close()


# Test function
def test_room_tracker():
    """Test room tracker with available cameras."""
    print("\n" + "=" * 60)
    print("ROOM TRACKER TEST")
    print("=" * 60)

    # Detect cameras
    print("\nDetecting cameras...")
    available_cameras = []
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available_cameras.append(i)
            cap.release()

    print(f"Found {len(available_cameras)} camera(s): {available_cameras}")

    if len(available_cameras) < 2:
        print("\n❌ Need at least 2 cameras!")
        return

    # Setup cameras
    if len(available_cameras) >= 3:
        entry_idx, exit_idx, room_idx = available_cameras[0:3]
    else:
        entry_idx, exit_idx = available_cameras[0:2]
        room_idx = None

    print(f"\n📹 Camera assignment:")
    print(f"   Entry: Camera {entry_idx}")
    print(f"   Exit: Camera {exit_idx}")
    if room_idx is not None:
        print(f"   Room: Camera {room_idx}")
    else:
        print(f"   Room: Not available (2-camera mode)")

    # Initialize system
    db = EnhancedDatabase("data/room_tracker_test.db")
    alert_mgr = AlertManager(cooldown_seconds=3.0, console_output=True)

    system = MultiCameraSystem(
        entry_camera_index=entry_idx,
        exit_camera_index=exit_idx,
        room_camera_index=room_idx,
        database=db,
        alert_manager=alert_mgr,
    )

    print(f"\n✅ System initialized in {system.mode} mode")
    print("\nPress 'q' to quit")
    print("=" * 60 + "\n")

    # Open cameras for display
    entry_cap = cv2.VideoCapture(entry_idx)
    exit_cap = cv2.VideoCapture(exit_idx)

    try:
        while True:
            # Read entry camera
            ret1, entry_frame = entry_cap.read()
            if ret1:
                entry_frame = cv2.resize(entry_frame, (640, 480))
                cv2.putText(
                    entry_frame,
                    "ENTRY",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Entry Camera", entry_frame)

            # Read exit camera
            ret2, exit_frame = exit_cap.read()
            if ret2:
                exit_frame = cv2.resize(exit_frame, (640, 480))
                cv2.putText(
                    exit_frame,
                    "EXIT",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                )
                cv2.imshow("Exit Camera", exit_frame)

            # Read room camera if available
            if system.room_tracker:
                ret3, room_frame = system.room_tracker.cap.read()
                if ret3:
                    room_frame = cv2.resize(room_frame, (640, 480))
                    # Process frame (detect people, match IDs)
                    annotated_frame = system.process_room_frame(room_frame)
                    cv2.imshow("Room Camera", annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")

    finally:
        entry_cap.release()
        exit_cap.release()
        cv2.destroyAllWindows()
        system.cleanup()

        # Print stats
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        stats = system.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    test_room_tracker()
