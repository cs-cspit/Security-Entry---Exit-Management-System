"""
Enhanced Multi-Modal Person Re-Identification System
Combines OSNet embeddings, clothing analysis, face features, and skin tone
for robust person tracking across cameras.
"""

import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class EnhancedMultiModalReID:
    """
    Enhanced person re-identification combining:
    - OSNet body embeddings (learned features)
    - Clothing color, pattern, and style analysis
    - Skin tone features
    - Face features (from existing detectors)
    - Temporal consistency
    """

    def __init__(
        self,
        osnet_weight: float = 0.35,
        clothing_weight: float = 0.25,
        face_weight: float = 0.30,
        skin_weight: float = 0.10,
        similarity_threshold: float = 0.70,
        confidence_gap: float = 0.15,
        body_only_threshold: float = 0.65,
        use_osnet: bool = True,
    ):
        """
        Initialize enhanced multi-modal re-identification system.

        Args:
            osnet_weight: Weight for OSNet body embeddings (0-1)
            clothing_weight: Weight for clothing features (0-1)
            face_weight: Weight for face similarity (0-1)
            skin_weight: Weight for skin tone (0-1)
            similarity_threshold: Minimum similarity for matching (with all features)
            confidence_gap: Minimum gap between best and 2nd best match
            body_only_threshold: Threshold for body-only matching (room camera)
            use_osnet: Whether to use OSNet (if False, uses only clothing features)
        """
        self.osnet_weight = osnet_weight
        self.clothing_weight = clothing_weight
        self.face_weight = face_weight
        self.skin_weight = skin_weight
        self.similarity_threshold = similarity_threshold
        self.confidence_gap = confidence_gap
        self.body_only_threshold = body_only_threshold
        self.use_osnet = use_osnet

        # Normalize weights
        total = osnet_weight + clothing_weight + face_weight + skin_weight
        self.osnet_weight = osnet_weight / total
        self.clothing_weight = clothing_weight / total
        self.face_weight = face_weight / total
        self.skin_weight = skin_weight / total

        # Initialize feature extractors
        self._init_extractors()

        # Registered people database
        self.people = {}  # person_id -> features dict
        self.person_metadata = {}  # person_id -> metadata (name, timestamp, etc.)

        print(f"✅ Enhanced Multi-modal Re-ID initialized:")
        print(f"   OSNet weight: {self.osnet_weight:.2f}")
        print(f"   Clothing weight: {self.clothing_weight:.2f}")
        print(f"   Face weight: {self.face_weight:.2f}")
        print(f"   Skin weight: {self.skin_weight:.2f}")
        print(f"   Similarity threshold: {self.similarity_threshold:.2f}")
        print(f"   Confidence gap: {self.confidence_gap:.2f}")
        print(f"   Body-only threshold: {self.body_only_threshold:.2f}")

    def _init_extractors(self):
        """Initialize feature extractors."""
        # Import here to avoid circular dependencies
        try:
            from features.clothing_analyzer import ClothingAnalyzer
            from features.osnet_extractor import create_osnet_extractor

            # Initialize OSNet
            if self.use_osnet:
                print("🔧 Initializing OSNet extractor...")
                self.osnet_extractor = create_osnet_extractor(
                    model_name="osnet_x1_0", pretrained=True, device="auto"
                )
            else:
                print("⚠️ OSNet disabled, using clothing features only")
                self.osnet_extractor = None

            # Initialize clothing analyzer
            print("🔧 Initializing Clothing Analyzer...")
            self.clothing_analyzer = ClothingAnalyzer()

            print("✅ Feature extractors initialized")

        except Exception as e:
            print(f"⚠️ Failed to initialize extractors: {e}")
            print("⚠️ Falling back to basic features...")
            self.osnet_extractor = None
            self.clothing_analyzer = None

    def register_person(
        self,
        person_id: str,
        image: np.ndarray,
        face_features: Optional[np.ndarray] = None,
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
        body_bbox: Optional[Tuple[int, int, int, int]] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Register a new person with enhanced features.

        Args:
            person_id: Unique identifier for the person
            image: Full BGR image
            face_features: Pre-extracted face features (256-dim histogram or embedding)
            face_bbox: Face bounding box (x, y, w, h)
            body_bbox: Body bounding box (x, y, w, h)
            metadata: Additional metadata (name, timestamp, etc.)

        Returns:
            True if registration successful
        """
        print(f"\n🔧 Registering person: {person_id}")

        features = {}

        # Extract OSNet features
        if self.osnet_extractor is not None and body_bbox is not None:
            try:
                features["osnet"] = self.osnet_extractor.extract_features(
                    image, body_bbox
                )
                print(f"   ✅ OSNet features extracted: {features['osnet'].shape}")
            except Exception as e:
                print(f"   ⚠️ OSNet extraction failed: {e}")
                features["osnet"] = None
        else:
            features["osnet"] = None

        # Extract clothing features
        if self.clothing_analyzer is not None:
            try:
                features["clothing"] = self.clothing_analyzer.extract_features(
                    image, body_bbox, face_bbox
                )
                print(
                    f"   ✅ Clothing features: Upper={features['clothing']['upper_color_names']}, "
                    f"Lower={features['clothing']['lower_color_names']}"
                )
                if features["clothing"]["skin_tone"]:
                    print(
                        f"   ✅ Skin tone: {features['clothing']['skin_tone']['tone']}"
                    )
            except Exception as e:
                print(f"   ⚠️ Clothing extraction failed: {e}")
                features["clothing"] = None
        else:
            features["clothing"] = None

        # Store face features
        features["face"] = face_features

        # Store bounding boxes for reference
        features["face_bbox"] = face_bbox
        features["body_bbox"] = body_bbox

        # Store registration image (small thumbnail)
        if body_bbox is not None:
            x, y, w, h = body_bbox
            thumbnail = image[y : y + h, x : x + w]
            thumbnail = cv2.resize(thumbnail, (64, 128))
            features["thumbnail"] = thumbnail
        else:
            features["thumbnail"] = None

        # Save to database
        self.people[person_id] = features
        self.person_metadata[person_id] = metadata or {
            "registered_at": time.time(),
            "name": person_id,
        }

        print(f"✅ Person {person_id} registered successfully\n")
        return True

    def match_person(
        self,
        image: np.ndarray,
        face_features: Optional[np.ndarray] = None,
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
        body_bbox: Optional[Tuple[int, int, int, int]] = None,
        mode: str = "auto",
    ) -> Tuple[Optional[str], float, Dict]:
        """
        Match a person against registered database.

        Args:
            image: Full BGR image
            face_features: Query face features
            face_bbox: Query face bounding box
            body_bbox: Query body bounding box
            mode: Matching mode ('auto', 'face_primary', 'body_primary', 'body_only')

        Returns:
            Tuple of (person_id, similarity, debug_info)
            person_id is None if no match found
        """
        if len(self.people) == 0:
            return None, 0.0, {"reason": "no_registered_people"}

        # Extract query features
        query_features = self._extract_query_features(
            image, face_features, face_bbox, body_bbox
        )

        # Determine matching mode
        has_face = query_features["face"] is not None
        has_body = (
            query_features["osnet"] is not None
            or query_features["clothing"] is not None
        )

        if mode == "auto":
            if has_face and has_body:
                mode = "face_primary"
            elif has_body:
                mode = "body_primary"
            elif has_face:
                mode = "face_only"
            else:
                return None, 0.0, {"reason": "no_features"}

        # Compute similarities against all registered people
        similarities = {}
        detailed_scores = {}

        for person_id, person_features in self.people.items():
            sim, details = self._compute_similarity(
                query_features, person_features, mode
            )
            similarities[person_id] = sim
            detailed_scores[person_id] = details

        # Sort by similarity
        sorted_matches = sorted(similarities.items(), key=lambda x: x[1], reverse=True)

        if len(sorted_matches) == 0:
            return None, 0.0, {"reason": "no_candidates"}

        best_id, best_sim = sorted_matches[0]
        second_sim = sorted_matches[1][1] if len(sorted_matches) > 1 else 0.0

        # Apply thresholds
        threshold = (
            self.body_only_threshold
            if mode == "body_only"
            else self.similarity_threshold
        )

        debug_info = {
            "mode": mode,
            "best_match": best_id,
            "best_similarity": best_sim,
            "second_similarity": second_sim,
            "confidence_gap": best_sim - second_sim,
            "threshold": threshold,
            "all_scores": detailed_scores,
        }

        # Check threshold
        if best_sim < threshold:
            return None, best_sim, {**debug_info, "reason": "below_threshold"}

        # Check confidence gap
        if best_sim - second_sim < self.confidence_gap:
            return None, best_sim, {**debug_info, "reason": "ambiguous_match"}

        # Match found!
        return best_id, best_sim, {**debug_info, "reason": "match"}

    def _extract_query_features(
        self,
        image: np.ndarray,
        face_features: Optional[np.ndarray],
        face_bbox: Optional[Tuple[int, int, int, int]],
        body_bbox: Optional[Tuple[int, int, int, int]],
    ) -> Dict:
        """Extract all features from query image."""
        features = {}

        # OSNet features
        if self.osnet_extractor is not None and body_bbox is not None:
            try:
                features["osnet"] = self.osnet_extractor.extract_features(
                    image, body_bbox
                )
            except Exception as e:
                features["osnet"] = None
        else:
            features["osnet"] = None

        # Clothing features
        if self.clothing_analyzer is not None and body_bbox is not None:
            try:
                features["clothing"] = self.clothing_analyzer.extract_features(
                    image, body_bbox, face_bbox
                )
            except Exception as e:
                features["clothing"] = None
        else:
            features["clothing"] = None

        # Face features
        features["face"] = face_features

        return features

    def _compute_similarity(
        self, query: Dict, reference: Dict, mode: str
    ) -> Tuple[float, Dict]:
        """
        Compute similarity between query and reference features.

        Returns:
            Tuple of (overall_similarity, detailed_scores)
        """
        scores = {}
        weights = {}

        # OSNet similarity
        if query["osnet"] is not None and reference["osnet"] is not None:
            scores["osnet"] = self.osnet_extractor.compute_similarity(
                query["osnet"], reference["osnet"]
            )
            weights["osnet"] = self.osnet_weight
        else:
            scores["osnet"] = None
            weights["osnet"] = 0.0

        # Clothing similarity
        if query["clothing"] is not None and reference["clothing"] is not None:
            clothing_sim = self.clothing_analyzer.compare_features(
                query["clothing"], reference["clothing"]
            )
            scores["clothing"] = clothing_sim["overall"]
            scores["clothing_details"] = clothing_sim
            weights["clothing"] = self.clothing_weight
        else:
            scores["clothing"] = None
            weights["clothing"] = 0.0

        # Face similarity
        if query["face"] is not None and reference["face"] is not None:
            scores["face"] = self._cosine_similarity(query["face"], reference["face"])
            weights["face"] = self.face_weight
        else:
            scores["face"] = None
            weights["face"] = 0.0

        # Skin tone similarity (included in clothing)
        if (
            query["clothing"] is not None
            and reference["clothing"] is not None
            and query["clothing"].get("skin_tone") is not None
            and reference["clothing"].get("skin_tone") is not None
        ):
            # Already included in clothing overall score
            pass

        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0, scores

        weights = {k: v / total_weight for k, v in weights.items()}

        # Compute weighted average
        overall = 0.0
        for key in ["osnet", "clothing", "face"]:
            if scores[key] is not None:
                overall += scores[key] * weights[key]

        return overall, scores

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

    def remove_person(self, person_id: str) -> bool:
        """Remove a person from the database."""
        if person_id in self.people:
            del self.people[person_id]
            del self.person_metadata[person_id]
            print(f"✅ Person {person_id} removed from database")
            return True
        return False

    def get_registered_people(self) -> List[str]:
        """Get list of registered person IDs."""
        return list(self.people.keys())

    def get_person_info(self, person_id: str) -> Optional[Dict]:
        """Get information about a registered person."""
        if person_id not in self.people:
            return None

        return {
            "person_id": person_id,
            "features": self.people[person_id],
            "metadata": self.person_metadata[person_id],
            "thumbnail": self.people[person_id].get("thumbnail"),
        }

    def visualize_features(
        self, person_id: str, save_path: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """
        Create a visualization of a person's features.

        Returns:
            Visualization image or None
        """
        if person_id not in self.people:
            return None

        features = self.people[person_id]
        metadata = self.person_metadata[person_id]

        # Create visualization canvas
        vis = np.ones((400, 600, 3), dtype=np.uint8) * 255

        # Draw thumbnail
        if features["thumbnail"] is not None:
            thumb = features["thumbnail"]
            h, w = thumb.shape[:2]
            vis[10 : 10 + h, 10 : 10 + w] = thumb

        # Draw text info
        y_offset = 150
        texts = [
            f"ID: {person_id}",
            f"Registered: {time.ctime(metadata.get('registered_at', 0))}",
        ]

        if features["clothing"] is not None:
            texts.append(
                f"Upper: {', '.join(features['clothing']['upper_color_names'][:2])}"
            )
            texts.append(
                f"Lower: {', '.join(features['clothing']['lower_color_names'][:2])}"
            )
            texts.append(
                f"Upper Pattern: {features['clothing']['upper_pattern']['type']}"
            )
            texts.append(
                f"Lower Pattern: {features['clothing']['lower_pattern']['type']}"
            )

            if features["clothing"].get("skin_tone"):
                texts.append(f"Skin Tone: {features['clothing']['skin_tone']['tone']}")

        for i, text in enumerate(texts):
            cv2.putText(
                vis,
                text,
                (100, y_offset + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
            )

        if save_path:
            cv2.imwrite(save_path, vis)

        return vis


def demo_enhanced_reid():
    """Demo function to test enhanced re-ID system."""
    print("=" * 80)
    print("TESTING ENHANCED MULTI-MODAL RE-ID")
    print("=" * 80)
    print()

    # Create system
    reid = EnhancedMultiModalReID(
        osnet_weight=0.35,
        clothing_weight=0.25,
        face_weight=0.30,
        skin_weight=0.10,
        similarity_threshold=0.70,
        confidence_gap=0.15,
    )

    print("\n✅ Enhanced Re-ID system initialized!")
    print(f"✅ Registered people: {len(reid.get_registered_people())}")


if __name__ == "__main__":
    demo_enhanced_reid()
