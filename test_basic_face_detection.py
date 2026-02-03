#!/usr/bin/env python3
"""
Minimal Face Detection Script with Persistent UUID Tracking
============================================================
Tests basic face detection using Mac webcam.
- Detects faces using OpenCV Haar Cascade
- Assigns persistent UUID per person with grace period
- Shows total unique persons on Ctrl+C

Usage:
    python test_basic_face_detection.py

Press 'q' or Ctrl+C to exit and see summary.
"""

import signal
import sys
import time
import uuid
from datetime import datetime, timedelta

import cv2
import numpy as np


class SimpleFaceTracker:
    """Minimal face tracker with grace period to prevent ID switching."""

    def __init__(self, grace_period_seconds=3.0, similarity_threshold=0.7):
        """
        Args:
            grace_period_seconds: How long to remember a person after they disappear
            similarity_threshold: Histogram similarity threshold (0-1, higher = stricter)
        """
        self.grace_period = timedelta(seconds=grace_period_seconds)
        self.similarity_threshold = similarity_threshold
        self.active_people = {}  # {person_id: {'last_seen': datetime, 'histogram': np.array, 'bbox': tuple}}
        self.total_unique_people = set()  # All unique person IDs ever seen

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

    def update(self, frame, face_bboxes):
        """
        Update tracker with new frame and detected faces.

        Args:
            frame: Current video frame
            face_bboxes: List of (x, y, w, h) tuples

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

        # Create new IDs for unmatched faces
        for idx, face in enumerate(face_data):
            if idx not in used_face_indices:
                new_id = str(uuid.uuid4())[:8]  # Short UUID
                self.active_people[new_id] = {
                    "last_seen": now,
                    "histogram": face["histogram"],
                    "bbox": face["bbox"],
                }
                self.total_unique_people.add(new_id)
                matched_people.append((new_id, face["bbox"]))

        return matched_people

    def get_total_unique_count(self):
        """Get total number of unique people ever detected."""
        return len(self.total_unique_people)


class FaceDetectionApp:
    """Main application for face detection."""

    def __init__(self):
        self.running = True
        self.tracker = SimpleFaceTracker(
            grace_period_seconds=3.0, similarity_threshold=0.65
        )

        # Load Haar Cascade for face detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        if self.face_cascade.empty():
            raise RuntimeError("Failed to load Haar Cascade classifier")

        # Setup signal handler for graceful exit
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n" + "=" * 60)
        print("SHUTTING DOWN...")
        print("=" * 60)
        self.running = False

    def run(self):
        """Main detection loop."""
        # Open webcam
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("ERROR: Cannot open webcam!")
            print("\nTroubleshooting:")
            print("1. Check System Settings → Privacy & Security → Camera")
            print("2. Enable camera access for Terminal/iTerm/VS Code")
            print("3. Restart terminal after enabling")
            print("4. Try: sudo killall VDCAssistant")
            return

        print("\n" + "=" * 60)
        print("FACE DETECTION STARTED")
        print("=" * 60)
        print("Instructions:")
        print("  - Show your face to the camera")
        print("  - Each unique person gets a Unique ID")
        print("  - Press 'q' or Ctrl+C to exit and see summary")
        print("=" * 60 + "\n")

        frame_count = 0

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to grab frame")
                    break

                frame_count += 1

                # Detect faces every frame
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                )

                # Update tracker
                matched_people = self.tracker.update(frame, faces)

                # Draw bounding boxes and IDs
                for person_id, (x, y, w, h) in matched_people:
                    # Draw rectangle
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Draw ID label with background
                    label = f"ID: {person_id}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    thickness = 2
                    (label_w, label_h), baseline = cv2.getTextSize(
                        label, font, font_scale, thickness
                    )

                    # Background rectangle
                    cv2.rectangle(
                        frame,
                        (x, y - label_h - 10),
                        (x + label_w + 10, y),
                        (0, 255, 0),
                        -1,
                    )
                    # Text
                    cv2.putText(
                        frame,
                        label,
                        (x + 5, y - 5),
                        font,
                        font_scale,
                        (0, 0, 0),
                        thickness,
                    )

                # Show stats
                active_count = len(self.tracker.active_people)
                total_count = self.tracker.get_total_unique_count()

                stats_text = f"Active: {active_count} | Total Unique: {total_count}"
                cv2.putText(
                    frame,
                    stats_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

                # Display frame
                cv2.imshow("Face Detection - Press Q to Exit", frame)

                # Print status every 30 frames
                if frame_count % 30 == 0:
                    print(
                        f"Frame {frame_count:4d} | Active: {active_count} | Total Unique: {total_count}"
                    )

                # Check for exit
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:  # 'q' or ESC
                    self.running = False
                    break

        finally:
            # Cleanup
            cap.release()
            cv2.destroyAllWindows()

            # Print final summary
            self._print_summary()

    def _print_summary(self):
        """Print final detection summary."""
        total_unique = self.tracker.get_total_unique_count()
        all_ids = sorted(list(self.tracker.total_unique_people))

        print("\n" + "=" * 60)
        print("DETECTION SUMMARY")
        print("=" * 60)
        print(f"Total Unique Persons Detected: {total_unique}")
        print("\nUnique IDs:")
        for idx, person_id in enumerate(all_ids, 1):
            print(f"  {idx}. {person_id}")
        print("=" * 60 + "\n")


def main():
    """Entry point."""
    try:
        app = FaceDetectionApp()
        app.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
