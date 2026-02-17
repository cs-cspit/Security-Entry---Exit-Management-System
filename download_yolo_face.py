#!/usr/bin/env python3
"""
Download YOLOv8-face model for face detection.
This script provides multiple methods to obtain the YOLOv8-face model.
"""

import os
import sys
import urllib.request
from pathlib import Path


def download_file(url: str, destination: str, description: str = "file"):
    """Download a file with progress indication."""
    print(f"📥 Downloading {description}...")
    print(f"   URL: {url}")

    try:

        def report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                sys.stdout.write(
                    f"\r   Progress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)"
                )
                sys.stdout.flush()

        urllib.request.urlretrieve(url, destination, report_progress)
        print("\n✅ Download complete!")
        return True

    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        return False


def try_git_clone_method():
    """Try to get the model via git clone."""
    print("\n" + "=" * 60)
    print("METHOD 2: GIT CLONE (trying...)")
    print("=" * 60)

    try:
        import subprocess

        # Clone the repo
        print("📦 Cloning yolov8-face repository...")
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/akanametov/yolov8-face.git",
                "/tmp/yolov8-face",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Try to find the model in the cloned repo
            model_locations = [
                "/tmp/yolov8-face/weights/yolov8n-face.pt",
                "/tmp/yolov8-face/yolov8n-face.pt",
            ]

            for loc in model_locations:
                if os.path.exists(loc):
                    print(f"✅ Found model at: {loc}")
                    # Copy to current directory
                    import shutil

                    shutil.copy(loc, "yolov8n-face.pt")
                    print("✅ Model copied successfully!")
                    return True

            print("⚠️  Repository cloned but model file not found")
        else:
            print(f"❌ Git clone failed: {result.stderr}")

    except Exception as e:
        print(f"❌ Git clone method failed: {e}")

    return False


def create_alternative_solution():
    """Create a script that uses standard YOLOv8 face detection as fallback."""
    print("\n" + "=" * 60)
    print("METHOD 3: ALTERNATIVE SOLUTION")
    print("=" * 60)
    print()
    print("Creating fallback solution using MediaPipe or standard YOLO...")

    fallback_code = '''#!/usr/bin/env python3
"""
Alternative face detector using MediaPipe or standard YOLOv8.
Use this if YOLOv8-face model is unavailable.
"""

import cv2
import numpy as np
from typing import List, Tuple

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("⚠️  MediaPipe not available. Install with: pip install mediapipe")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class AlternativeFaceDetector:
    """Alternative face detector using available methods."""

    def __init__(self):
        self.method = None

        # Try MediaPipe first
        if MEDIAPIPE_AVAILABLE:
            try:
                self.mp_face_detection = mp.solutions.face_detection
                self.face_detection = self.mp_face_detection.FaceDetection(
                    min_detection_confidence=0.5
                )
                self.method = "mediapipe"
                print("✅ Using MediaPipe Face Detection")
                return
            except Exception as e:
                print(f"⚠️  MediaPipe initialization failed: {e}")

        # Try Haar Cascade as last resort
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            self.method = "haar"
            print("✅ Using Haar Cascade Face Detection (basic)")
            return
        except Exception as e:
            print(f"❌ Could not initialize any face detector: {e}")

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces in frame."""
        if self.method == "mediapipe":
            return self._detect_mediapipe(frame)
        elif self.method == "haar":
            return self._detect_haar(frame)
        else:
            return []

    def _detect_mediapipe(self, frame):
        """Detect using MediaPipe."""
        results = self.face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        detections = []
        if results.detections:
            h, w = frame.shape[:2]
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                width = int(bbox.width * w)
                height = int(bbox.height * h)
                conf = detection.score[0]

                if conf >= 0.5:
                    detections.append((x, y, width, height, float(conf)))

        return detections

    def _detect_haar(self, frame):
        """Detect using Haar Cascade."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)

        detections = []
        for (x, y, w, h) in faces:
            detections.append((x, y, w, h, 0.8))  # Haar doesn't provide confidence

        return detections


if __name__ == "__main__":
    print("Testing alternative face detector...")
    detector = AlternativeFaceDetector()

    if detector.method:
        print(f"✅ Detector initialized using: {detector.method}")
    else:
        print("❌ No face detection method available")
'''

    with open("alternative_face_detector.py", "w") as f:
        f.write(fallback_code)

    print("✅ Created: alternative_face_detector.py")
    print("   You can use this as a fallback if YOLOv8-face is unavailable")

    return True


