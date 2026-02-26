#!/usr/bin/env python3
"""
Hybrid Face Detector Module
=============================
Automatically uses YOLO26-pose if available, falls back to MediaPipe or
Haar Cascade.

Migration note
--------------
Previously this module loaded YOLOv8-face (yolov8n-face.pt) as its primary
detector.  It has been migrated to YOLO26-pose (yolo26n-pose.pt), which is
the single unified model used throughout the entire security system.

YOLO26 strategy
---------------
  1. Run YOLO26-pose inference → person bounding boxes + 17 COCO keypoints.
  2. Extract face bounding boxes from the 5 facial keypoints
     (nose, left/right eye, left/right ear).
  3. Fall back to top-20% of person bbox when keypoints are low-confidence.

Detection priority
------------------
  1. YOLO26-pose  (best accuracy, unified model — no extra .pt file needed)
  2. MediaPipe    (good accuracy, no model file)
  3. Haar Cascade (basic, built into OpenCV)

Public API is identical to the original HybridFaceDetector so every
existing caller works without modification.
"""

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np


class HybridFaceDetector:
    """
    Hybrid face detector that tries multiple detection backends in order:

    1. YOLO26-pose  — high accuracy, pose keypoints, single unified model
    2. MediaPipe    — good accuracy, CPU-friendly, no model file required
    3. Haar Cascade — basic accuracy, built into OpenCV
    """

    def __init__(
        self,
        model_path: str = "yolo26n-pose.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ):
        """
        Initialize hybrid face detector.

        Args:
            model_path: Path to the YOLO26-pose model file.
                        Legacy 'yolov8n-face.pt' / 'yolov8s-face.pt' / etc.
                        paths are silently remapped to 'yolo26n-pose.pt'.
            confidence_threshold: Minimum detection confidence (0.0–1.0).
            device: 'cpu', 'cuda', 'mps', or 'auto'.
        """
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.method: Optional[str] = None
        self.detector = None

        # ── Remap legacy YOLOv8-face model paths ─────────────────────────
        _legacy_face_models = {
            "yolov8n-face.pt",
            "yolov8s-face.pt",
            "yolov8m-face.pt",
            "yolov8l-face.pt",
            "yolov8x-face.pt",
        }
        if os.path.basename(model_path) in _legacy_face_models:
            print(
                f"⚠️  Legacy YOLOv8-face model path '{model_path}' detected — "
                f"remapping to 'yolo26n-pose.pt' (migration to YOLO26)."
            )
            model_path = "yolo26n-pose.pt"

        self._model_path = model_path

        # COCO facial keypoint indices (nose, L/R eye, L/R ear)
        self._FACE_KPT_INDICES = [0, 1, 2, 3, 4]
        # Minimum per-keypoint confidence to count towards the face bbox
        self._KPT_CONF_THRESHOLD = 0.3
        # Fractional expansion applied to the keypoint bbox
        self._BBOX_EXPANSION = 0.35

        print("🔧 Initializing Hybrid Face Detector...")

        # Try backends in priority order
        if self._try_yolo26(model_path):
            return
        if self._try_mediapipe():
            return
        if self._try_haar():
            return

        raise RuntimeError(
            "Could not initialize any face detection backend.\n"
            "Install at least one of:\n"
            "  pip install ultralytics   (YOLO26 — recommended)\n"
            "  pip install mediapipe     (MediaPipe fallback)\n"
            "OpenCV Haar Cascade is bundled with opencv-python."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Backend initialisation
    # ─────────────────────────────────────────────────────────────────────────

    def _try_yolo26(self, model_path: str) -> bool:
        """Try to initialise the YOLO26-pose backend."""
        try:
            if not os.path.exists(model_path):
                print(f"⚠️  YOLO26 model not found: {model_path}")
                return False

            import torch
            from ultralytics import YOLO

            # Resolve device
            if self.device == "auto":
                if torch.cuda.is_available():
                    self.device = "cuda"
                elif torch.backends.mps.is_available():
                    self.device = "mps"
                else:
                    self.device = "cpu"

            self.detector = YOLO(model_path)
            self.detector.to(self.device)
            self.method = "yolo26"

            print(f"✅ Using YOLO26-pose face detection on {self.device}")
            return True

        except ImportError:
            print("⚠️  ultralytics not installed (pip install ultralytics)")
            return False
        except Exception as exc:
            print(f"⚠️  YOLO26 initialisation failed: {exc}")
            return False

    def _try_mediapipe(self) -> bool:
        """Try to initialise the MediaPipe face detection backend."""
        try:
            import mediapipe as mp

            self.mp_face_detection = mp.solutions.face_detection
            self.detector = self.mp_face_detection.FaceDetection(
                min_detection_confidence=self.confidence_threshold
            )
            self.method = "mediapipe"

            print("✅ Using MediaPipe Face Detection")
            return True

        except ImportError:
            print("⚠️  mediapipe not installed (pip install mediapipe)")
            return False
        except Exception as exc:
            print(f"⚠️  MediaPipe initialisation failed: {exc}")
            return False

    def _try_haar(self) -> bool:
        """Try to initialise the Haar Cascade face detection backend."""
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.detector = cv2.CascadeClassifier(cascade_path)

            if self.detector.empty():
                print("⚠️  Haar Cascade classifier is empty")
                return False

            self.method = "haar"
            print("✅ Using Haar Cascade Face Detection (basic accuracy)")
            return True

        except Exception as exc:
            print(f"⚠️  Haar Cascade initialisation failed: {exc}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Public detection API
    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces in a frame.

        Args:
            frame: Input image (BGR format).

        Returns:
            List of (x, y, w, h, confidence) tuples, one per detected face.
        """
        if self.method == "yolo26":
            return self._detect_yolo26(frame)
        elif self.method == "mediapipe":
            return self._detect_mediapipe(frame)
        elif self.method == "haar":
            return self._detect_haar(frame)
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # Per-backend detection implementations
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_yolo26(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using the YOLO26-pose backend."""
        try:
            results = self.detector(
                frame,
                verbose=False,
                conf=self.confidence_threshold,
            )
        except Exception as exc:
            print(f"⚠️  YOLO26 inference error: {exc}")
            return []

        if not results or results[0].boxes is None:
            return []

        result = results[0]
        boxes = result.boxes.xyxy.cpu().numpy()  # (N, 4) [x1 y1 x2 y2]
        confidences = result.boxes.conf.cpu().numpy()  # (N,)

        # Pose keypoints — shape (N, 17, 3) when available
        keypoints_data: Optional[np.ndarray] = None
        if hasattr(result, "keypoints") and result.keypoints is not None:
            keypoints_data = result.keypoints.data.cpu().numpy()

        detections: List[Tuple[int, int, int, int, float]] = []

        for i, (box, conf) in enumerate(zip(boxes, confidences)):
            if conf < self.confidence_threshold:
                continue

            # Primary: derive face bbox from COCO facial keypoints
            face_bbox: Optional[Tuple[int, int, int, int]] = None
            if keypoints_data is not None and i < len(keypoints_data):
                face_bbox = self._face_bbox_from_keypoints(
                    keypoints_data[i], frame.shape
                )

            # Fallback: top 20% of person bounding box
            if face_bbox is None:
                face_bbox = self._face_bbox_from_body_box(box, frame.shape)

            if face_bbox is not None:
                detections.append((*face_bbox, float(conf)))

        return detections

    def _detect_mediapipe(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using the MediaPipe backend."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb_frame)

        if not results.detections:
            return []

        h, w = frame.shape[:2]
        detections: List[Tuple[int, int, int, int, float]] = []

        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)

            conf = float(detection.score[0]) if detection.score else 0.8

            x = max(0, x)
            y = max(0, y)
            width = min(width, w - x)
            height = min(height, h - y)

            if conf >= self.confidence_threshold:
                detections.append((x, y, width, height, conf))

        return detections

    def _detect_haar(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using the Haar Cascade backend."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        # detectMultiScale returns an empty tuple when nothing is found
        if not isinstance(faces, np.ndarray) or len(faces) == 0:
            return []

        return [(x, y, w, h, 0.8) for x, y, w, h in faces]

    # ─────────────────────────────────────────────────────────────────────────
    # Feature extraction & comparison (unchanged from original)
    # ─────────────────────────────────────────────────────────────────────────

    def extract_face_features(
        self, frame: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """
        Extract face appearance features (HSV histogram) from a face bbox.

        Returns a 256-dimensional float32 vector (same descriptor as before).
        """
        x, y, w, h = bbox
        padding = 10

        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + w + padding)
        y2 = min(frame.shape[0], y + h + padding)

        face_roi = frame[y1:y2, x1:x2]

        if face_roi.size == 0:
            return np.zeros(256, dtype=np.float32)

        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        hist_h = cv2.calcHist([hsv], [0], None, [128], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [128], [0, 256])

        hist = np.concatenate([hist_h.flatten(), hist_s.flatten()])
        hist = cv2.normalize(hist, hist).flatten()
        return hist.astype(np.float32)

    def compare_features(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """
        Compare two feature vectors and return a similarity score in [0, 1].
        """
        if feat1 is None or feat2 is None:
            return 0.0
        if len(feat1) == 0 or len(feat2) == 0:
            return 0.0

        similarity = cv2.compareHist(
            feat1.astype(np.float32),
            feat2.astype(np.float32),
            cv2.HISTCMP_CORREL,
        )
        return float((similarity + 1.0) / 2.0)

    # ─────────────────────────────────────────────────────────────────────────
    # Visualisation
    # ─────────────────────────────────────────────────────────────────────────

    def visualize_detections(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, int, int, int, float]],
    ) -> np.ndarray:
        """Draw face bounding boxes on a copy of the frame."""
        out = frame.copy()

        for x, y, w, h, conf in detections:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)

            label = f"Face ({self.method}): {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(out, (x, y - th - 6), (x + tw, y), (0, 200, 0), -1)
            cv2.putText(
                out,
                label,
                (x, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        return out

    # ─────────────────────────────────────────────────────────────────────────
    # Introspection helpers
    # ─────────────────────────────────────────────────────────────────────────

    def get_method_info(self) -> dict:
        """Return metadata about the active detection backend."""
        info: dict = {
            "method": self.method,
            "confidence_threshold": self.confidence_threshold,
        }
        if self.method == "yolo26":
            info["device"] = self.device
            info["model"] = self._model_path
            info["accuracy"] = "high"
        elif self.method == "mediapipe":
            info["accuracy"] = "good"
        elif self.method == "haar":
            info["accuracy"] = "basic"
        return info

    # ─────────────────────────────────────────────────────────────────────────
    # YOLO26 internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _face_bbox_from_keypoints(
        self,
        keypoints: np.ndarray,
        frame_shape: Tuple[int, ...],
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Derive a face bounding box from COCO pose keypoints.

        Uses the 5 facial landmarks: nose (0), left_eye (1), right_eye (2),
        left_ear (3), right_ear (4).  Returns None when fewer than 2 landmarks
        are visible at the required confidence.

        Args:
            keypoints:   (17, 3) array [x, y, confidence] per keypoint.
            frame_shape: (H, W, C) — used for clamping.

        Returns:
            (x, y, w, h) integer bbox, or None.
        """
        if keypoints is None or keypoints.shape[0] < 5:
            return None

        face_pts: List[List[float]] = []
        for idx in self._FACE_KPT_INDICES:
            kx, ky, kconf = keypoints[idx]
            if kconf > self._KPT_CONF_THRESHOLD:
                face_pts.append([float(kx), float(ky)])

        if len(face_pts) < 2:
            return None

        pts = np.array(face_pts)
        x_min, y_min = pts.min(axis=0)
        x_max, y_max = pts.max(axis=0)

        kw = max(1.0, x_max - x_min)
        kh = max(1.0, y_max - y_min)
        exp = self._BBOX_EXPANSION

        x1 = int(x_min - kw * exp)
        y1 = int(y_min - kh * exp)
        x2 = int(x_max + kw * exp)
        y2 = int(y_max + kh * exp * 1.5)  # extra room below for chin

        H, W = frame_shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(W, x2)
        y2 = min(H, y2)

        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0:
            return None

        return (x1, y1, w, h)

    def _face_bbox_from_body_box(
        self,
        box: np.ndarray,
        frame_shape: Tuple[int, ...],
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Fallback: estimate the face region as the top 20% of the person bbox.

        Used when keypoints are absent or all facial keypoints have low
        confidence (e.g. person facing away from camera).

        Args:
            box:         [x1, y1, x2, y2] float array.
            frame_shape: (H, W, C) for clamping.

        Returns:
            (x, y, w, h) integer bbox, or None.
        """
        x1, y1, x2, y2 = map(float, box)
        bw = x2 - x1
        bh = y2 - y1

        if bw <= 0 or bh <= 0:
            return None

        face_h = bh * 0.20
        exp = self._BBOX_EXPANSION

        # Narrow horizontally — face is not as wide as the full shoulder span
        fx1 = int(x1 + bw * 0.15)
        fy1 = int(y1 - face_h * exp)
        fx2 = int(x2 - bw * 0.15)
        fy2 = int(y1 + face_h * (1.0 + exp))

        H, W = frame_shape[:2]
        fx1 = max(0, fx1)
        fy1 = max(0, fy1)
        fx2 = min(W, fx2)
        fy2 = min(H, fy2)

        w = fx2 - fx1
        h = fy2 - fy1

        if w <= 0 or h <= 0:
            return None

        return (fx1, fy1, w, h)

    # ─────────────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────────────

    def __del__(self):
        """Release MediaPipe resources if active."""
        if self.method == "mediapipe" and self.detector is not None:
            try:
                self.detector.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing Hybrid Face Detector (YOLO26 primary)...")
    print()

    try:
        detector = HybridFaceDetector()
        print()
        print(f"✅ Detector ready — method: {detector.method}")
        print(f"   Info: {detector.get_method_info()}")
        print()

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Could not open webcam.")
        else:
            print("Webcam opened — press 'q' to quit.")
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                faces = detector.detect(frame)
                vis = detector.visualize_detections(frame, faces)
                cv2.imshow("Hybrid Face Detector", vis)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            cap.release()
            cv2.destroyAllWindows()

    except Exception as exc:
        print(f"❌ Error: {exc}")
