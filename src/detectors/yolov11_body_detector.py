#!/usr/bin/env python3
"""
YOLO26 Body Detector Module
=============================
Previously: YOLOv11 Body Detector (yolo11n.pt)
Now:        YOLO26-pose Body Detector (yolo26n-pose.pt)

Migration notes:
  - The old YOLOv11BodyDetector loaded yolo11n.pt and returned plain person
    bounding boxes (x, y, w, h, confidence) with no keypoint information.
  - This module is now a thin shim over YOLO26BodyDetector, which uses the
    single unified yolo26n-pose.pt model for person detection + pose keypoints.
  - The public API (detect / extract_body_features / compare_features /
    visualize_detections / get_body_center / estimate_person_height) is kept
    100% backwards-compatible so every existing caller works without changes.
  - Legacy model-path arguments (e.g. "yolo11n.pt", "yolo11s.pt") are silently
    remapped to "yolo26n-pose.pt".

Extra capability vs. the old v11 detector:
  - detect() now also accepts an optional `return_full_dicts` keyword argument.
    When True, it returns the richer YOLO26BodyDetector dict format
    (body_bbox, face_bbox, keypoints, confidence, has_face) instead of the
    plain (x, y, w, h, confidence) tuples.  Default is False (legacy format).
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, cast

import cv2
import numpy as np


class YOLO26BodyDetectorShim:
    """
    YOLO26-pose based body detector.

    This class wraps YOLO26BodyDetector and exposes the same interface that
    the legacy YOLOv11BodyDetector had, so all call-sites are unaffected by
    the migration.

    Detection pipeline
    ------------------
    1. Run yolo26n-pose.pt inference on the frame.
    2. Return person bounding boxes + optional keypoints.

    The COCO-17 pose keypoints are available via ``return_full_dicts=True``
    or through the ``detect_full()`` convenience method.
    """

    def __init__(
        self,
        model_path: str = "yolo26n-pose.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ):
        """
        Initialize YOLO26 body detector.

        Args:
            model_path: Path to YOLO26-pose model weights.
                        Legacy YOLOv11 paths (yolo11*.pt) are automatically
                        remapped to 'yolo26n-pose.pt'.
            confidence_threshold: Minimum confidence for person detection.
            device: 'cpu', 'cuda', 'mps', or 'auto'.
        """
        self.confidence_threshold = confidence_threshold

        # ── Remap legacy YOLOv11 model paths ─────────────────────────────
        _legacy_v11_prefixes = ("yolo11", "yolov11")
        if any(
            Path(model_path).name.lower().startswith(p) for p in _legacy_v11_prefixes
        ):
            print(
                f"⚠️  Legacy YOLOv11 model path '{model_path}' detected — "
                f"remapping to 'yolo26n-pose.pt' (migration to YOLO26)."
            )
            model_path = "yolo26n-pose.pt"

        self.model_path = model_path

        # ── Delegate to YOLO26BodyDetector ────────────────────────────────
        # Import here so the module can be imported even if the project src/
        # path hasn't been added yet (callers typically do sys.path.insert
        # before importing this module).
        try:
            from detectors.yolo26_body_detector import YOLO26BodyDetector
        except ImportError:
            # Fallback: try relative import from the same package
            from .yolo26_body_detector import (
                YOLO26BodyDetector,  # type: ignore[no-redef]
            )

        self._detector = YOLO26BodyDetector(
            model_name=model_path,
            confidence_threshold=confidence_threshold,
            device=device,
        )

        # Expose device so callers that read .device continue to work
        self.device = self._detector.device

        # COCO person class ID (kept for API compatibility; YOLO26-pose
        # detects people exclusively so this is always 0)
        self.person_class_id = 0

        print("✅ YOLO26 body detector ready (shim over YOLO26BodyDetector)")

    # ─────────────────────────────────────────────────────────────────────────
    # Primary detection API (backwards-compatible with YOLOv11BodyDetector)
    # ─────────────────────────────────────────────────────────────────────────

    def detect(
        self,
        frame: np.ndarray,
        *,
        return_full_dicts: bool = False,
    ) -> Union[List[Tuple[int, int, int, int, float]], List[Dict]]:
        """
        Detect persons (bodies) in a frame.

        Args:
            frame: Input image (BGR format).
            return_full_dicts: When False (default) returns the legacy
                (x, y, w, h, confidence) tuple format identical to the old
                YOLOv11BodyDetector.  When True returns the richer YOLO26
                dict format (body_bbox, face_bbox, keypoints, confidence,
                has_face) — useful when callers want pose data.

        Returns:
            Legacy mode  → List of (x, y, w, h, confidence) tuples.
            Full-dict mode → List of YOLO26 detection dicts.
        """
        full_detections = self._detector.detect(frame)

        if return_full_dicts:
            return full_detections

        # Convert to legacy (x, y, w, h, confidence) tuples
        legacy: List[Tuple[int, int, int, int, float]] = []
        for det in full_detections:
            x, y, w, h = det["body_bbox"]
            conf = det["confidence"]
            legacy.append((x, y, w, h, float(conf)))

        return legacy

    def detect_full(self, frame: np.ndarray) -> List[Dict]:
        """
        Convenience wrapper — always returns the full YOLO26 detection dicts.

        Each dict contains:
            body_bbox  : (x, y, w, h)
            face_bbox  : (x, y, w, h) or None
            keypoints  : (17, 3) numpy array or None
            confidence : float
            has_face   : bool
        """
        return self._detector.detect(frame)

    # ─────────────────────────────────────────────────────────────────────────
    # Feature extraction (unchanged from YOLOv11BodyDetector)
    # ─────────────────────────────────────────────────────────────────────────

    def extract_body_features(
        self, frame: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> Dict[str, np.ndarray]:
        """
        Extract body appearance features from a detected person region.

        Returns the same feature dictionary as the legacy YOLOv11BodyDetector:
            upper_body_hist : (256,) float32 — upper clothing HSV histogram
            lower_body_hist : (256,) float32 — lower clothing HSV histogram
            full_body_hist  : (256,) float32 — full body HSV histogram
            shape_features  : (4,)   float32 — [aspect_ratio, rel_h, rel_w, area]

        Args:
            frame: Full BGR frame.
            bbox:  (x, y, w, h) person bounding box.
        """
        x, y, w, h = bbox

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(frame.shape[1], x + w)
        y2 = min(frame.shape[0], y + h)

        body_roi = frame[y1:y2, x1:x2]

        _zero_hist = np.zeros(256, dtype=np.float32)
        _zero_shape = np.zeros(4, dtype=np.float32)

        if body_roi.size == 0:
            return {
                "upper_body_hist": _zero_hist,
                "lower_body_hist": _zero_hist,
                "full_body_hist": _zero_hist,
                "shape_features": _zero_shape,
            }

        hsv_body = cv2.cvtColor(body_roi, cv2.COLOR_BGR2HSV)

        body_height = body_roi.shape[0]
        upper_split = int(body_height * 0.5)

        upper_body = hsv_body[:upper_split, :]
        lower_body = hsv_body[upper_split:, :]

        def _hsv_hist(region: np.ndarray) -> np.ndarray:
            if region.size == 0:
                return _zero_hist.copy()
            h_hist = cv2.calcHist([region], [0], None, [128], [0, 180])
            s_hist = cv2.calcHist([region], [1], None, [128], [0, 256])
            hist = np.concatenate([h_hist.flatten(), s_hist.flatten()])
            hist = cv2.normalize(hist, hist).flatten()
            return hist.astype(np.float32)

        upper_body_hist = _hsv_hist(upper_body)
        lower_body_hist = _hsv_hist(lower_body)
        full_body_hist = _hsv_hist(hsv_body)

        # Shape features
        fh, fw = frame.shape[:2]
        aspect_ratio = w / h if h > 0 else 0.0
        normalized_height = h / fh if fh > 0 else 0.0
        normalized_width = w / fw if fw > 0 else 0.0
        body_area = (w * h) / (fh * fw) if (fh * fw) > 0 else 0.0

        shape_features = np.array(
            [aspect_ratio, normalized_height, normalized_width, body_area],
            dtype=np.float32,
        )

        return {
            "upper_body_hist": upper_body_hist,
            "lower_body_hist": lower_body_hist,
            "full_body_hist": full_body_hist,
            "shape_features": shape_features,
        }

    def compare_features(
        self,
        feat1: Dict[str, np.ndarray],
        feat2: Dict[str, np.ndarray],
    ) -> float:
        """
        Compare two body feature dicts and return a similarity score.

        Uses the same weighted combination as the legacy YOLOv11BodyDetector:
            upper_body_hist : 35%
            lower_body_hist : 35%
            full_body_hist  : 20%
            shape_features  : 10%

        Returns:
            Similarity in [0, 1] (higher = more similar).
        """
        if feat1 is None or feat2 is None:
            return 0.0

        weights = {
            "upper_body_hist": 0.35,
            "lower_body_hist": 0.35,
            "full_body_hist": 0.20,
            "shape_features": 0.10,
        }

        total = 0.0

        for key in ("upper_body_hist", "lower_body_hist", "full_body_hist"):
            if key in feat1 and key in feat2:
                sim = cv2.compareHist(
                    feat1[key].astype(np.float32),
                    feat2[key].astype(np.float32),
                    cv2.HISTCMP_CORREL,
                )
                total += weights[key] * ((sim + 1.0) / 2.0)

        if "shape_features" in feat1 and "shape_features" in feat2:
            s1, s2 = feat1["shape_features"], feat2["shape_features"]
            n1, n2 = np.linalg.norm(s1), np.linalg.norm(s2)
            if n1 > 0 and n2 > 0:
                sim = np.dot(s1, s2) / (n1 * n2)
                total += weights["shape_features"] * ((sim + 1.0) / 2.0)

        return float(total)

    # ─────────────────────────────────────────────────────────────────────────
    # Visualisation helpers
    # ─────────────────────────────────────────────────────────────────────────

    def visualize_detections(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, int, int, int, float]],
        labels: Optional[List[str]] = None,
    ) -> np.ndarray:
        """
        Draw person bounding boxes on a copy of the frame.

        Args:
            frame:      BGR input image.
            detections: List of (x, y, w, h, confidence) tuples.
            labels:     Optional per-detection label strings.

        Returns:
            Annotated frame copy.
        """
        out = frame.copy()

        for i, (x, y, w, h, conf) in enumerate(detections):
            cv2.rectangle(out, (x, y), (x + w, y + h), (255, 0, 255), 2)

            label = labels[i] if labels and i < len(labels) else "Person"
            label_text = f"{label} (YOLO26): {conf:.2f}"

            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(out, (x, y - th - 10), (x + tw, y), (255, 0, 255), -1)
            cv2.putText(
                out,
                label_text,
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        return out

    # ─────────────────────────────────────────────────────────────────────────
    # Geometry helpers (unchanged from YOLOv11BodyDetector)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_body_center(bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """
        Return the centre point of a body bounding box.

        Args:
            bbox: (x, y, w, h)

        Returns:
            (center_x, center_y)
        """
        x, y, w, h = bbox
        return (x + w // 2, y + h // 2)

    @staticmethod
    def estimate_person_height(
        bbox: Tuple[int, int, int, int],
        camera_height_m: float = 2.5,
    ) -> float:
        """
        Rough estimate of a person's real-world height from their bbox.

        This is a simple heuristic (same as the legacy v11 implementation) —
        for accurate measurements use camera calibration.

        Args:
            bbox:            (x, y, w, h) bounding box.
            camera_height_m: Camera mounting height in metres.

        Returns:
            Estimated height in metres.
        """
        _x, _y, _w, h = bbox
        frame_height = 1080  # Assume standard HD resolution
        relative_height = h / frame_height
        # Person filling 50% of frame height ≈ 1.7 m tall
        return relative_height * 3.4


# ---------------------------------------------------------------------------
# Backwards-compatible alias — code that imported YOLOv11BodyDetector by name
# continues to work without any changes.
# ---------------------------------------------------------------------------
YOLOv11BodyDetector = YOLO26BodyDetectorShim


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing YOLO26 Body Detector (migrated from YOLOv11)...")
    print()

    try:
        detector = YOLO26BodyDetectorShim(model_path="yolo26n-pose.pt")
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

                detections = cast(
                    List[Tuple[int, int, int, int, float]],
                    detector.detect(frame),
                )
                vis = detector.visualize_detections(frame, detections)
                cv2.imshow("YOLO26 Body Detector", vis)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            cap.release()
            cv2.destroyAllWindows()

    except Exception as exc:
        print(f"❌ Error: {exc}")