def main():
    print("=" * 60)
    print("YOLOv8-FACE MODEL SETUP")
    print("=" * 60)
    print()

    current_dir = Path.cwd()
    destination = current_dir / "yolov8n-face.pt"

    # Check if model already exists
    if destination.exists():
        file_size = destination.stat().st_size / (1024 * 1024)
        print(f"✅ yolov8n-face.pt already exists ({file_size:.1f} MB)")
        print(f"   Location: {destination}")
        print()
        print("✅ SETUP COMPLETE!")
        return 0

    print(f"📂 Current directory: {current_dir}")
    print()

    # Method 1: Direct download URLs (multiple sources)
    print("=" * 60)
    print("METHOD 1: DIRECT DOWNLOAD")
    print("=" * 60)
    print()

    urls = [
        # Google Drive alternatives
        "https://drive.google.com/uc?export=download&id=1qcr9DbgsX3ryrz2uU8w4Xm3cOrRywXqb",
        # Roboflow public models
        "https://github.com/akanametov/yolov8-face/releases/download/v0.0.0/yolov8n-face.pt",
        # Alternative repositories
        "https://huggingface.co/arnabdhar/YOLOv8-Face-Detection/resolve/main/yolov8n-face.pt",
    ]

    for i, url in enumerate(urls, 1):
        print(f"Attempt {i}/{len(urls)}...")
        if download_file(
            url, str(destination), f"YOLOv8n-face model ({i}/{len(urls)})"
        ):
            print()
            print("=" * 60)
            print("✅ SETUP COMPLETE!")
            print("=" * 60)
            print()
            print("You can now run:")
            print("  python demo_yolo_cameras.py")
            print()
            return 0
        print()

    # Method 2: Try git clone
    if try_git_clone_method():
        print()
        print("=" * 60)
        print("✅ SETUP COMPLETE!")
        print("=" * 60)
        return 0

    # Method 3: Create alternative solution
    create_alternative_solution()

    # All methods failed - provide manual instructions
    print()
    print("=" * 60)
    print("⚠️  AUTOMATIC DOWNLOAD FAILED")
    print("=" * 60)
    print()
    print("OPTION 1: MANUAL DOWNLOAD (Recommended)")
    print("-" * 60)
    print()
    print("Visit one of these sources and download yolov8n-face.pt:")
    print()
    print("1. GitHub Release:")
    print("   https://github.com/akanametov/yolov8-face")
    print("   Look for 'Releases' → Download yolov8n-face.pt")
    print()
    print("2. Hugging Face:")
    print("   https://huggingface.co/arnabdhar/YOLOv8-Face-Detection")
    print("   Click 'Files and versions' → Download yolov8n-face.pt")
    print()
    print("3. Google Drive (if provided in repo README):")
    print("   Check the yolov8-face repository README for Google Drive links")
    print()
    print(f"4. Place the downloaded file here:")
    print(f"   {current_dir}/yolov8n-face.pt")
    print()
    print("=" * 60)
    print()
    print("OPTION 2: USE ALTERNATIVE DETECTOR")
    print("-" * 60)
    print()
    print("An alternative face detector has been created:")
    print("  alternative_face_detector.py")
    print()
    print("Install MediaPipe for better accuracy:")
    print("  pip install mediapipe")
    print()
    print("Then modify demo_yolo_cameras.py to use AlternativeFaceDetector")
    print("instead of YOLOv8FaceDetector")
    print()
    print("=" * 60)
    print()
    print("OPTION 3: TRAIN YOUR OWN MODEL")
    print("-" * 60)
    print()
    print("Train YOLOv8 on face detection dataset:")
    print("1. Clone: git clone https://github.com/akanametov/yolov8-face")
    print("2. Follow training instructions in the repository")
    print("3. Use trained weights as yolov8n-face.pt")
    print()
    print("=" * 60)

    return 1


if __name__ == "__main__":
    sys.exit(main())
