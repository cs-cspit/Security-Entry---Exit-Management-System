"""
OSNet-based Body Re-Identification Feature Extractor
Uses Omni-Scale Network for robust person re-identification across cameras
"""

import os
from typing import Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms as T


class OSNetExtractor:
    """
    OSNet feature extractor for person re-identification.

    OSNet (Omni-Scale Network) is specifically designed for person re-ID
    and produces 512-dimensional embeddings that are much more discriminative
    than color histograms.
    """

    def __init__(
        self,
        model_name: str = "osnet_x1_0",
        pretrained: bool = True,
        device: str = "auto",
    ):
        """
        Initialize OSNet feature extractor.

        Args:
            model_name: OSNet variant ('osnet_x1_0', 'osnet_x0_75', 'osnet_x0_5', 'osnet_x0_25')
            pretrained: Use pretrained weights
            device: Device ('cpu', 'cuda', 'mps', or 'auto')
        """
        self.model_name = model_name

        # Determine device
        if device == "auto":
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)

        print(f"🔧 Initializing OSNet on {self.device}...")

        # Try to import torchreid
        try:
            import torchreid

            self.torchreid = torchreid
        except ImportError:
            print("⚠️ torchreid not installed. Installing...")
            import subprocess
            import sys

            subprocess.check_call([sys.executable, "-m", "pip", "install", "torchreid"])
            import torchreid

            self.torchreid = torchreid

        # Load model
        try:
            self.model = torchreid.models.build_model(
                name=model_name,
                num_classes=1000,  # Not used for feature extraction
                pretrained=pretrained,
                use_gpu=(self.device.type in ["cuda", "mps"]),
            )

            self.model = self.model.to(self.device)
            self.model.eval()

            print(f"✅ OSNet model '{model_name}' loaded successfully")

        except Exception as e:
            print(f"❌ Failed to load OSNet: {e}")
            print("⚠️ Falling back to dummy extractor...")
            self.model = None

        # Image preprocessing transforms
        self.transform = T.Compose(
            [
                T.ToPILImage(),
                T.Resize((256, 128)),  # Standard person re-ID size
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

        self.feature_dim = 512  # OSNet output dimension

    def extract_features(
        self, image: np.ndarray, bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> np.ndarray:
        """
        Extract OSNet features from person image.

        Args:
            image: BGR image (full frame or cropped person)
            bbox: Optional bounding box (x, y, w, h) to crop person region

        Returns:
            512-dimensional feature vector (normalized)
        """
        if self.model is None:
            # Return dummy features if model not loaded
            return np.random.randn(self.feature_dim).astype(np.float32)

        # Crop person region if bbox provided
        if bbox is not None:
            x, y, w, h = bbox
            x, y = max(0, x), max(0, y)
            person_img = image[y : y + h, x : x + w]
        else:
            person_img = image

        if person_img.size == 0:
            return np.zeros(self.feature_dim, dtype=np.float32)

        # Convert BGR to RGB
        person_rgb = cv2.cvtColor(person_img, cv2.COLOR_BGR2RGB)

        # Preprocess
        try:
            img_tensor = self.transform(person_rgb)
            img_tensor = img_tensor.unsqueeze(0).to(self.device)

            # Extract features
            with torch.no_grad():
                features = self.model(img_tensor)

                # OSNet returns features before classification layer
                if isinstance(features, tuple):
                    features = features[0]

                # Normalize features
                features = F.normalize(features, p=2, dim=1)

                # Convert to numpy
                features = features.cpu().numpy().flatten()

            return features.astype(np.float32)

        except Exception as e:
            print(f"⚠️ OSNet feature extraction failed: {e}")
            return np.zeros(self.feature_dim, dtype=np.float32)

    def compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """
        Compute cosine similarity between two feature vectors.

        Args:
            features1: First feature vector
            features2: Second feature vector

        Returns:
            Similarity score (0-1)
        """
        # Cosine similarity (features are already normalized)
        similarity = np.dot(features1, features2)

        # Clip to [0, 1] range (should already be in [-1, 1])
        similarity = float(np.clip((similarity + 1) / 2, 0, 1))

        return similarity

    def batch_extract_features(self, images: list) -> np.ndarray:
        """
        Extract features from multiple images in batch.

        Args:
            images: List of BGR images

        Returns:
            Array of shape (N, 512) with feature vectors
        """
        if self.model is None or len(images) == 0:
            return np.zeros((len(images), self.feature_dim), dtype=np.float32)

        # Preprocess all images
        tensors = []
        for img in images:
            if img.size == 0:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            tensor = self.transform(rgb)
            tensors.append(tensor)

        if len(tensors) == 0:
            return np.zeros((len(images), self.feature_dim), dtype=np.float32)

        # Stack into batch
        batch = torch.stack(tensors).to(self.device)

        # Extract features
        with torch.no_grad():
            features = self.model(batch)

            if isinstance(features, tuple):
                features = features[0]

            # Normalize
            features = F.normalize(features, p=2, dim=1)

            # Convert to numpy
            features = features.cpu().numpy()

        return features.astype(np.float32)


class DummyOSNetExtractor:
    """
    Dummy OSNet extractor for testing without dependencies.
    Returns random features for compatibility.
    """

    def __init__(self, *args, **kwargs):
        """Initialize dummy extractor."""
        print("⚠️ Using dummy OSNet extractor (no real model)")
        self.feature_dim = 512
        self.device = torch.device("cpu")

    def extract_features(
        self, image: np.ndarray, bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> np.ndarray:
        """Return random features."""
        # Use image hash for consistency
        img_hash = hash(image.tobytes()) % 1000000
        np.random.seed(img_hash)
        features = np.random.randn(self.feature_dim).astype(np.float32)
        # Normalize
        features = features / (np.linalg.norm(features) + 1e-8)
        return features

    def compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """Compute cosine similarity."""
        similarity = np.dot(features1, features2)
        return float(np.clip((similarity + 1) / 2, 0, 1))

    def batch_extract_features(self, images: list) -> np.ndarray:
        """Extract features from batch."""
        return np.array([self.extract_features(img) for img in images])


def create_osnet_extractor(
    model_name: str = "osnet_x1_0",
    pretrained: bool = True,
    device: str = "auto",
    fallback_to_dummy: bool = True,
) -> OSNetExtractor:
    """
    Factory function to create OSNet extractor with fallback.

    Args:
        model_name: OSNet variant
        pretrained: Use pretrained weights
        device: Device to use
        fallback_to_dummy: If True, return dummy extractor on failure

    Returns:
        OSNetExtractor or DummyOSNetExtractor
    """
    try:
        extractor = OSNetExtractor(model_name, pretrained, device)
        if extractor.model is not None:
            return extractor
        elif fallback_to_dummy:
            return DummyOSNetExtractor()
        else:
            raise RuntimeError("Failed to load OSNet model")
    except Exception as e:
        print(f"⚠️ Failed to create OSNet extractor: {e}")
        if fallback_to_dummy:
            print("⚠️ Falling back to dummy extractor")
            return DummyOSNetExtractor()
        else:
            raise


def demo_osnet():
    """Demo function to test OSNet extractor."""
    print("=" * 80)
    print("TESTING OSNET FEATURE EXTRACTOR")
    print("=" * 80)
    print()

    # Create extractor
    extractor = create_osnet_extractor(device="auto")

    # Create test images
    print("Creating test images...")
    img1 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    img2 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    img3 = img1.copy()  # Same as img1

    # Extract features
    print("Extracting features...")
    features1 = extractor.extract_features(img1)
    features2 = extractor.extract_features(img2)
    features3 = extractor.extract_features(img3)

    print(f"✅ Feature dimension: {features1.shape}")
    print(f"✅ Feature norm: {np.linalg.norm(features1):.4f}")

    # Compare features
    print()
    print("Computing similarities...")
    sim_12 = extractor.compute_similarity(features1, features2)
    sim_13 = extractor.compute_similarity(features1, features3)

    print(f"✅ Similarity (img1 vs img2 - different): {sim_12:.4f}")
    print(f"✅ Similarity (img1 vs img3 - same): {sim_13:.4f}")

    if sim_13 > sim_12:
        print("✅ Same images are more similar than different images!")
    else:
        print("⚠️ Unexpected: different images are more similar")

    # Test batch extraction
    print()
    print("Testing batch extraction...")
    batch_features = extractor.batch_extract_features([img1, img2, img3])
    print(f"✅ Batch features shape: {batch_features.shape}")

    print()
    print("=" * 80)
    print("OSNet test complete!")
    print("=" * 80)


if __name__ == "__main__":
    demo_osnet()
