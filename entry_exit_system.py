#!/usr/bin/env python3
"""
Dual-Camera Entry/Exit Tracking System
=======================================
Tracks visitors entering and exiting using two cameras.
- Camera 0 (Phone/Iriun) = ENTRY point
- Camera 1 (Mac webcam) = EXIT point
- Prevents ID switching with grace period
- Maintains "Inside_Now" database
- Shows entry/exit statistics

Usage:
    python entry_exit_system.py

Press 'q' or Ctrl+C to exit and see summary.
"""

import signal
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

import cv2
import numpy as np


class SimpleFaceTracker:
    """Minimal face tracker with grace period to prevent ID switching."""

    def __init__(self, grace_period_seconds=3.0, similarity_threshold=0.65):
        """
        Args:
            grace_period_seconds: How long to remember a person after they disappear
            similarity_threshold: Histogram similarity threshold (0-1, higher = stricter)
        """
        self.grace_period = timedelta(seconds=grace_period_seconds)
        self.similarity_threshold = similarity_threshold
        self.active_people = {}  # {person_id: {'last_seen': datetime, 'histogram': np.array, 'bbox': tuple}}
        self.seen_in_session = (
            set()
        )  # All unique person IDs seen in this camera session

    def _compute_histogram(self, face_roi):
        """Compute simple color histogram of face region."""
        if face_roi is None or face_roi.size == 0:
            return None

        # Convert to HSV and compute histogram
        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist

    def _compare_histograms(self, hist1, hist2):
        """Compare two histograms using correlation."""
        if hist1 is None or hist2 is None:
            return 0.0
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    def _clean_expired_people(self):
        """Remove people who haven't been seen within grace period."""
        now = datetime.now()
        expired_ids = [
            person_id
            for person_id, data in self.active_people.items()
            if now - data["last_seen"] > self.grace_period
        ]
        for person_id in expired_ids:
            del self.active_people[person_id]

    def update(self, frame, face_bboxes, global_database):
        """
        Update tracker with new frame and detected faces.

        Args:
            frame: Current video frame
            face_bboxes: List of (x, y, w, h) tuples
            global_database: Global database of all known people

        Returns:
            List of (person_id, bbox) tuples
        """
        self._clean_expired_people()
        now = datetime.now()

        # Extract face histograms for all detected faces
        face_data = []
        for x, y, w, h in face_bboxes:
            face_roi = frame[y : y + h, x : x + w]
            histogram = self._compute_histogram(face_roi)
            face_data.append({"bbox": (x, y, w, h), "histogram": histogram})

        # Match detected faces to existing people
        matched_people = []
        used_face_indices = set()

        # Try to match each active person to a detected face
        for person_id, person_data in list(self.active_people.items()):
            best_match_idx = None
            best_similarity = 0.0

            for idx, face in enumerate(face_data):
                if idx in used_face_indices:
                    continue

                similarity = self._compare_histograms(
                    person_data["histogram"], face["histogram"]
                )
                if (
                    similarity > best_similarity
                    and similarity > self.similarity_threshold
                ):
                    best_similarity = similarity
                    best_match_idx = idx

            if best_match_idx is not None:
                # Re-identified existing person
                matched_face = face_data[best_match_idx]
                self.active_people[person_id] = {
                    "last_seen": now,
                    "histogram": matched_face["histogram"],
                    "bbox": matched_face["bbox"],
                }
                matched_people.append((person_id, matched_face["bbox"]))
                used_face_indices.add(best_match_idx)

        # Try to match unmatched faces against global database
        for idx, face in enumerate(face_data):
            if idx not in used_face_indices:
                # Try to match against global database
                best_match_id = None
                best_similarity = 0.0

                for global_id, global_data in global_database.items():
                    similarity = self._compare_histograms(
                        global_data["histogram"], face["histogram"]
                    )
                    if (
                        similarity > best_similarity
                        and similarity > self.similarity_threshold
                    ):
                        best_similarity = similarity
                        best_match_id = global_id

                if best_match_id is not None:
                    # Recognized from global database
                    person_id = best_match_id
                else:
                    # Create new ID
                    person_id = str(uuid.uuid4())[:8]
                    # Add to global database
                    global_database[person_id] = {
                        "histogram": face["histogram"],
                        "first_seen": now,
                    }

                self.active_people[person_id] = {
                    "last_seen": now,
                    "histogram": face["histogram"],
                    "bbox": face["bbox"],
                }
                self.seen_in_session.add(person_id)
                matched_people.append((person_id, face["bbox"]))
                used_face_indices.add(idx)

        return matched_people


