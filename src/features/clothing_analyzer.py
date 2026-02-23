"""
Advanced Clothing and Skin Tone Feature Analyzer
Extracts rich features from person appearance for robust re-identification
"""

import colorsys
from collections import Counter
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class ClothingAnalyzer:
    """
    Advanced clothing and appearance analyzer for person re-identification.

    Extracts:
    - Dominant clothing colors (upper/lower body)
    - Clothing patterns (solid, striped, checkered, etc.)
    - Clothing style features
    - Skin tone from face/hands
    - Color distribution histograms
    """

    # Color ranges for pattern detection (HSV)
    COLOR_RANGES = {
        "red": [(0, 50, 50), (10, 255, 255), (170, 50, 50), (180, 255, 255)],
        "orange": [(10, 50, 50), (25, 255, 255)],
        "yellow": [(25, 50, 50), (35, 255, 255)],
        "green": [(35, 50, 50), (85, 255, 255)],
        "cyan": [(85, 50, 50), (95, 255, 255)],
        "blue": [(95, 50, 50), (125, 255, 255)],
        "purple": [(125, 50, 50), (145, 255, 255)],
        "pink": [(145, 50, 50), (170, 255, 255)],
        "white": [(0, 0, 200), (180, 30, 255)],
        "gray": [(0, 0, 50), (180, 30, 200)],
        "black": [(0, 0, 0), (180, 255, 50)],
    }

    def __init__(self):
        """Initialize clothing analyzer."""
        self.debug = False

    def extract_features(
        self,
        image: np.ndarray,
        body_bbox: Optional[Tuple[int, int, int, int]] = None,
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict:
        """
        Extract comprehensive clothing and appearance features.

        Args:
            image: Full image (BGR)
            body_bbox: Body bounding box (x, y, w, h)
            face_bbox: Face bounding box (x, y, w, h) for skin tone

        Returns:
            Dictionary of features
        """
        features = {}

        if body_bbox is None:
            # Use full image if no body bbox
            body_bbox = (0, 0, image.shape[1], image.shape[0])

        x, y, w, h = body_bbox
        body_img = image[y : y + h, x : x + w]

        if body_img.size == 0:
            return self._empty_features()

        # Split body into upper and lower regions
        split_point = int(h * 0.6)  # Upper 60%, lower 40%
        upper_body = body_img[:split_point, :]
        lower_body = body_img[split_point:, :]

        # Extract color features
        features["upper_colors"] = self._extract_dominant_colors(upper_body, n_colors=3)
        features["lower_colors"] = self._extract_dominant_colors(lower_body, n_colors=3)

        # Extract color names
        features["upper_color_names"] = self._colors_to_names(features["upper_colors"])
        features["lower_color_names"] = self._colors_to_names(features["lower_colors"])

        # Extract pattern features
        features["upper_pattern"] = self._detect_pattern(upper_body)
        features["lower_pattern"] = self._detect_pattern(lower_body)

        # Extract brightness/contrast features
        features["upper_brightness"] = self._get_brightness(upper_body)
        features["lower_brightness"] = self._get_brightness(lower_body)

        # Extract texture features
        features["upper_texture"] = self._get_texture_features(upper_body)
        features["lower_texture"] = self._get_texture_features(lower_body)

        # Extract color distribution (enhanced histograms)
        features["upper_color_dist"] = self._get_color_distribution(upper_body)
        features["lower_color_dist"] = self._get_color_distribution(lower_body)

        # Extract skin tone if face is available
        if face_bbox is not None:
            fx, fy, fw, fh = face_bbox
            face_img = image[fy : fy + fh, fx : fx + fw]
            if face_img.size > 0:
                features["skin_tone"] = self._extract_skin_tone(face_img)
            else:
                features["skin_tone"] = None
        else:
            features["skin_tone"] = None

        # Compute overall appearance signature
        features["appearance_signature"] = self._compute_signature(features)

        return features

    def _extract_dominant_colors(
        self, image: np.ndarray, n_colors: int = 3
    ) -> List[Tuple[int, int, int]]:
        """
        Extract dominant colors using k-means clustering.

        Args:
            image: BGR image
            n_colors: Number of dominant colors to extract

        Returns:
            List of (B, G, R) color tuples
        """
        # Reshape to list of pixels
        pixels = image.reshape(-1, 3).astype(np.float32)

        # Remove very dark pixels (likely shadows)
        brightness = np.mean(pixels, axis=1)
        pixels = pixels[brightness > 30]

        if len(pixels) < 10:
            return [(128, 128, 128)] * n_colors

        # K-means clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, n_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )

        # Count pixels per cluster
        counts = Counter(labels.flatten())

        # Sort by frequency
        sorted_centers = [centers[i] for i, _ in counts.most_common()]

        # Convert to int tuples
        colors = [tuple(map(int, color)) for color in sorted_centers]

        return colors

    def _colors_to_names(self, colors: List[Tuple[int, int, int]]) -> List[str]:
        """Convert BGR colors to human-readable color names."""
        names = []
        for bgr in colors:
            # Convert BGR to HSV
            bgr_pixel = np.uint8([[bgr]])
            hsv = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2HSV)[0][0]

            name = self._get_color_name(hsv)
            names.append(name)

        return names

    def _get_color_name(self, hsv: Tuple[int, int, int]) -> str:
        """Get color name from HSV value."""
        h, s, v = hsv

        # Check achromatic colors first
        if v < 50:
            return "black"
        elif s < 30:
            if v > 200:
                return "white"
            else:
                return "gray"

        # Check chromatic colors
        for color_name, ranges in self.COLOR_RANGES.items():
            if color_name in ["white", "gray", "black"]:
                continue

            if len(ranges) == 2:  # Single range
                lower, upper = ranges
                if (
                    lower[0] <= h <= upper[0]
                    and lower[1] <= s <= upper[1]
                    and lower[2] <= v <= upper[2]
                ):
                    return color_name
            elif len(ranges) == 4:  # Red wraps around
                lower1, upper1, lower2, upper2 = ranges
                if (
                    (lower1[0] <= h <= upper1[0] or lower2[0] <= h <= upper2[0])
                    and lower1[1] <= s <= upper1[1]
                    and lower1[2] <= v <= upper1[2]
                ):
                    return color_name

        return "unknown"

    def _detect_pattern(self, image: np.ndarray) -> Dict:
        """
        Detect clothing pattern (solid, striped, checkered, etc.).

        Returns:
            Dictionary with pattern type and confidence
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Compute edge density
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size

        # Compute variance (texture complexity)
        variance = np.var(gray)

        # Compute FFT for frequency analysis
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)

        # Get power in different frequency bands
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2

        # Low frequency (0-10% from center)
        low_freq_region = magnitude[
            center_h - h // 20 : center_h + h // 20,
            center_w - w // 20 : center_w + w // 20,
        ]
        low_freq_power = np.mean(low_freq_region)

        # Medium frequency (10-30% from center)
        mask = np.zeros_like(magnitude)
        cv2.circle(mask, (center_w, center_h), w // 3, 1, -1)
        cv2.circle(mask, (center_w, center_h), w // 10, 0, -1)
        med_freq_power = np.mean(magnitude * mask)

        # Classify pattern
        if edge_density < 0.05 and variance < 500:
            pattern_type = "solid"
            confidence = 0.9
        elif edge_density > 0.15 and med_freq_power > low_freq_power * 0.3:
            # Check for directionality (stripes vs checkered)
            sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            ratio = np.abs(np.mean(sobel_x)) / (np.abs(np.mean(sobel_y)) + 1e-6)

            if ratio > 1.5 or ratio < 0.67:
                pattern_type = "striped"
                confidence = 0.7
            else:
                pattern_type = "checkered"
                confidence = 0.6
        elif variance > 1000:
            pattern_type = "textured"
            confidence = 0.6
        else:
            pattern_type = "mixed"
            confidence = 0.5

        return {
            "type": pattern_type,
            "confidence": confidence,
            "edge_density": edge_density,
            "variance": variance,
        }

    def _get_brightness(self, image: np.ndarray) -> float:
        """Get average brightness of image."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def _get_texture_features(self, image: np.ndarray) -> np.ndarray:
        """
        Extract texture features using Local Binary Patterns (LBP).

        Returns:
            64-dimensional texture histogram
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Simple LBP implementation
        h, w = gray.shape
        lbp = np.zeros_like(gray)

        for i in range(1, h - 1):
            for j in range(1, w - 1):
                center = gray[i, j]
                code = 0
                code |= (gray[i - 1, j - 1] >= center) << 7
                code |= (gray[i - 1, j] >= center) << 6
                code |= (gray[i - 1, j + 1] >= center) << 5
                code |= (gray[i, j + 1] >= center) << 4
                code |= (gray[i + 1, j + 1] >= center) << 3
                code |= (gray[i + 1, j] >= center) << 2
                code |= (gray[i + 1, j - 1] >= center) << 1
                code |= (gray[i, j - 1] >= center) << 0
                lbp[i, j] = code

        # Compute histogram (256 bins -> reduce to 64)
        hist, _ = np.histogram(lbp.ravel(), bins=64, range=(0, 256))
        hist = hist.astype(np.float32)
        hist = hist / (np.sum(hist) + 1e-6)

        return hist

    def _get_color_distribution(self, image: np.ndarray) -> np.ndarray:
        """
        Get color distribution in HSV space.

        Returns:
            Concatenated H, S, V histograms (96-dimensional)
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Compute histograms for each channel
        hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [32], [0, 256])
        hist_v = cv2.calcHist([hsv], [2], None, [32], [0, 256])

        # Normalize
        hist_h = hist_h.flatten() / (np.sum(hist_h) + 1e-6)
        hist_s = hist_s.flatten() / (np.sum(hist_s) + 1e-6)
        hist_v = hist_v.flatten() / (np.sum(hist_v) + 1e-6)

        # Concatenate
        color_dist = np.concatenate([hist_h, hist_s, hist_v])

        return color_dist

    def _extract_skin_tone(self, face_image: np.ndarray) -> Dict:
        """
        Extract skin tone from face region.

        Returns:
            Dictionary with skin tone features
        """
        # Convert to different color spaces
        hsv = cv2.cvtColor(face_image, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(face_image, cv2.COLOR_BGR2YCrCb)

        # Define skin color range in YCrCb (more robust)
        lower_skin = np.array([0, 133, 77], dtype=np.uint8)
        upper_skin = np.array([255, 173, 127], dtype=np.uint8)

        # Create skin mask
        skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)

        # Apply mask to get skin pixels
        skin_pixels = face_image[skin_mask > 0]

        if len(skin_pixels) < 10:
            # Fallback: use center region of face
            h, w = face_image.shape[:2]
            center_region = face_image[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3]
            skin_pixels = center_region.reshape(-1, 3)

        # Compute average skin color
        avg_skin_bgr = np.mean(skin_pixels, axis=0)

        # Convert to HSV for hue-based skin tone
        avg_skin_hsv = cv2.cvtColor(np.uint8([[avg_skin_bgr]]), cv2.COLOR_BGR2HSV)[0][0]

        # Classify skin tone
        hue = avg_skin_hsv[0]
        saturation = avg_skin_hsv[1]
        value = avg_skin_hsv[2]

        # Simple skin tone classification
        if value < 100:
            tone = "dark"
        elif value > 180:
            tone = "light"
        else:
            tone = "medium"

        return {
            "bgr": tuple(map(int, avg_skin_bgr)),
            "hsv": tuple(map(int, avg_skin_hsv)),
            "tone": tone,
            "hue": int(hue),
            "saturation": int(saturation),
            "value": int(value),
        }

    def _compute_signature(self, features: Dict) -> np.ndarray:
        """
        Compute overall appearance signature vector.

        Combines all features into a single descriptor.

        Returns:
            256-dimensional signature vector
        """
        signature_parts = []

        # Add color distributions (96 + 96 = 192 dims)
        signature_parts.append(features["upper_color_dist"])
        signature_parts.append(features["lower_color_dist"])

        # Add brightness features (2 dims)
        signature_parts.append(
            np.array(
                [
                    features["upper_brightness"] / 255.0,
                    features["lower_brightness"] / 255.0,
                ]
            )
        )

        # Add pattern features (4 dims)
        pattern_encoding = {
            "solid": 0,
            "striped": 1,
            "checkered": 2,
            "textured": 3,
            "mixed": 4,
        }
        upper_pattern = pattern_encoding.get(features["upper_pattern"]["type"], 4)
        lower_pattern = pattern_encoding.get(features["lower_pattern"]["type"], 4)

        signature_parts.append(
            np.array(
                [
                    upper_pattern / 4.0,
                    features["upper_pattern"]["confidence"],
                    lower_pattern / 4.0,
                    features["lower_pattern"]["confidence"],
                ]
            )
        )

        # Add skin tone if available (3 dims)
        if features["skin_tone"] is not None:
            signature_parts.append(
                np.array(
                    [
                        features["skin_tone"]["hue"] / 180.0,
                        features["skin_tone"]["saturation"] / 255.0,
                        features["skin_tone"]["value"] / 255.0,
                    ]
                )
            )
        else:
            signature_parts.append(np.zeros(3))

        # Concatenate all parts
        signature = np.concatenate(signature_parts)

        # Pad or truncate to 256 dimensions
        if len(signature) < 256:
            signature = np.pad(signature, (0, 256 - len(signature)))
        else:
            signature = signature[:256]

        # Normalize to unit vector
        norm = np.linalg.norm(signature)
        if norm > 0:
            signature = signature / norm

        return signature

    def _empty_features(self) -> Dict:
        """Return empty feature dictionary."""
        return {
            "upper_colors": [(128, 128, 128)],
            "lower_colors": [(128, 128, 128)],
            "upper_color_names": ["gray"],
            "lower_color_names": ["gray"],
            "upper_pattern": {
                "type": "unknown",
                "confidence": 0.0,
                "edge_density": 0.0,
                "variance": 0.0,
            },
            "lower_pattern": {
                "type": "unknown",
                "confidence": 0.0,
                "edge_density": 0.0,
                "variance": 0.0,
            },
            "upper_brightness": 128.0,
            "lower_brightness": 128.0,
            "upper_texture": np.zeros(64),
            "lower_texture": np.zeros(64),
            "upper_color_dist": np.zeros(96),
            "lower_color_dist": np.zeros(96),
            "skin_tone": None,
            "appearance_signature": np.zeros(256),
        }

    def compare_features(self, features1: Dict, features2: Dict) -> Dict[str, float]:
        """
        Compare two feature dictionaries.

        Returns:
            Dictionary of similarity scores (0-1) for each feature type
        """
        similarities = {}

        # Compare color distributions
        similarities["upper_color"] = self._cosine_similarity(
            features1["upper_color_dist"], features2["upper_color_dist"]
        )
        similarities["lower_color"] = self._cosine_similarity(
            features1["lower_color_dist"], features2["lower_color_dist"]
        )

        # Compare color names (exact match bonus)
        upper_match = (
            len(
                set(features1["upper_color_names"])
                & set(features2["upper_color_names"])
            )
            / 3.0
        )
        lower_match = (
            len(
                set(features1["lower_color_names"])
                & set(features2["lower_color_names"])
            )
            / 3.0
        )

        similarities["color_names"] = (upper_match + lower_match) / 2.0

        # Compare patterns
        pattern_match = 0.0
        if features1["upper_pattern"]["type"] == features2["upper_pattern"]["type"]:
            pattern_match += 0.5
        if features1["lower_pattern"]["type"] == features2["lower_pattern"]["type"]:
            pattern_match += 0.5
        similarities["pattern"] = pattern_match

        # Compare brightness
        brightness_diff = abs(
            features1["upper_brightness"] - features2["upper_brightness"]
        )
        brightness_diff += abs(
            features1["lower_brightness"] - features2["lower_brightness"]
        )
        similarities["brightness"] = max(0, 1.0 - brightness_diff / 255.0)

        # Compare skin tone
        if features1["skin_tone"] is not None and features2["skin_tone"] is not None:
            skin_diff = abs(
                features1["skin_tone"]["hue"] - features2["skin_tone"]["hue"]
            )
            skin_diff += abs(
                features1["skin_tone"]["saturation"]
                - features2["skin_tone"]["saturation"]
            )
            skin_diff += abs(
                features1["skin_tone"]["value"] - features2["skin_tone"]["value"]
            )
            similarities["skin_tone"] = max(0, 1.0 - skin_diff / 600.0)
        else:
            similarities["skin_tone"] = 0.5  # Neutral if not available

        # Compare overall signatures
        similarities["signature"] = self._cosine_similarity(
            features1["appearance_signature"], features2["appearance_signature"]
        )

        # Compute weighted average
        weights = {
            "upper_color": 0.20,
            "lower_color": 0.20,
            "color_names": 0.15,
            "pattern": 0.10,
            "brightness": 0.05,
            "skin_tone": 0.10,
            "signature": 0.20,
        }

        similarities["overall"] = sum(
            similarities[k] * weights[k] for k in weights.keys()
        )

        return similarities

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(np.clip(similarity, 0, 1))


def demo_clothing_analyzer():
    """Demo function to test clothing analyzer."""
    print("🔧 Testing Clothing Analyzer...")

    analyzer = ClothingAnalyzer()

    # Create test image
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Upper body: red shirt
    test_img[100:300, 200:440] = [0, 0, 255]
    # Lower body: blue jeans
    test_img[300:450, 200:440] = [255, 0, 0]

    # Extract features
    body_bbox = (200, 100, 240, 350)
    features = analyzer.extract_features(test_img, body_bbox)

    print(f"✅ Upper colors: {features['upper_color_names']}")
    print(f"✅ Lower colors: {features['lower_color_names']}")
    print(f"✅ Upper pattern: {features['upper_pattern']['type']}")
    print(f"✅ Lower pattern: {features['lower_pattern']['type']}")
    print(f"✅ Signature shape: {features['appearance_signature'].shape}")


if __name__ == "__main__":
    demo_clothing_analyzer()
