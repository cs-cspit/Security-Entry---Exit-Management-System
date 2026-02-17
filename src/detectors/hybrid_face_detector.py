"""
Hybrid Face Detector Module
Automatically uses YOLOv8-face if available, falls back to MediaPipe or Haar Cascade.
"""

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np


class HybridFaceDetector:
    """
    Hybrid face detector that tries multiple methods:
    1. YOLOv8-face (best accuracy, requires model file)
    2. MediaPipe Face Detection (good accuracy, no model file needed)
    3. Haar Cascade (basic, built into OpenCV)
    """

    def __init__(
        self,
        model_path: str = "yolov8n-face.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ):
        """
        Initialize hybrid face detector.

        Args:
            model_path: Path to YOLOv8-face model (if using YOLO)
            confidence_threshold: Minimum confidence for detection
            device: 'cpu', 'cuda', 'mps', or 'auto' for automatic selection
        """
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.method = None
        self.detector = None

        print("🔧 Initializing Hybrid Face Detector...")

        # Try YOLOv8-face first
        if self._try_yolov8(model_path):
            return

        # Try MediaPipe second
        if self._try_mediapipe():
            return

        # Fall back to Haar Cascade
        if self._try_haar():
            return

        # If nothing works
        raise RuntimeError(
            "Could not initialize any face detection method. "
            "Please install required dependencies or download models."
        )

    def _try_yolov8(self, model_path: str) -> bool:
        """Try to initialize YOLOv8-face detector."""
        try:
            # Check if model file exists
            if not os.path.exists(model_path):
                print(f"⚠️  YOLOv8-face model not found: {model_path}")
                return False

            import torch
            from ultralytics import YOLO

            # Auto-detect device
            if self.device == "auto":
                if torch.cuda.is_available():
                    self.device = "cuda"
                elif torch.backends.mps.is_available():
                    self.device = "mps"
                else:
                    self.device = "cpu"

            # Load model
            self.detector = YOLO(model_path)
            self.detector.to(self.device)
            self.method = "yolov8"

            print(f"✅ Using YOLOv8-face on {self.device}")
            return True

        except ImportError:
            print("⚠️  Ultralytics not installed (pip install ultralytics)")
            return False
        except Exception as e:
            print(f"⚠️  YOLOv8-face initialization failed: {e}")
            return False

    def _try_mediapipe(self) -> bool:
        """Try to initialize MediaPipe face detector."""
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
            print("⚠️  MediaPipe not installed (pip install mediapipe)")
            return False
        except Exception as e:
            print(f"⚠️  MediaPipe initialization failed: {e}")
            return False

    def _try_haar(self) -> bool:
        """Try to initialize Haar Cascade detector."""
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.detector = cv2.CascadeClassifier(cascade_path)

            if self.detector.empty():
                return False

            self.method = "haar"
            print("✅ Using Haar Cascade Face Detection (basic accuracy)")
            return True

        except Exception as e:
            print(f"⚠️  Haar Cascade initialization failed: {e}")
            return False

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces in frame.

        Args:
            frame: Input image (BGR format)

        Returns:
            List of (x, y, w, h, confidence) tuples for each detected face
        """
        if self.method == "yolov8":
            return self._detect_yolov8(frame)
        elif self.method == "mediapipe":
            return self._detect_mediapipe(frame)
        elif self.method == "haar":
            return self._detect_haar(frame)
        else:
            return []

    def _detect_yolov8(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using YOLOv8-face."""
        results = self.detector(frame, verbose=False, conf=self.confidence_threshold)

        detections = []

        if len(results) > 0:
            result = results[0]

            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                confidences = result.boxes.conf.cpu().numpy()

                for box, conf in zip(boxes, confidences):
                    x1, y1, x2, y2 = map(int, box)
                    w = x2 - x1
                    h = y2 - y1

                    if conf >= self.confidence_threshold:
                        detections.append((x1, y1, w, h, float(conf)))

        return detections

    def _detect_mediapipe(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using MediaPipe."""
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb_frame)

        detections = []

        if results.detections:
            h, w = frame.shape[:2]

            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box

                # Convert relative coordinates to absolute
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                width = int(bbox.width * w)
                height = int(bbox.height * h)

                # Get confidence score
                conf = detection.score[0] if detection.score else 0.8

                # Ensure coordinates are within frame bounds
                x = max(0, x)
                y = max(0, y)
                width = min(width, w - x)
                height = min(height, h - y)

                if conf >= self.confidence_threshold:
                    detections.append((x, y, width, height, float(conf)))

        return detections

    def _detect_haar(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using Haar Cascade."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        detections = []

        for x, y, w, h in faces:
            # Haar doesn't provide confidence, use fixed value
            detections.append((x, y, w, h, 0.8))

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

            # Draw confidence and method
            label = f"Face ({self.method}): {conf:.2f}"
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

    def get_method_info(self) -> dict:
        """
        Get information about the current detection method.

        Returns:
            Dictionary with method name and details
        """
        info = {
            "method": self.method,
            "confidence_threshold": self.confidence_threshold,
        }

        if self.method == "yolov8":
            info["device"] = self.device
            info["accuracy"] = "high"
        elif self.method == "mediapipe":
            info["accuracy"] = "good"
        elif self.method == "haar":
            info["accuracy"] = "basic"

        return info

    def __del__(self):
        """Cleanup resources."""
        if self.method == "mediapipe" and self.detector is not None:
            try:
                self.detector.close()
            except:
                pass


# Test function
if __name__ == "__main__":
    print("Testing Hybrid Face Detector...")
    print()

    try:
        detector = HybridFaceDetector()
        print()
        print(f"✅ Detector initialized successfully!")
        print(f"   Method: {detector.method}")
        print(f"   Info: {detector.get_method_info()}")
        print()

        # Test with webcam
        print("Opening webcam for testing...")
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Could not open webcam")
        else:
            print("✅ Webcam opened. Press 'q' to quit.")
            print()

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Detect faces
                detections = detector.detect(frame)

                # Visualize
                vis_frame = detector.visualize_detections(frame, detections)

                # Show
                cv2.imshow("Hybrid Face Detector Test", vis_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            cap.release()
            cv2.destroyAllWindows()

    except Exception as e:
        print(f"❌ Error: {e}")
