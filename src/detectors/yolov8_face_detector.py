#!/usr/bin/env python3
"""
YOLO26 Face Detector Module
============================
Detects faces using a two-stage pipeline:

  1. YOLO26-pose (yolo26n-pose.pt) — person detection + 17 COCO keypoints
  2. YOLO26-face (yolo26n-face.pt) — **custom-trained** dedicated face
     detector that runs on tight head-region crops derived from stage 1.
     Outputs class 0 = "face".  Dramatically reduces false positives
     compared to the old generic COCO detector (yolo26n.pt) which could
     only detect "person" class and wasn't designed for face localisation.

When the custom face model is not available, falls back to deriving face
bounding boxes from pose keypoints (nose, eyes, ears) — the original
single-model strategy.

Previously used YOLOv8-face (yolov8n-face.pt) — fully migrated to YOLO26.

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
    YOLO26-based face detector with custom-trained face model support.

    Two-stage pipeline (when custom face model is available):
      1. YOLO26-pose (yolo26n-pose.pt) → person bboxes + 17 COCO keypoints
      2. YOLO26-face (yolo26n-face.pt, custom-trained) → precise face bbox
         from tight head-region crop derived from keypoints in stage 1.
         The custom model outputs class 0 = "face" and is far more accurate
         for face localisation than the generic COCO detector.

    Single-stage fallback (when custom face model is absent):
      - Derives face bounding boxes from the 5 facial keypoints
        (nose, left/right eye, left/right ear) of the pose model.

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
            print(f"✅ YOLO26 pose model loaded — model: {model_path}")

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

        # ── Custom YOLO26-face model (dedicated face detector) ────────────
        # Load the custom-trained face model for precise face localisation.
        # This model outputs class 0 = "face" and dramatically reduces
        # false positives compared to keypoint-only face derivation.
        self._face_model = None
        self._face_model_is_custom = False
        self._load_custom_face_model()

    def _load_custom_face_model(self) -> None:
        """
        Attempt to load the custom-trained YOLO26-face model.

        Fallback chain:
          1. yolo26n-face.pt (project root — preferred)
          2. custom_models/yolo26_face_results/weights/best.pt (source weights)
        """
        _candidates = [
            "yolo26n-face.pt",
            os.path.join("custom_models", "yolo26_face_results", "weights", "best.pt"),
        ]
        for _path in _candidates:
            if not os.path.exists(_path):
                continue
            try:
                from ultralytics import YOLO

                self._face_model = YOLO(_path)
                self._face_model.to(self.device)
                self._face_model_is_custom = True
                print(f"✅ Custom YOLO26-face model loaded: {_path}")
                print(f"   Outputs class 0 = 'face' for precise face localisation")
                return
            except Exception as exc:
                print(f"⚠️  Failed to load custom face model {_path}: {exc}")
                continue

        print(
            "ℹ️  Custom YOLO26-face model not found — using keypoint-derived face boxes"
        )

    def _run_face_model_on_head_crop(
        self,
        frame: np.ndarray,
        head_crop: np.ndarray,
        crop_origin: Tuple[int, int],
    ) -> Optional[Tuple[int, int, int, int, float]]:
        """
        Run the custom YOLO26-face model on a head-region crop and return
        the best face bbox in full-frame coordinates.

        Args:
            frame: Original full frame (for bounds checking).
            head_crop: Cropped head region (BGR).
            crop_origin: (x_offset, y_offset) of the crop within frame.

        Returns:
            (x, y, w, h, confidence) in full-frame coords, or None.
        """
        if self._face_model is None or head_crop.size == 0:
            return None

        hch, hcw = head_crop.shape[:2]

        # Upscale tiny crops — the face model was trained at 640px
        _min_dim = 80
        if hch < _min_dim or hcw < _min_dim:
            _scale = max(_min_dim / hch, _min_dim / hcw)
            head_crop_scaled = cv2.resize(
                head_crop,
                (int(hcw * _scale), int(hch * _scale)),
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            head_crop_scaled = head_crop

        try:
            results = self._face_model(head_crop_scaled, verbose=False, conf=0.30)
            if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                return None

            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy().astype(int)

            # Class 0 = "face" in the custom model
            valid_mask = classes == 0
            if not valid_mask.any():
                return None

            valid_boxes = boxes[valid_mask]
            valid_confs = confs[valid_mask]
            best_idx = int(valid_confs.argmax())
            best_conf = float(valid_confs[best_idx])
            fx1, fy1, fx2, fy2 = valid_boxes[best_idx]

            # Map back to original crop coordinates if we scaled
            if head_crop_scaled is not head_crop:
                _inv_scale = hcw / head_crop_scaled.shape[1]
                fx1 *= _inv_scale
                fy1 *= _inv_scale
                fx2 *= _inv_scale
                fy2 *= _inv_scale

            # Expand by 12% for chin/forehead
            fw, fh = fx2 - fx1, fy2 - fy1
            _expand = 0.12
            fx1 = fx1 - fw * _expand
            fy1 = fy1 - fh * _expand
            fx2 = fx2 + fw * _expand
            fy2 = fy2 + fh * _expand * 1.3

            # Map to full-frame coordinates
            ox, oy = crop_origin
            abs_x1 = max(0, int(fx1 + ox))
            abs_y1 = max(0, int(fy1 + oy))
            abs_x2 = min(frame.shape[1], int(fx2 + ox))
            abs_y2 = min(frame.shape[0], int(fy2 + oy))

            w = abs_x2 - abs_x1
            h = abs_y2 - abs_y1
            if w > 5 and h > 5:
                return (abs_x1, abs_y1, w, h, best_conf)

        except Exception:
            pass

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Public API (drop-in compatible with legacy YOLOv8FaceDetector)
    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces in frame.

        When the custom YOLO26-face model is available, uses a two-stage
        pipeline for dramatically better face localisation:
          1. YOLO26-pose → person bboxes + 17 COCO keypoints
          2. For each person, crop head region from keypoints
          3. Run YOLO26-face (custom, class 0 = "face") on the head crop
        Falls back to keypoint-derived face boxes when the custom model
        is absent or fails to detect a face in the crop.

        Args:
            frame: Input image (BGR format).

        Returns:
            List of (x, y, w, h, confidence) tuples, one per detected face.
            Confidence is the face-model confidence when the custom model
            fires, otherwise the YOLO26 person-detection confidence.
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

            # ── Stage 1 (custom face model): keypoints → head crop → YOLO26-face ──
            if (
                self._face_model_is_custom
                and keypoints_data is not None
                and i < len(keypoints_data)
            ):
                kpts = keypoints_data[i]
                # Extract head crop from facial keypoints
                face_pts = []
                for idx in self._FACE_KPT_INDICES:
                    kx, ky, kconf = kpts[idx]
                    if kconf > self._KPT_CONF_THRESHOLD:
                        face_pts.append((float(kx), float(ky)))

                head_crop = None
                crop_origin = (0, 0)
                if len(face_pts) >= 2:
                    xs = [p[0] for p in face_pts]
                    ys = [p[1] for p in face_pts]
                    pad_x = max(30, (max(xs) - min(xs)) * 0.8)
                    pad_y = max(30, (max(ys) - min(ys)) * 1.0)
                    hx1 = max(0, int(min(xs) - pad_x))
                    hy1 = max(0, int(min(ys) - pad_y))
                    hx2 = min(frame.shape[1], int(max(xs) + pad_x))
                    hy2 = min(frame.shape[0], int(max(ys) + pad_y * 1.5))
                    if hx2 > hx1 + 20 and hy2 > hy1 + 20:
                        head_crop = frame[hy1:hy2, hx1:hx2]
                        crop_origin = (hx1, hy1)

                # Fallback head crop: top 25% of body bbox
                if head_crop is None or head_crop.size == 0:
                    bx1, by1, bx2, by2 = map(int, box)
                    bw, bh = bx2 - bx1, by2 - by1
                    head_h = int(bh * 0.25)
                    hy1 = max(0, by1)
                    hy2 = min(frame.shape[0], by1 + head_h)
                    hx1 = max(0, int(bx1 + bw * 0.05))
                    hx2 = min(frame.shape[1], int(bx1 + bw * 0.95))
                    if hx2 > hx1 + 10 and hy2 > hy1 + 10:
                        head_crop = frame[hy1:hy2, hx1:hx2]
                        crop_origin = (hx1, hy1)

                if head_crop is not None and head_crop.size > 0:
                    result_face = self._run_face_model_on_head_crop(
                        frame, head_crop, crop_origin
                    )
                    if result_face is not None:
                        detections.append(result_face)
                        continue  # Got a precise face — skip keypoint fallback

            # ── Stage 2 (fallback): derive face bbox from keypoints ──
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
