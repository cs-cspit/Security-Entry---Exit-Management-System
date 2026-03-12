#!/usr/bin/env python3
"""
Hybrid Face Detector Module
=============================
Automatically uses the best available face detection backend:

1. **YOLO26-face (custom-trained)** — highest accuracy for face localisation.
   Uses your custom-trained ``yolo26n-face.pt`` (class 0 = "face").
   This model was trained specifically on face data and dramatically
   reduces false positives compared to the generic COCO detector.

2. **YOLO26-pose** — fallback when the custom face model is absent.
   Derives face bounding boxes from COCO facial keypoints
   (nose, left/right eye, left/right ear).

3. **MediaPipe** — CPU-friendly fallback (no model file required).

4. **Haar Cascade** — basic accuracy, built into OpenCV.

Migration note
--------------
Previously this module loaded YOLOv8-face (yolov8n-face.pt) as its primary
detector.  It was first migrated to YOLO26-pose (yolo26n-pose.pt), and is
now further upgraded to prefer the custom-trained yolo26n-face.pt model
when available.

Detection priority
------------------
  1. YOLO26-face  (custom trained — best for face detection)
  2. YOLO26-pose  (keypoint-derived face boxes — good fallback)
  3. MediaPipe    (good accuracy, no model file)
  4. Haar Cascade (basic, built into OpenCV)

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

        # ── Custom face model (separate from pose model) ─────────────────
        # The custom yolo26n-face.pt is a dedicated face detector trained
        # on face data (class 0 = "face").  When available it is used as
        # the PRIMARY face detector and the pose model is only used for
        # body bbox + keypoints (not for face localisation).
        self._face_model = None
        self._face_model_is_custom = False

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

        # Try custom YOLO26-face model first (dedicated face detector)
        self._try_custom_face_model()

        # Try backends in priority order for body/pose detection
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

    def _try_custom_face_model(self) -> bool:
        """
        Try to load the custom-trained YOLO26-face model for dedicated
        face detection.  This model outputs class 0 = "face" and is
        far more accurate for face localisation than the generic COCO model.

        Fallback chain:
          1. yolo26n-face.pt (project root)
          2. custom_models/yolo26_face_results/weights/best.pt
        """
        _candidates = [
            "yolo26n-face.pt",
            os.path.join("custom_models", "yolo26_face_results", "weights", "best.pt"),
        ]
        for _path in _candidates:
            if not os.path.exists(_path):
                continue
            try:
                import torch
                from ultralytics import YOLO

                _dev = self.device
                if _dev == "auto":
                    if torch.cuda.is_available():
                        _dev = "cuda"
                    elif torch.backends.mps.is_available():
                        _dev = "mps"
                    else:
                        _dev = "cpu"

                self._face_model = YOLO(_path)
                self._face_model.to(_dev)
                self._face_model_is_custom = True
                print(f"✅ Custom YOLO26-face model loaded: {_path} (on {_dev})")
                print(
                    f"   This model outputs class 0 = 'face' for precise face localisation"
                )
                return True
            except ImportError:
                break
            except Exception as exc:
                print(f"⚠️  Failed to load custom face model {_path}: {exc}")
                continue

        print(
            "ℹ️  Custom YOLO26-face model not found — will derive faces from pose keypoints"
        )
        return False

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

            if self._face_model_is_custom:
                print(
                    f"✅ Using YOLO26-pose (body/keypoints) + YOLO26-face (custom) on {self.device}"
                )
            else:
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

        When the custom YOLO26-face model is available AND the primary backend
        is YOLO26-pose, a two-stage pipeline runs:
          1. YOLO26-pose → person bboxes + keypoints
          2. For each person, crop head region from keypoints
          3. Run YOLO26-face on the head crop → precise face bbox
        This gives dramatically better face localisation than keypoint-only
        derivation, which was the primary source of false positives.

        Falls back to single-stage detection when custom model is absent.

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

    def _run_custom_face_on_crop(
        self,
        frame: np.ndarray,
        head_crop: np.ndarray,
        crop_origin: Tuple[int, int],
    ) -> Optional[Tuple[int, int, int, int, float]]:
        """
        Run the custom YOLO26-face model on a head-region crop and return
        the best face bbox in *full-frame* coordinates.

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
            # Custom face model — lower confidence is fine (trained for faces)
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
                fx1, fy1, fx2, fy2 = (
                    fx1 * _inv_scale,
                    fy1 * _inv_scale,
                    fx2 * _inv_scale,
                    fy2 * _inv_scale,
                )

            # Expand by 12% for chin/forehead (custom model gives tight boxes)
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

        except Exception as exc:
            # Silently fall back — don't break the pipeline
            pass

        return None

    def _detect_yolo26(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces using the YOLO26-pose backend.

        When the custom YOLO26-face model is available, uses a two-stage
        pipeline: pose → head crop → custom face detector.  This gives
        dramatically more precise face bounding boxes than keypoint-only
        derivation.
        """
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

            face_bbox: Optional[Tuple[int, int, int, int]] = None

            # ── Stage 1 (custom face model available): keypoints → head crop → YOLO26-face ──
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
                    result_face = self._run_custom_face_on_crop(
                        frame, head_crop, crop_origin
                    )
                    if result_face is not None:
                        detections.append(result_face)
                        continue  # Got a precise face — skip keypoint fallback

            # ── Stage 2 (fallback): derive face bbox from COCO facial keypoints ──
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
