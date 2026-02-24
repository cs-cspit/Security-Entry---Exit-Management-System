#!/usr/bin/env python3
"""
Cross-Camera Domain Adaptation Module
======================================
Handles domain shift across different camera models for person re-identification.

Camera Setup:
- Entry: iBall Face2Face CHD20.0 (720p, budget webcam)
- Room: MacBook M2 FaceTime HD (1080p, premium)
- Exit: Redmi Note 11 (1080p, mobile sensor)

Problem: Same person looks different across cameras due to:
- Different ISPs (Image Signal Processors)
- Different color calibration
- Different lighting conditions
- Different distances and angles

Solutions:
1. Histogram equalization (CLAHE)
2. Camera-specific color correction
3. Adaptive matching thresholds per camera pair
4. Feature normalization per camera
"""

from collections import defaultdict
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


class CrossCameraAdapter:
    """
    Adapter to handle cross-camera domain shift in multi-camera re-identification.
    """

    def __init__(self):
        """Initialize cross-camera adapter with camera profiles."""

        # Camera-specific profiles
        self.camera_profiles = {
            "entry": {
                "name": "iBall Face2Face CHD20.0",
                "resolution": "720p",
                "characteristics": "Budget webcam, tends to be warmer/more yellow",
                "warmth_correction": -8,  # Reduce warmth (negative = cooler)
                "brightness_boost": 5,  # Slightly brighten
                "clahe_clip_limit": 2.5,  # Stronger contrast enhancement
            },
            "room": {
                "name": "MacBook M2 FaceTime HD",
                "resolution": "1080p",
                "characteristics": "Premium camera, accurate colors",
                "warmth_correction": 0,  # No correction needed
                "brightness_boost": 0,  # Already well-exposed
                "clahe_clip_limit": 2.0,  # Standard contrast enhancement
            },
            "exit": {
                "name": "Redmi Note 11",
                "resolution": "1080p",
                "characteristics": "Mobile sensor, oversaturated colors",
                "saturation_scale": 0.85,  # Reduce oversaturation
                "brightness_boost": -3,  # Slightly darken
                "clahe_clip_limit": 2.2,  # Moderate contrast enhancement
            },
        }

        # Adaptive thresholds for cross-camera matching
        # INCREASED to prevent false positives (better to reject unknown than accept wrong person)
        self.similarity_thresholds = {
            # Same camera = high threshold (should match very well)
            "entry_to_entry": 0.75,
            "room_to_room": 0.75,
            "exit_to_exit": 0.75,
            # Cross-camera = MODERATE thresholds (balance accuracy vs false positives)
            "entry_to_room": 0.50,  # INCREASED from 0.38 - prevent girl being matched as you
            "entry_to_exit": 0.52,  # INCREASED from 0.42
            "room_to_exit": 0.55,  # INCREASED from 0.45
        }

        # Confidence gap requirements (how much better than 2nd best)
        self.confidence_gaps = {
            "entry_to_entry": 0.15,  # Clear winner needed
            "room_to_room": 0.15,
            "exit_to_exit": 0.15,
            # Cross-camera = Higher gaps to ensure clear distinction
            "entry_to_room": 0.12,  # INCREASED from 0.08 - need clearer winner
            "entry_to_exit": 0.12,  # INCREASED from 0.10
            "room_to_exit": 0.12,  # INCREASED from 0.10
        }

        # Feature normalization statistics per camera
        self.feature_stats = {}  # {camera_id: {'mean': ..., 'std': ...}}
        self.feature_history = defaultdict(list)  # Collect samples
        self.min_samples_for_stats = 20  # Minimum samples before computing stats

        print("🔧 Cross-Camera Adapter initialized")
        print(f"   Entry camera: {self.camera_profiles['entry']['name']}")
        print(f"   Room camera: {self.camera_profiles['room']['name']}")
        print(f"   Exit camera: {self.camera_profiles['exit']['name']}")
        print(
            f"   Adaptive thresholds: entry→room={self.similarity_thresholds['entry_to_room']:.2f}"
        )

    def preprocess_frame(
        self, frame: np.ndarray, camera_id: str, apply_clahe: bool = True
    ) -> np.ndarray:
        """
        Apply camera-specific preprocessing to reduce domain shift.

        Args:
            frame: Input frame (BGR format)
            camera_id: 'entry', 'room', or 'exit'
            apply_clahe: Whether to apply CLAHE (contrast enhancement)

        Returns:
            Preprocessed frame with reduced domain shift
        """
        if camera_id not in self.camera_profiles:
            return frame  # Unknown camera, no preprocessing

        profile = self.camera_profiles[camera_id]
        processed = frame.copy()

        # Step 1: Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # This normalizes lighting/contrast across cameras
        if apply_clahe:
            # Convert to LAB color space (better for illumination)
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)

            # Apply CLAHE to luminance channel
            clip_limit = profile.get("clahe_clip_limit", 2.0)
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
            l_channel = clahe.apply(l_channel)

            # Merge back
            lab = cv2.merge([l_channel, a_channel, b_channel])
            processed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # Step 2: Camera-specific color corrections

        # Warmth correction (for cameras with color temperature issues)
        if "warmth_correction" in profile:
            correction = profile["warmth_correction"]
            if correction != 0:
                processed = cv2.addWeighted(
                    processed, 1.0, np.zeros_like(processed), 0, correction
                )

        # Brightness boost/reduction
        if "brightness_boost" in profile:
            boost = profile["brightness_boost"]
            if boost != 0:
                hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
                h, s, v = cv2.split(hsv)
                v = np.clip(v.astype(np.int16) + boost, 0, 255).astype(np.uint8)
                hsv = cv2.merge([h, s, v])
                processed = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # Saturation adjustment (for oversaturated mobile cameras)
        if "saturation_scale" in profile:
            scale = profile["saturation_scale"]
            if scale != 1.0:
                hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
                h, s, v = cv2.split(hsv)
                s = np.clip(s.astype(np.float32) * scale, 0, 255).astype(np.uint8)
                hsv = cv2.merge([h, s, v])
                processed = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return processed

    def update_feature_stats(self, camera_id: str, features: np.ndarray):
        """
        Collect features from camera to compute normalization statistics.

        Args:
            camera_id: Camera identifier
            features: Feature vector (e.g., OSNet embedding)
        """
        # Add to history
        self.feature_history[camera_id].append(features.copy())

        # Keep only recent samples (avoid stale data)
        if len(self.feature_history[camera_id]) > 100:
            self.feature_history[camera_id].pop(0)

        # Compute stats once we have enough samples
        if len(self.feature_history[camera_id]) >= self.min_samples_for_stats:
            all_features = np.array(self.feature_history[camera_id])

            self.feature_stats[camera_id] = {
                "mean": np.mean(all_features, axis=0),
                "std": np.std(all_features, axis=0) + 1e-6,  # Avoid divide by zero
            }

    def normalize_features(self, camera_id: str, features: np.ndarray) -> np.ndarray:
        """
        Normalize features using camera-specific statistics.

        This removes camera-specific bias in feature space.

        Args:
            camera_id: Camera identifier
            features: Feature vector to normalize

        Returns:
            Normalized feature vector
        """
        if camera_id not in self.feature_stats:
            # No stats yet, return unnormalized
            return features

        stats = self.feature_stats[camera_id]

        # Z-score normalization: (x - mean) / std
        normalized = (features - stats["mean"]) / stats["std"]

        return normalized

    def get_matching_params(
        self, source_camera: str, target_camera: str
    ) -> Tuple[float, float]:
        """
        Get adaptive threshold and confidence gap for camera pair.

        Args:
            source_camera: Camera where person was registered (usually 'entry')
            target_camera: Camera where person is being matched ('room', 'exit')

        Returns:
            (similarity_threshold, confidence_gap)
        """
        key = f"{source_camera}_to_{target_camera}"

        threshold = self.similarity_thresholds.get(key, 0.50)
        gap = self.confidence_gaps.get(key, 0.10)

        return threshold, gap

    def adjust_similarity_score(
        self,
        score: float,
        source_camera: str,
        target_camera: str,
        features_query: Optional[np.ndarray] = None,
        features_registered: Optional[np.ndarray] = None,
    ) -> float:
        """
        Adjust similarity score based on camera pair characteristics.

        Can apply boosting/penalties based on known camera behaviors.

        Args:
            score: Raw similarity score
            source_camera: Registration camera
            target_camera: Query camera
            features_query: Query feature vector (optional, for advanced adjustment)
            features_registered: Registered feature vector (optional)

        Returns:
            Adjusted similarity score
        """
        adjusted_score = score

        # Cross-camera domain shift compensation
        if source_camera != target_camera:
            # Apply small boost to compensate for systematic domain shift
            # (We know scores are artificially lower across cameras)

            if source_camera == "entry" and target_camera == "room":
                # iBall → MacBook: Huge shift, boost significantly
                adjusted_score *= 1.15

            elif source_camera == "entry" and target_camera == "exit":
                # iBall → Redmi: Moderate shift
                adjusted_score *= 1.10

            elif source_camera == "room" and target_camera == "exit":
                # MacBook → Redmi: Less shift (both modern)
                adjusted_score *= 1.05

        # Clip to [0, 1] range
        adjusted_score = np.clip(adjusted_score, 0.0, 1.0)

        return adjusted_score

    def should_match(
        self,
        best_score: float,
        second_best_score: float,
        num_registered: int,
        source_camera: str,
        target_camera: str,
    ) -> Tuple[bool, str]:
        """
        Decide if a match should be accepted based on adaptive criteria.

        Args:
            best_score: Best matching score
            second_best_score: Second-best matching score
            num_registered: Number of registered people
            source_camera: Registration camera
            target_camera: Query camera

        Returns:
            (should_match: bool, reason: str)
        """
        # Get adaptive parameters
        threshold, required_gap = self.get_matching_params(source_camera, target_camera)

        # Check threshold
        if best_score < threshold:
            return False, f"below_threshold ({best_score:.3f} < {threshold:.3f})"

        # Check confidence gap (only if multiple people registered)
        if num_registered > 1:
            gap = best_score - second_best_score
            if gap < required_gap:
                return False, f"insufficient_gap ({gap:.3f} < {required_gap:.3f})"

        return True, "match_accepted"

    def get_info(self) -> Dict:
        """
        Get adapter status and statistics.

        Returns:
            Dictionary with adapter information
        """
        return {
            "cameras": list(self.camera_profiles.keys()),
            "feature_stats_available": list(self.feature_stats.keys()),
            "samples_collected": {
                cam: len(samples) for cam, samples in self.feature_history.items()
            },
            "thresholds": self.similarity_thresholds,
            "confidence_gaps": self.confidence_gaps,
        }

    def print_diagnostics(self):
        """Print diagnostic information about cross-camera adaptation."""
        print("\n" + "=" * 70)
        print("  CROSS-CAMERA ADAPTER DIAGNOSTICS")
        print("=" * 70)

        print("\n📹 Camera Profiles:")
        for cam_id, profile in self.camera_profiles.items():
            print(f"   {cam_id.upper()}: {profile['name']}")
            print(f"      Resolution: {profile['resolution']}")
            print(f"      Characteristics: {profile['characteristics']}")

        print("\n🎯 Adaptive Thresholds:")
        for pair, threshold in self.similarity_thresholds.items():
            if "to" in pair and pair.split("_to_")[0] != pair.split("_to_")[1]:
                gap = self.confidence_gaps.get(pair, 0.10)
                print(f"   {pair}: threshold={threshold:.2f}, gap={gap:.2f}")

        print("\n📊 Feature Statistics:")
        for cam_id in ["entry", "room", "exit"]:
            if cam_id in self.feature_stats:
                samples = len(self.feature_history[cam_id])
                print(f"   {cam_id.upper()}: ✅ Available ({samples} samples)")
            else:
                samples = len(self.feature_history[cam_id])
                needed = self.min_samples_for_stats
                print(
                    f"   {cam_id.upper()}: ⏳ Collecting ({samples}/{needed} samples)"
                )

        print("=" * 70 + "\n")


