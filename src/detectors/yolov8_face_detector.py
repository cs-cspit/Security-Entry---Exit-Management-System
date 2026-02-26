#!/usr/bin/env python3
"""
YOLO26 Face Detector Module
============================
Detects faces using YOLO26-pose model.

Previously used YOLOv8-face (yolov8n-face.pt) — now migrated to YOLO26.

Strategy:
  - Run YOLO26-pose inference on the frame (same model used for body detection)
  - Extract face bounding boxes from pose keypoints (nose, eyes, ears)
  - This gives a single unified model for both face AND body detection
  - No separate face model file required

Drop-in replacement: the public API (detect / extract_face_features /
compare_features / visualize_detections) is identical to the old
YOLOv8FaceDetector so every existing caller works without changes.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class YOLO26FaceDetector:
    """
    YOLO26-pose based face detector.

    Uses YOLO26-pose (yolo26n-pose.pt) to detect people, then derives face
    bounding boxes from the 5 facial keypoints (nose, left/right eye,
    left/right ear).  This replaces the old YOLOv8-face pipeline with a
    single unified model that also provides body and pose information.

    Public API is identical to the legacy YOLOv8FaceDetector so all existing
    callers continue to work without modification.
    """

    def __init__(
        self,
        model_path: str = "yolo26n-pose.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ):
        """
        Initialize YOLO26 face detector.

        Args:
            model_path: Path to YOLO26-pose model weights.
                        Accepts any yolo26*-pose.pt variant.
                        Legacy 'yolov8n-face.pt' / 'yolov8s-face.pt' paths
                        are silently remapped to 'yolo26n-pose.pt'.
            confidence_threshold: Minimum confidence for person detection.
            device: 'cpu', 'cuda', 'mps', or 'auto'.
        """
        self.confidence_threshold = confidence_threshold

        # ── Remap legacy model paths ──────────────────────────────────────
        _legacy_face_models = {
            "yolov8n-face.pt",
            "yolov8s-face.pt",
            "yolov8m-face.pt",
            "yolov8l-face.pt",
            "yolov8x-face.pt",
        }
        if Path(model_path).name in _legacy_face_models:
            print(
                f"⚠️  Legacy YOLOv8-face model path '{model_path}' detected — "
                f"remapping to 'yolo26n-pose.pt' (migration to YOLO26)."
            )
            model_path = "yolo26n-pose.pt"

        self.model_path = model_path

        # ── Device selection ──────────────────────────────────────────────
        if device == "auto":
            import torch

            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

        print(f"🔧 Initializing YOLO26 face detector on {self.device}...")

        try:
            from ultralytics import YOLO

            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"YOLO26 model not found: '{model_path}'. "
                    f"Place yolo26n-pose.pt in the project root or provide "
                    f"the correct path."
                )

            self.model = YOLO(model_path)
            self.model.to(self.device)
            print(f"✅ YOLO26 face detector loaded — model: {model_path}")

        except ImportError:
            raise ImportError(
                "ultralytics package not found. Install with: pip install ultralytics"
            )
        except FileNotFoundError as exc:
            raise RuntimeError(str(exc))
        except Exception as exc:
            raise RuntimeError(f"Failed to load YOLO26 model: {exc}")

        # ── Keypoint indices (COCO 17-point schema) ───────────────────────
        # 0=nose  1=left_eye  2=right_eye  3=left_ear  4=right_ear
        self._FACE_KPT_INDICES = [0, 1, 2, 3, 4]
        # Minimum keypoint confidence to include a point in the face bbox
        self._KPT_CONF_THRESHOLD = 0.3
        # Padding multiplier applied to the raw keypoint bbox
        self._BBOX_EXPANSION = 0.35

    # ─────────────────────────────────────────────────────────────────────────
    # Public API (drop-in compatible with legacy YOLOv8FaceDetector)
    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces in frame.

        Args:
            frame: Input image (BGR format).

        Returns:
            List of (x, y, w, h, confidence) tuples, one per detected face.
            Confidence is the YOLO26 person-detection confidence for that
            individual (same meaning as the old YOLOv8-face confidence).
        """
        try:
            results = self.model(
                frame,
                verbose=False,
                conf=self.confidence_threshold,
            )
        except Exception as exc:
            print(f"⚠️  YOLO26 face detection failed: {exc}")
            return []

        if not results or results[0].boxes is None:
            return []

        result = results[0]
        boxes = result.boxes.xyxy.cpu().numpy()  # (N, 4) [x1 y1 x2 y2]
        confidences = result.boxes.conf.cpu().numpy()  # (N,)

        # Get pose keypoints when available
        keypoints_data: Optional[np.ndarray] = None
        if hasattr(result, "keypoints") and result.keypoints is not None:
            keypoints_data = result.keypoints.data.cpu().numpy()  # (N, 17, 3)

        detections: List[Tuple[int, int, int, int, float]] = []

        for i, (box, conf) in enumerate(zip(boxes, confidences)):
            if conf < self.confidence_threshold:
                continue

            # Derive face bbox from keypoints when available
            face_bbox: Optional[Tuple[int, int, int, int]] = None

            if keypoints_data is not None and i < len(keypoints_data):
                face_bbox = self._face_bbox_from_keypoints(keypoints_data[i])

            # Fall back: top 20% of person bbox is the head region
            if face_bbox is None:
                face_bbox = self._face_bbox_from_body_box(box, frame.shape)

            if face_bbox is not None:
                detections.append((*face_bbox, float(conf)))

        return detections

    def detect_with_body(self, frame: np.ndarray) -> List[Dict]:
        """
        Extended detection that returns both face AND body information.

        This is a YOLO26-specific bonus — callers that want the full detection
        dict (body_bbox, face_bbox, keypoints, confidence) can use this method.

        Returns:
            List of dicts compatible with YOLO26BodyDetector.detect() output:
              - body_bbox: (x, y, w, h)
              - face_bbox: (x, y, w, h) or None
              - keypoints: (17, 3) numpy array or None
              - confidence: float
              - has_face: bool
        """
        try:
            results = self.model(
                frame,
                verbose=False,
                conf=self.confidence_threshold,
            )
        except Exception as exc:
            print(f"⚠️  YOLO26 detection failed: {exc}")
            return []

        if not results or results[0].boxes is None:
            return []

        result = results[0]
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()

        keypoints_data: Optional[np.ndarray] = None
        if hasattr(result, "keypoints") and result.keypoints is not None:
            keypoints_data = result.keypoints.data.cpu().numpy()

        detections: List[Dict] = []

        for i, (box, conf) in enumerate(zip(boxes, confidences)):
            if conf < self.confidence_threshold:
                continue

            x1, y1, x2, y2 = map(int, box)
            body_bbox = (x1, y1, x2 - x1, y2 - y1)

            kpts = (
                keypoints_data[i]
                if (keypoints_data is not None and i < len(keypoints_data))
                else None
            )
            face_bbox = (
                self._face_bbox_from_keypoints(kpts) if kpts is not None else None
            )
            if face_bbox is None:
                face_bbox = self._face_bbox_from_body_box(box, frame.shape)

            detections.append(
                {
                    "body_bbox": body_bbox,
                    "face_bbox": face_bbox,
                    "keypoints": kpts,
                    "confidence": float(conf),
                    "has_face": face_bbox is not None,
                }
            )

        return detections

    def extract_face_features(
        self, frame: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """
        Extract face appearance features from a face bounding box.

        Uses HSV histogram (Hue + Saturation) — same descriptor as the
        legacy YOLOv8FaceDetector so existing matching logic is unaffected.

        Args:
            frame: Full BGR frame.
            bbox:  (x, y, w, h) face bounding box.

        Returns:
            256-dimensional normalised float32 feature vector.
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
        Compare two face feature vectors.

        Args:
            feat1: Feature vector from extract_face_features().
            feat2: Feature vector from extract_face_features().

        Returns:
            Similarity score in [0, 1] (higher = more similar).
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
        # Normalise [-1, 1] → [0, 1]
        return float((similarity + 1.0) / 2.0)

    def visualize_detections(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, int, int, int, float]],
    ) -> np.ndarray:
        """
        Draw face bounding boxes on a copy of the frame.

        Args:
            frame:      BGR input image.
            detections: List of (x, y, w, h, confidence) from detect().

        Returns:
            Annotated frame copy.
        """
        out = frame.copy()

        for x, y, w, h, conf in detections:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)

            label = f"Face (YOLO26): {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(out, (x, y - th - 6), (x + tw, y), (0, 255, 0), -1)
            cv2.putText(
                out,
                label,
                (x, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
            )

        return out

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _face_bbox_from_keypoints(
        self, keypoints: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Derive a face bounding box from COCO pose keypoints.

        Uses the 5 facial landmarks (nose, eyes, ears).  Returns None when
        fewer than 2 landmarks are visible at the required confidence.

        Args:
            keypoints: (17, 3) array of [x, y, confidence].

        Returns:
            (x, y, w, h) integer bbox, or None.
        """
        if keypoints is None or keypoints.shape[0] < 5:
            return None

        face_points: List[List[float]] = []
        for idx in self._FACE_KPT_INDICES:
            x, y, conf = keypoints[idx]
            if conf > self._KPT_CONF_THRESHOLD:
                face_points.append([float(x), float(y)])

        if len(face_points) < 2:
            return None

        pts = np.array(face_points)
        x_min, y_min = pts.min(axis=0)
        x_max, y_max = pts.max(axis=0)

        kw = max(1.0, x_max - x_min)
        kh = max(1.0, y_max - y_min)
        exp = self._BBOX_EXPANSION

        x1 = int(x_min - kw * exp)
        y1 = int(y_min - kh * exp)
        x2 = int(x_max + kw * exp)
        y2 = int(y_max + kh * exp * 1.5)  # extra room below for chin

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        return (x1, y1, w, h)

    def _face_bbox_from_body_box(
        self,
        box: np.ndarray,
        frame_shape: Tuple[int, ...],
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Fallback: estimate face bbox as top 20% of the person bounding box.

        Used when keypoints are unavailable or all facial keypoints have low
        confidence (e.g., person facing away).

        Args:
            box:         [x1, y1, x2, y2] float array.
            frame_shape: (H, W, C) tuple for clamping.

        Returns:
            (x, y, w, h) integer bbox, or None if box is degenerate.
        """
        x1, y1, x2, y2 = map(float, box)
        bw = x2 - x1
        bh = y2 - y1

        if bw <= 0 or bh <= 0:
            return None

        # Top 20% of body bbox is the head/face region
        face_h = bh * 0.20
        exp = self._BBOX_EXPANSION

        fx1 = int(x1 + bw * 0.15)  # narrow horizontally (not full shoulder width)
        fy1 = int(y1 - face_h * exp)  # small upward padding
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


# ---------------------------------------------------------------------------
# Backwards-compatible alias — existing code that imports YOLOv8FaceDetector
# by name continues to work without any changes.
# ---------------------------------------------------------------------------
YOLOv8FaceDetector = YOLO26FaceDetector


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing YOLO26 Face Detector (migrated from YOLOv8-face)...")
    print()

    try:
        detector = YOLO26FaceDetector(model_path="yolo26n-pose.pt")
        print()
        print("✅ Detector initialized.")
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
                cv2.imshow("YOLO26 Face Detector", vis)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            cap.release()
            cv2.destroyAllWindows()

    except Exception as exc:
        print(f"❌ Error: {exc}")
