"""
YOLOv8-Face Detector Module
Detects faces using YOLOv8-face model for high accuracy face detection.
"""

import os
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch


class YOLOv8FaceDetector:
    """
    YOLOv8-face detector for accurate face detection.
    Uses pre-trained YOLOv8-face model from Ultralytics.
    """

    def __init__(
        self,
        model_path: str = "yolov8n-face.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ):
        """
        Initialize YOLOv8-face detector.

        Args:
            model_path: Path to YOLOv8-face model weights
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

        print(f"🔧 Initializing YOLOv8-face detector on {self.device}...")

        try:
            from ultralytics import YOLO

            # Check if model exists, if not try to download
            if not os.path.exists(model_path):
                print(f"⚠️  Model file not found: {model_path}")
                print(f"🔄 Attempting to download...")

                if not self._download_model(model_path):
                    raise FileNotFoundError(
                        f"Model file '{model_path}' not found and auto-download failed.\n"
                        f"Please run: python download_yolo_face.py"
                    )

            # Load YOLOv8-face model
            self.model = YOLO(model_path)
            self.model.to(self.device)
            print(f"✅ YOLOv8-face model loaded successfully")

        except ImportError:
            raise ImportError(
                "ultralytics package not found. Install with: pip install ultralytics"
            )
        except FileNotFoundError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLOv8-face model: {e}")

    def _download_model(self, model_path: str) -> bool:
        """
        Attempt to download the YOLOv8-face model.

        Args:
            model_path: Path where model should be saved

        Returns:
            True if download successful, False otherwise
        """
        urls = [
            "https://github.com/derronqi/yolov8-face/releases/download/v1.0/yolov8n-face.pt",
            "https://huggingface.co/Bingsu/yolov8n-face/resolve/main/yolov8n-face.pt",
        ]

        for url in urls:
            try:
                print(f"   Trying: {url}")

                def progress_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        downloaded = block_num * block_size
                        percent = min(100, downloaded * 100 / total_size)
                        mb_downloaded = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        sys.stdout.write(
                            f"\r   Progress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)"
                        )
                        sys.stdout.flush()

                urllib.request.urlretrieve(url, model_path, progress_hook)
                print(f"\n✅ Model downloaded successfully!")
                return True

            except Exception as e:
                print(f"\n   Failed: {e}")
                continue

        print(f"\n❌ Could not download model from any source")
        print(f"\nPlease download manually:")
        print(f"1. Run: python download_yolo_face.py")
        print(f"2. Or visit: https://github.com/derronqi/yolov8-face")
        print(f"3. Download 'yolov8n-face.pt' and place it in the project root")

        return False

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces in frame.

        Args:
            frame: Input image (BGR format)

        Returns:
            List of (x, y, w, h, confidence) tuples for each detected face
        """
        # Run inference
        results = self.model(frame, verbose=False, conf=self.confidence_threshold)

        detections = []

        if len(results) > 0:
            result = results[0]

            # Extract bounding boxes
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                confidences = result.boxes.conf.cpu().numpy()

                for box, conf in zip(boxes, confidences):
                    x1, y1, x2, y2 = map(int, box)
                    w = x2 - x1
                    h = y2 - y1

                    # Filter by confidence
                    if conf >= self.confidence_threshold:
                        detections.append((x1, y1, w, h, float(conf)))

        return detections

    def extract_face_features(
        self, frame: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """
        Extract face features from detected face region.
        Uses HSV color histogram as feature descriptor.

        Args:
            frame: Input image
            bbox: Bounding box (x, y, w, h)

        Returns:
            Feature vector (normalized histogram)
        """
        x, y, w, h = bbox

        # Add padding
        padding = 10
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + w + padding)
        y2 = min(frame.shape[0], y + h + padding)

        face_roi = frame[y1:y2, x1:x2]

        if face_roi.size == 0:
            # Return zero vector if ROI is empty
            return np.zeros(256, dtype=np.float32)

        # Convert to HSV
        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)

        # Calculate histogram for Hue and Saturation channels
        hist_h = cv2.calcHist([hsv], [0], None, [128], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [128], [0, 256])

        # Concatenate and normalize
        hist = np.concatenate([hist_h.flatten(), hist_s.flatten()])
        hist = cv2.normalize(hist, hist).flatten()

        return hist

    def compare_features(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """
        Compare two feature vectors and return similarity score.

        Args:
            feat1: First feature vector
            feat2: Second feature vector

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        if feat1 is None or feat2 is None:
            return 0.0

        if len(feat1) == 0 or len(feat2) == 0:
            return 0.0

        # Use correlation method (returns value between -1 and 1)
        similarity = cv2.compareHist(
            feat1.astype(np.float32), feat2.astype(np.float32), cv2.HISTCMP_CORREL
        )

        # Normalize to 0-1 range
        similarity = (similarity + 1) / 2.0

        return float(similarity)

    def visualize_detections(
        self, frame: np.ndarray, detections: List[Tuple[int, int, int, int, float]]
    ) -> np.ndarray:
        """
        Draw bounding boxes on frame.

        Args:
            frame: Input image
            detections: List of (x, y, w, h, confidence) tuples

        Returns:
            Frame with visualizations
        """
        frame_copy = frame.copy()

        for x, y, w, h, conf in detections:
            # Draw bounding box
            cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Draw confidence
            label = f"Face: {conf:.2f}"
            cv2.putText(
                frame_copy,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        return frame_copy
