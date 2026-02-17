"""
Multi-Modal Person Re-Identification System
Combines face and body features for robust person tracking across cameras.
"""

import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class MultiModalReID:
    """
    Multi-modal person re-identification combining:
    - Face features (from YOLOv8-face)
    - Body appearance features (from YOLOv11)
    - Temporal tracking information
    """

    def __init__(
        self,
        face_weight: float = 0.6,
        body_weight: float = 0.4,
        similarity_threshold: float = 0.50,
    ):
        """
        Initialize multi-modal re-identification system.

        Args:
            face_weight: Weight for face similarity (0-1)
            body_weight: Weight for body similarity (0-1)
            similarity_threshold: Minimum similarity for matching
        """
        self.face_weight = face_weight
        self.body_weight = body_weight
        self.similarity_threshold = similarity_threshold

        # Normalize weights
        total = face_weight + body_weight
        self.face_weight = face_weight / total
        self.body_weight = body_weight / total

        print(f"✅ Multi-modal Re-ID initialized:")
        print(f"   Face weight: {self.face_weight:.2f}")
        print(f"   Body weight: {self.body_weight:.2f}")
        print(f"   Similarity threshold: {similarity_threshold:.2f}")

    def create_person_profile(
        self,
        person_id: str,
        face_features: Optional[np.ndarray] = None,
        body_features: Optional[Dict[str, np.ndarray]] = None,
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
        body_bbox: Optional[Tuple[int, int, int, int]] = None,
        timestamp: Optional[float] = None,
    ) -> Dict:
        """
        Create a person profile with face and body features.

        Args:
            person_id: Unique person identifier
            face_features: Face feature vector
            body_features: Dictionary of body feature vectors
            face_bbox: Face bounding box (x, y, w, h)
            body_bbox: Body bounding box (x, y, w, h)
            timestamp: Registration timestamp

        Returns:
            Person profile dictionary
        """
        if timestamp is None:
            timestamp = time.time()

        profile = {
            "person_id": person_id,
            "face_features": face_features,
            "body_features": body_features,
            "face_bbox": face_bbox,
            "body_bbox": body_bbox,
            "registered_time": timestamp,
            "last_seen": timestamp,
            "has_face": face_features is not None,
            "has_body": body_features is not None,
        }

        return profile

    def compare_profiles(
        self,
        profile1: Dict,
        profile2: Dict,
        mode: str = "auto",
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compare two person profiles and compute similarity score.

        Args:
            profile1: First person profile
            profile2: Second person profile
            mode: Comparison mode - 'auto', 'face_only', 'body_only', 'both'

        Returns:
            Tuple of (combined_similarity, detailed_scores)
        """
        detailed_scores = {
            "face_similarity": 0.0,
            "body_similarity": 0.0,
            "combined_similarity": 0.0,
            "mode_used": mode,
        }

        # Auto mode: use what's available
        if mode == "auto":
            has_face_both = profile1["has_face"] and profile2["has_face"]
            has_body_both = profile1["has_body"] and profile2["has_body"]

            if has_face_both and has_body_both:
                mode = "both"
            elif has_face_both:
                mode = "face_only"
            elif has_body_both:
                mode = "body_only"
            else:
                # No valid features to compare
                return 0.0, detailed_scores

        detailed_scores["mode_used"] = mode

        # Face similarity
        if (
            mode in ["face_only", "both"]
            and profile1["has_face"]
            and profile2["has_face"]
        ):
            face_sim = self._compare_face_features(
                profile1["face_features"], profile2["face_features"]
            )
            detailed_scores["face_similarity"] = face_sim
        else:
            face_sim = 0.0

        # Body similarity
        if (
            mode in ["body_only", "both"]
            and profile1["has_body"]
            and profile2["has_body"]
        ):
            body_sim = self._compare_body_features(
                profile1["body_features"], profile2["body_features"]
            )
            detailed_scores["body_similarity"] = body_sim
        else:
            body_sim = 0.0

        # Combine similarities based on mode
        if mode == "face_only":
            combined_sim = face_sim
        elif mode == "body_only":
            combined_sim = body_sim
        elif mode == "both":
            # Weighted combination
            combined_sim = self.face_weight * face_sim + self.body_weight * body_sim
        else:
            combined_sim = 0.0

        detailed_scores["combined_similarity"] = combined_sim

        return combined_sim, detailed_scores

    def _compare_face_features(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """
        Compare face features using histogram correlation.

        Args:
            feat1: First face feature vector
            feat2: Second face feature vector

        Returns:
            Similarity score (0-1)
        """
        if feat1 is None or feat2 is None:
            return 0.0

        if len(feat1) == 0 or len(feat2) == 0:
            return 0.0

        # Histogram correlation
        similarity = cv2.compareHist(
            feat1.astype(np.float32),
            feat2.astype(np.float32),
            cv2.HISTCMP_CORREL,
        )

        # Normalize to 0-1 range
        similarity = (similarity + 1) / 2.0

        return float(similarity)

    def _compare_body_features(
        self, feat1: Dict[str, np.ndarray], feat2: Dict[str, np.ndarray]
    ) -> float:
        """
        Compare body features using weighted combination.

        Args:
            feat1: First body feature dictionary
            feat2: Second body feature dictionary

        Returns:
            Similarity score (0-1)
        """
        if feat1 is None or feat2 is None:
            return 0.0

        # Weights for different body features
        weights = {
            "upper_body_hist": 0.35,
            "lower_body_hist": 0.35,
            "full_body_hist": 0.20,
            "shape_features": 0.10,
        }

        total_similarity = 0.0

        # Compare upper body
        if "upper_body_hist" in feat1 and "upper_body_hist" in feat2:
            sim = cv2.compareHist(
                feat1["upper_body_hist"].astype(np.float32),
                feat2["upper_body_hist"].astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            sim = (sim + 1) / 2.0
            total_similarity += weights["upper_body_hist"] * sim

        # Compare lower body
        if "lower_body_hist" in feat1 and "lower_body_hist" in feat2:
            sim = cv2.compareHist(
                feat1["lower_body_hist"].astype(np.float32),
                feat2["lower_body_hist"].astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            sim = (sim + 1) / 2.0
            total_similarity += weights["lower_body_hist"] * sim

        # Compare full body
        if "full_body_hist" in feat1 and "full_body_hist" in feat2:
            sim = cv2.compareHist(
                feat1["full_body_hist"].astype(np.float32),
                feat2["full_body_hist"].astype(np.float32),
                cv2.HISTCMP_CORREL,
            )
            sim = (sim + 1) / 2.0
            total_similarity += weights["full_body_hist"] * sim

        # Compare shape features
        if "shape_features" in feat1 and "shape_features" in feat2:
            shape1 = feat1["shape_features"]
            shape2 = feat2["shape_features"]

            # Cosine similarity
            dot = np.dot(shape1, shape2)
            norm1 = np.linalg.norm(shape1)
            norm2 = np.linalg.norm(shape2)

            if norm1 > 0 and norm2 > 0:
                sim = dot / (norm1 * norm2)
                sim = (sim + 1) / 2.0
                total_similarity += weights["shape_features"] * sim

        return float(total_similarity)

    def match_person(
        self,
        query_profile: Dict,
        registered_profiles: Dict[str, Dict],
        mode: str = "auto",
        top_k: int = 1,
    ) -> List[Tuple[str, float, Dict[str, float]]]:
        """
        Match a query profile against registered profiles.

        Args:
            query_profile: Query person profile
            registered_profiles: Dictionary of registered person profiles
            mode: Comparison mode
            top_k: Return top K matches

        Returns:
            List of (person_id, similarity, detailed_scores) sorted by similarity
        """
        if not registered_profiles:
            return []

        matches = []

        for person_id, registered_profile in registered_profiles.items():
            similarity, details = self.compare_profiles(
                query_profile, registered_profile, mode=mode
            )

            matches.append((person_id, similarity, details))

        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[1], reverse=True)

        # Return top K matches
        return matches[:top_k]

    def is_match(
        self,
        query_profile: Dict,
        registered_profiles: Dict[str, Dict],
        mode: str = "auto",
    ) -> Tuple[Optional[str], float, Dict[str, float]]:
        """
        Check if query profile matches any registered profile.

        Args:
            query_profile: Query person profile
            registered_profiles: Dictionary of registered profiles
            mode: Comparison mode

        Returns:
            Tuple of (matched_person_id or None, best_similarity, detailed_scores)
        """
        matches = self.match_person(
            query_profile, registered_profiles, mode=mode, top_k=1
        )

        if not matches:
            return None, 0.0, {}

        best_match_id, best_similarity, details = matches[0]

        # Check against threshold
        if best_similarity >= self.similarity_threshold:
            return best_match_id, best_similarity, details
        else:
            return None, best_similarity, details

    def update_profile_features(
        self,
        profile: Dict,
        face_features: Optional[np.ndarray] = None,
        body_features: Optional[Dict[str, np.ndarray]] = None,
        update_strategy: str = "replace",
    ) -> Dict:
        """
        Update a person profile with new features.

        Args:
            profile: Person profile to update
            face_features: New face features
            body_features: New body features
            update_strategy: 'replace', 'average', or 'best'

        Returns:
            Updated profile
        """
        if update_strategy == "replace":
            # Simply replace with new features
            if face_features is not None:
                profile["face_features"] = face_features
                profile["has_face"] = True

            if body_features is not None:
                profile["body_features"] = body_features
                profile["has_body"] = True

        elif update_strategy == "average":
            # Average with existing features (for stability)
            if face_features is not None and profile["has_face"]:
                old_feat = profile["face_features"]
                profile["face_features"] = (old_feat + face_features) / 2.0
            elif face_features is not None:
                profile["face_features"] = face_features
                profile["has_face"] = True

            if body_features is not None and profile["has_body"]:
                old_body = profile["body_features"]
                new_body = {}
                for key in body_features.keys():
                    if key in old_body:
                        new_body[key] = (old_body[key] + body_features[key]) / 2.0
                    else:
                        new_body[key] = body_features[key]
                profile["body_features"] = new_body
            elif body_features is not None:
                profile["body_features"] = body_features
                profile["has_body"] = True

        profile["last_seen"] = time.time()

        return profile

    def get_feature_quality(self, profile: Dict) -> Dict[str, float]:
        """
        Assess quality of features in a profile.

        Args:
            profile: Person profile

        Returns:
            Dictionary of quality scores
        """
        quality = {
            "has_face": profile["has_face"],
            "has_body": profile["has_body"],
            "completeness": 0.0,
            "face_confidence": 0.0,
            "body_confidence": 0.0,
        }

        # Completeness: how much data we have
        if profile["has_face"] and profile["has_body"]:
            quality["completeness"] = 1.0
        elif profile["has_face"] or profile["has_body"]:
            quality["completeness"] = 0.5
        else:
            quality["completeness"] = 0.0

        # Face confidence (based on feature vector magnitude)
        if profile["has_face"]:
            face_feat = profile["face_features"]
            face_norm = np.linalg.norm(face_feat)
            # Normalize to 0-1 range (assume good features have norm > 1.0)
            quality["face_confidence"] = min(1.0, face_norm / 10.0)

        # Body confidence (based on histogram variance)
        if profile["has_body"]:
            body_feat = profile["body_features"]
            if "full_body_hist" in body_feat:
                variance = np.var(body_feat["full_body_hist"])
                # Higher variance = more distinctive features
                quality["body_confidence"] = min(1.0, variance * 100)

        return quality

    def print_comparison_details(
        self,
        person_id1: str,
        person_id2: str,
        similarity: float,
        details: Dict[str, float],
    ):
        """
        Print detailed comparison results (for debugging).

        Args:
            person_id1: First person ID
            person_id2: Second person ID
            similarity: Combined similarity score
            details: Detailed scores dictionary
        """
        print(f"\n{'=' * 60}")
        print(f"COMPARISON: {person_id1} vs {person_id2}")
        print(f"{'=' * 60}")
        print(f"Mode: {details.get('mode_used', 'unknown')}")
        print(f"Face Similarity:     {details.get('face_similarity', 0.0):.3f}")
        print(f"Body Similarity:     {details.get('body_similarity', 0.0):.3f}")
        print(f"Combined Similarity: {similarity:.3f}")
        print(f"Threshold:           {self.similarity_threshold:.3f}")
        print(
            f"Match: {'✅ YES' if similarity >= self.similarity_threshold else '❌ NO'}"
        )
        print(f"{'=' * 60}\n")