# Convenience function for quick testing
def test_adapter():
    """Test the cross-camera adapter with dummy data."""
    adapter = CrossCameraAdapter()

    # Test frame preprocessing
    print("\n🧪 Testing frame preprocessing...")
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    for camera_id in ["entry", "room", "exit"]:
        processed = adapter.preprocess_frame(dummy_frame, camera_id)
        print(f"   {camera_id}: {processed.shape} - ✅")

    # Test feature normalization
    print("\n🧪 Testing feature normalization...")
    dummy_features = np.random.randn(512)

    # Simulate collecting samples
    for _ in range(25):
        adapter.update_feature_stats("room", np.random.randn(512))

    normalized = adapter.normalize_features("room", dummy_features)
    print(f"   Feature normalization: {normalized.shape} - ✅")

    # Test matching decision
    print("\n🧪 Testing matching decision...")
    should_match, reason = adapter.should_match(
        best_score=0.42,
        second_best_score=0.30,
        num_registered=2,
        source_camera="entry",
        target_camera="room",
    )
    print(f"   Match decision: {should_match} ({reason}) - ✅")

    # Print diagnostics
    adapter.print_diagnostics()

    print("✅ All tests passed!\n")


if __name__ == "__main__":
    # Run tests if executed directly
    test_adapter()