class EntryExitDatabase:
    """Manages visitor entry/exit records."""

    def __init__(self):
        self.inside_now = {}  # {person_id: {'entry_time': datetime, 'encounters': int}}
        self.all_entries = []  # List of all entry events
        self.all_exits = []  # List of all exit events
        self.global_people = {}  # Global database of all known people

    def record_entry(self, person_id):
        """Record a person entering."""
        now = datetime.now()
        if person_id not in self.inside_now:
            self.inside_now[person_id] = {
                "entry_time": now,
                "encounters": 1,
            }
            self.all_entries.append({"person_id": person_id, "time": now})
            return True  # New entry
        else:
            # Already inside, increment encounters
            self.inside_now[person_id]["encounters"] += 1
            return False  # Already inside

    def record_exit(self, person_id):
        """Record a person exiting."""
        now = datetime.now()
        if person_id in self.inside_now:
            entry_time = self.inside_now[person_id]["entry_time"]
            duration = (now - entry_time).total_seconds()
            self.all_exits.append(
                {
                    "person_id": person_id,
                    "time": now,
                    "entry_time": entry_time,
                    "duration_seconds": duration,
                }
            )
            del self.inside_now[person_id]
            return True  # Successful exit
        return False  # Not inside

    def get_stats(self):
        """Get current statistics."""
        return {
            "currently_inside": len(self.inside_now),
            "total_entries": len(self.all_entries),
            "total_exits": len(self.all_exits),
            "unique_visitors": len(set([e["person_id"] for e in self.all_entries])),
        }


