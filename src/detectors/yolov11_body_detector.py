"""
YOLOv11 Body Detector Module
Detects human bodies using YOLOv11 model for person tracking in large spaces.
"""

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch


class YOLOv11BodyDetector:
    """
    YOLOv11 body detector for accurate person detection and tracking.
    Uses pre-trained YOLOv11 model from Ultralytics for person class detection.
    """

    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ):
        """
        Initialize YOLOv11 body detector.

        Args:
            model_path: Path to YOLOv11 model weights
            confidence_threshold: Minimum confidence for detection
            device: 'cpu', 'cuda', 'mps', or 'auto' for automatic selection
        """
        self.confidence_threshold = confidence_threshold

        # Auto-detect device
        if device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

        print(f"🔧 Initializing YOLOv11 body detector on {self.device}...")

        try:
            from ultralytics import YOLO

            # Load YOLOv11 model
            self.model = YOLO(model_path)
            self.model.to(self.device)
            print(f"✅ YOLOv11 model loaded successfully")

        except ImportError:
            raise ImportError(
                "ultralytics package not found. Install with: pip install ultralytics"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLOv11 model: {e}")

        # COCO person class ID is 0
        self.person_class_id = 0

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect persons (bodies) in frame.

        Args:
            frame: Input image (BGR format)

        Returns:
            List of (x, y, w, h, confidence) tuples for each detected person
        """
        # Run inference
        results = self.model(frame, verbose=False, conf=self.confidence_threshold)

        detections = []

        if len(results) > 0:
            result = results[0]

            # Extract bounding boxes for person class only
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                confidences = result.boxes.conf.cpu().numpy()
                classes = result.boxes.cls.cpu().numpy()

                for box, conf, cls in zip(boxes, confidences, classes):
                    # Filter for person class only
                    if (
                        int(cls) == self.person_class_id
                        and conf >= self.confidence_threshold
                    ):
                        x1, y1, x2, y2 = map(int, box)
                        w = x2 - x1
                        h = y2 - y1

                        detections.append((x1, y1, w, h, float(conf)))

        return detections

    def extract_body_features(
        self, frame: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> Dict[str, np.ndarray]:
        """
        Extract body appearance features from detected person region.
        Uses multiple feature descriptors for robust re-identification:
        - Upper body color histogram (torso/shirt)
        - Lower body color histogram (pants/legs)
        - Full body color histogram
        - Body shape features (aspect ratio, height)

        Args:
            frame: Input image
            bbox: Bounding box (x, y, w, h)

        Returns:
            Dictionary of feature vectors
        """
        x, y, w, h = bbox

        # Ensure bbox is within frame bounds
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(frame.shape[1], x + w)
        y2 = min(frame.shape[0], y + h)

        body_roi = frame[y1:y2, x1:x2]

        if body_roi.size == 0:
            # Return zero vectors if ROI is empty
            return {
                "upper_body_hist": np.zeros(256, dtype=np.float32),
                "lower_body_hist": np.zeros(256, dtype=np.float32),
                "full_body_hist": np.zeros(256, dtype=np.float32),
                "shape_features": np.zeros(4, dtype=np.float32),
            }

        # Convert to HSV for better color representation
        hsv_body = cv2.cvtColor(body_roi, cv2.COLOR_BGR2HSV)

        # Split body into upper and lower regions
        body_height = body_roi.shape[0]
        upper_split = int(body_height * 0.5)  # Top 50% is upper body

        upper_body = hsv_body[:upper_split, :]
        lower_body = hsv_body[upper_split:, :]

        # Extract color histograms for each region
        # Upper body histogram (clothing color - shirt/jacket)
        hist_upper_h = cv2.calcHist([upper_body], [0], None, [128], [0, 180])
        hist_upper_s = cv2.calcHist([upper_body], [1], None, [128], [0, 256])
        upper_body_hist = np.concatenate(
            [hist_upper_h.flatten(), hist_upper_s.flatten()]
        )
        upper_body_hist = cv2.normalize(upper_body_hist, upper_body_hist).flatten()

        # Lower body histogram (clothing color - pants/legs)
        hist_lower_h = cv2.calcHist([lower_body], [0], None, [128], [0, 180])
        hist_lower_s = cv2.calcHist([lower_body], [1], None, [128], [0, 256])
        lower_body_hist = np.concatenate(
            [hist_lower_h.flatten(), hist_lower_s.flatten()]
        )
        lower_body_hist = cv2.normalize(lower_body_hist, lower_body_hist).flatten()

        # Full body histogram (overall appearance)
        hist_full_h = cv2.calcHist([hsv_body], [0], None, [128], [0, 180])
        hist_full_s = cv2.calcHist([hsv_body], [1], None, [128], [0, 256])
        full_body_hist = np.concatenate([hist_full_h.flatten(), hist_full_s.flatten()])
        full_body_hist = cv2.normalize(full_body_hist, full_body_hist).flatten()

        # Shape features (aspect ratio, relative height, width)
        aspect_ratio = w / h if h > 0 else 0
        normalized_height = h / frame.shape[0] if frame.shape[0] > 0 else 0
        normalized_width = w / frame.shape[1] if frame.shape[1] > 0 else 0
        body_area = (
            (w * h) / (frame.shape[0] * frame.shape[1])
            if (frame.shape[0] * frame.shape[1]) > 0
            else 0
        )

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
        self, feat1: Dict[str, np.ndarray], feat2: Dict[str, np.ndarray]
    ) -> float:
        """
        Compare two body feature dictionaries and return similarity score.
        Uses weighted combination of multiple features for robust matching.

        Args:
            feat1: First feature dictionary
            feat2: Second feature dictionary

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        if feat1 is None or feat2 is None:
            return 0.0

        # Weights for different features
        weights = {
            "upper_body_hist": 0.35,  # Upper body clothing is most distinctive
            "lower_body_hist": 0.35,  # Lower body clothing is also important
            "full_body_hist": 0.20,  # Overall appearance
            "shape_features": 0.10,  # Body shape (less reliable due to pose changes)
        }

        total_similarity = 0.0

        # Compare upper body histogram
        if "upper_body_hist" in feat1 and "upper_body_hist" in feat2:
            sim = cv2.compareHist(
                feat1["upper_body_hist"].astype(np.float32),
                feat2["upper_body_hist"].astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            sim = (sim + 1) / 2.0  # Normalize to 0-1
            total_similarity += weights["upper_body_hist"] * sim

        # Compare lower body histogram
        if "lower_body_hist" in feat1 and "lower_body_hist" in feat2:
            sim = cv2.compareHist(
                feat1["lower_body_hist"].astype(np.float32),
                feat2["lower_body_hist"].astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            sim = (sim + 1) / 2.0  # Normalize to 0-1
            total_similarity += weights["lower_body_hist"] * sim

        # Compare full body histogram
        if "full_body_hist" in feat1 and "full_body_hist" in feat2:
            sim = cv2.compareHist(
                feat1["full_body_hist"].astype(np.float32),
                feat2["full_body_hist"].astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            sim = (sim + 1) / 2.0  # Normalize to 0-1
            total_similarity += weights["full_body_hist"] * sim

        # Compare shape features (using cosine similarity)
        if "shape_features" in feat1 and "shape_features" in feat2:
            shape1 = feat1["shape_features"]
            shape2 = feat2["shape_features"]

            # Cosine similarity
            dot_product = np.dot(shape1, shape2)
            norm1 = np.linalg.norm(shape1)
            norm2 = np.linalg.norm(shape2)

            if norm1 > 0 and norm2 > 0:
                sim = dot_product / (norm1 * norm2)
                sim = (sim + 1) / 2.0  # Normalize to 0-1
                total_similarity += weights["shape_features"] * sim

        return float(total_similarity)

    def visualize_detections(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, int, int, int, float]],
        labels: Optional[List[str]] = None,
    ) -> np.ndarray:
        """
        Draw bounding boxes on frame with labels.

        Args:
            frame: Input image
            detections: List of (x, y, w, h, confidence) tuples
            labels: Optional list of labels for each detection

        Returns:
            Frame with visualizations
        """
        frame_copy = frame.copy()

        for i, (x, y, w, h, conf) in enumerate(detections):
            # Draw bounding box
            cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (255, 0, 255), 2)

            # Draw label
            if labels and i < len(labels):
                label_text = f"{labels[i]}: {conf:.2f}"
            else:
                label_text = f"Person: {conf:.2f}"

            # Background for text
            (text_w, text_h), _ = cv2.getTextSize(
                label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            cv2.rectangle(
                frame_copy,
                (x, y - text_h - 10),
                (x + text_w, y),
                (255, 0, 255),
                -1,
            )

            # Text
            cv2.putText(
                frame_copy,
                label_text,
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        return frame_copy

    def get_body_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """
        Get center point of body bounding box.

        Args:
            bbox: Bounding box (x, y, w, h)

        Returns:
            (center_x, center_y)
        """
        x, y, w, h = bbox
        center_x = x + w // 2
        center_y = y + h // 2
        return (center_x, center_y)

    def estimate_person_height(
        self, bbox: Tuple[int, int, int, int], camera_height_m: float = 2.5
    ) -> float:
        """
        Estimate person's real-world height based on bounding box.
        This is a rough estimation assuming camera is at fixed height.

        Args:
            bbox: Bounding box (x, y, w, h)
            camera_height_m: Camera mounting height in meters

        Returns:
            Estimated height in meters
        """
        x, y, w, h = bbox

        # Simple perspective estimation
        # Assumes person at bottom of frame is closer
        # This is a rough heuristic - for accurate results, camera calibration needed
        frame_height = 1080  # Assume standard HD resolution
        relative_height = h / frame_height

        # Rough estimation: person filling 50% of frame height ~ 1.7m tall
        estimated_height = relative_height * 3.4  # 3.4 = 1.7 * 2

        return estimated_height
