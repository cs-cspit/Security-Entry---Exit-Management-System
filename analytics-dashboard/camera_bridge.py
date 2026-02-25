#!/usr/bin/env python3
"""
Camera Bridge Module
====================
Bridges the Security Camera System with the Analytics Dashboard.

Responsibilities:
- Opens and manages OpenCV camera captures (entry, room, exit)
- Optionally runs YOLO26 detection + re-identification pipeline
- Provides thread-safe frame generators for MJPEG streaming
- Writes all detection/tracking data to the shared SQLite database
- Falls back gracefully if YOLO/torch dependencies aren't available

Usage:
    bridge = CameraBridge(entry_idx=0, room_idx=2, exit_idx=1)
    bridge.start()          # Start capture + processing threads
    bridge.stop()           # Stop everything

    # MJPEG generators for Flask streaming
    for jpeg_bytes in bridge.generate_frames('entry'):
        yield jpeg_bytes
"""

import os
import signal
import sys
import threading
import time
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Import LiveDatabase (always available — no external deps)
# ---------------------------------------------------------------------------
from live_database import LiveDatabase

# ---------------------------------------------------------------------------
# Attempt to import the full YOLO security system dependencies
# ---------------------------------------------------------------------------
YOLO_AVAILABLE = False
# analytics-dashboard is now INSIDE the main project folder, so ".." IS the project root
SECURITY_SYS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
)
SECURITY_SRC_PATH = os.path.join(SECURITY_SYS_PATH, "src")

# Add to path so we can import the project modules
if os.path.isdir(SECURITY_SRC_PATH):
    sys.path.insert(0, os.path.abspath(SECURITY_SRC_PATH))
    sys.path.insert(0, os.path.abspath(SECURITY_SYS_PATH))

try:
    from alert_manager import AlertLevel, AlertManager, AlertType
    from cross_camera_adapter import CrossCameraAdapter
    from detectors.yolo26_body_detector import YOLO26BodyDetector
    from features.body_only_analyzer import BodyOnlyAnalyzer
    from features.osnet_extractor import OSNetExtractor

    YOLO_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Lightweight face detector fallback (Haar Cascade — no extra deps)
# ---------------------------------------------------------------------------
def _nms_boxes(boxes, iou_threshold=0.35):
    """
    Non-Maximum Suppression: remove redundant overlapping bounding boxes.
    boxes: list of [x, y, w, h]
    Returns: filtered list of [x, y, w, h]
    """
    if not boxes:
        return []
    boxes = np.array(boxes, dtype=np.float32)
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 0] + boxes[:, 2]
    y2 = boxes[:, 1] + boxes[:, 3]
    areas = boxes[:, 2] * boxes[:, 3]
    order = areas.argsort()[::-1]
    keep = []
    while len(order) > 0:
        i = order[0]
        keep.append(i)
        if len(order) == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return boxes[keep].astype(int).tolist()


