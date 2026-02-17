#!/usr/bin/env python3
"""
YOLO-Based Three-Camera Entry/Exit/Room Monitoring System
Uses YOLOv8-face for face detection and YOLOv11 for body detection
Multi-modal re-identification for robust tracking across cameras
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
    from detectors.hybrid_face_detector import HybridFaceDetector
    from detectors.yolov11_body_detector import YOLOv11BodyDetector
    from enhanced_database import EnhancedDatabase
    from multi_modal_reid import MultiModalReID
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("\n💡 Please install required packages:")
    print("   pip install ultralytics torch torchvision opencv-python numpy pyyaml")
    print("   Optional (for better face detection): pip install mediapipe")
    sys.exit(1)


class YOLOThreeCameraSystem:
    """
    Three-camera monitoring system using YOLO models for detection
    and multi-modal re-identification.
    """

    def __init__(self, entry_idx=0, room_idx=2, exit_idx=1):
        """Initialize the YOLO-based three-camera system."""
        print("\n" + "=" * 60)
        print("YOLO-BASED THREE-CAMERA MONITORING SYSTEM")
        print("=" * 60)
        print("Using YOLOv8-face + YOLOv11 + Multi-Modal Re-ID\n")

        self.entry_idx = entry_idx
        self.room_idx = room_idx
        self.exit_idx = exit_idx
        self.running = True

        # Initialize detectors
        print("🔧 Initializing detectors...")
        try:
            # Use hybrid face detector (auto-fallback to MediaPipe/Haar if YOLO unavailable)
            self.face_detector = HybridFaceDetector(
                model_path="yolov8n-face.pt", confidence_threshold=0.5, device="auto"
            )

            # Body detector (YOLOv11 will auto-download)
            self.body_detector = YOLOv11BodyDetector(
                model_path="yolo11n.pt", confidence_threshold=0.5, device="auto"
            )

            print("✅ Detectors initialized successfully")
            print(f"   Face detection: {self.face_detector.method}")
            print(f"   Body detection: yolov11\n")
        except Exception as e:
            print(f"❌ Failed to initialize detectors: {e}")
            print("\n💡 Troubleshooting:")
            print("   1. For YOLOv8-face: Run 'python download_yolo_face.py'")
            print("   2. For MediaPipe fallback: pip install mediapipe")
            print("   3. Haar Cascade (built-in) will be used as last resort")
            raise

        # Initialize multi-modal re-ID system
        self.reid_system = MultiModalReID(
            face_weight=0.6,
            body_weight=0.4,
            similarity_threshold=0.45,  # Lower threshold for multi-modal
        )

        # Initialize alert manager and database
        self.alert_manager = AlertManager()
        self.database = EnhancedDatabase()

        # Person database with session tracking
        self.registered_people = {}  # {person_id: profile}
        self.inside_people = {}  # {person_id: last_seen_time}
        self.active_sessions = {}  # {person_id: session_id} - ONLY active entries
        self.person_status = {}  # {person_id: 'active' or 'exited'}

        # Session counter for unique session IDs
        self.session_counter = 0

        # Tracking data
        self.trajectories = defaultdict(list)
        self.velocity_data = defaultdict(list)
        self.last_detection_time = defaultdict(float)

        # Statistics
        self.stats = {
            "registered_people": 0,
            "people_inside": 0,
            "people_exited": 0,
            "unauthorized_detections": 0,
            "total_detections": 0,
        }

        # Auto-registration settings
        self.entry_cooldown = {}
        self.auto_register_cooldown = 3.0

        # Visual notifications
        self.notification_queue = []
        self.notification_duration = 3.0

        # Open cameras
        self._init_cameras()

        # Setup signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        print("\n✅ YOLO-based system ready!")
        print("=" * 60 + "\n")

    def _init_cameras(self):
        """Initialize camera connections."""
        print("📹 Opening cameras...")
        self.cap_entry = cv2.VideoCapture(self.entry_idx)
        self.cap_room = cv2.VideoCapture(self.room_idx)
        self.cap_exit = cv2.VideoCapture(self.exit_idx)

        cameras_ok = all(
            [
                self.cap_entry.isOpened(),
                self.cap_room.isOpened(),
                self.cap_exit.isOpened(),
            ]
        )

        if not cameras_ok:
            raise RuntimeError("Failed to open all cameras")

        print("✅ All cameras opened successfully\n")

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n⚠️  Interrupt signal received...")
        self.running = False

    def auto_register_at_entry(self, frame):
        """
        Auto-register new people at entry using both face and body detection.
        """
        current_time = time.time()

        # Detect faces
        face_detections = self.face_detector.detect(frame)

        # Detect bodies
        body_detections = self.body_detector.detect(frame)

        # Process each face detection
        for face_bbox in face_detections:
            x, y, w, h, conf = face_bbox

            # Check cooldown
            face_key = f"{x}_{y}_{w}_{h}"
            if face_key in self.entry_cooldown:
                if (
                    current_time - self.entry_cooldown[face_key]
                    < self.auto_register_cooldown
                ):
                    continue

            # Extract face features
            face_features = self.face_detector.extract_face_features(
                frame, (x, y, w, h)
            )

            # Find matching body (closest body to face)
            body_bbox = self._find_matching_body(face_bbox, body_detections)
            body_features = None

            if body_bbox:
                bx, by, bw, bh, _ = body_bbox
                body_features = self.body_detector.extract_body_features(
                    frame, (bx, by, bw, bh)
                )

            # Create query profile
            query_profile = self.reid_system.create_person_profile(
                person_id="QUERY",
                face_features=face_features,
                body_features=body_features,
                face_bbox=(x, y, w, h),
                body_bbox=(bx, by, bw, bh) if body_bbox else None,
            )

            # Check if already registered
            matched_id, similarity, details = self.reid_system.is_match(
                query_profile, self.registered_people, mode="auto"
            )

            if matched_id is None:
                # New person - register
                person_id = f"P{len(self.registered_people) + 1:03d}"

                # 🔒 SECURITY: Create new session for this entry
                self.session_counter += 1
                session_id = f"S{self.session_counter:04d}"

                # Create full profile
                profile = self.reid_system.create_person_profile(
                    person_id=person_id,
                    face_features=face_features,
                    body_features=body_features,
                    face_bbox=(x, y, w, h),
                    body_bbox=(bx, by, bw, bh) if body_bbox else None,
                    timestamp=current_time,
                )

                # Store in database
                self.registered_people[person_id] = profile
                self.database.record_entry(person_id)
                self.inside_people[person_id] = current_time

                # 🔒 SECURITY: Activate session
                self.active_sessions[person_id] = session_id
                self.person_status[person_id] = "active"

                # Update stats
                self.stats["registered_people"] += 1
                self.stats["people_inside"] += 1

                # Add notification
                notification = f"✅ {person_id} REGISTERED (Face+Body)"
                self.notification_queue.append(
                    (notification, current_time, (0, 255, 0))
                )

                # Log
                print(
                    f"🤖 AUTO-REGISTERED: {person_id} (Session {session_id}) | Face conf: {conf:.2f} | Mode: {details.get('mode_used', 'N/A')}"
                )
                print(f"🔒 Active session created: {session_id} for {person_id}")

                # Alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.INFO,
                    message=f"🤖 AUTO-REGISTERED: Person {person_id} entered (Session {session_id})",
                    person_id=person_id,
                    camera_source="entry",
                )

                # Update cooldown
                self.entry_cooldown[face_key] = current_time
            elif matched_id and self.person_status.get(matched_id) == "exited":
                # 🔒 SECURITY: Known person RE-ENTERING after exit - create NEW session
                self.session_counter += 1
                session_id = f"S{self.session_counter:04d}"

                # Re-activate this person with new session
                self.inside_people[matched_id] = current_time
                self.active_sessions[matched_id] = session_id
                self.person_status[matched_id] = "active"

                # Record new entry in database
                self.database.record_entry(matched_id)
                self.stats["people_inside"] += 1

                # Add notification
                notification = f"↩️ {matched_id} RE-ENTERED (New Session)"
                self.notification_queue.append(
                    (notification, current_time, (0, 255, 255))
                )

                # Log
                print(
                    f"↩️ RE-ENTRY: {matched_id} (New Session {session_id}) | Previous session was closed"
                )
                print(f"🔒 New active session created: {session_id} for {matched_id}")

                # Alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.INFO,
                    message=f"↩️ RE-ENTRY: {matched_id} entered (New Session {session_id})",
                    person_id=matched_id,
                    camera_source="entry",
                )

                # Update cooldown
                self.entry_cooldown[face_key] = current_time

    def _find_matching_body(self, face_bbox, body_detections):
        """Find the body detection that best matches a face detection."""
        fx, fy, fw, fh, _ = face_bbox
        face_center_x = fx + fw // 2
        face_center_y = fy + fh // 2

        best_body = None
        min_distance = float("inf")

        for body_bbox in body_detections:
            bx, by, bw, bh, _ = body_bbox
            body_center_x = bx + bw // 2
            body_center_y = by + bh // 2

            # Face should be in upper part of body
            if (
                face_center_y < body_center_y
                and face_center_x > bx
                and face_center_x < (bx + bw)
            ):
                distance = abs(face_center_x - body_center_x)
                if distance < min_distance:
                    min_distance = distance
                    best_body = body_bbox

        return best_body

    def process_entry_camera(self, frame):
        """Process entry camera frame."""
        # Auto-register new people
        self.auto_register_at_entry(frame)

        # Visualize detections
        face_detections = self.face_detector.detect(frame)
        body_detections = self.body_detector.detect(frame)

        # Draw face detections
        for x, y, w, h, conf in face_detections:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            label = f"Face: {conf:.2f}"
            cv2.putText(
                frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
            )

        # Draw body detections
        for x, y, w, h, conf in body_detections:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 255), 2)
            label = f"Body: {conf:.2f}"
            cv2.putText(
                frame,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 255),
                2,
            )

        return frame

    def process_room_camera(self, frame):
        """Process room camera frame with body tracking."""
        current_time = time.time()

        # Detect bodies (primary) and faces (fallback)
        body_detections = self.body_detector.detect(frame)
        face_detections = self.face_detector.detect(frame)

        self.stats["total_detections"] += len(body_detections)

        for body_bbox in body_detections:
            x, y, w, h, conf = body_bbox
            center_x = x + w // 2
            center_y = y + h // 2

            # Extract body features
            body_features = self.body_detector.extract_body_features(
                frame, (x, y, w, h)
            )

            # Try to find matching face
            matching_face = self._find_matching_face((x, y, w, h), face_detections)
            face_features = None

            if matching_face:
                fx, fy, fw, fh, _ = matching_face
                face_features = self.face_detector.extract_face_features(
                    frame, (fx, fy, fw, fh)
                )

            # Create query profile
            query_profile = self.reid_system.create_person_profile(
                person_id="QUERY",
                face_features=face_features,
                body_features=body_features,
                face_bbox=(fx, fy, fw, fh) if matching_face else None,
                body_bbox=(x, y, w, h),
            )

            # Match against registered people
            matched_id, similarity, details = self.reid_system.is_match(
                query_profile, self.registered_people, mode="auto"
            )

            # 🔒 SECURITY CHECK: Verify person has ACTIVE session
            is_authorized = False
            if matched_id:
                if (
                    matched_id in self.active_sessions
                    and self.person_status.get(matched_id) == "active"
                ):
                    # Person has valid active session - AUTHORIZED
                    is_authorized = True
                else:
                    # Person was registered before but has no active session
                    # This means they exited and are now bypassing entry - THREAT!
                    matched_id = None  # Treat as unmatched/unauthorized

            if is_authorized and matched_id:
                # Authorized person with active session
                color = (0, 255, 0)
                label = matched_id

                # Update tracking
                self.inside_people[matched_id] = current_time
                self.last_detection_time[matched_id] = current_time

                # Draw trajectory
                self.trajectories[matched_id].append((center_x, center_y, current_time))
                if len(self.trajectories[matched_id]) > 50:
                    self.trajectories[matched_id] = self.trajectories[matched_id][-50:]

                self._draw_trajectory(frame, matched_id)

                # Record in database
                self.database.add_trajectory_point(
                    person_id=matched_id, x=center_x, y=center_y, camera_source="room"
                )

                # Draw bounding box and label
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

                # Label with UUID and similarity
                label_text = f"{label} ({similarity:.2f})"
                label_bg = cv2.getTextSize(
                    label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                )[0]
                cv2.rectangle(
                    frame, (x, y - label_bg[1] - 10), (x + label_bg[0], y), color, -1
                )
                cv2.putText(
                    frame,
                    label_text,
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 0),
                    2,
                )

                # Show detection mode
                mode_text = f"Mode: {details.get('mode_used', 'N/A')}"
                cv2.putText(
                    frame,
                    mode_text,
                    (x, y + h + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )

            else:
                # Unauthorized person (either never registered OR exited and bypassing entry)
                color = (0, 0, 255)

                # Check if this is a known person who exited
                if matched_id and self.person_status.get(matched_id) == "exited":
                    label = f"THREAT: {matched_id} (BYPASSED ENTRY)"
                    threat_msg = f"🚨 CRITICAL: {matched_id} detected in room WITHOUT re-entry! Previous session ended."
                    print(threat_msg)

                    # Critical alert
                    self.alert_manager.add_alert(
                        alert_type=AlertType.UNAUTHORIZED_ENTRY,
                        person_id=matched_id,
                        camera_source="room",
                        description=f"SECURITY BREACH: {matched_id} bypassed entry after exit",
                        level=AlertLevel.CRITICAL,
                    )
                else:
                    label = "UNAUTHORIZED"

                self.stats["unauthorized_detections"] += 1

                # Draw bounding box
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
                cv2.putText(
                    frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
                )

                # Alert
                self.alert_manager.create_alert(
                    alert_type=AlertType.UNAUTHORIZED_ENTRY,
                    alert_level=AlertLevel.CRITICAL,
                    message=f"UNAUTHORIZED person detected in room",
                    camera_source="room",
                )

                print(
                    f"❌ UNAUTHORIZED detected | Similarity: {similarity:.3f} | Mode: {details.get('mode_used', 'N/A')}"
                )

        return frame

    def _find_matching_face(self, body_bbox, face_detections):
        """Find face that matches a body detection."""
        bx, by, bw, bh = body_bbox
        body_upper_y = by + bh // 3  # Upper third of body

        for face_bbox in face_detections:
            fx, fy, fw, fh, _ = face_bbox
            face_center_x = fx + fw // 2
            face_center_y = fy + fh // 2

            # Face should be in upper body region
            if (
                face_center_y < body_upper_y
                and face_center_x > bx
                and face_center_x < (bx + bw)
            ):
                return face_bbox

        return None

    def _draw_trajectory(self, frame, person_id):
        """Draw trajectory trail for a person."""
        trajectory = self.trajectories.get(person_id, [])

        if len(trajectory) < 2:
            return

        points = [(int(x), int(y)) for x, y, _ in trajectory]

        for i in range(1, len(points)):
            pt1 = points[i - 1]
            pt2 = points[i]
            alpha = i / len(points)
            thickness = max(1, int(alpha * 3))
            cv2.line(frame, pt1, pt2, (255, 0, 255), thickness)

    def process_exit_camera(self, frame):
        """Process exit camera frame."""
        current_time = time.time()

        # Detect faces and bodies
        face_detections = self.face_detector.detect(frame)
        body_detections = self.body_detector.detect(frame)

        # Draw all body detections (blue boxes)
        for body_bbox in body_detections:
            bx, by, bw, bh, bconf = body_bbox
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 150, 0), 2)
            cv2.putText(
                frame,
                f"Body: {bconf:.2f}",
                (bx, by - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 150, 0),
                2,
            )

        # Process face detections for exit matching
        for face_bbox in face_detections:
            x, y, w, h, conf = face_bbox

            # Draw face detection (yellow box by default)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            cv2.putText(
                frame,
                f"Face: {conf:.2f}",
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                2,
            )

            # Extract features
            face_features = self.face_detector.extract_face_features(
                frame, (x, y, w, h)
            )

            # Find matching body
            body_bbox = self._find_matching_body(face_bbox, body_detections)
            body_features = None

            if body_bbox:
                bx, by, bw, bh, _ = body_bbox
                body_features = self.body_detector.extract_body_features(
                    frame, (bx, by, bw, bh)
                )

            # Create query profile
            query_profile = self.reid_system.create_person_profile(
                person_id="QUERY",
                face_features=face_features,
                body_features=body_features,
                face_bbox=(x, y, w, h),
                body_bbox=(bx, by, bw, bh) if body_bbox else None,
            )

            # Match against people inside
            matched_id, similarity, details = self.reid_system.is_match(
                query_profile,
                {pid: self.registered_people[pid] for pid in self.inside_people.keys()},
                mode="auto",
            )

            if matched_id and matched_id in self.inside_people:
                # Person exiting - draw GREEN box over the yellow one
                color = (0, 255, 0)
                label = f"{matched_id} EXITING"

                # Record exit
                self.database.record_exit(matched_id)

                # 🔒 SECURITY: Invalidate session and mark as exited
                session_id = self.active_sessions.get(matched_id, "N/A")
                if matched_id in self.active_sessions:
                    del self.active_sessions[matched_id]
                self.person_status[matched_id] = "exited"

                # Remove from inside tracking
                del self.inside_people[matched_id]
                self.stats["people_exited"] += 1
                self.stats["people_inside"] -= 1

                # Notification
                notification = f"👋 {matched_id} EXITED"
                self.notification_queue.append(
                    (notification, current_time, (0, 255, 255))
                )

                print(
                    f"👋 EXIT DETECTED: {matched_id} (Session {session_id} ended) | Similarity: {similarity:.3f}"
                )
                print(
                    f"🔒 Authorization revoked for {matched_id} - must re-enter through ENTRY camera"
                )

                # Draw MATCHED detection (green, thicker)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

                # Label background
                label_bg = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                cv2.rectangle(
                    frame, (x, y - label_bg[1] - 10), (x + label_bg[0], y), color, -1
                )
                cv2.putText(
                    frame,
                    label,
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 0),
                    2,
                )

        # Add color legend to exit camera
        legend_y = 30
        cv2.putText(
            frame,
            "EXIT DETECTION:",
            (10, legend_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            "Yellow=Face | Blue=Body | GREEN=MATCHED EXIT",
            (10, legend_y + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
        )

        return frame

    def draw_stats_panel(self, frame, camera_name):
        """Draw statistics panel on frame."""
        panel_height = 120
        panel = np.zeros((panel_height, frame.shape[1], 3), dtype=np.uint8)
        panel[:] = (40, 40, 40)

        # Title
        title = f"{camera_name} CAMERA - YOLO"
        cv2.putText(
            panel, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
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

        return np.vstack([panel, frame])

    def _draw_notifications(self, frame):
        """Draw notifications on frame."""
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
            # Background
            text_size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            padding = 15
            box_x1 = frame.shape[1] - text_size[0] - padding * 2 - 20
            box_y1 = y_offset - text_size[1] - padding
            box_x2 = frame.shape[1] - 20
            box_y2 = y_offset + padding

            overlay = frame.copy()
            cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

            # Border
            cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), color, 2)

            # Text
            cv2.putText(
                frame,
                msg,
                (box_x1 + padding, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )

            y_offset -= text_size[1] + padding * 2 + 10

    def run(self):
        """Main loop."""
        print("🎥 Starting YOLO three-camera system...\n")

        frame_count = 0
        fps_start_time = time.time()

        try:
            while self.running:
                # Read frames
                ret_entry, frame_entry = self.cap_entry.read()
                ret_room, frame_room = self.cap_room.read()
                ret_exit, frame_exit = self.cap_exit.read()

                if not (ret_entry and ret_room and ret_exit):
                    print("❌ Failed to read from cameras")
                    break

                # Process frames
                frame_entry = self.process_entry_camera(frame_entry)
                frame_room = self.process_room_camera(frame_room)
                frame_exit = self.process_exit_camera(frame_exit)

                # Add stats panels
                frame_entry = self.draw_stats_panel(frame_entry, "ENTRY")
                frame_room = self.draw_stats_panel(frame_room, "ROOM")
                frame_exit = self.draw_stats_panel(frame_exit, "EXIT")

                # Add notifications
                self._draw_notifications(frame_entry)
                self._draw_notifications(frame_room)
                self._draw_notifications(frame_exit)

                # Display
                cv2.imshow("Entry Camera (YOLO)", frame_entry)
                cv2.imshow("Room Camera (YOLO)", frame_room)
                cv2.imshow("Exit Camera (YOLO)", frame_exit)

                # FPS calculation
                frame_count += 1
                if frame_count % 30 == 0:
                    elapsed = time.time() - fps_start_time
                    fps = frame_count / elapsed
                    print(
                        f"📊 FPS: {fps:.1f} | Inside: {len(self.inside_people)} | Total Registered: {self.stats['registered_people']}"
                    )

                # Handle keys
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

        except KeyboardInterrupt:
            print("\n⚠️  Keyboard interrupt received...")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        print("\n" + "=" * 60)
        print("SHUTTING DOWN YOLO SYSTEM")
        print("=" * 60)

        # Release cameras
        self.cap_entry.release()
        self.cap_room.release()
        self.cap_exit.release()
        cv2.destroyAllWindows()
        print("✅ Cameras released")

        # Export data
        export_path = (
            f"data/yolo_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            self.database.export_to_json(export_path)
            print(f"✅ Session data exported to: {export_path}")
        except Exception as e:
            print(f"⚠️  Failed to export data: {e}")

        # Print summary
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Registered People:        {self.stats['registered_people']}")
        print(f"People Exited:            {self.stats['people_exited']}")
        print(f"Unauthorized Detections:  {self.stats['unauthorized_detections']}")
        print(f"Total Detections:         {self.stats['total_detections']}")
        print(f"Currently Inside:         {len(self.inside_people)}")
        print(f"Active Sessions:          {len(self.active_sessions)}")
        print("=" * 60)

        # Alert stats
        alert_stats = self.alert_manager.get_stats()
        print("\nALERT STATISTICS:")
        print(f"  Total Alerts: {alert_stats.get('total_alerts', 0)}")
        print(f"  Info:         {alert_stats.get('info', 0)}")
        print(f"  Warning:      {alert_stats.get('warning', 0)}")
        print(f"  Critical:     {alert_stats.get('critical', 0)}")
        print(f"  Suppressed:   {alert_stats.get('suppressed', 0)}")

        print("\n✅ YOLO system shutdown complete")
        print("=" * 60 + "\n")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("YOLO-BASED THREE-CAMERA SYSTEM")
    print("=" * 60)
    print("YOLOv8-face + YOLOv11 + Multi-Modal Re-ID")
    print("=" * 60 + "\n")

    try:
        system = YOLOThreeCameraSystem(entry_idx=0, room_idx=2, exit_idx=1)
        system.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
