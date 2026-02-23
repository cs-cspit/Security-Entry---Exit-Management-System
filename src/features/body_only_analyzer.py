"""
Body-Only Feature Analyzer for Room Camera
Extracts hair color and skin tone from body detection bbox (no face detection needed)
Designed for distant room cameras where faces are not clearly visible.
"""

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class BodyOnlyAnalyzer:
    """
    Analyzes body detection bbox to extract:
    1. Hair color (top 10-15% of body bbox)
    2. Skin tone (from exposed body parts like arms, neck)
    3. Upper/lower clothing colors
    4. Body color distribution

    No face detection required - works purely from body bbox.
    """

    def __init__(self):
        """Initialize body-only analyzer."""
        self.skin_lower_hsv = np.array([0, 20, 70], dtype=np.uint8)
        self.skin_upper_hsv = np.array([20, 150, 255], dtype=np.uint8)

    def extract_features(
        self, image: np.ndarray, body_bbox: Tuple[int, int, int, int]
    ) -> Dict[str, any]:
        """
        Extract all body-only features from body detection.

        Args:
            image: Full frame (BGR)
            body_bbox: (x, y, w, h) of body detection

        Returns:
            Dictionary with:
            - hair_color: Dict with dominant hair colors
            - skin_tone: Dict with skin HSV values
            - upper_clothing: Dict with upper body clothing colors
            - lower_clothing: Dict with lower body clothing colors
            - body_color_histogram: Full body color distribution
        """
        x, y, w, h = body_bbox

        # Validate bbox
        if w <= 0 or h <= 0:
            return self._empty_features()

        # Extract body region
        x2 = min(x + w, image.shape[1])
        y2 = min(y + h, image.shape[0])
        x = max(0, x)
        y = max(0, y)

        if x >= x2 or y >= y2:
            return self._empty_features()

        body_img = image[y:y2, x:x2]

        if body_img.size == 0:
            return self._empty_features()

        # Extract each feature
        features = {
            "hair_color": self._extract_hair_color(body_img),
            "skin_tone": self._extract_skin_tone(body_img),
            "upper_clothing": self._extract_upper_clothing(body_img),
            "lower_clothing": self._extract_lower_clothing(body_img),
            "body_color_histogram": self._extract_body_histogram(body_img),
        }

        return features

    def _extract_hair_color(self, body_img: np.ndarray) -> Dict[str, any]:
        """
        Extract hair color from top 10-15% of body bbox.
        Assumes head/hair is at the top of the detection.

        Returns:
            Dict with dominant_color, hsv_mean, confidence
        """
        h, w = body_img.shape[:2]

        # Top 12% of body is likely hair
        hair_region_height = int(h * 0.12)
        if hair_region_height < 5:
            return {"dominant_color": None, "hsv_mean": None, "confidence": 0.0}

        hair_region = body_img[0:hair_region_height, :]

        if hair_region.size == 0:
            return {"dominant_color": None, "hsv_mean": None, "confidence": 0.0}

        # Convert to HSV
        hair_hsv = cv2.cvtColor(hair_region, cv2.COLOR_BGR2HSV)

        # Get dominant color
        pixels = hair_hsv.reshape(-1, 3)

        # Remove very dark (likely shadows) and very bright (likely background)
        mask = (pixels[:, 2] > 30) & (pixels[:, 2] < 240)
        valid_pixels = pixels[mask]

        if len(valid_pixels) < 10:
            return {"dominant_color": None, "hsv_mean": None, "confidence": 0.0}

        # Calculate mean HSV
        hsv_mean = np.mean(valid_pixels, axis=0)

        # Determine hair color name
        hair_color_name = self._classify_hair_color(hsv_mean)

        # Confidence based on region consistency
        hsv_std = np.std(valid_pixels, axis=0)
        confidence = 1.0 / (
            1.0 + np.mean(hsv_std) / 50.0
        )  # Lower std = higher confidence

        return {
            "dominant_color": hair_color_name,
            "hsv_mean": hsv_mean.tolist(),
            "confidence": float(confidence),
        }

    def _classify_hair_color(self, hsv_mean: np.ndarray) -> str:
        """Classify hair color from HSV values."""
        h, s, v = hsv_mean

        # Very low value = black hair
        if v < 50:
            return "black"

        # Low saturation = gray/white hair
        if s < 30:
            if v > 150:
                return "white"
            elif v > 100:
                return "gray"
            else:
                return "dark_gray"

        # Brown tones (hue 10-25)
        if 10 <= h <= 25:
            if v < 80:
                return "dark_brown"
            elif v < 140:
                return "brown"
            else:
                return "light_brown"

        # Blonde (hue 25-40, high value)
        if 25 <= h <= 40 and v > 120:
            return "blonde"

        # Red tones (hue 0-10 or 160-180)
        if h <= 10 or h >= 160:
            if s > 50:
                return "red"

        # Default to dark/light based on value
        if v < 100:
            return "dark"
        else:
            return "light"

    def _extract_skin_tone(self, body_img: np.ndarray) -> Dict[str, any]:
        """
        Extract skin tone from visible body parts (arms, neck, hands).
        Uses skin color detection in HSV space.

        Returns:
            Dict with hsv_mean, percentage, confidence
        """
        # Convert to HSV
        body_hsv = cv2.cvtColor(body_img, cv2.COLOR_BGR2HSV)

        # Create skin mask using expanded HSV range
        # Multiple skin tone ranges
        skin_mask1 = cv2.inRange(
            body_hsv,
            np.array([0, 20, 70], dtype=np.uint8),
            np.array([20, 150, 255], dtype=np.uint8),
        )
        skin_mask2 = cv2.inRange(
            body_hsv,
            np.array([0, 10, 60], dtype=np.uint8),
            np.array([25, 170, 255], dtype=np.uint8),
        )

        skin_mask = cv2.bitwise_or(skin_mask1, skin_mask2)

        # Apply morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)

        # Extract skin pixels
        skin_pixels = body_hsv[skin_mask > 0]

        if len(skin_pixels) < 50:
            return {"hsv_mean": None, "percentage": 0.0, "confidence": 0.0}

        # Calculate mean skin tone
        hsv_mean = np.mean(skin_pixels, axis=0)

        # Calculate percentage of skin in body
        total_pixels = body_img.shape[0] * body_img.shape[1]
        skin_percentage = len(skin_pixels) / total_pixels

        # Confidence based on amount of skin detected
        confidence = min(1.0, skin_percentage / 0.15)  # 15% skin is high confidence

        return {
            "hsv_mean": hsv_mean.tolist(),
            "percentage": float(skin_percentage),
            "confidence": float(confidence),
        }

    def _extract_upper_clothing(self, body_img: np.ndarray) -> Dict[str, any]:
        """
        Extract upper body clothing colors (chest/torso area).
        Region: 15-50% from top of body bbox.
        """
        h, w = body_img.shape[:2]

        # Upper clothing region (chest/torso)
        upper_start = int(h * 0.15)  # Below hair
        upper_end = int(h * 0.50)  # Above waist

        if upper_end <= upper_start or upper_start >= h:
            return {"dominant_colors": [], "hsv_mean": None}

        upper_region = body_img[upper_start:upper_end, :]

        if upper_region.size == 0:
            return {"dominant_colors": [], "hsv_mean": None}

        # Get dominant colors
        dominant_colors = self._get_dominant_colors(upper_region, n_colors=3)

        # Mean HSV
        upper_hsv = cv2.cvtColor(upper_region, cv2.COLOR_BGR2HSV)
        hsv_mean = np.mean(upper_hsv.reshape(-1, 3), axis=0)

        return {"dominant_colors": dominant_colors, "hsv_mean": hsv_mean.tolist()}

    def _extract_lower_clothing(self, body_img: np.ndarray) -> Dict[str, any]:
        """
        Extract lower body clothing colors (pants/legs).
        Region: 50-100% from top of body bbox.
        """
        h, w = body_img.shape[:2]

        # Lower clothing region (legs/pants)
        lower_start = int(h * 0.50)
        lower_end = h

        if lower_end <= lower_start:
            return {"dominant_colors": [], "hsv_mean": None}

        lower_region = body_img[lower_start:lower_end, :]

        if lower_region.size == 0:
            return {"dominant_colors": [], "hsv_mean": None}

        # Get dominant colors
        dominant_colors = self._get_dominant_colors(lower_region, n_colors=3)

        # Mean HSV
        lower_hsv = cv2.cvtColor(lower_region, cv2.COLOR_BGR2HSV)
        hsv_mean = np.mean(lower_hsv.reshape(-1, 3), axis=0)

        return {"dominant_colors": dominant_colors, "hsv_mean": hsv_mean.tolist()}

    def _extract_body_histogram(self, body_img: np.ndarray) -> np.ndarray:
        """
        Extract full body color histogram for overall appearance.
        """
        body_hsv = cv2.cvtColor(body_img, cv2.COLOR_BGR2HSV)

        # Calculate 3D histogram
        hist = cv2.calcHist(
            [body_hsv],
            [0, 1, 2],
            None,
            [8, 8, 8],  # Bins per channel
            [0, 180, 0, 256, 0, 256],
        )

        # Normalize
        hist = hist.flatten()
        hist = hist / (np.sum(hist) + 1e-6)

        return hist

    def _get_dominant_colors(self, region: np.ndarray, n_colors: int = 3) -> List[str]:
        """
        Get dominant color names from a region using k-means clustering.
        """
        # Resize for speed
        small = cv2.resize(region, (50, 50))
        pixels = small.reshape(-1, 3)

        # Convert to float
        pixels = np.float32(pixels)

        # K-means clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, n_colors, None, criteria, 3, cv2.KMEANS_PP_CENTERS
        )

        # Count pixels in each cluster
        unique, counts = np.unique(labels, return_counts=True)

        # Sort by frequency
        sorted_indices = np.argsort(counts)[::-1]

        # Get dominant colors
        dominant_colors = []
        for idx in sorted_indices:
            bgr = centers[idx]
            color_name = self._classify_color(bgr)
            dominant_colors.append(color_name)

        return dominant_colors

    def _classify_color(self, bgr: np.ndarray) -> str:
        """Classify a BGR color into a named color."""
        b, g, r = bgr

        # Convert to HSV for better classification
        bgr_pixel = np.uint8([[[b, g, r]]])
        hsv_pixel = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2HSV)[0][0]
        h, s, v = hsv_pixel

        # Black
        if v < 50:
            return "black"

        # White
        if v > 200 and s < 30:
            return "white"

        # Gray
        if s < 30:
            return "gray"

        # Chromatic colors
        if h < 10 or h >= 170:
            return "red"
        elif 10 <= h < 25:
            return "orange"
        elif 25 <= h < 40:
            return "yellow"
        elif 40 <= h < 80:
            return "green"
        elif 80 <= h < 130:
            return "blue"
        elif 130 <= h < 150:
            return "cyan"
        elif 150 <= h < 170:
            return "purple"

        return "unknown"

    def _empty_features(self) -> Dict[str, any]:
        """Return empty feature dict when extraction fails."""
        return {
            "hair_color": {"dominant_color": None, "hsv_mean": None, "confidence": 0.0},
            "skin_tone": {"hsv_mean": None, "percentage": 0.0, "confidence": 0.0},
            "upper_clothing": {"dominant_colors": [], "hsv_mean": None},
            "lower_clothing": {"dominant_colors": [], "hsv_mean": None},
            "body_color_histogram": None,
        }

    def compare_features(
        self, features1: Dict[str, any], features2: Dict[str, any]
    ) -> float:
        """
        Compare two body-only feature sets.

        Returns:
            Similarity score 0.0-1.0
        """
        total_similarity = 0.0
        total_weight = 0.0

        # Hair color similarity (weight: 0.25)
        hair_sim = self._compare_hair(features1["hair_color"], features2["hair_color"])
        if hair_sim >= 0:
            total_similarity += hair_sim * 0.25
            total_weight += 0.25

        # Skin tone similarity (weight: 0.20)
        skin_sim = self._compare_skin(features1["skin_tone"], features2["skin_tone"])
        if skin_sim >= 0:
            total_similarity += skin_sim * 0.20
            total_weight += 0.20

        # Upper clothing similarity (weight: 0.30)
        upper_sim = self._compare_clothing(
            features1["upper_clothing"], features2["upper_clothing"]
        )
        if upper_sim >= 0:
            total_similarity += upper_sim * 0.30
            total_weight += 0.30

        # Lower clothing similarity (weight: 0.25)
        lower_sim = self._compare_clothing(
            features1["lower_clothing"], features2["lower_clothing"]
        )
        if lower_sim >= 0:
            total_similarity += lower_sim * 0.25
            total_weight += 0.25

        if total_weight == 0:
            return 0.0

        return total_similarity / total_weight

    def _compare_hair(self, hair1: Dict, hair2: Dict) -> float:
        """Compare hair color features."""
        if hair1["dominant_color"] is None or hair2["dominant_color"] is None:
            return -1.0

        # Exact match
        if hair1["dominant_color"] == hair2["dominant_color"]:
            return 1.0

        # Similar colors (e.g., dark_brown vs brown)
        if hair1["hsv_mean"] is not None and hair2["hsv_mean"] is not None:
            hsv1 = np.array(hair1["hsv_mean"])
            hsv2 = np.array(hair2["hsv_mean"])

            # Weighted distance (H is circular, S and V are linear)
            h_dist = min(abs(hsv1[0] - hsv2[0]), 180 - abs(hsv1[0] - hsv2[0]))
            s_dist = abs(hsv1[1] - hsv2[1])
            v_dist = abs(hsv1[2] - hsv2[2])

            total_dist = (
                (h_dist / 180.0) * 0.5
                + (s_dist / 255.0) * 0.25
                + (v_dist / 255.0) * 0.25
            )

            return 1.0 - total_dist

        return 0.0

    def _compare_skin(self, skin1: Dict, skin2: Dict) -> float:
        """Compare skin tone features."""
        if skin1["hsv_mean"] is None or skin2["hsv_mean"] is None:
            return -1.0

        hsv1 = np.array(skin1["hsv_mean"])
        hsv2 = np.array(skin2["hsv_mean"])

        # Similar calculation as hair
        h_dist = min(abs(hsv1[0] - hsv2[0]), 180 - abs(hsv1[0] - hsv2[0]))
        s_dist = abs(hsv1[1] - hsv2[1])
        v_dist = abs(hsv1[2] - hsv2[2])

        total_dist = (
            (h_dist / 180.0) * 0.3 + (s_dist / 255.0) * 0.3 + (v_dist / 255.0) * 0.4
        )

        return 1.0 - total_dist

    def _compare_clothing(self, clothing1: Dict, clothing2: Dict) -> float:
        """Compare clothing features."""
        if not clothing1["dominant_colors"] or not clothing2["dominant_colors"]:
            return -1.0

        # Count matching colors
        colors1 = set(clothing1["dominant_colors"])
        colors2 = set(clothing2["dominant_colors"])

        common = len(colors1.intersection(colors2))
        total = len(colors1.union(colors2))

        if total == 0:
            return 0.0

        return common / total
