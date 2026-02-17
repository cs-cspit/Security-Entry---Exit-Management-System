#!/usr/bin/env python3
"""
Three-Camera Entry/Exit/Room Monitoring Demo
============================================
Complete Phase 2 implementation with Entry, Exit, and Room cameras
working simultaneously.

Features:
- Entry Camera: Register people entering
- Exit Camera: Detect people exiting
- Room Camera: Track authorized people, detect unauthorized entries,
  track trajectories, compute velocity, detect gatherings

Usage:
    python demo_three_cameras.py

Controls:
    - Press 'e' to register person at entry camera
    - Press 'x' to register person at exit camera
    - Press 'q' to quit and export session data
"""

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

from alert_manager import AlertLevel, AlertManager, AlertType
from enhanced_database import EnhancedDatabase


class SimpleFaceTracker:
    """Simple face detection and tracking using Haar cascades and color histograms."""

    def __init__(self, grace_period_seconds=3.0, similarity_threshold=0.65):
        self.grace_period = grace_period_seconds
        self.similarity_threshold = similarity_threshold

        # Load Haar cascade
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        if self.face_cascade.empty():
            raise RuntimeError("Failed to load Haar cascade")

        # Track last seen times
        self.last_seen = {}  # {person_id: timestamp}

    def _compute_histogram(self, face_roi):
        """Compute HSV color histogram for face region."""
        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    def _compare_histograms(self, hist1, hist2):
        """Compare two histograms and return similarity score (0-1)."""
        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        return max(0, correlation)  # Correlation ranges from -1 to 1

    def detect_faces(self, frame):
        """Detect faces in frame and return bounding boxes."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        return faces

    def extract_features(self, frame, bbox):
        """Extract histogram features from face region."""
        x, y, w, h = bbox
        face_roi = frame[y : y + h, x : x + w]
        return self._compute_histogram(face_roi)


class ThreeCameraDemo:
    """3-camera demo: Entry gate + Exit gate + Room monitoring."""

    def __init__(self, entry_idx=0, exit_idx=1, room_idx=2):
        self.running = True
        self.entry_camera_index = entry_idx
        self.exit_camera_index = exit_idx
        self.room_camera_index = room_idx

        # Initialize database and alert manager
        self.database = EnhancedDatabase("data/three_camera_demo.db")
        self.alert_manager = AlertManager(
            cooldown_seconds=5.0,
            console_output=True,
            file_logging=True,
            log_path="data/three_camera_alerts.log",
        )

        # Initialize trackers
        self.entry_tracker = SimpleFaceTracker(
            grace_period_seconds=3.0, similarity_threshold=0.60
        )
        self.exit_tracker = SimpleFaceTracker(
            grace_period_seconds=3.0, similarity_threshold=0.60
        )
        self.room_tracker = SimpleFaceTracker(
            grace_period_seconds=2.0, similarity_threshold=0.65
        )

        # Open cameras
        print("\n" + "=" * 60)
        print("THREE-CAMERA SYSTEM INITIALIZATION")
        print("=" * 60)
        print("Attempting to open cameras...")

        self.entry_cap = cv2.VideoCapture(entry_idx)
        self.exit_cap = cv2.VideoCapture(exit_idx)
        self.room_cap = cv2.VideoCapture(room_idx)

        cameras_ok = True

        if not self.entry_cap.isOpened():
            print(f"❌ Failed to open entry camera at index {entry_idx}")
            cameras_ok = False
        else:
            print(f"✅ Entry camera (index {entry_idx}): READY")

        if not self.exit_cap.isOpened():
            print(f"❌ Failed to open exit camera at index {exit_idx}")
            cameras_ok = False
        else:
            print(f"✅ Exit camera (index {exit_idx}): READY")

        if not self.room_cap.isOpened():
            print(f"❌ Failed to open room camera at index {room_idx}")
            cameras_ok = False
        else:
            print(f"✅ Room camera (index {room_idx}): READY")

        if not cameras_ok:
            self.cleanup()
            raise RuntimeError(
                "Failed to open all cameras. Please check camera indices."
            )

        print("=" * 60 + "\n")

        # Person database
        self.registered_people = {}  # {person_id: {'features': hist, 'name': str, 'entry_time': time}}
        self.inside_people = {}  # {person_id: {'last_seen': time, 'location': (x,y)}}

        # Statistics
        self.stats = {
            "entry_detections": 0,
            "exit_detections": 0,
            "room_detections": 0,
            "registered_people": 0,
            "unauthorized_detections": 0,
            "people_exited": 0,
        }

        # Trajectory tracking
        self.trajectories = defaultdict(list)  # {person_id: [(x,y,time), ...]}

        # Velocity tracking
        self.velocity_data = defaultdict(list)  # {person_id: [velocity_values]}

        # Setup signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        # Auto-registration tracking
        self.entry_last_seen = {}  # {face_key: last_time} to prevent duplicate registration
        self.auto_register_cooldown = 3.0  # seconds between auto-registrations

        # Visual notifications for auto-registration
        self.notification_queue = []  # List of (message, timestamp, color) tuples
        self.notification_duration = 3.0  # seconds to show notification

        print("\n📋 SYSTEM READY - FULLY AUTOMATED")
        print("-" * 60)
        print("🤖 AUTO-REGISTRATION MODE:")
        print("  ✅ Entry camera will AUTO-REGISTER new people")
        print("  ✅ Room camera will AUTO-TRACK registered people")
        print("  ✅ Exit camera will AUTO-DETECT exits")
        print("\nManual Controls:")
        print("  - Press 'r' to FORCE register person at entry (override)")
        print("  - Press 'q' to quit and save session data")
        print("  - Click buttons on screen for manual control")
        print("-" * 60 + "\n")

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n⚠️  Interrupt signal received...")
        self.running = False

    def _get_face_key(self, bbox):
        """Generate a simple key for a face to track duplicates."""
        x, y, w, h = bbox
        return f"{x}_{y}_{w}_{h}"

    def auto_register_at_entry(self, frame):
        """Automatically register new people detected at entry camera."""
        faces = self.entry_tracker.detect_faces(frame)
        current_time = time.time()

        for bbox in faces:
            x, y, w, h = bbox

            # Check if we recently registered this face position
            face_key = self._get_face_key(bbox)
            last_seen = self.entry_last_seen.get(face_key, 0)

            if current_time - last_seen < self.auto_register_cooldown:
                continue  # Skip, too soon

            # Extract features
            features = self.entry_tracker.extract_features(frame, bbox)

            # Check if this person is already registered (match existing features)
            is_already_registered = False
            for person_id, person_info in self.registered_people.items():
                registered_features = person_info["features"]
                similarity = self.entry_tracker._compare_histograms(
                    features, registered_features
                )
                if similarity >= 0.70:  # High threshold for auto-registration
                    is_already_registered = True
                    break

            if is_already_registered:
                continue  # Already registered, skip

            # Generate person ID
            person_id = f"P{len(self.registered_people) + 1:03d}"
            timestamp = time.time()

            # Store in database
            self.database.record_entry(person_id)

            # Store locally
            self.registered_people[person_id] = {
                "features": features,
                "name": person_id,
                "entry_time": timestamp,
                "bbox": bbox,
            }

            # Update last seen
            self.entry_last_seen[face_key] = current_time

            self.stats["registered_people"] += 1
            self.stats["entry_detections"] += 1

            # Create alert
            self.alert_manager.create_alert(
                alert_type=AlertType.UNAUTHORIZED_ENTRY,
                alert_level=AlertLevel.INFO,
                message=f"🤖 AUTO-REGISTERED: Person {person_id} entered",
                person_id=person_id,
                camera_source="entry",
            )

            print(f"🤖 AUTO-REGISTERED: Person {person_id} at ENTRY camera")

            # Add visual notification
            self.notification_queue.append(
                (f"AUTO-REGISTERED: {person_id}", current_time, (0, 255, 0))
            )

    def manual_register_at_entry(self):
        """Manually register a person detected at entry camera (force override)."""
        ret, frame = self.entry_cap.read()
        if not ret:
            print("❌ Failed to capture from entry camera")
            return

        faces = self.entry_tracker.detect_faces(frame)

        if len(faces) == 0:
            print("⚠️  No face detected at entry camera. Please position face in frame.")
            return

        # Use first detected face
        bbox = faces[0]
        features = self.entry_tracker.extract_features(frame, bbox)

        # Generate person ID
        person_id = f"P{len(self.registered_people) + 1:03d}"
        timestamp = time.time()

        # Store in database
        self.database.record_entry(person_id)

        # Store locally
        self.registered_people[person_id] = {
            "features": features,
            "name": person_id,
            "entry_time": timestamp,
            "bbox": bbox,
        }

        self.stats["registered_people"] += 1
        self.stats["entry_detections"] += 1

        # Create alert
        self.alert_manager.create_alert(
            alert_type=AlertType.UNAUTHORIZED_ENTRY,
            alert_level=AlertLevel.INFO,
            message=f"👤 MANUAL REGISTRATION: Person {person_id} at ENTRY",
            person_id=person_id,
            camera_source="entry",
        )

        print(f"✅ MANUAL: Person {person_id} registered at ENTRY camera")

    def register_person_at_exit(self):
        """Register a person detected at exit camera (for testing)."""
        ret, frame = self.exit_cap.read()
        if not ret:
            print("❌ Failed to capture from exit camera")
            return

        faces = self.exit_tracker.detect_faces(frame)

        if len(faces) == 0:
            print("⚠️  No face detected at exit camera. Please position face in frame.")
            return

        # Use first detected face
        bbox = faces[0]

        print(f"✅ Face detected at EXIT camera (position: {bbox})")
        self.stats["exit_detections"] += 1

    def process_entry_camera(self, frame):
        """Process entry camera frame with AUTO-REGISTRATION."""
        # Auto-register any detected faces
        self.auto_register_at_entry(frame)

        faces = self.entry_tracker.detect_faces(frame)

        for x, y, w, h in faces:
            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

            # Draw label with background for better visibility
            label = "AUTO-ENTRY"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            label_w, label_h = label_size

            # Draw background rectangle for label
            cv2.rectangle(
                frame, (x, y - label_h - 10), (x + label_w + 10, y), (0, 255, 0), -1
            )

            # Draw text on background
            cv2.putText(
                frame,
                label,
                (x + 5, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 0),
                2,
            )

        # Add status message
        cv2.putText(
            frame,
            f"AUTO-REGISTER MODE | Total: {self.stats['registered_people']}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

        # Draw notifications
        self._draw_notifications(frame)

        # Draw manual override button
        button_x, button_y, button_w, button_h = 10, 50, 200, 40
        cv2.rectangle(
            frame,
            (button_x, button_y),
            (button_x + button_w, button_y + button_h),
            (0, 200, 0),
            -1,
        )
        cv2.rectangle(
            frame,
            (button_x, button_y),
            (button_x + button_w, button_y + button_h),
            (0, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            "FORCE REGISTER (R)",
            (button_x + 10, button_y + 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )

        return frame

    def process_exit_camera(self, frame):
        """Process exit camera frame."""
        faces = self.exit_tracker.detect_faces(frame)

        for x, y, w, h in faces:
            # Try to match with inside people
            features = self.exit_tracker.extract_features(frame, (x, y, w, h))

            matched_id = None
            best_similarity = 0.0

            for person_id in list(self.inside_people.keys()):
                if person_id in self.registered_people:
                    registered_features = self.registered_people[person_id]["features"]
                    similarity = self.exit_tracker._compare_histograms(
                        features, registered_features
                    )

                    if (
                        similarity > best_similarity
                        and similarity >= self.exit_tracker.similarity_threshold
                    ):
                        best_similarity = similarity
                        matched_id = person_id

            if matched_id:
                # Person exiting - draw with prominent label
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 3)

                label = f"EXIT: {matched_id}"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                label_w, label_h = label_size

                # Draw background rectangle for label
                cv2.rectangle(
                    frame,
                    (x, y - label_h - 10),
                    (x + label_w + 10, y),
                    (0, 255, 255),
                    -1,
                )

                # Draw text on background
                cv2.putText(
                    frame,
                    label,
                    (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 0),
                    2,
                )

                # Record exit
                self.database.record_exit(matched_id)

                # Remove from inside tracking
                if matched_id in self.inside_people:
                    del self.inside_people[matched_id]

                self.stats["people_exited"] += 1

                # Alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.INFO,
                    message=f"Person {matched_id} exited",
                    person_id=matched_id,
                    camera_source="exit",
                )
            else:
                # Unknown person at exit
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 165, 255), 3)

                label = "UNKNOWN"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                label_w, label_h = label_size

                # Draw background rectangle for label
                cv2.rectangle(
                    frame,
                    (x, y - label_h - 10),
                    (x + label_w + 10, y),
                    (0, 165, 255),
                    -1,
                )

                # Draw text on background
                cv2.putText(
                    frame,
                    label,
                    (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                )

        # Add instructions
        cv2.putText(
            frame,
            "Press 'x' to test detection",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        return frame

    def process_room_camera(self, frame):
        """Process room camera frame - main monitoring logic."""
        faces = self.room_tracker.detect_faces(frame)
        current_time = time.time()

        for x, y, w, h in faces:
            center_x = x + w // 2
            center_y = y + h // 2

            # Extract features
            features = self.room_tracker.extract_features(frame, (x, y, w, h))

            # Try to match with registered people
            matched_id = self._match_with_inside_people(features)

            if matched_id:
                # Authorized person
                color = (0, 255, 0)  # Green
                label = matched_id

                # Update tracking
                self.inside_people[matched_id] = {
                    "last_seen": current_time,
                    "location": (center_x, center_y),
                }

                # Record trajectory
                self.trajectories[matched_id].append((center_x, center_y, current_time))

                # Keep last 50 points
                if len(self.trajectories[matched_id]) > 50:
                    self.trajectories[matched_id] = self.trajectories[matched_id][-50:]

                # Calculate velocity
                velocity = self._calculate_velocity(matched_id)
                if velocity is not None:
                    self.velocity_data[matched_id].append(velocity)

                    # Check for running (velocity threshold)
                    if velocity > 2.0:  # meters per second
                        self.alert_manager.create_alert(
                            alert_type=AlertType.RUNNING,
                            alert_level=AlertLevel.WARNING,
                            message=f"Person {matched_id} running detected (velocity: {velocity:.2f} m/s)",
                            person_id=matched_id,
                            camera_source="room",
                        )

                # Draw trajectory
                self._draw_trajectory(frame, matched_id)

                # Record in database
                self.database.add_trajectory_point(
                    person_id=matched_id, x=center_x, y=center_y, camera_source="room"
                )

            else:
                # Unauthorized person!
                color = (0, 0, 255)  # Red
                label = "UNAUTHORIZED"

                self.stats["unauthorized_detections"] += 1

                # Create alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.CRITICAL,
                    message=f"UNAUTHORIZED person detected in room at ({center_x}, {center_y})",
                    camera_source="room",
                )

            # Draw bounding box with thicker line
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

            # Draw label with background box for better visibility
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
            label_w, label_h = label_size

            # Background color (same as bounding box)
            bg_color = color

            # Text color (contrasting - white for red, black for green)
            if matched_id:
                text_color = (0, 0, 0)  # Black text on green background
            else:
                text_color = (255, 255, 255)  # White text on red background

            # Draw filled rectangle as background for label
            cv2.rectangle(
                frame, (x, y - label_h - 15), (x + label_w + 15, y), bg_color, -1
            )

            # Draw the label text
            cv2.putText(
                frame,
                label,
                (x + 7, y - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                text_color,
                2,
            )

            # Draw center point
            cv2.circle(frame, (center_x, center_y), 5, color, -1)

            self.stats["room_detections"] += 1

        # Check for mass gathering
        if len(faces) >= 5:
            self.alert_manager.create_alert(
                alert_type=AlertType.MASS_GATHERING,
                alert_level=AlertLevel.WARNING,
                message=f"Mass gathering detected: {len(faces)} people in room",
                camera_source="room",
            )

        return frame

    def _match_with_inside_people(self, features):
        """Match detected person with registered people."""
        best_match_id = None
        best_similarity = 0.0

        for person_id, person_info in self.registered_people.items():
            registered_features = person_info["features"]
            similarity = self.room_tracker._compare_histograms(
                features, registered_features
            )

            if (
                similarity > best_similarity
                and similarity >= self.room_tracker.similarity_threshold
            ):
                best_similarity = similarity
                best_match_id = person_id

        return best_match_id

    def _calculate_velocity(self, person_id):
        """Calculate velocity from recent trajectory points."""
        trajectory = self.trajectories.get(person_id, [])

        if len(trajectory) < 2:
            return None

        # Use last two points
        (x1, y1, t1) = trajectory[-2]
        (x2, y2, t2) = trajectory[-1]

        # Calculate distance
        distance_pixels = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        time_delta = t2 - t1

        if time_delta <= 0:
            return None

        # Convert pixels to meters (rough calibration - adjust per camera)
        pixels_per_meter = 100  # Calibrate this value!
        distance_meters = distance_pixels / pixels_per_meter

        # Velocity in m/s
        velocity = distance_meters / time_delta

        return velocity

    def _draw_trajectory(self, frame, person_id):
        """Draw trajectory tail for person."""
        trajectory = self.trajectories.get(person_id, [])

        if len(trajectory) < 2:
            return

        # Draw lines connecting trajectory points
        for i in range(1, len(trajectory)):
            pt1 = (int(trajectory[i - 1][0]), int(trajectory[i - 1][1]))
            pt2 = (int(trajectory[i][0]), int(trajectory[i][1]))

            # Fade effect: older points are more transparent
            alpha = i / len(trajectory)
            thickness = max(1, int(alpha * 3))

            cv2.line(frame, pt1, pt2, (255, 0, 255), thickness)

    def draw_stats_panel(self, frame, camera_name):
        """Draw statistics panel on frame."""
        panel_height = 120
        panel = np.zeros((panel_height, frame.shape[1], 3), dtype=np.uint8)

        # Background
        panel[:] = (40, 40, 40)

        # Title with AUTO indicator
        title = f"{camera_name} CAMERA"
        if camera_name == "ENTRY":
            title += " 🤖 AUTO"

        cv2.putText(
            panel,
            title,
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0) if camera_name == "ENTRY" else (255, 255, 255),
            2,
        )

        # Stats
        stats_text = [
            f"Registered: {self.stats['registered_people']}",
            f"Inside: {len(self.inside_people)}",
            f"Exited: {self.stats['people_exited']}",
            f"Unauthorized: {self.stats['unauthorized_detections']}",
        ]

        y_offset = 50
        for text in stats_text:
            cv2.putText(
                panel,
                text,
                (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            y_offset += 20

        # Time
        current_time = datetime.now().strftime("%H:%M:%S")
        cv2.putText(
            panel,
            current_time,
            (frame.shape[1] - 100, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

        # Combine
        return np.vstack([panel, frame])

    def _draw_notifications(self, frame):
        """Draw notification messages on frame."""
        current_time = time.time()

        # Remove expired notifications
        self.notification_queue = [
            (msg, ts, color)
            for msg, ts, color in self.notification_queue
            if current_time - ts < self.notification_duration
        ]

        # Draw active notifications
        y_offset = frame.shape[0] - 60
        for msg, ts, color in self.notification_queue:
            # Calculate fade based on age
            age = current_time - ts
            alpha = 1.0 - (age / self.notification_duration)

            # Draw semi-transparent background
            text_size, _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            text_w, text_h = text_size

            # Background box
            padding = 15
            box_x1 = frame.shape[1] - text_w - padding * 2 - 20
            box_y1 = y_offset - text_h - padding
            box_x2 = frame.shape[1] - 20
            box_y2 = y_offset + padding

            # Draw background with transparency effect
            overlay = frame.copy()
            cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

            # Draw border
            cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), color, 2)

            # Draw text
            cv2.putText(
                frame,
                msg,
                (box_x1 + padding, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )

            y_offset -= text_h + padding * 2 + 10

    def run(self):
        """Main loop."""
        print("🎥 Starting three-camera monitoring system...\n")

        frame_count = 0
        fps_start_time = time.time()

        try:
            while self.running:
                # Read from all cameras
                ret_entry, frame_entry = self.entry_cap.read()
                ret_exit, frame_exit = self.exit_cap.read()
                ret_room, frame_room = self.room_cap.read()

                if not (ret_entry and ret_exit and ret_room):
                    print("⚠️  Failed to read from one or more cameras")
                    break

                # Process each camera
                frame_entry = self.process_entry_camera(frame_entry)
                frame_exit = self.process_exit_camera(frame_exit)
                frame_room = self.process_room_camera(frame_room)

                # Resize for display (to fit screen)
                display_width = 640
                display_height = 480

                frame_entry = cv2.resize(frame_entry, (display_width, display_height))
                frame_exit = cv2.resize(frame_exit, (display_width, display_height))
                frame_room = cv2.resize(frame_room, (display_width, display_height))

                # Add stats panels
                frame_entry = self.draw_stats_panel(frame_entry, "ENTRY")
                frame_exit = self.draw_stats_panel(frame_exit, "EXIT")
                frame_room = self.draw_stats_panel(frame_room, "ROOM")

                # Draw notifications on all frames
                self._draw_notifications(frame_exit)
                self._draw_notifications(frame_room)

                # Display all three windows
                cv2.imshow("Entry Camera", frame_entry)
                cv2.imshow("Exit Camera", frame_exit)
                cv2.imshow("Room Camera", frame_room)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    print("\n✅ Quit command received...")
                    break
                elif key == ord("r"):
                    # Manual override - force register
                    self.manual_register_at_entry()
                elif key == ord("x"):
                    self.register_person_at_exit()

                # Calculate FPS every 30 frames
                frame_count += 1
                if frame_count % 30 == 0:
                    elapsed = time.time() - fps_start_time
                    fps = 30 / elapsed if elapsed > 0 else 0
                    print(
                        f"📊 FPS: {fps:.1f} | Inside: {len(self.inside_people)} | "
                        f"Total Registered: {self.stats['registered_people']}"
                    )
                    fps_start_time = time.time()

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user (Ctrl+C)")

        finally:
            self.cleanup()

    def print_session_summary(self):
        """Print session statistics."""
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Registered People:        {self.stats['registered_people']}")
        print(f"Entry Detections:         {self.stats['entry_detections']}")
        print(f"Exit Detections:          {self.stats['exit_detections']}")
        print(f"Room Detections:          {self.stats['room_detections']}")
        print(f"People Exited:            {self.stats['people_exited']}")
        print(f"Unauthorized Detections:  {self.stats['unauthorized_detections']}")
        print(f"Currently Inside:         {len(self.inside_people)}")
        print("=" * 60)

        # Alert statistics
        alert_stats = self.alert_manager.get_stats()
        print("\nALERT STATISTICS:")
        print(f"  Total Alerts: {alert_stats['total_alerts']}")
        print(f"  Info:         {alert_stats['by_level'].get('info', 0)}")
        print(f"  Warning:      {alert_stats['by_level'].get('warning', 0)}")
        print(f"  Critical:     {alert_stats['by_level'].get('critical', 0)}")
        print(f"  Suppressed:   {alert_stats['suppressed_count']}")
        print()

    def cleanup(self):
        """Clean up resources and export data."""
        print("\n" + "=" * 60)
        print("SHUTTING DOWN SYSTEM")
        print("=" * 60)

        # Release cameras
        if hasattr(self, "entry_cap"):
            self.entry_cap.release()
        if hasattr(self, "exit_cap"):
            self.exit_cap.release()
        if hasattr(self, "room_cap"):
            self.room_cap.release()

        cv2.destroyAllWindows()

        print("✅ Cameras released")

        # Export database
        export_path = f"data/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            self.database.export_to_json(export_path)
            print(f"✅ Session data exported to: {export_path}")
        except Exception as e:
            print(f"⚠️  Failed to export data: {e}")

        # Print summary
        self.print_session_summary()

        print("\n✅ System shutdown complete")
        print("=" * 60 + "\n")


def detect_cameras():
    """Detect available cameras and return indices."""
    print("\n" + "=" * 60)
    print("DETECTING CAMERAS")
    print("=" * 60)

    available = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"✅ Camera {i}: {width}x{height}")
                available.append(i)
            cap.release()

    print(f"\nTotal cameras found: {len(available)}")
    print("=" * 60 + "\n")

    return available


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("THREE-CAMERA ENTRY/EXIT/ROOM MONITORING SYSTEM")
    print("=" * 60)
    print("Phase 2 Complete Implementation")
    print()

    # Detect cameras
    available_cameras = detect_cameras()

    if len(available_cameras) < 3:
        print("⚠️  WARNING: Less than 3 cameras detected!")
        print(f"   Found: {len(available_cameras)} camera(s)")
        print("\nPlease ensure:")
        print("  1. All phone cameras are connected via Iriun")
        print("  2. Iriun app is running on both phones and Mac")
        print("  3. Phones and Mac are on the same network")
        print("\nYou can still run the demo, but it will use fewer cameras.")

        if len(available_cameras) < 2:
            print("\n❌ Need at least 2 cameras to run the system.")
            return 1

        response = input("\nContinue with available cameras? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Exiting...")
            return 0

    # Determine camera indices
    if len(available_cameras) >= 3:
        entry_idx = available_cameras[0]
        exit_idx = available_cameras[1]
        room_idx = available_cameras[2]
        print(f"\n✅ Using 3-camera configuration:")
    else:
        entry_idx = available_cameras[0]
        exit_idx = available_cameras[0]  # Use same as entry for testing
        room_idx = available_cameras[1]
        print(f"\n⚠️  Using 2-camera configuration (Entry=Exit):")

    print(f"   Entry Camera: Index {entry_idx}")
    print(f"   Exit Camera:  Index {exit_idx}")
    print(f"   Room Camera:  Index {room_idx}")
    print()

    # Create data directory
    Path("data").mkdir(exist_ok=True)

    # Run demo
    try:
        demo = ThreeCameraDemo(
            entry_idx=entry_idx, exit_idx=exit_idx, room_idx=room_idx
        )
        demo.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
