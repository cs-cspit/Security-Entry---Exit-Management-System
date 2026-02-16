#!/usr/bin/env python3
"""
Entry + Room Camera Demo
=========================
2-Camera demonstration of Phase 2 features:
- Camera 0 (MacBook): ENTRY gate - generates temp UUIDs
- Camera 1 (Phone): ROOM monitoring - tracks people and detects unauthorized entries

Features:
- Automatic UUID generation at entry
- Room tracking with person re-identification
- Unauthorized entry detection (people in room without entry record)
- Real-time statistics and alerts
- Trajectory tracking

Press 'e' when person is at entry camera to register them
Press 'q' to quit
"""

import signal
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from alert_manager import AlertLevel, AlertManager, AlertType
from enhanced_database import EnhancedDatabase, PersonState


class SimpleFaceTracker:
    """Face detection and tracking with histogram matching."""

    def __init__(self, grace_period_seconds=3.0, similarity_threshold=0.65):
        self.grace_period = timedelta(seconds=grace_period_seconds)
        self.similarity_threshold = similarity_threshold
        self.active_people = {}

        # Load face detector
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def _compute_histogram(self, face_roi):
        """Compute color histogram of face."""
        if face_roi is None or face_roi.size == 0:
            return None

        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist

    def _compare_histograms(self, hist1, hist2):
        """Compare two histograms."""
        if hist1 is None or hist2 is None:
            return 0.0
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    def detect_faces(self, frame):
        """Detect faces in frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]

    def extract_features(self, frame, bbox):
        """Extract features from detected face."""
        x, y, w, h = bbox
        face_roi = frame[y : y + h, x : x + w]
        return self._compute_histogram(face_roi)


class EntryRoomDemo:
    """2-camera demo: Entry gate + Room monitoring."""

    def __init__(self, entry_camera_index=0, room_camera_index=1):
        self.running = True
        self.entry_camera_index = entry_camera_index
        self.room_camera_index = room_camera_index

        # Initialize database and alert manager
        self.database = EnhancedDatabase("data/entry_room_demo.db")
        self.alert_manager = AlertManager(
            cooldown_seconds=5.0,
            console_output=True,
            file_logging=True,
            log_path="data/demo_alerts.log",
        )

        # Initialize trackers
        self.entry_tracker = SimpleFaceTracker(grace_period_seconds=3.0)
        self.room_tracker = SimpleFaceTracker(
            grace_period_seconds=2.0, similarity_threshold=0.60
        )

        # Open cameras
        print("\n" + "=" * 60)
        print("Initializing cameras...")

        self.entry_cap = cv2.VideoCapture(entry_camera_index)
        self.room_cap = cv2.VideoCapture(room_camera_index)

        if not self.entry_cap.isOpened():
            raise RuntimeError(f"Failed to open entry camera {entry_camera_index}")
        if not self.room_cap.isOpened():
            raise RuntimeError(f"Failed to open room camera {room_camera_index}")

        print(f"✅ Entry camera (index {entry_camera_index}): READY")
        print(f"✅ Room camera (index {room_camera_index}): READY")
        print("=" * 60 + "\n")

        # Statistics
        self.stats = {
            "entry_detections": 0,
            "room_detections": 0,
            "registered_people": 0,
            "unauthorized_detections": 0,
        }

        # Trajectory tracking
        self.trajectories = defaultdict(list)  # {person_id: [(x,y,time), ...]}

        # Setup signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n⚠️  Shutting down...")
        self.running = False

    def register_person_at_entry(self, frame):
        """
        Register a new person at entry gate (manual trigger).
        Returns person_id if registered, None otherwise.
        """
        faces = self.entry_tracker.detect_faces(frame)

        if not faces:
            return None

        # Take the first detected face
        bbox = faces[0]
        x, y, w, h = bbox

        # Extract features
        histogram = self.entry_tracker.extract_features(frame, bbox)

        if histogram is None:
            return None

        # Generate temporary UUID
        person_id = f"TEMP-{str(uuid.uuid4())[:8]}"

        # Add to database
        self.database.add_person(
            person_id, state=PersonState.WAITING_TO_ENTER, histogram=histogram
        )

        # Record entry
        self.database.record_entry(person_id)

        self.stats["registered_people"] += 1

        print(f"\n✅ Registered new person: {person_id}")
        print(f"   Currently inside: {len(self.database.inside_now)}")

        return person_id

    def process_entry_camera(self, frame):
        """Process entry camera frame."""
        faces = self.entry_tracker.detect_faces(frame)
        self.stats["entry_detections"] += len(faces)

        annotated = frame.copy()

        # Draw detections
        for bbox in faces:
            x, y, w, h = bbox
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                "FACE DETECTED",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        # Instructions
        cv2.putText(
            annotated,
            "Press 'e' to register person",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        # Stats
        cv2.putText(
            annotated,
            f"Inside: {len(self.database.inside_now)}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        return annotated

    def process_room_camera(self, frame):
        """Process room camera frame with re-identification."""
        faces = self.room_tracker.detect_faces(frame)
        self.stats["room_detections"] += len(faces)

        annotated = frame.copy()
        now = datetime.now()

        for bbox in faces:
            x, y, w, h = bbox
            center_x, center_y = x + w // 2, y + h // 2

            # Extract features
            features = self.room_tracker.extract_features(frame, bbox)

            if features is None:
                continue

            # Try to match with people inside (from entry gate)
            person_id, similarity = self._match_with_inside_people(features)

            if person_id:
                # AUTHORIZED - matched with entry gate record
                color = (0, 255, 0)  # Green
                label = f"{person_id} ({similarity:.2f})"

                # Update trajectory
                self.trajectories[person_id].append((center_x, center_y, now))

                # Keep only last 30 points
                if len(self.trajectories[person_id]) > 30:
                    self.trajectories[person_id].pop(0)

                # Calculate velocity
                velocity = self._calculate_velocity(person_id)

                # Add to database trajectory
                self.database.add_trajectory_point(
                    person_id, center_x, center_y, "room_camera", velocity=velocity
                )

                # Draw trajectory tail
                self._draw_trajectory(annotated, person_id)

            else:
                # UNAUTHORIZED - no entry gate record!
                person_id = f"UNAUTH-{self.stats['unauthorized_detections']}"
                color = (0, 0, 255)  # Red
                label = "UNAUTHORIZED!"

                self.stats["unauthorized_detections"] += 1

                # Record unauthorized entry
                self.database.record_unauthorized_entry(person_id, "room_camera")

                # Create alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.CRITICAL,
                    message=f"Unauthorized person detected in room!",
                    person_id=person_id,
                    camera_source="room_camera",
                )

            # Draw bounding box
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)

            # Draw label
            cv2.putText(
                annotated, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
            )

        return annotated

    def _match_with_inside_people(self, features):
        """
        Match detected person with people who entered through entry gate.
        Returns (person_id, similarity) or (None, 0.0).
        """
        if not self.database.inside_now:
            return None, 0.0

        best_id = None
        best_score = 0.0

        for person_id in self.database.inside_now.keys():
            if person_id not in self.database.global_features:
                continue

            person_features = self.database.global_features[person_id]
            if (
                "histogram" not in person_features
                or person_features["histogram"] is None
            ):
                continue

            # Compare histograms
            similarity = cv2.compareHist(
                features, person_features["histogram"], cv2.HISTCMP_CORREL
            )

            if similarity > best_score:
                best_score = similarity
                best_id = person_id

        # Threshold check
        if best_score >= 0.60:
            return best_id, best_score

        return None, best_score

    def _calculate_velocity(self, person_id):
        """Calculate velocity from trajectory."""
        trajectory = self.trajectories.get(person_id, [])

        if len(trajectory) < 2:
            return 0.0

        # Get last two points
        (x1, y1, t1) = trajectory[-2]
        (x2, y2, t2) = trajectory[-1]

        # Calculate distance
        distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # Calculate time difference
        time_diff = (t2 - t1).total_seconds()

        if time_diff > 0:
            return distance / time_diff  # pixels per second

        return 0.0

    def _draw_trajectory(self, frame, person_id):
        """Draw trajectory tail on frame."""
        trajectory = self.trajectories.get(person_id, [])

        if len(trajectory) < 2:
            return

        # Draw polyline
        points = [(int(x), int(y)) for x, y, _ in trajectory]

        # Color code by velocity
        velocities = [self._calculate_velocity(person_id)]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0

        if avg_velocity > 100:
            color = (0, 165, 255)  # Orange - running
        elif avg_velocity > 50:
            color = (0, 255, 255)  # Yellow - walking
        else:
            color = (0, 255, 0)  # Green - slow

        # Draw trail
        for i in range(1, len(points)):
            thickness = max(1, int(3 * (i / len(points))))
            cv2.line(frame, points[i - 1], points[i], color, thickness)

    def draw_stats_bar(self, frame, camera_name):
        """Draw statistics bar at bottom of frame."""
        h, w = frame.shape[:2]
        bar_height = 80

        # Create stats bar
        stats_bar = np.zeros((bar_height, w, 3), dtype=np.uint8)

        # Add text
        db_stats = self.database.get_stats()

        texts = [
            f"{camera_name}",
            f"Inside: {db_stats['currently_inside']}",
            f"Total Entries: {db_stats['total_entries']}",
            f"Unauthorized: {self.stats['unauthorized_detections']}",
            f"Alerts: {db_stats['total_alerts']}",
        ]

        y_pos = 25
        for text in texts:
            cv2.putText(
                stats_bar,
                text,
                (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            y_pos += 15

        # Combine
        combined = np.vstack([frame, stats_bar])
        return combined

    def run(self):
        """Main loop."""
        print("\n" + "=" * 60)
        print("ENTRY + ROOM CAMERA DEMO")
        print("=" * 60)
        print("\n📹 Camera Configuration:")
        print(f"   Camera {self.entry_camera_index}: ENTRY gate")
        print(f"   Camera {self.room_camera_index}: ROOM monitoring")
        print("\n🎮 Controls:")
        print("   'e' - Register person at entry")
        print("   'q' - Quit")
        print("\n💡 Instructions:")
        print("   1. Show face to ENTRY camera")
        print("   2. Press 'e' to register (generates UUID)")
        print("   3. Move to ROOM camera")
        print("   4. System will track you with UUID")
        print("   5. Try entering room WITHOUT registering at entry")
        print("      → System will detect UNAUTHORIZED entry!")
        print("=" * 60 + "\n")

        frame_count = 0

        try:
            while self.running:
                # Read entry camera
                ret1, entry_frame = self.entry_cap.read()
                if not ret1:
                    print("⚠️  Failed to read entry camera")
                    break

                # Read room camera
                ret2, room_frame = self.room_cap.read()
                if not ret2:
                    print("⚠️  Failed to read room camera")
                    break

                # Process frames
                entry_annotated = self.process_entry_camera(entry_frame)
                room_annotated = self.process_room_camera(room_frame)

                # Resize for display
                entry_annotated = cv2.resize(entry_annotated, (640, 480))
                room_annotated = cv2.resize(room_annotated, (640, 480))

                # Add stats bars
                entry_with_stats = self.draw_stats_bar(entry_annotated, "ENTRY GATE")
                room_with_stats = self.draw_stats_bar(room_annotated, "ROOM MONITOR")

                # Display
                cv2.imshow("Entry Camera", entry_with_stats)
                cv2.imshow("Room Camera", room_with_stats)

                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    print("\n✅ Quitting...")
                    break
                elif key == ord("e"):
                    # Register person at entry
                    person_id = self.register_person_at_entry(entry_frame)
                    if person_id is None:
                        print("❌ No face detected at entry camera")

                frame_count += 1

                # Print status every 5 seconds
                if frame_count % 150 == 0:
                    self.print_status()

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")

        finally:
            self.cleanup()

    def print_status(self):
        """Print current status."""
        print("\n" + "-" * 60)
        print("STATUS UPDATE")
        print("-" * 60)
        db_stats = self.database.get_stats()
        print(f"Currently Inside: {db_stats['currently_inside']}")
        print(f"Total Entries: {db_stats['total_entries']}")
        print(f"Unauthorized Detections: {self.stats['unauthorized_detections']}")
        print(f"Total Alerts: {db_stats['total_alerts']}")
        print("-" * 60)

    def cleanup(self):
        """Cleanup resources."""
        print("\n" + "=" * 60)
        print("SHUTTING DOWN")
        print("=" * 60)

        # Print final stats
        print("\n📊 Final Statistics:")
        db_stats = self.database.get_stats()
        print(f"   Total Entries: {db_stats['total_entries']}")
        print(f"   Unique Visitors: {db_stats['unique_visitors']}")
        print(f"   Unauthorized Detections: {self.stats['unauthorized_detections']}")
        print(f"   Total Alerts: {db_stats['total_alerts']}")
        print(f"   Entry Detections: {self.stats['entry_detections']}")
        print(f"   Room Detections: {self.stats['room_detections']}")

        # Export data
        export_path = "data/demo_export.json"
        print(f"\n💾 Exporting data to {export_path}...")
        self.database.export_to_json(export_path)

        # Release cameras
        self.entry_cap.release()
        self.room_cap.release()
        cv2.destroyAllWindows()

        # Close database
        self.database.close()

        print("\n✅ Cleanup complete!")
        print("=" * 60 + "\n")


def main():
    """Main entry point."""
    print("\n🎥 Entry + Room Camera Demo")
    print("Phase 2 Implementation - ID Generation & Tracking\n")

    # Detect cameras
    print("Detecting cameras...")
    available = []
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(i)
            cap.release()

    print(f"Found {len(available)} camera(s): {available}\n")

    if len(available) < 2:
        print("❌ Need at least 2 cameras!")
        print("   Current: MacBook webcam + 1 phone via Iriun")
        print("   Connect second phone or use available cameras")
        sys.exit(1)

    # Use first two cameras
    entry_idx = available[0]
    room_idx = available[1]

    print(f"✅ Using cameras:")
    print(f"   Entry: Camera {entry_idx}")
    print(f"   Room: Camera {room_idx}\n")

    # Run demo
    demo = EntryRoomDemo(entry_camera_index=entry_idx, room_camera_index=room_idx)
    demo.run()


if __name__ == "__main__":
    main()
