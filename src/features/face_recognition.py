#!/usr/bin/env python3
"""
Face Recognition Module using InsightFace
=========================================
High-accuracy face detection and embedding extraction for entry/exit gates.

Uses InsightFace's ArcFace model for face recognition:
- Face detection (SCRFD)
- Face alignment (5-point landmarks)
- Face embedding extraction (ArcFace)
- 512-dimensional face embeddings
- Cosine similarity matching

Model: buffalo_l (recommended) or buffalo_sc (smaller, faster)
"""

import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class FaceRecognitionExtractor:
    """
    Face recognition using InsightFace ArcFace model.
    """

    def __init__(
        self, model_name: str = "buffalo_l", det_size: Tuple[int, int] = (640, 640)
    ):
        """
        Initialize face recognition extractor.

        Args:
            model_name: InsightFace model name
                - 'buffalo_l': High accuracy, 512D embeddings (recommended)
                - 'buffalo_sc': Smaller, faster, 512D embeddings
                - 'antelopev2': Alternative high-accuracy model
            det_size: Detection input size (width, height)
                - (640, 640): Standard accuracy and speed
                - (320, 320): Faster but less accurate
                - (1280, 1280): More accurate but slower
        """
        self.model_name = model_name
        self.det_size = det_size
        self.app = None
        self.initialized = False

        print(f"🔧 Initializing InsightFace face recognition...")
        print(f"   Model: {model_name}")
        print(f"   Detection size: {det_size}")

        try:
            self._initialize_model()
        except Exception as e:
            print(f"❌ Failed to initialize InsightFace: {e}")
            print(f"   Please install: pip install insightface onnxruntime")
            self.initialized = False

    def _initialize_model(self):
        """Initialize InsightFace model."""
        try:
            import insightface
            from insightface.app import FaceAnalysis

            # Initialize face analysis app
            self.app = FaceAnalysis(
                name=self.model_name,
                providers=[
                    "CPUExecutionProvider"
                ],  # Use CPU (change to CUDAExecutionProvider for GPU)
            )

            # Prepare model with detection size
            self.app.prepare(ctx_id=0, det_size=self.det_size)

            self.initialized = True
            print(f"✅ InsightFace initialized successfully")
            print(f"   Models will be downloaded to: ~/.insightface/models/")

        except ImportError as e:
            print(f"❌ InsightFace not installed: {e}")
            print(f"   Install with: pip install insightface onnxruntime")
            raise
        except Exception as e:
            print(f"❌ Error initializing InsightFace: {e}")
            raise

    def detect_faces(
        self, frame: np.ndarray, min_confidence: float = 0.5
    ) -> List[Dict]:
        """
        Detect all faces in frame.

        Args:
            frame: Input frame (BGR format)
            min_confidence: Minimum detection confidence (0.0-1.0)

        Returns:
            List of face dictionaries with:
            - bbox: [x, y, w, h] bounding box
            - landmarks: 5-point facial landmarks
            - confidence: detection confidence
            - embedding: 512D face embedding
            - age: estimated age (if available)
            - gender: 0=female, 1=male (if available)
        """
        if not self.initialized or self.app is None:
            return []

        try:
            # InsightFace expects RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            faces = self.app.get(frame_rgb)

            # Filter by confidence and format output
            results = []
            for face in faces:
                if face.det_score < min_confidence:
                    continue

                # Extract bbox (convert from [x1, y1, x2, y2] to [x, y, w, h])
                bbox_xyxy = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox_xyxy
                bbox = [x1, y1, x2 - x1, y2 - y1]  # [x, y, w, h]

                face_dict = {
                    "bbox": bbox,
                    "bbox_xyxy": bbox_xyxy,  # Keep original format too
                    "landmarks": face.kps.astype(int) if hasattr(face, "kps") else None,
                    "confidence": float(face.det_score),
                    "embedding": face.normed_embedding,  # Already L2-normalized
                    "embedding_raw": face.embedding,  # Raw embedding (not normalized)
                }

                # Add age/gender if available
                if hasattr(face, "age"):
                    face_dict["age"] = int(face.age)
                if hasattr(face, "gender"):
                    face_dict["gender"] = int(face.gender)  # 0=female, 1=male

                results.append(face_dict)

            return results

        except Exception as e:
            print(f"⚠️ Face detection failed: {e}")
            return []

    def extract_face_embedding(
        self,
        frame: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.5,
    ) -> Optional[np.ndarray]:
        """
        Extract face embedding from frame.

        Args:
            frame: Input frame (BGR format)
            bbox: Optional bounding box [x, y, w, h]. If None, detect largest face.
            min_confidence: Minimum detection confidence

        Returns:
            512D face embedding (L2-normalized) or None if no face found
        """
        if not self.initialized or self.app is None:
            return None

        try:
            faces = self.detect_faces(frame, min_confidence)

            if not faces:
                return None

            # If bbox provided, find face closest to it
            if bbox is not None:
                x, y, w, h = bbox
                center = (x + w / 2, y + h / 2)

                # Find closest face to given bbox
                best_face = None
                min_dist = float("inf")

                for face in faces:
                    fx, fy, fw, fh = face["bbox"]
                    f_center = (fx + fw / 2, fy + fh / 2)
                    dist = np.sqrt(
                        (center[0] - f_center[0]) ** 2 + (center[1] - f_center[1]) ** 2
                    )

                    if dist < min_dist:
                        min_dist = dist
                        best_face = face

                return best_face["embedding"] if best_face else None

            else:
                # Return largest face (most prominent)
                best_face = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
                return best_face["embedding"]

        except Exception as e:
            print(f"⚠️ Face embedding extraction failed: {e}")
            return None

    def compare_faces(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compare two face embeddings using cosine similarity.

        Args:
            embedding1: First face embedding (512D)
            embedding2: Second face embedding (512D)

        Returns:
            Similarity score (0.0-1.0, higher is more similar)
            Typical threshold: 0.4-0.5 for same person
        """
        try:
            # InsightFace embeddings are already L2-normalized
            # Cosine similarity = dot product for normalized vectors
            similarity = float(np.dot(embedding1, embedding2))

            # Clamp to [0, 1] range (sometimes numerical errors cause slight overflow)
            similarity = max(0.0, min(1.0, similarity))

            return similarity

        except Exception as e:
            print(f"⚠️ Face comparison failed: {e}")
            return 0.0

    def verify_face(
        self,
        frame: np.ndarray,
        registered_embedding: np.ndarray,
        threshold: float = 0.45,
        bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Tuple[bool, float]:
        """
        Verify if face in frame matches registered embedding.

        Args:
            frame: Input frame (BGR format)
            registered_embedding: Registered face embedding
            threshold: Similarity threshold for match (0.4-0.5 typical)
            bbox: Optional bounding box hint

        Returns:
            (is_match, similarity_score)
        """
        query_embedding = self.extract_face_embedding(frame, bbox)

        if query_embedding is None:
            return False, 0.0

        similarity = self.compare_faces(query_embedding, registered_embedding)
        is_match = similarity >= threshold

        return is_match, similarity

    def draw_face_detection(
        self,
        frame: np.ndarray,
        faces: List[Dict],
        draw_landmarks: bool = True,
        draw_info: bool = True,
    ) -> np.ndarray:
        """
        Draw face detection results on frame.

        Args:
            frame: Input frame (will be modified)
            faces: List of face dictionaries from detect_faces()
            draw_landmarks: Whether to draw facial landmarks
            draw_info: Whether to draw age/gender info

        Returns:
            Frame with drawings
        """
        for face in faces:
            bbox = face["bbox"]
            x, y, w, h = bbox

            # Draw bounding box
            confidence = face["confidence"]
            color = (0, 255, 0) if confidence > 0.7 else (0, 255, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            # Draw confidence
            cv2.putText(
                frame,
                f"{confidence:.2f}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

            # Draw landmarks
            if draw_landmarks and face.get("landmarks") is not None:
                landmarks = face["landmarks"]
                for lx, ly in landmarks:
                    cv2.circle(frame, (lx, ly), 2, (255, 0, 0), -1)

            # Draw age/gender
            if draw_info:
                info_text = []
                if "age" in face:
                    info_text.append(f"Age: {face['age']}")
                if "gender" in face:
                    gender_str = "M" if face["gender"] == 1 else "F"
                    info_text.append(f"Gender: {gender_str}")

                if info_text:
                    text = ", ".join(info_text)
                    cv2.putText(
                        frame,
                        text,
                        (x, y + h + 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                    )

        return frame

    def get_face_quality_score(self, face: Dict) -> float:
        """
        Calculate quality score for a detected face.

        Args:
            face: Face dictionary from detect_faces()

        Returns:
            Quality score (0.0-1.0, higher is better)
        """
        score = 0.0

        # Detection confidence (0-40 points)
        score += face["confidence"] * 0.4

        # Face size (0-30 points) - larger faces are better
        bbox = face["bbox"]
        face_area = bbox[2] * bbox[3]
        size_score = min(face_area / (200 * 200), 1.0)  # Normalize by 200x200 pixels
        score += size_score * 0.3

        # Frontal pose (0-30 points) - check if landmarks are well-aligned
        if face.get("landmarks") is not None:
            landmarks = face["landmarks"]
            # Simple frontal check: left and right eye should be roughly horizontal
            if len(landmarks) >= 2:
                left_eye, right_eye = landmarks[0], landmarks[1]
                eye_distance = np.linalg.norm(left_eye - right_eye)
                vertical_diff = abs(left_eye[1] - right_eye[1])
                alignment_score = 1.0 - min(vertical_diff / (eye_distance + 1e-6), 1.0)
                score += alignment_score * 0.3

        return min(score, 1.0)

    def select_best_face(self, faces: List[Dict]) -> Optional[Dict]:
        """
        Select best quality face from list.

        Args:
            faces: List of face dictionaries

        Returns:
            Best face or None if no faces
        """
        if not faces:
            return None

        # Score all faces
        scored_faces = [(face, self.get_face_quality_score(face)) for face in faces]

        # Return face with highest score
        best_face, best_score = max(scored_faces, key=lambda x: x[1])

        return best_face

    def is_initialized(self) -> bool:
        """Check if model is initialized."""
        return self.initialized


# Standalone test function
def test_face_recognition():
    """Test face recognition on webcam."""
    print("🧪 Testing Face Recognition...")

    try:
        # Initialize
        face_recognizer = FaceRecognitionExtractor(
            model_name="buffalo_sc", det_size=(640, 640)
        )

        if not face_recognizer.is_initialized():
            print("❌ Face recognizer not initialized!")
            return

        # Open webcam
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Cannot open webcam!")
            return

        print("✅ Press 'q' to quit, 'r' to register face, 's' to verify")

        registered_embedding = None
        registered_label = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Detect faces
            faces = face_recognizer.detect_faces(frame, min_confidence=0.5)

            # Draw detections
            display = frame.copy()
            face_recognizer.draw_face_detection(display, faces)

            # If faces detected, show best face info
            if faces:
                best_face = face_recognizer.select_best_face(faces)
                quality = face_recognizer.get_face_quality_score(best_face)

                cv2.putText(
                    display,
                    f"Faces: {len(faces)}, Best Quality: {quality:.2f}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

                # If registered, verify
                if registered_embedding is not None and best_face:
                    similarity = face_recognizer.compare_faces(
                        best_face["embedding"], registered_embedding
                    )
                    match = similarity >= 0.45
                    color = (0, 255, 0) if match else (0, 0, 255)
                    label = (
                        f"{registered_label}: {similarity:.3f}"
                        if match
                        else f"Unknown: {similarity:.3f}"
                    )

                    cv2.putText(
                        display,
                        label,
                        (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        color,
                        2,
                    )

            # Show instructions
            cv2.putText(
                display,
                "R: Register | S: Verify | Q: Quit",
                (10, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

            cv2.imshow("Face Recognition Test", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r") and faces:
                # Register best face
                best_face = face_recognizer.select_best_face(faces)
                registered_embedding = best_face["embedding"]
                registered_label = "Person1"
                print(f"✅ Registered {registered_label}")
            elif key == ord("s") and faces and registered_embedding is not None:
                # Verify
                best_face = face_recognizer.select_best_face(faces)
                similarity = face_recognizer.compare_faces(
                    best_face["embedding"], registered_embedding
                )
                match = similarity >= 0.45
                print(
                    f"{'✅ MATCH' if match else '❌ NO MATCH'}: Similarity = {similarity:.3f}"
                )

        cap.release()
        cv2.destroyAllWindows()
        print("✅ Test complete!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_face_recognition()