class HaarFaceDetector:
    """
    Robust multi-cascade person detector for CCTV scenarios.

    Uses three cascades in priority order:
      1. haarcascade_frontalface_alt2   – most accurate frontal face
      2. haarcascade_profileface        – side-profile faces
      3. haarcascade_upperbody          – fallback when face not visible

    Applies histogram equalisation + NMS to minimise false positives.
    """

    def __init__(self):
        hc = cv2.data.haarcascades
        self.face_cascade = cv2.CascadeClassifier(
            hc + "haarcascade_frontalface_alt2.xml"
        )
        self.profile_cascade = cv2.CascadeClassifier(hc + "haarcascade_profileface.xml")
        self.upper_body_cascade = cv2.CascadeClassifier(
            hc + "haarcascade_upperbody.xml"
        )
        # Validate cascades loaded correctly
        for name, cas in [
            ("frontalface_alt2", self.face_cascade),
            ("profileface", self.profile_cascade),
            ("upperbody", self.upper_body_cascade),
        ]:
            if cas.empty():
                print(f"   ⚠️  Cascade failed to load: {name}")

    # ------------------------------------------------------------------
    def _preprocess(self, frame):
        """Convert to equalised grayscale for detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.equalizeHist(gray)

    def detect_people(self, frame):
        """
        Detect people in frame using multi-cascade approach.
        Returns list of (x, y, w, h) after NMS deduplication.
        """
        gray = self._preprocess(frame)
        all_boxes = []

        # --- 1. Frontal face (primary) ---
        try:
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=8,  # high = fewer false positives
                minSize=(45, 45),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            if len(faces) > 0:
                all_boxes.extend(faces.tolist())
        except Exception:
            pass

        # --- 2. Profile face (catches 45-90° turned faces) ---
        try:
            profiles = self.profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=7,
                minSize=(40, 40),
            )
            if len(profiles) > 0:
                all_boxes.extend(profiles.tolist())
            # Mirror the frame and detect again for opposite profile
            profiles_flip = self.profile_cascade.detectMultiScale(
                cv2.flip(gray, 1),
                scaleFactor=1.08,
                minNeighbors=7,
                minSize=(40, 40),
            )
            if len(profiles_flip) > 0:
                fw = frame.shape[1]
                for x, y, w, h in profiles_flip.tolist():
                    all_boxes.append([fw - x - w, y, w, h])
        except Exception:
            pass

        # --- 3. Upper-body fallback (only when no face found) ---
        if not all_boxes:
            try:
                bodies = self.upper_body_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.05,
                    minNeighbors=6,
                    minSize=(60, 90),
                )
                if len(bodies) > 0:
                    all_boxes.extend(bodies.tolist())
            except Exception:
                pass

        if not all_boxes:
            return []

        return _nms_boxes(all_boxes, iou_threshold=0.35)

    # Back-compat aliases used elsewhere in the file
    def detect_faces(self, frame):
        return self.detect_people(frame)

    def detect_bodies(self, frame):
        return self.detect_people(frame)


# ---------------------------------------------------------------------------
# Simple color histogram tracker for re-ID without YOLO
# ---------------------------------------------------------------------------
class SimpleHistogramTracker:
    """
    Lightweight person tracker using HSV colour histograms.

    Improvements over the original:
    - Higher similarity threshold (0.78) to avoid false re-ID matches
    - Uses an expanded ROI around the detection for richer colour info
    - Multi-channel histogram (H + S) with more bins for discrimination
    - Separate match() and register() helpers so callers can decide
      whether to register a new person or just query.
    """

    def __init__(self, similarity_threshold=0.78):
        self.people = {}  # {person_id: histogram}
        self.counter = 0
        self.similarity_threshold = similarity_threshold

    def _compute_histogram(self, frame, bbox):
        x, y, w, h = bbox
        fh, fw = frame.shape[:2]
        # Expand ROI slightly to capture clothing below face
        pad_x = int(w * 0.15)
        pad_y = int(h * 0.15)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(fw, x + w + pad_x)
        y2 = min(fh, y + h + pad_y * 3)  # more padding below (body/clothing)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # More bins → better discrimination between people
        hist = cv2.calcHist([hsv], [0, 1], None, [18, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    def match(self, frame, bbox):
        """
        Try to match bbox against known people.
        Returns (best_id, best_score) — best_id is None if no match.
        """
        hist = self._compute_histogram(frame, bbox)
        if hist is None:
            return None, 0.0

        best_id = None
        best_score = 0.0
        for pid, stored_hist in self.people.items():
            score = cv2.compareHist(
                hist.reshape(-1, 1).astype(np.float32),
                stored_hist.reshape(-1, 1).astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            if score > best_score:
                best_score = score
                best_id = pid

        if best_score >= self.similarity_threshold and best_id is not None:
            # EMA update so the model adapts to appearance changes
            self.people[best_id] = 0.75 * self.people[best_id] + 0.25 * hist
            return best_id, best_score
        return None, best_score

    def register(self, frame, bbox, person_id=None):
        """
        Register a new person.  If person_id is given use it, otherwise
        auto-generate one.  Returns the person_id.
        """
        hist = self._compute_histogram(frame, bbox)
        if hist is None:
            self.counter += 1
            person_id = person_id or f"P{self.counter:03d}"
            return person_id
        if person_id is None:
            self.counter += 1
            person_id = f"P{self.counter:03d}"
        self.people[person_id] = hist
        return person_id

    def match_or_register(self, frame, bbox):
        """Legacy API — match first, register if no match found."""
        pid, score = self.match(frame, bbox)
        if pid is not None:
            return pid, score
        pid = self.register(frame, bbox)
        return pid, 1.0  # 1.0 signals "new registration"

    def remove(self, person_id: str):
        """
        Remove a person from the tracker (e.g. after they have fully exited).
        Prevents stale histogram entries from causing ghost re-matches later.
        """
        self.people.pop(person_id, None)


# ---------------------------------------------------------------------------
# Frame annotator (draws bounding boxes, labels, overlays)
# ---------------------------------------------------------------------------
class FrameAnnotator:
    """Draws detection results onto frames for display."""

    FONT = cv2.FONT_HERSHEY_SIMPLEX
    COLORS = {
        "green": (0, 255, 0),
        "red": (0, 0, 255),
        "yellow": (0, 255, 255),
        "orange": (0, 165, 255),
        "cyan": (255, 255, 0),
        "magenta": (255, 0, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
    }

    @staticmethod
    def draw_detection(frame, bbox, label, color=(0, 255, 0), thickness=2):
        x, y, w, h = bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
        # Label background
        label_size = cv2.getTextSize(label, FrameAnnotator.FONT, 0.5, 1)[0]
        cv2.rectangle(
            frame,
            (x, y - label_size[1] - 10),
            (x + label_size[0] + 4, y),
            color,
            -1,
        )
        cv2.putText(
            frame, label, (x + 2, y - 5), FrameAnnotator.FONT, 0.5, (0, 0, 0), 1
        )

    @staticmethod
    def draw_overlay(frame, camera_name, stats_dict, color=(0, 255, 255)):
        """Draw status overlay at top of frame."""
        h, w = frame.shape[:2]
        overlay_h = 70
        cv2.rectangle(frame, (0, 0), (w, overlay_h), (0, 0, 0), -1)
        cv2.putText(frame, camera_name, (10, 25), FrameAnnotator.FONT, 0.7, color, 2)

        y_pos = 50
        for key, val in stats_dict.items():
            text = f"{key}: {val}"
            cv2.putText(
                frame, text, (10, y_pos), FrameAnnotator.FONT, 0.4, (200, 200, 200), 1
            )
            y_pos += 16

    @staticmethod
    def draw_velocity(frame, bbox, velocity):
        """Draw velocity indicator below bbox."""
        x, y, w, h = bbox
        text = f"{velocity:.2f} m/s"
        if velocity > 4.0:
            color = (0, 0, 255)
            text += " RUNNING!"
        elif velocity > 2.0:
            color = (0, 165, 255)
            text += " FAST"
        elif velocity > 1.0:
            color = (0, 255, 255)
        else:
            color = (0, 255, 0)

        cv2.putText(frame, text, (x, y + h + 18), FrameAnnotator.FONT, 0.4, color, 1)

    @staticmethod
    def draw_trajectory(frame, points, color=(255, 255, 0)):
        """Draw trajectory trail."""
        if len(points) < 2:
            return
        for i in range(1, len(points)):
            alpha = i / len(points)
            pt1 = (int(points[i - 1][0]), int(points[i - 1][1]))
            pt2 = (int(points[i][0]), int(points[i][1]))
            thickness = max(1, int(alpha * 3))
            c = tuple(int(v * alpha) for v in color)
            cv2.line(frame, pt1, pt2, c, thickness)


# ---------------------------------------------------------------------------
# Main Camera Bridge
# ---------------------------------------------------------------------------
class CameraBridge:
    """
    Central bridge between cameras, YOLO processing, database, and web dashboard.

    Modes:
        - FULL MODE: YOLO26 + OSNet + full re-ID pipeline (all deps installed)
        - LITE MODE: Haar Cascade face detection + histogram tracker (no extra deps)
        - RAW MODE:  Camera streaming only (no detection, just raw feeds)
    """

    def __init__(
        self,
        entry_idx: int = 0,
        room_idx: int = 2,
        exit_idx: int = 1,
        db_path: Optional[str] = None,
        auto_detect_cameras: bool = True,
        target_fps: int = 15,
        frame_width: int = 640,
        frame_height: int = 480,
        jpeg_quality: int = 70,
    ):
        self.running = False
        self.target_fps = target_fps
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.jpeg_quality = jpeg_quality
        self._lock = threading.Lock()

        # Camera indices
        self.camera_indices = {
            "entry": entry_idx,
            "room": room_idx,
            "exit": exit_idx,
        }

        # Camera captures (opened later)
        self.captures = {}  # {name: cv2.VideoCapture}

        # Latest frames (thread-safe access via lock)
        self._latest_frames = {
            "entry": None,
            "room": None,
            "exit": None,
        }
        self._latest_annotated = {
            "entry": None,
            "room": None,
            "exit": None,
        }

        # Processing threads
        self._threads = {}

        # Detect available cameras
        if auto_detect_cameras:
            self._auto_detect_cameras()

        # Determine mode
        self.mode = "RAW"
        if YOLO_AVAILABLE:
            self.mode = "FULL"
        elif (
            cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            ).empty()
            is False
        ):
            self.mode = "LITE"

        # Database path — use the SAME database as the dashboard
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(__file__), "data", "live_security.db"
            )
        self.db_path = os.path.abspath(db_path)

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # LiveDatabase — writes IMMEDIATELY to SQLite (shared with dashboard)
        self.live_db = None  # Initialized in start()

        # Legacy references (kept for FULL mode compatibility)
        self.database = None
        self.alert_manager = None
        self.detector = None
        self.osnet = None
        self.body_analyzer = None
        self.cross_camera = None
        self.haar_detector = None
        self.histogram_tracker = None

        # Tracking state (shared across all modes)
        self.registered_people = {}  # {person_id: profile}
        self.active_sessions = {}  # {person_id: session_info}
        self.person_status = {}  # {person_id: 'active'|'exited'}
        self.person_counter = 0
        self.trajectories = defaultdict(list)  # {person_id: [(x, y, time)]}
        self.velocity_data = defaultdict(list)
        self.pixels_per_meter = 100.0

        # Entry cooldown to prevent duplicate registrations
        self.entry_cooldown = {}
        self.entry_cooldown_seconds = 10.0
        self.last_entry_bbox = None
        self.entry_overlap_threshold = 0.2

        # Entry confirmation buffer — require N consecutive frames before
        # registering a brand-new person (reduces Haar false-positive registrations)
        self._entry_confirm_buffer = {}  # {coarse_grid_key: {'count', 'bbox', 'first_t'}}
        self._entry_confirm_min_frames = 2  # frames needed to confirm a new arrival

        # Exit deduplication — prevent the same person from triggering multiple
        # exit events while they linger at the exit gate
        self.recently_exited = {}  # {person_id: exit_timestamp (float)}
        self.exit_redetect_secs = 8.0  # seconds to suppress re-exit for same person

        # Running-alert cooldown — prevent spamming the alerts table when a
        # person is moving fast for several consecutive frames
        self.running_alert_cooldown = {}  # {person_id: last_alert_timestamp (float)}
        self.running_alert_cooldown_secs = 10.0  # minimum seconds between alerts

        # Temporal smoothing for stable IDs
        self.detection_history = defaultdict(list)
        self.stable_ids = {}
        self.temporal_window = 3

        # Stats (real-time, shared with dashboard)
        self.stats = {
            "registered": 0,
            "inside": 0,
            "exited": 0,
            "unauthorized": 0,
            "total_detections": 0,
            "entry_detections": 0,
            "room_detections": 0,
            "exit_detections": 0,
            "fps_entry": 0.0,
            "fps_room": 0.0,
            "fps_exit": 0.0,
            "mode": self.mode,
            "cameras_connected": 0,
            "start_time": None,
        }

        # FPS tracking
        self._frame_times = {"entry": [], "room": [], "exit": []}

        print(f"\n{'=' * 60}")
        print(f"  CAMERA BRIDGE — {self.mode} MODE")
        print(f"{'=' * 60}")
        if self.mode == "FULL":
            print("  ✅ YOLO26 + OSNet + Full Re-ID Pipeline")
        elif self.mode == "LITE":
            print("  ⚡ Haar Cascade + Histogram Tracker (lightweight)")
        else:
            print("  📹 Raw Camera Streaming (no detection)")
        print(f"  Database: {self.db_path}")
        print(f"  Target FPS: {self.target_fps}")
        print(f"  Resolution: {self.frame_width}x{self.frame_height}")
        print(f"{'=' * 60}\n")

    # -----------------------------------------------------------------------
    # Camera detection
    # -----------------------------------------------------------------------
    def _auto_detect_cameras(self):
        """Auto-detect available cameras and reassign indices."""
        print("📹 Detecting cameras...")
        available = []

        def _try_camera(idx, result_list):
            """Try to open a single camera index with a hard timeout guard."""
            try:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        result_list.append(idx)
                    cap.release()
                else:
                    cap.release()
            except Exception:
                pass

        for i in range(8):
            found = []
            t = threading.Thread(target=_try_camera, args=(i, found), daemon=True)
            t.start()
            t.join(timeout=3.0)  # give each camera index at most 3 seconds
            if found:
                available.append(found[0])

        print(f"   Found {len(available)} camera(s): {available}")

        if len(available) == 0:
            print("   ⚠️  No cameras found — will use placeholder frames")
            self.camera_indices = {"entry": -1, "room": -1, "exit": -1}
            return

        # Assign cameras
        if len(available) >= 3:
            self.camera_indices = {
                "entry": available[0],
                "room": available[2] if len(available) > 2 else available[0],
                "exit": available[1],
            }
        elif len(available) == 2:
            self.camera_indices = {
                "entry": available[0],
                "room": available[1],
                "exit": available[0],  # Shared
            }
        else:
            # Single camera — assign to all
            self.camera_indices = {
                "entry": available[0],
                "room": available[0],
                "exit": available[0],
            }

        print(f"   Entry: Camera {self.camera_indices['entry']}")
        print(f"   Room:  Camera {self.camera_indices['room']}")
        print(f"   Exit:  Camera {self.camera_indices['exit']}")

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------
    def _init_components(self):
        """Initialize detection/tracking components based on mode."""
        if self.mode == "FULL":
            self._init_full_mode()
        elif self.mode == "LITE":
            self._init_lite_mode()
        else:
            self._init_raw_mode()

    def _init_full_mode(self):
        """Initialize full YOLO26 pipeline."""
        print("🔧 Initializing FULL mode components...")
        try:
            self.detector = YOLO26BodyDetector(
                model_name="yolo26n-pose.pt",
                confidence_threshold=0.5,
                device="auto",
            )
            self.osnet = OSNetExtractor(device="auto")
            self.body_analyzer = BodyOnlyAnalyzer()
            self.cross_camera = CrossCameraAdapter()

            self.alert_manager = AlertManager(
                cooldown_seconds=5.0,
                console_output=True,
                file_logging=True,
                log_path=os.path.join(
                    os.path.dirname(self.db_path), "bridge_alerts.log"
                ),
            )

            # Feature weights (same as yolo26_complete_system.py)
            self.osnet_weight = 0.70
            self.hair_weight = 0.05
            self.skin_weight = 0.05
            self.clothing_weight = 0.20
            self.min_osnet_threshold = 0.50
            self.similarity_threshold = 0.38
            self.exit_threshold = 0.42
            self.confidence_gap = 0.15
            self.exit_confidence_gap = 0.10

            print("   ✅ YOLO26 detector loaded")
            print("   ✅ OSNet extractor loaded")
            print("   ✅ Body analyzer loaded")
            print("   ✅ Cross-camera adapter loaded")

        except Exception as e:
            print(f"   ❌ Failed to initialize FULL mode: {e}")
            traceback.print_exc()
            print("   ⚠️  Falling back to LITE mode")
            self.mode = "LITE"
            self.stats["mode"] = "LITE"
            self._init_lite_mode()

    def _init_lite_mode(self):
        """Initialize lightweight multi-cascade + histogram pipeline."""
        print("🔧 Initializing LITE mode components...")
        self.haar_detector = HaarFaceDetector()
        # Higher threshold = fewer false re-ID matches across cameras
        self.histogram_tracker = SimpleHistogramTracker(similarity_threshold=0.78)

        print("   ✅ Multi-cascade detector loaded (frontal + profile + upper-body)")
        print("   ✅ Histogram tracker loaded (threshold=0.78)")

    def _init_raw_mode(self):
        """Initialize raw streaming mode (no detection)."""
        print("🔧 Initializing RAW mode (camera streaming only)...")

    # -----------------------------------------------------------------------
    # Camera open/close
    # -----------------------------------------------------------------------
    def _open_cameras(self):
        """Open all camera captures."""
        connected = 0
        for name, idx in self.camera_indices.items():
            if idx < 0:
                self.captures[name] = None
                continue

            # Avoid opening same camera twice
            already_opened = None
            for other_name, other_cap in self.captures.items():
                if other_cap is not None and self.camera_indices.get(other_name) == idx:
                    already_opened = other_name
                    break

            if already_opened:
                self.captures[name] = self.captures[already_opened]
                connected += 1
                print(f"   📹 {name}: Sharing camera {idx} with {already_opened}")
                continue

            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                self.captures[name] = cap
                connected += 1
                print(f"   📹 {name}: Opened camera {idx}")
            else:
                self.captures[name] = None
                print(f"   ⚠️  {name}: Failed to open camera {idx}")

        self.stats["cameras_connected"] = connected
        return connected

    def _close_cameras(self):
        """Release all camera captures."""
        closed_ids = set()
        for name, cap in self.captures.items():
            if cap is not None:
                cap_id = id(cap)
                if cap_id not in closed_ids:
                    cap.release()
                    closed_ids.add(cap_id)
        self.captures.clear()

    # -----------------------------------------------------------------------
    # Frame capture
    # -----------------------------------------------------------------------
    def _read_frame(self, camera_name: str) -> Optional[np.ndarray]:
        """Read a frame from the specified camera."""
        cap = self.captures.get(camera_name)
        if cap is None or not cap.isOpened():
            return None

        ret, frame = cap.read()
        if not ret or frame is None:
            return None

        # Resize if needed
        h, w = frame.shape[:2]
        if w != self.frame_width or h != self.frame_height:
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))

        return frame

    def _generate_placeholder_frame(self, camera_name: str) -> np.ndarray:
        """Generate a placeholder frame when camera is unavailable."""
        frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        # Dark gradient background
        for y in range(self.frame_height):
            val = int(20 + 15 * (y / self.frame_height))
            frame[y, :] = (val, val, val + 5)

        # Camera name
        label = f"{camera_name.upper()} CAMERA"
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        tx = (self.frame_width - text_size[0]) // 2
        ty = self.frame_height // 2 - 20
        cv2.putText(
            frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 120), 2
        )

        # Status
        status = "NOT CONNECTED"
        text_size2 = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        sx = (self.frame_width - text_size2[0]) // 2
        cv2.putText(
            frame,
            status,
            (sx, ty + 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (80, 80, 100),
            1,
        )

        # Pulsing dot
        pulse = int(128 + 127 * np.sin(time.time() * 2))
        cv2.circle(frame, (self.frame_width // 2, ty + 60), 5, (0, 0, pulse), -1)

        return frame

    # -----------------------------------------------------------------------
    # Frame encoding for MJPEG
    # -----------------------------------------------------------------------
    def _encode_jpeg(self, frame: np.ndarray) -> bytes:
        """Encode a frame as JPEG bytes."""
        ret, buffer = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ret:
            return b""
        return buffer.tobytes()

    # -----------------------------------------------------------------------
    # FULL MODE processing
    # -----------------------------------------------------------------------
    def _extract_features_full(self, frame, detection):
        """Extract features using YOLO + OSNet + body analysis."""
        body_bbox = detection["body_bbox"]
        bx, by, bw, bh = body_bbox

        # Extract body ROI
        h, w = frame.shape[:2]
        x1 = max(0, bx)
        y1 = max(0, by)
        x2 = min(w, bx + bw)
        y2 = min(h, by + bh)
        body_roi = frame[y1:y2, x1:x2]

        if body_roi.size == 0:
            return None

        features = {}

        # OSNet embedding
        try:
            osnet_feat = self.osnet.extract(body_roi)
            if osnet_feat is not None:
                features["osnet"] = osnet_feat
        except Exception:
            pass

        # Body analysis (hair, skin, clothing)
        try:
            body_features = self.body_analyzer.analyze(body_roi)
            if body_features:
                features["body"] = body_features
        except Exception:
            pass

        return features if features else None

    def _match_person_full(self, frame, detection, target_camera="room"):
        """Full YOLO + OSNet matching pipeline."""
        features = self._extract_features_full(frame, detection)
        if not features or not self.registered_people:
            return None, 0.0, {}

        osnet_query = features.get("osnet")
        body_query = features.get("body", {})

        best_id = None
        best_score = 0.0
        second_best = 0.0
        all_scores = {}

        for pid, profile in self.registered_people.items():
            reg_features = profile.get("features", {})
            osnet_reg = reg_features.get("osnet")

            # OSNet similarity
            osnet_sim = 0.0
            if osnet_query is not None and osnet_reg is not None:
                try:
                    osnet_sim = float(
                        np.dot(osnet_query.flatten(), osnet_reg.flatten())
                        / (
                            np.linalg.norm(osnet_query) * np.linalg.norm(osnet_reg)
                            + 1e-8
                        )
                    )
                    osnet_sim = max(0.0, osnet_sim)
                except Exception:
                    osnet_sim = 0.0

            # Skip if OSNet alone is too low
            if osnet_sim < self.min_osnet_threshold:
                all_scores[pid] = {"total": 0, "osnet": osnet_sim, "rejected": True}
                continue

            # Body feature similarities (simplified)
            hair_sim = 0.5
            skin_sim = 0.5
            clothing_sim = 0.5

            reg_body = reg_features.get("body", {})
            if body_query and reg_body:
                # Hair color comparison
                h1 = body_query.get("hair_color", {}).get("dominant_color", "")
                h2 = reg_body.get("hair_color", {}).get("dominant_color", "")
                if h1 and h2:
                    hair_sim = 1.0 if h1 == h2 else 0.3

                # Upper clothing comparison
                u1 = body_query.get("upper_clothing", {}).get("dominant_colors", [])
                u2 = reg_body.get("upper_clothing", {}).get("dominant_colors", [])
                if u1 and u2:
                    common = set(u1[:2]) & set(u2[:2])
                    clothing_sim = len(common) / max(len(set(u1[:2]) | set(u2[:2])), 1)

            total = (
                osnet_sim * self.osnet_weight
                + hair_sim * self.hair_weight
                + skin_sim * self.skin_weight
                + clothing_sim * self.clothing_weight
            )

            all_scores[pid] = {
                "total": total,
                "osnet": osnet_sim,
                "hair": hair_sim,
                "skin": skin_sim,
                "clothing": clothing_sim,
            }

            if total > best_score:
                second_best = best_score
                best_score = total
                best_id = pid
            elif total > second_best:
                second_best = total

        # Apply threshold
        threshold = self.similarity_threshold
        gap_required = self.confidence_gap

        if target_camera == "exit":
            threshold = self.exit_threshold
            gap_required = self.exit_confidence_gap

        # Cross-camera adaptive threshold
        if self.cross_camera:
            threshold, gap_required = self.cross_camera.get_matching_params(
                "entry", target_camera
            )

        debug_info = {
            "all_scores": all_scores,
            "adaptive_threshold": threshold,
            "adaptive_gap": gap_required,
            "gap": best_score - second_best,
            "second_best": second_best,
        }

        if best_score < threshold:
            debug_info["reason"] = "below_threshold"
            return None, best_score, debug_info

        if len(self.registered_people) > 1:
            if (best_score - second_best) < gap_required:
                debug_info["reason"] = "ambiguous"
                return None, best_score, debug_info

        return best_id, best_score, debug_info

    def _register_person_full(self, person_id, frame, detection):
        """Register a person using full feature extraction."""
        features = self._extract_features_full(frame, detection)
        if not features:
            return False

        self.registered_people[person_id] = {
            "features": features,
            "registration_time": datetime.now(),
            "registration_camera": "entry",
        }
        return True

    # -----------------------------------------------------------------------
    # Processing loops per camera
    # -----------------------------------------------------------------------
    def _process_entry_full(self, frame):
        """Process entry camera with full YOLO pipeline."""
        display = frame.copy()
        current_time = time.time()

        detections = self.detector.detect(frame)
        self.stats["entry_detections"] += len(detections)

        for det in detections:
            bbox = det["body_bbox"]
            bx, by, bw, bh = bbox

            # Draw detection
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), (0, 255, 255), 2)

            # Check overlap cooldown
            skip = False
            if self.last_entry_bbox is not None:
                overlap = self._bbox_overlap(bbox, self.last_entry_bbox)
                elapsed = current_time - self.entry_cooldown.get("last_reg", 0)
                if (
                    overlap > self.entry_overlap_threshold
                    and elapsed < self.entry_cooldown_seconds
                ):
                    skip = True
                    cv2.putText(
                        display,
                        "REGISTERED",
                        (bx, by - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2,
                    )

            if not skip:
                self.person_counter += 1
                pid = f"P{self.person_counter:03d}"
                success = self._register_person_full(pid, frame, det)
                if success:
                    self.entry_cooldown["last_reg"] = current_time
                    self.last_entry_bbox = bbox
                    self.stats["registered"] += 1
                    self.stats["inside"] += 1
                    self.active_sessions[pid] = {
                        "entry_time": datetime.now(),
                    }
                    self.person_status[pid] = "active"
                    if self.live_db:
                        self.live_db.record_entry(pid)

                    FrameAnnotator.draw_detection(
                        display, bbox, f"NEW: {pid}", (0, 255, 0)
                    )

        FrameAnnotator.draw_overlay(
            display,
            "ENTRY GATE",
            {
                "Registered": self.stats["registered"],
                "Inside": self.stats["inside"],
            },
            (0, 255, 255),
        )

        return display

    def _process_room_full(self, frame):
        """Process room camera with full YOLO pipeline."""
        if self.cross_camera:
            frame = self.cross_camera.preprocess_frame(frame, camera_id="room")

        display = frame.copy()
        current_time = datetime.now()

        detections = self.detector.detect(frame)
        self.stats["room_detections"] += len(detections)
        self.stats["total_detections"] += len(detections)

        authorized = 0
        unauthorized = 0

        for det in detections:
            bbox = det["body_bbox"]
            bx, by, bw, bh = bbox
            cx, cy = bx + bw // 2, by + bh // 2

            pid, sim, debug = self._match_person_full(frame, det, "room")

            if pid and pid in self.active_sessions:
                authorized += 1
                FrameAnnotator.draw_detection(
                    display, bbox, f"{pid} ({sim:.2f})", (0, 255, 0)
                )

                # Trajectory
                self.trajectories[pid].append((cx, cy, current_time))
                if len(self.trajectories[pid]) > 50:
                    self.trajectories[pid].pop(0)

                # Velocity
                velocity = self._calculate_velocity(pid)
                self.velocity_data[pid].append(velocity)
                FrameAnnotator.draw_velocity(display, bbox, velocity)

                # Draw trajectory trail
                points = [(p[0], p[1]) for p in self.trajectories[pid]]
                FrameAnnotator.draw_trajectory(display, points)

                # Database — write IMMEDIATELY to SQLite
                if self.live_db:
                    self.live_db.add_trajectory_point(
                        pid, cx, cy, "room_camera", velocity=velocity
                    )
            else:
                unauthorized += 1
                self.stats["unauthorized"] += 1
                FrameAnnotator.draw_detection(
                    display, bbox, f"UNAUTH ({sim:.2f})", (0, 0, 255)
                )

                if self.live_db:
                    self.live_db.record_unauthorized(pid or "unknown", "room_camera")

        FrameAnnotator.draw_overlay(
            display,
            "ROOM MONITORING",
            {
                "Authorized": authorized,
                "Unauthorized": unauthorized,
                "Inside": self.stats["inside"],
            },
            (255, 255, 0),
        )

        return display

    def _process_exit_full(self, frame):
        """Process exit camera with full YOLO pipeline."""
        if self.cross_camera:
            frame = self.cross_camera.preprocess_frame(frame, camera_id="exit")

        display = frame.copy()
        current_time = datetime.now()

        detections = self.detector.detect(frame)
        self.stats["exit_detections"] += len(detections)

        for det in detections:
            bbox = det["body_bbox"]
            bx, by, bw, bh = bbox

            pid, sim, debug = self._match_person_full(frame, det, "exit")

            if pid and pid in self.active_sessions:
                session = self.active_sessions[pid]
                entry_time = session["entry_time"]
                duration = (current_time - entry_time).total_seconds()

                vels = self.velocity_data.get(pid, [0.0])
                avg_vel = sum(vels) / max(len(vels), 1)
                max_vel = max(vels) if vels else 0.0

                if self.live_db:
                    self.live_db.update_person_velocity(pid, avg_vel, max_vel)
                    self.live_db.record_exit(pid)

                del self.active_sessions[pid]
                self.person_status[pid] = "exited"
                self.stats["inside"] = max(0, self.stats["inside"] - 1)
                self.stats["exited"] += 1

                label = f"{pid} EXIT ({duration:.0f}s)"
                FrameAnnotator.draw_detection(display, bbox, label, (0, 255, 0))
            else:
                FrameAnnotator.draw_detection(
                    display, bbox, f"UNKNOWN ({sim:.2f})", (0, 0, 255)
                )

        FrameAnnotator.draw_overlay(
            display,
            "EXIT GATE",
            {
                "Exited": self.stats["exited"],
                "Inside": self.stats["inside"],
            },
            (255, 0, 255),
        )

        return display

    # -----------------------------------------------------------------------
    # LITE MODE processing
    # -----------------------------------------------------------------------

    def _ensure_active(self, pid, frame, bbox, source_camera="auto"):
        """
        Ensure a person is in active_sessions.
        If they were already registered (entry cam) they're already there.
        If they appear first in room/exit, auto-register them so we never
        generate spurious 'unauthorized' alerts just because the entry
        camera missed them.
        """
        if pid not in self.active_sessions:
            self.stats["registered"] += 1
            self.stats["inside"] += 1
            self.active_sessions[pid] = {
                "entry_time": datetime.now(),
                "source": source_camera,
            }
            self.person_status[pid] = "active"
            if self.live_db:
                self.live_db.record_entry(pid)

    def _process_entry_lite(self, frame):
        """
        Entry gate — detect arrivals and register new people.

        Detection pipeline:
          1. Multi-cascade person detection (frontal + profile + upper-body)
          2. Histogram match against known people
          3. If known person → update session; if brand-new → buffer for
             _entry_confirm_min_frames consecutive frames before registering
             (eliminates Haar cascade false-positive flash registrations)
        """
        display = frame.copy()
        current_time = time.time()

        # Expire stale confirm-buffer entries that haven't been seen for >2 s
        stale_keys = [
            k
            for k, v in self._entry_confirm_buffer.items()
            if current_time - v.get("last_seen", 0) > 2.0
        ]
        for k in stale_keys:
            del self._entry_confirm_buffer[k]

        detections = self.haar_detector.detect_people(frame)
        self.stats["entry_detections"] += len(detections)

        # Track which grid cells had a live detection this frame so we can
        # expire buffer entries whose subject has walked away.
        active_keys = set()

        for x, y, w, h in detections:
            bbox = (x, y, w, h)

            # --- cooldown: skip if same person still standing at entry ---
            if self.last_entry_bbox is not None:
                overlap = self._bbox_overlap(bbox, self.last_entry_bbox)
                elapsed = current_time - self.entry_cooldown.get("last_reg", 0)
                if (
                    overlap > self.entry_overlap_threshold
                    and elapsed < self.entry_cooldown_seconds
                ):
                    FrameAnnotator.draw_detection(
                        display, bbox, "REGISTERED ✓", (0, 200, 80)
                    )
                    active_keys.add(self._coarse_bbox_key(bbox, frame.shape))
                    continue

            # --- try to match against existing registered people ---
            pid, score = self.histogram_tracker.match(frame, bbox)

            if pid is not None:
                # Known person re-appearing at entry (e.g. re-entry after exit)
                if pid not in self.active_sessions:
                    self._ensure_active(pid, frame, bbox, "entry")
                label = f"{pid} ✓ ({score:.2f})"
                color = (0, 220, 80)
                active_keys.add(self._coarse_bbox_key(bbox, frame.shape))
            else:
                # Unknown detection — require N consecutive frames before
                # committing to a new registration (kills single-frame noise).
                key = self._coarse_bbox_key(bbox, frame.shape)
                active_keys.add(key)
                buf = self._entry_confirm_buffer.get(
                    key,
                    {
                        "count": 0,
                        "bbox": bbox,
                        "first_t": current_time,
                        "last_seen": current_time,
                    },
                )
                buf["count"] += 1
                buf["bbox"] = bbox  # keep the latest (most accurate) bbox
                buf["last_seen"] = current_time
                self._entry_confirm_buffer[key] = buf

                if buf["count"] < self._entry_confirm_min_frames:
                    # Not confirmed yet — show a neutral "detecting" indicator
                    FrameAnnotator.draw_detection(
                        display,
                        bbox,
                        f"DETECTING… ({buf['count']}/{self._entry_confirm_min_frames})",
                        (160, 160, 40),
                    )
                    continue  # do NOT register yet

                # ── Confirmed over N frames → register now ──
                pid = self.histogram_tracker.register(frame, bbox)
                del self._entry_confirm_buffer[key]  # clear buffer slot

                self.stats["registered"] += 1
                self.stats["inside"] += 1
                self.active_sessions[pid] = {
                    "entry_time": datetime.now(),
                    "source": "entry",
                }
                self.person_status[pid] = "active"
                self.entry_cooldown["last_reg"] = current_time
                self.last_entry_bbox = bbox
                if self.live_db:
                    self.live_db.record_entry(pid)
                label = f"NEW: {pid}"
                color = (0, 255, 180)

            FrameAnnotator.draw_detection(display, bbox, label, color)

        # Expire buffer entries whose grid cell had no detection this frame
        gone_keys = set(self._entry_confirm_buffer.keys()) - active_keys
        for k in gone_keys:
            del self._entry_confirm_buffer[k]

        FrameAnnotator.draw_overlay(
            display,
            "ENTRY GATE",
            {"Registered": self.stats["registered"], "Inside": self.stats["inside"]},
            (0, 255, 200),
        )
        return display

    def _process_room_lite(self, frame):
        """
        Room camera — track active people, record trajectories.

        Key fix: if a detection doesn't match an active session it is
        auto-registered (they entered when the entry cam was blocked) rather
        than being flagged UNAUTHORIZED.  LITE mode does not have the
        biometric capability to reliably determine authorization.
        """
        display = frame.copy()
        current_time = datetime.now()

        detections = self.haar_detector.detect_people(frame)
        self.stats["room_detections"] += len(detections)
        self.stats["total_detections"] += len(detections)

        for x, y, w, h in detections:
            bbox = (x, y, w, h)
            cx, cy = x + w // 2, y + h // 2

            # --- try to match ---
            pid, score = self.histogram_tracker.match(frame, bbox)

            if pid is None:
                # No histogram match — register as new person
                # (may have entered without being caught by entry cam)
                pid = self.histogram_tracker.register(frame, bbox)
                score = 1.0

            # Ensure they are in active_sessions (auto-register if needed)
            self._ensure_active(pid, frame, bbox, "room")

            # --- track trajectory & velocity ---
            self.trajectories[pid].append((cx, cy, current_time))
            if len(self.trajectories[pid]) > 60:
                self.trajectories[pid].pop(0)

            velocity = self._calculate_velocity(pid)
            self.velocity_data[pid].append(velocity)

            # Smooth velocity over the last 5 samples to suppress spikes from
            # a single bad tracking frame (e.g. ID swap, detection jump).
            recent_vels = self.velocity_data[pid][-5:]
            smoothed_vel = sum(recent_vels) / max(len(recent_vels), 1)

            # --- alert on sustained running (smoothed, with per-person cooldown) ---
            now_ts = time.time()
            last_alert = self.running_alert_cooldown.get(pid, 0)
            if (
                smoothed_vel > 3.5
                and self.live_db
                and (now_ts - last_alert) > self.running_alert_cooldown_secs
            ):
                self.live_db.create_alert(
                    alert_type="running",
                    alert_level="warning",
                    person_id=pid,
                    camera_source="room_camera",
                    message=f"{pid} moving fast ({smoothed_vel:.1f} m/s avg)",
                )
                self.running_alert_cooldown[pid] = now_ts

            # Draw annotations — show smoothed velocity on-screen
            label = f"{pid} ({score:.2f})"
            color = (0, 220, 80)
            FrameAnnotator.draw_detection(display, bbox, label, color)
            FrameAnnotator.draw_velocity(display, bbox, smoothed_vel)

            points = [(p[0], p[1]) for p in self.trajectories[pid]]
            FrameAnnotator.draw_trajectory(display, points)

            # Write trajectory IMMEDIATELY to SQLite
            if self.live_db:
                self.live_db.add_trajectory_point(
                    pid, cx, cy, "room_camera", velocity=velocity
                )

        FrameAnnotator.draw_overlay(
            display,
            "ROOM MONITORING",
            {"Tracking": len(detections), "Inside": self.stats["inside"]},
            (255, 220, 0),
        )
        return display

    def _process_exit_lite(self, frame):
        """
        Exit gate — detect departures and record exit events.

        Key improvements over original:
        - Exit deduplication: a person lingering at the exit gate (common!)
          would previously trigger a new exit event every single frame.
          We now suppress re-exits for `exit_redetect_secs` seconds.
        - After a confirmed exit the person is removed from the histogram
          tracker so their stale entry never causes a ghost match later.
        - Unknown detections at exit are auto-registered + immediately exited
          (they bypassed the entry cam) rather than showing a red box.
        """
        display = frame.copy()
        now_ts = time.time()  # float for cooldown arithmetic
        current_time = datetime.now()  # datetime for duration calculation

        # Prune stale recently-exited records to keep the dict small
        self.recently_exited = {
            p: t
            for p, t in self.recently_exited.items()
            if now_ts - t < self.exit_redetect_secs
        }

        detections = self.haar_detector.detect_people(frame)
        self.stats["exit_detections"] += len(detections)

        for x, y, w, h in detections:
            bbox = (x, y, w, h)

            # --- try to match against known people ---
            pid, score = self.histogram_tracker.match(frame, bbox)

            if pid is None:
                # No histogram match — register briefly so we can record exit
                pid = self.histogram_tracker.register(frame, bbox)
                score = 1.0

            # ── Deduplication: skip if this person exited very recently ──
            # (handles the "person standing in exit doorway" case)
            if pid in self.recently_exited:
                label = f"{pid} EXIT ✓"
                FrameAnnotator.draw_detection(display, bbox, label, (0, 160, 160))
                continue

            # Auto-register in active_sessions if they bypassed the entry cam
            self._ensure_active(pid, frame, bbox, "exit")

            session = self.active_sessions.get(pid)
            if session:
                entry_time = session["entry_time"]
                duration = (current_time - entry_time).total_seconds()

                vels = self.velocity_data.get(pid, [0.0])
                avg_vel = sum(vels) / max(len(vels), 1)
                max_vel = max(vels) if vels else 0.0

                if self.live_db:
                    self.live_db.update_person_velocity(pid, avg_vel, max_vel)
                    self.live_db.record_exit(pid)

                del self.active_sessions[pid]
                self.person_status[pid] = "exited"
                self.stats["inside"] = max(0, self.stats["inside"] - 1)
                self.stats["exited"] += 1

                # Mark as recently-exited to block duplicate events
                self.recently_exited[pid] = now_ts

                # Remove from histogram tracker — their appearance data is now
                # stale (different clothes angle, lighting at gate vs room).
                # Keeping them would cause ghost re-matches in future frames.
                self.histogram_tracker.remove(pid)

                label = f"{pid} EXIT  {duration:.0f}s"
                color = (0, 200, 255)
            else:
                label = f"{pid} ({score:.2f})"
                color = (0, 200, 100)

            FrameAnnotator.draw_detection(display, bbox, label, color)

        FrameAnnotator.draw_overlay(
            display,
            "EXIT GATE",
            {"Exited": self.stats["exited"], "Inside": self.stats["inside"]},
            (180, 0, 255),
        )
        return display

    # -----------------------------------------------------------------------
    # RAW MODE processing (just overlay text)
    # -----------------------------------------------------------------------
    def _process_raw(self, frame, camera_name):
        """Just add a minimal overlay to raw frames."""
        display = frame.copy()
        h, w = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w, 35), (0, 0, 0), -1)
        label_map = {
            "entry": ("ENTRY GATE [RAW]", (0, 255, 255)),
            "room": ("ROOM [RAW]", (255, 255, 0)),
            "exit": ("EXIT GATE [RAW]", (255, 0, 255)),
        }
        label, color = label_map.get(camera_name, ("CAMERA", (255, 255, 255)))
        cv2.putText(display, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        # Timestamp
        ts = datetime.now().strftime("%H:%M:%S")
        cv2.putText(
            display, ts, (w - 90, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1
        )
        return display

    # -----------------------------------------------------------------------
    # Utility methods
    # -----------------------------------------------------------------------
    def _coarse_bbox_key(self, bbox, frame_shape, grid: int = 8):
        """
        Map a bounding box centre to a coarse grid-cell key.

        Used by the entry confirmation buffer to decide whether two detections
        in consecutive frames are "the same person in roughly the same spot."

        Args:
            bbox:        (x, y, w, h)
            frame_shape: frame.shape  (h, w, [c])
            grid:        number of cells per axis (default 8 → 64 cells total)

        Returns:
            (grid_x, grid_y) integer tuple
        """
        x, y, w, h = bbox
        cx = x + w // 2
        cy = y + h // 2
        fh, fw = frame_shape[:2]
        gx = int(cx * grid / max(fw, 1))
        gy = int(cy * grid / max(fh, 1))
        return (gx, gy)

    def _bbox_overlap(self, bbox1, bbox2):
        """Calculate IoU overlap between two bboxes (x, y, w, h)."""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        xa = max(x1, x2)
        ya = max(y1, y2)
        xb = min(x1 + w1, x2 + w2)
        yb = min(y1 + h1, y2 + h2)

        inter = max(0, xb - xa) * max(0, yb - ya)
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - inter

        return inter / max(union, 1)

    def _calculate_velocity(self, person_id: str) -> float:
        """Calculate instantaneous velocity from trajectory."""
        traj = self.trajectories.get(person_id, [])
        if len(traj) < 2:
            return 0.0

        p1 = traj[-2]
        p2 = traj[-1]

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist_px = np.sqrt(dx * dx + dy * dy)
        dist_m = dist_px / self.pixels_per_meter

        # Time difference
        t1 = p1[2]
        t2 = p2[2]
        if isinstance(t1, datetime) and isinstance(t2, datetime):
            dt = (t2 - t1).total_seconds()
        else:
            dt = 1.0 / max(self.target_fps, 1)

        if dt <= 0:
            return 0.0

        return dist_m / dt

    # -----------------------------------------------------------------------
    # Camera processing thread
    # -----------------------------------------------------------------------
    def _camera_loop(self, camera_name: str):
        """Main loop for a single camera — runs in its own thread."""
        frame_interval = 1.0 / max(self.target_fps, 1)

        while self.running:
            loop_start = time.time()

            # Read frame
            frame = self._read_frame(camera_name)
            if frame is None:
                frame = self._generate_placeholder_frame(camera_name)
                annotated = frame
            else:
                # Process based on mode
                try:
                    if self.mode == "FULL":
                        if camera_name == "entry":
                            annotated = self._process_entry_full(frame)
                        elif camera_name == "room":
                            annotated = self._process_room_full(frame)
                        else:
                            annotated = self._process_exit_full(frame)
                    elif self.mode == "LITE":
                        if camera_name == "entry":
                            annotated = self._process_entry_lite(frame)
                        elif camera_name == "room":
                            annotated = self._process_room_lite(frame)
                        else:
                            annotated = self._process_exit_lite(frame)
                    else:
                        annotated = self._process_raw(frame, camera_name)
                except Exception as e:
                    # Don't crash on processing errors — show raw frame
                    annotated = frame.copy()
                    cv2.putText(
                        annotated,
                        f"ERROR: {str(e)[:50]}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        1,
                    )

            # Update shared frames (thread-safe)
            with self._lock:
                self._latest_frames[camera_name] = frame
                self._latest_annotated[camera_name] = annotated

            # FPS tracking
            elapsed = time.time() - loop_start
            self._frame_times[camera_name].append(elapsed)
            if len(self._frame_times[camera_name]) > 30:
                self._frame_times[camera_name].pop(0)

            avg_time = sum(self._frame_times[camera_name]) / len(
                self._frame_times[camera_name]
            )
            self.stats[f"fps_{camera_name}"] = round(1.0 / max(avg_time, 0.001), 1)

            # Throttle to target FPS
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # -----------------------------------------------------------------------
    # Public API — Frame generators for MJPEG streaming
    # -----------------------------------------------------------------------
    def generate_frames(
        self, camera_name: str, annotated: bool = True
    ) -> Generator[bytes, None, None]:
        """
        Generator that yields JPEG frames for MJPEG streaming.

        Usage in Flask:
            @app.route('/video/<camera>')
            def video(camera):
                return Response(
                    bridge.generate_frames(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame'
                )

        Args:
            camera_name: 'entry', 'room', or 'exit'
            annotated: If True, return annotated frames; else raw frames

        Yields:
            MJPEG frame bytes with boundary headers
        """
        while self.running:
            with self._lock:
                if annotated:
                    frame = self._latest_annotated.get(camera_name)
                else:
                    frame = self._latest_frames.get(camera_name)

            if frame is None:
                frame = self._generate_placeholder_frame(camera_name)

            jpeg = self._encode_jpeg(frame)
            if jpeg:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")

            # Control stream rate
            time.sleep(1.0 / max(self.target_fps, 1))

    def get_latest_frame(
        self, camera_name: str, annotated: bool = True
    ) -> Optional[np.ndarray]:
        """Get the latest frame for a camera (non-blocking)."""
        with self._lock:
            if annotated:
                return self._latest_annotated.get(camera_name)
            return self._latest_frames.get(camera_name)

    def get_latest_jpeg(
        self, camera_name: str, annotated: bool = True
    ) -> Optional[bytes]:
        """Get the latest frame as JPEG bytes."""
        frame = self.get_latest_frame(camera_name, annotated)
        if frame is None:
            return None
        return self._encode_jpeg(frame)

    def get_stats(self) -> Dict:
        """Get current system statistics."""
        uptime = 0
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()

        return {
            **self.stats,
            "uptime_seconds": round(uptime, 1),
            "active_sessions": len(self.active_sessions),
            "registered_count": len(self.registered_people),
            "active_people": list(self.active_sessions.keys()),
        }

    def get_active_people(self) -> List[Dict]:
        """Get list of currently active (inside) people."""
        result = []
        now = datetime.now()
        for pid, session in self.active_sessions.items():
            entry = session.get("entry_time", now)
            duration = (now - entry).total_seconds()
            vels = self.velocity_data.get(pid, [0.0])
            avg_vel = sum(vels) / max(len(vels), 1)
            result.append(
                {
                    "person_id": pid,
                    "entry_time": entry.isoformat(),
                    "duration_seconds": round(duration, 1),
                    "avg_velocity": round(avg_vel, 2),
                    "trajectory_points": len(self.trajectories.get(pid, [])),
                    "status": self.person_status.get(pid, "unknown"),
                }
            )
        return result

    # -----------------------------------------------------------------------
    # Start / Stop
    # -----------------------------------------------------------------------
    def start(self):
        """Start camera capture and processing threads."""
        if self.running:
            return

        print("\n🚀 Starting Camera Bridge...")
        self.running = True
        self.stats["start_time"] = datetime.now()

        # Initialize LiveDatabase — writes IMMEDIATELY to SQLite
        try:
            self.live_db = LiveDatabase(self.db_path)
            self._session_id = self.live_db.start_session(
                {"mode": self.mode, "fps": self.target_fps}
            )
            print(f"   ✅ LiveDatabase connected: {self.db_path}")
        except Exception as e:
            print(f"   ⚠️  LiveDatabase failed: {e}")
            self.live_db = None

        # Initialize detection/tracking components
        self._init_components()

        # Open cameras
        connected = self._open_cameras()
        if connected == 0:
            print("⚠️  No cameras connected — using placeholders")

        # Start processing threads
        for cam_name in ["entry", "room", "exit"]:
            t = threading.Thread(
                target=self._camera_loop,
                args=(cam_name,),
                daemon=True,
                name=f"cam-{cam_name}",
            )
            t.start()
            self._threads[cam_name] = t
            print(f"   ▶ Started {cam_name} camera thread")

        print(f"\n✅ Camera Bridge running ({self.mode} mode)")
        print(f"   {connected} camera(s) connected")
        print(f"   Database: {self.db_path}")
        print(f"   Streaming at {self.target_fps} FPS target\n")

    def stop(self):
        """Stop all threads and release resources."""
        if not self.running:
            return

        print("\n🛑 Stopping Camera Bridge...")
        self.running = False

        # Wait for threads to finish
        for name, t in self._threads.items():
            t.join(timeout=3.0)
            print(f"   ■ Stopped {name} camera thread")

        self._threads.clear()

        # Close cameras
        self._close_cameras()

        # End session and close LiveDatabase
        if self.live_db:
            try:
                if hasattr(self, "_session_id") and self._session_id:
                    self.live_db.end_session(self._session_id)
                self.live_db.close()
            except Exception:
                pass
            self.live_db = None

        print("✅ Camera Bridge stopped\n")

    def is_running(self) -> bool:
        return self.running


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\nCamera Bridge — Standalone Test\n")

    bridge = CameraBridge(auto_detect_cameras=True, target_fps=10)
    bridge.start()

    print("Press Ctrl+C to stop...\n")

    try:
        while True:
            stats = bridge.get_stats()
            fps_e = stats.get("fps_entry", 0)
            fps_r = stats.get("fps_room", 0)
            fps_x = stats.get("fps_exit", 0)
            mode = stats.get("mode", "?")
            inside = stats.get("inside", 0)
            reg = stats.get("registered", 0)
            print(
                f"\r  [{mode}] FPS: entry={fps_e:.0f} room={fps_r:.0f} exit={fps_x:.0f}"
                f" | Registered={reg} Inside={inside}    ",
                end="",
                flush=True,
            )
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
