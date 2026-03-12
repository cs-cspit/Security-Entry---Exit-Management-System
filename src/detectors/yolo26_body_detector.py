"""
YOLO26-pose Body Detector
==========================
Handles person detection, body bounding boxes, and 17-point COCO pose
keypoints using the YOLO26-pose variant (yolo26n-pose.pt).

Role within the four-model YOLO26 architecture
-----------------------------------------------
  yolo26n-pose.pt  ← THIS FILE
      Person detection (body bbox) + 17 COCO keypoints.
      Drives ByteTrack multi-person tracking in the room camera.
      Provides head-region keypoints (nose/eyes/ears) used to crop
      tight face regions before passing to the dedicated face detector.

  yolo26n-face.pt  (custom-trained, loaded in YOLO26CompleteSystem)
      **Custom-trained** dedicated face detector.  Outputs class 0 = "face".
      Runs on the tight head-region crop extracted from pose keypoints
      above.  Gives precise face bounding boxes that InsightFace ArcFace
      then embeds into 512-D vectors.
      This replaces the previous generic yolo26n.pt (COCO person class)
      which was a major source of false positives because it wasn't
      trained for face localisation.
      Critical for CISF/uniform scenarios where clothing appearance
      is identical across individuals.

  yolo26n.pt  (loaded directly in YOLO26CompleteSystem)
      Generic COCO detector used for body-level re-ID features (OSNet).
      No longer used for face detection (replaced by yolo26n-face.pt).

  yolo26n-seg.pt  (loaded directly in YOLO26CompleteSystem)
      Instance segmentation masks.  Used to isolate exact clothing
      pixels before colour-histogram extraction, eliminating background
      bleed that would corrupt appearance-based re-ID.

This module only concerns itself with the pose model.  The face, detection,
and segmentation models are managed by YOLO26CompleteSystem directly.
"""

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO


class YOLO26BodyDetector:
    """
    Person detector and pose estimator using YOLO26-pose.

    Responsibilities (within the four-model pipeline):
    - Detect all people in a frame (body bounding boxes)
    - Estimate 17 COCO pose keypoints per person
    - Derive a rough face-region bbox from facial keypoints
      (nose=0, left_eye=1, right_eye=2, left_ear=3, right_ear=4)
      — this crop is then refined by the custom-trained YOLO26-face model
        (yolo26n-face.pt, class 0 = "face") for precise face localisation
    - Provide body-region crops for OSNet and body-analyser features
    - Back the ByteTrack multi-person tracker (room camera)

    NOT responsible for:
    - Face detection (→ YOLO26-face custom model)
    - Face embedding extraction (→ YOLO26-face + InsightFace)
    - Clothing mask generation (→ YOLO26-seg)

    End-to-end NMS-free inference (YOLO26 native).
    """

    def __init__(
        self,
        model_name: str = "yolo26n-pose.pt",
        confidence_threshold: float = 0.4,
        device: str = "auto",
    ):
        """
        Initialize YOLO26 body detector.

        Args:
            model_name: YOLO26 model variant (yolo26n-pose.pt for speed)
            confidence_threshold: Minimum confidence for detection
            device: 'cpu', 'mps', 'cuda', or 'auto'
        """
        self.confidence_threshold = confidence_threshold

        # Auto-detect device
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

        print(f"🔧 Initializing YOLO26 body detector on {self.device}...")

        try:
            # Load YOLO26 pose model
            self.model = YOLO(model_name)
            self.model.to(self.device)
            print(f"✅ YOLO26 {model_name} loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load YOLO26: {e}")
            raise

        # COCO pose keypoint indices
        self.KEYPOINT_NAMES = [
            "nose",  # 0
            "left_eye",  # 1
            "right_eye",  # 2
            "left_ear",  # 3
            "right_ear",  # 4
            "left_shoulder",  # 5
            "right_shoulder",  # 6
            "left_elbow",  # 7
            "right_elbow",  # 8
            "left_wrist",  # 9
            "right_wrist",  # 10
            "left_hip",  # 11
            "right_hip",  # 12
            "left_knee",  # 13
            "right_knee",  # 14
            "left_ankle",  # 15
            "right_ankle",  # 16
        ]

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect all people in frame with pose keypoints.

        Args:
            frame: Input image (BGR format)

        Returns:
            List of dicts with:
            - body_bbox: (x, y, w, h) full body bounding box
            - face_bbox: (x, y, w, h) face region (from keypoints)
            - keypoints: (17, 3) array of [x, y, confidence]
            - confidence: detection confidence
            - has_face: whether face region was extracted
        """
        detections = []

        try:
            # Run YOLO26 inference (end-to-end, no NMS needed)
            results = self.model(frame, verbose=False, conf=self.confidence_threshold)

            if len(results) == 0:
                return detections

            result = results[0]

            # Check if we have detections
            if result.boxes is None or len(result.boxes) == 0:
                return detections

            # Extract boxes and keypoints
            boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
            confidences = result.boxes.conf.cpu().numpy()

            # Get keypoints if available
            keypoints = None
            if hasattr(result, "keypoints") and result.keypoints is not None:
                keypoints = result.keypoints.data.cpu().numpy()  # (N, 17, 3)

            for i, (box, conf) in enumerate(zip(boxes, confidences)):
                if conf < self.confidence_threshold:
                    continue

                # Body bbox
                x1, y1, x2, y2 = map(int, box)
                body_bbox = (x1, y1, x2 - x1, y2 - y1)

                # Extract face region from keypoints
                face_bbox = None
                has_face = False
                person_keypoints = None

                if keypoints is not None and i < len(keypoints):
                    person_keypoints = keypoints[i]  # (17, 3)
                    face_bbox = self._extract_face_from_keypoints(person_keypoints)
                    has_face = face_bbox is not None

                detections.append(
                    {
                        "body_bbox": body_bbox,
                        "face_bbox": face_bbox,
                        "keypoints": person_keypoints,
                        "confidence": float(conf),
                        "has_face": has_face,
                    }
                )

        except Exception as e:
            print(f"⚠️ Detection failed: {e}")
            return []

        return detections

    def _extract_face_from_keypoints(
        self, keypoints: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Extract face bounding box from pose keypoints.
        Uses nose, eyes, and ears to estimate face region.

        Args:
            keypoints: (17, 3) array of [x, y, confidence]

        Returns:
            (x, y, w, h) face bbox or None if not enough keypoints
        """
        # Face keypoints: nose, eyes, ears
        face_keypoint_indices = [
            0,
            1,
            2,
            3,
            4,
        ]  # nose, left_eye, right_eye, left_ear, right_ear

        # Extract face keypoints with sufficient confidence
        face_points = []
        for idx in face_keypoint_indices:
            x, y, conf = keypoints[idx]
            if conf > 0.3:  # Confidence threshold for keypoint
                face_points.append([x, y])

        if len(face_points) < 2:
            return None

        face_points = np.array(face_points)

        # Get bounding box of face keypoints
        x_min = np.min(face_points[:, 0])
        y_min = np.min(face_points[:, 1])
        x_max = np.max(face_points[:, 0])
        y_max = np.max(face_points[:, 1])

        # Expand bbox by 30% to include full face
        w = x_max - x_min
        h = y_max - y_min

        expansion = 0.3
        x_min = int(x_min - w * expansion)
        y_min = int(y_min - h * expansion)
        x_max = int(x_max + w * expansion)
        y_max = int(y_max + h * expansion * 1.5)  # More expansion below for chin

        # Ensure positive dimensions
        w = max(1, x_max - x_min)
        h = max(1, y_max - y_min)

        return (x_min, y_min, w, h)

    def extract_body_regions(
        self, frame: np.ndarray, detection: Dict
    ) -> Dict[str, np.ndarray]:
        """
        Extract body regions for feature analysis.

        Args:
            frame: Input image
            detection: Detection dict from detect()

        Returns:
            Dict with:
            - full_body: Full body image
            - upper_body: Upper body (torso)
            - lower_body: Lower body (legs)
            - face: Face region (if available)
            - hair: Hair region (top of head)
        """
        regions = {}

        body_bbox = detection["body_bbox"]
        x, y, w, h = body_bbox

        # Validate bbox
        if w <= 0 or h <= 0:
            return regions

        x2 = min(x + w, frame.shape[1])
        y2 = min(y + h, frame.shape[0])
        x = max(0, x)
        y = max(0, y)

        if x >= x2 or y >= y2:
            return regions

        # Full body
        regions["full_body"] = frame[y:y2, x:x2]

        # Upper body (top 50%)
        mid_y = y + h // 2
        regions["upper_body"] = frame[y:mid_y, x:x2]

        # Lower body (bottom 50%)
        regions["lower_body"] = frame[mid_y:y2, x:x2]

        # Hair region (top 15% of body)
        hair_h = int(h * 0.15)
        if hair_h > 0:
            regions["hair"] = frame[y : y + hair_h, x:x2]

        # Face region (if available)
        if detection["has_face"] and detection["face_bbox"] is not None:
            fx, fy, fw, fh = detection["face_bbox"]
            fx2 = min(fx + fw, frame.shape[1])
            fy2 = min(fy + fh, frame.shape[0])
            fx = max(0, fx)
            fy = max(0, fy)

            if fx < fx2 and fy < fy2:
                regions["face"] = frame[fy:fy2, fx:fx2]

        return regions

    def get_body_keypoint_features(self, detection: Dict) -> Dict[str, any]:
        """
        Extract structured features from pose keypoints.

        Returns:
            Dict with:
            - shoulder_width: Distance between shoulders
            - hip_width: Distance between hips
            - body_height: Top to bottom distance
            - torso_length: Shoulder to hip distance
            - pose_vector: Flattened keypoint coordinates
        """
        if detection["keypoints"] is None:
            return {}

        kpts = detection["keypoints"]

        features = {}

        # Shoulder width
        left_shoulder = kpts[5][:2]
        right_shoulder = kpts[6][:2]
        if kpts[5][2] > 0.3 and kpts[6][2] > 0.3:
            features["shoulder_width"] = np.linalg.norm(left_shoulder - right_shoulder)

        # Hip width
        left_hip = kpts[11][:2]
        right_hip = kpts[12][:2]
        if kpts[11][2] > 0.3 and kpts[12][2] > 0.3:
            features["hip_width"] = np.linalg.norm(left_hip - right_hip)

        # Body height (nose to ankle)
        nose = kpts[0][:2]
        left_ankle = kpts[15][:2]
        right_ankle = kpts[16][:2]
        if kpts[0][2] > 0.3 and (kpts[15][2] > 0.3 or kpts[16][2] > 0.3):
            ankle = left_ankle if kpts[15][2] > kpts[16][2] else right_ankle
            features["body_height"] = np.linalg.norm(nose - ankle)

        # Torso length (shoulder to hip)
        if "shoulder_width" in features and "hip_width" in features:
            mid_shoulder = (left_shoulder + right_shoulder) / 2
            mid_hip = (left_hip + right_hip) / 2
            features["torso_length"] = np.linalg.norm(mid_shoulder - mid_hip)

        # Pose vector (flattened, normalized coordinates)
        valid_kpts = kpts[kpts[:, 2] > 0.3][:, :2]  # Only confident keypoints
        if len(valid_kpts) > 0:
            features["pose_vector"] = valid_kpts.flatten()

        return features