class EntryExitApp:
    """Main application for dual-camera entry/exit tracking."""

    def __init__(self, entry_camera_index=1, exit_camera_index=0):
        self.running = True
        self.entry_camera_index = entry_camera_index
        self.exit_camera_index = exit_camera_index

        # Initialize database
        self.database = EntryExitDatabase()

        # Initialize trackers
        self.entry_tracker = SimpleFaceTracker(
            grace_period_seconds=3.0, similarity_threshold=0.65
        )
        self.exit_tracker = SimpleFaceTracker(
            grace_period_seconds=3.0, similarity_threshold=0.65
        )

        # Load Haar Cascade for face detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        if self.face_cascade.empty():
            raise RuntimeError("Failed to load Haar Cascade classifier")

        # Setup signal handler for graceful exit
        signal.signal(signal.SIGINT, self.signal_handler)

        # Track previous frame IDs to detect new entries/exits
        self.prev_entry_ids = set()
        self.prev_exit_ids = set()

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n" + "=" * 70)
        print("SHUTTING DOWN...")
        print("=" * 70)
        self.running = False

    def detect_faces(self, frame):
        """Detect faces in a frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return faces

    def draw_annotations(self, frame, matched_people, camera_type, stats):
        """Draw bounding boxes and labels on frame."""
        # Set color based on camera type
        if camera_type == "ENTRY":
            color = (0, 255, 0)  # Green for entry
            label_prefix = "ENTRY"
        else:
            color = (0, 0, 255)  # Red for exit
            label_prefix = "EXIT"

        # Draw bounding boxes and IDs
        for person_id, (x, y, w, h) in matched_people:
            # Draw rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            # Draw ID label with background
            label = f"{person_id}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 2
            (label_w, label_h), baseline = cv2.getTextSize(
                label, font, font_scale, thickness
            )

            # Background rectangle
            cv2.rectangle(
                frame,
                (x, y - label_h - 10),
                (x + label_w + 10, y),
                color,
                -1,
            )
            # Text
            cv2.putText(
                frame,
                label,
                (x + 5, y - 5),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
            )

        # Draw camera type label
        cv2.rectangle(frame, (0, 0), (250, 40), color, -1)
        cv2.putText(
            frame,
            f"{camera_type} CAMERA",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        # Draw stats
        active_count = len(matched_people)
        stats_text = f"Detected: {active_count}"
        cv2.putText(
            frame,
            stats_text,
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

        return frame

    def run(self):
        """Main detection loop."""
        # Try to open both cameras
        entry_cap = cv2.VideoCapture(self.entry_camera_index)
        exit_cap = cv2.VideoCapture(self.exit_camera_index)

        if not entry_cap.isOpened():
            print(f"ERROR: Cannot open ENTRY camera (index {self.entry_camera_index})!")
            print("\nTroubleshooting:")
            print("1. Check if Iriun app is running on phone and Mac")
            print("2. Check if phone and Mac are on same network")
            print("3. Check camera permissions in System Settings")
            return

        if not exit_cap.isOpened():
            print(f"ERROR: Cannot open EXIT camera (index {self.exit_camera_index})!")
            print("\nTroubleshooting:")
            print("1. Check if Mac webcam is available")
            print("2. Check camera permissions in System Settings")
            print("3. Try camera index 2 instead of 0")
            entry_cap.release()
            return

        print("\n" + "=" * 70)
        print("ENTRY/EXIT TRACKING SYSTEM STARTED")
        print("=" * 70)
        print("Configuration:")
        print(f"  ENTRY Camera: Index {self.entry_camera_index} (Phone/Iriun)")
        print(f"  EXIT Camera:  Index {self.exit_camera_index} (Mac Webcam)")
        print("\nInstructions:")
        print("  - Show face at ENTRY camera to enter")
        print("  - Show face at EXIT camera to exit")
        print("  - System tracks who's currently inside")
        print("  - Press 'q' or Ctrl+C to exit and see summary")
        print("=" * 70 + "\n")

        frame_count = 0

        try:
            while self.running:
                # Read from both cameras
                ret_entry, frame_entry = entry_cap.read()
                ret_exit, frame_exit = exit_cap.read()

                if not ret_entry or not ret_exit:
                    print("Failed to grab frames")
                    break

                frame_count += 1

                # Detect faces in both cameras
                entry_faces = self.detect_faces(frame_entry)
                exit_faces = self.detect_faces(frame_exit)

                # Update trackers
                entry_people = self.entry_tracker.update(
                    frame_entry, entry_faces, self.database.global_people
                )
                exit_people = self.exit_tracker.update(
                    frame_exit, exit_faces, self.database.global_people
                )

                # Get current IDs
                current_entry_ids = set([pid for pid, _ in entry_people])
                current_exit_ids = set([pid for pid, _ in exit_people])

                # Detect new entries (IDs that appeared at entry camera)
                new_entries = current_entry_ids - self.prev_entry_ids
                for person_id in new_entries:
                    if self.database.record_entry(person_id):
                        print(f"✓ ENTRY: {person_id} entered")

                # Detect new exits (IDs that appeared at exit camera)
                new_exits = current_exit_ids - self.prev_exit_ids
                for person_id in new_exits:
                    if self.database.record_exit(person_id):
                        print(f"✗ EXIT:  {person_id} exited")

                # Update previous IDs
                self.prev_entry_ids = current_entry_ids
                self.prev_exit_ids = current_exit_ids

                # Get stats
                stats = self.database.get_stats()

                # Draw annotations
                frame_entry = self.draw_annotations(
                    frame_entry, entry_people, "ENTRY", stats
                )
                frame_exit = self.draw_annotations(
                    frame_exit, exit_people, "EXIT", stats
                )

                # Combine frames side-by-side
                # Resize if needed to make them same height
                h_entry, w_entry = frame_entry.shape[:2]
                h_exit, w_exit = frame_exit.shape[:2]

                if h_entry != h_exit:
                    # Resize exit frame to match entry frame height
                    scale = h_entry / h_exit
                    new_w_exit = int(w_exit * scale)
                    frame_exit = cv2.resize(frame_exit, (new_w_exit, h_entry))

                # Concatenate horizontally
                combined_frame = np.hstack((frame_entry, frame_exit))

                # Add overall stats at the bottom
                h_combined, w_combined = combined_frame.shape[:2]
                stats_bar = np.zeros((80, w_combined, 3), dtype=np.uint8)

                # Draw stats
                cv2.putText(
                    stats_bar,
                    f"Currently Inside: {stats['currently_inside']}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    stats_bar,
                    f"Total Entries: {stats['total_entries']}",
                    (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )
                cv2.putText(
                    stats_bar,
                    f"Total Exits: {stats['total_exits']}",
                    (w_combined // 2, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )
                cv2.putText(
                    stats_bar,
                    f"Unique Visitors: {stats['unique_visitors']}",
                    (w_combined // 2, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

                # Combine with stats bar
                final_frame = np.vstack((combined_frame, stats_bar))

                # Display frame
                cv2.imshow("Entry/Exit Tracking - Press Q to Exit", final_frame)

                # Print status every 30 frames
                if frame_count % 30 == 0:
                    print(
                        f"Frame {frame_count:4d} | Inside: {stats['currently_inside']} | "
                        f"Entries: {stats['total_entries']} | Exits: {stats['total_exits']}"
                    )

                # Check for exit
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:  # 'q' or ESC
                    self.running = False
                    break

        finally:
            # Cleanup
            entry_cap.release()
            exit_cap.release()
            cv2.destroyAllWindows()

            # Print final summary
            self._print_summary()

    def _print_summary(self):
        """Print final tracking summary."""
        stats = self.database.get_stats()

        print("\n" + "=" * 70)
        print("ENTRY/EXIT TRACKING SUMMARY")
        print("=" * 70)
        print(f"Total Unique Visitors:    {stats['unique_visitors']}")
        print(f"Total Entries:            {stats['total_entries']}")
        print(f"Total Exits:              {stats['total_exits']}")
        print(f"Currently Inside:         {stats['currently_inside']}")
        print("=" * 70)

        if self.database.inside_now:
            print("\nPeople Currently Inside:")
            for idx, (person_id, data) in enumerate(
                self.database.inside_now.items(), 1
            ):
                entry_time = data["entry_time"]
                duration = (datetime.now() - entry_time).total_seconds()
                print(
                    f"  {idx}. {person_id} (Inside for {duration:.0f}s, "
                    f"seen {data['encounters']} times)"
                )
        else:
            print("\n✓ Everyone has exited!")

        if self.database.all_exits:
            print("\nRecent Exits (Last 5):")
            for idx, exit_data in enumerate(self.database.all_exits[-5:], 1):
                person_id = exit_data["person_id"]
                duration = exit_data["duration_seconds"]
                print(f"  {idx}. {person_id} (Visit duration: {duration:.0f}s)")

        print("=" * 70 + "\n")


def find_cameras():
    """Helper function to find available cameras."""
    print("\n" + "=" * 70)
    print("SCANNING FOR AVAILABLE CAMERAS...")
    print("=" * 70)

    available_cameras = []
    for i in range(5):  # Check indices 0-4
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                available_cameras.append(i)
                print(f"✓ Camera {i}: Available")
            cap.release()
        else:
            print(f"✗ Camera {i}: Not available")

    print("=" * 70 + "\n")
    return available_cameras


def main():
    """Entry point."""
    print("\n" + "=" * 70)
    print("ENTRY/EXIT TRACKING SYSTEM")
    print("=" * 70)

    # Find available cameras
    available = find_cameras()

    if len(available) < 2:
        print("ERROR: Need at least 2 cameras!")
        print(f"Found only {len(available)} camera(s): {available}")
        print("\nTroubleshooting:")
        print("1. Make sure Iriun app is running on phone")
        print("2. Ensure phone and Mac are on same WiFi network")
        print("3. Check camera permissions in System Settings")
        print("\nTo manually specify camera indices, edit entry_exit_system.py")
        print(
            "and change: app = EntryExitApp(entry_camera_index=0, exit_camera_index=1)"
        )
        return

    print(f"Found {len(available)} cameras: {available}")
    print(f"\nUsing:")
    print(f"  Camera {available[1]} as ENTRY (Phone/Iriun)")
    print(f"  Camera {available[0]} as EXIT (Mac Webcam)")
    print("\nStarting in 3 seconds...")
    time.sleep(3)

    try:
        app = EntryExitApp(
            entry_camera_index=available[1], exit_camera_index=available[0]
        )
        app.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
