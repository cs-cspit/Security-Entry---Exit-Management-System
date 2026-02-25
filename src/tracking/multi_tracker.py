#!/usr/bin/env python3
"""
Multi-Person Tracker (Phase 6)
================================
Uses YOLO26's built-in ByteTrack tracker (via ultralytics model.track())
to assign persistent, stable track IDs across frames — no external tracking
library (norfair / boxmot / filterpy) needed.

Key features:
  - Stable track IDs via ByteTrack (built into ultralytics)
  - Per-track OSNet embedding aggregation (temporal mean pooling)
  - Track → Person ID mapping and re-association after occlusion
  - Track lifecycle management (birth / active / lost / dead)
  - Pose keypoints forwarded from YOLO26-pose results
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TrackedPerson:
    """
    Represents a single person detection enriched with a stable ByteTrack ID.
    Drop-in replacement for the plain detection dict produced by
    YOLO26BodyDetector.detect() but includes `track_id`.
    """

    track_id: int
    body_bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    keypoints: Optional[np.ndarray] = None  # (17, 3)  [x, y, conf]
    face_bbox: Optional[Tuple[int, int, int, int]] = None
    has_face: bool = False

    # Re-ID bridge fields — filled in by the main system
    person_id: Optional[str] = None  # registered person ID if matched
    similarity: float = 0.0
    is_authorized: bool = False

    def to_detection_dict(self) -> dict:
        """
        Convert to the legacy detection-dict format so existing code
        (register_person, match_person, draw routines) can consume it
        without modification.
        """
        return {
            "track_id": self.track_id,
            "body_bbox": self.body_bbox,
            "confidence": self.confidence,
            "keypoints": self.keypoints,
            "face_bbox": self.face_bbox,
            "has_face": self.has_face,
        }


@dataclass
class TrackState:
    """Internal lifecycle state for one ByteTrack ID."""

    track_id: int
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    frame_count: int = 0
    is_lost: bool = False
    lost_time: Optional[float] = None

    # Person association
    person_id: Optional[str] = None

    # Aggregated OSNet embeddings (ring buffer, max 15 frames)
    osnet_embeddings: List[np.ndarray] = field(default_factory=list)
    MAX_EMBEDDINGS: int = 15

    def add_embedding(self, emb: np.ndarray):
        self.osnet_embeddings.append(emb)
        if len(self.osnet_embeddings) > self.MAX_EMBEDDINGS:
            self.osnet_embeddings.pop(0)

    def get_mean_embedding(self) -> Optional[np.ndarray]:
        if not self.osnet_embeddings:
            return None
        return np.mean(self.osnet_embeddings, axis=0)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class MultiPersonTracker:
    """
    Multi-person tracker backed by YOLO26's native ByteTrack integration.

    Usage
    -----
    >>> tracker = MultiPersonTracker(detector)
    >>> tracked = tracker.update(frame)          # List[TrackedPerson]
    >>> for tp in tracked:
    ...     print(tp.track_id, tp.body_bbox)
    >>> tracker.associate(track_id=3, person_id="P001")
    >>> tracker.add_embedding(track_id=3, embedding=osnet_vec)
    >>> mean_emb = tracker.get_aggregated_embedding(track_id=3)

    Parameters
    ----------
    detector:
        An instance of YOLO26BodyDetector.  The tracker calls
        ``detector.model.track()`` directly to leverage the built-in
        ByteTrack runner (persist=True keeps the byte-track state across
        calls).
    tracker_type:
        "bytetrack" (default) or "botsort".  Both are bundled with
        ultralytics ≥ 8.1; YOLO26 ships with the same package.
    lost_track_timeout:
        Seconds to remember a lost track for potential re-association.
    max_feature_age:
        Maximum frames to keep in the per-track embedding buffer.
    """

    TRACKER_CONFIGS = {
        "bytetrack": "bytetrack.yaml",
        "botsort": "botsort.yaml",
    }

    def __init__(
        self,
        detector,
        tracker_type: str = "bytetrack",
        lost_track_timeout: float = 30.0,
        max_feature_age: int = 15,
    ):
        self.detector = detector
        self.tracker_cfg = self.TRACKER_CONFIGS.get(tracker_type, "bytetrack.yaml")
        self.lost_track_timeout = lost_track_timeout
        self.max_feature_age = max_feature_age

        # Track registry
        self._tracks: Dict[int, TrackState] = {}  # track_id → TrackState

        # Active / lost sets (track IDs)
        self._active_ids: set = set()
        self._lost_ids: set = set()

        # Reverse map for quick lookup
        self._person_to_track: Dict[str, int] = {}  # person_id → track_id

    # ------------------------------------------------------------------
    # Core update
    # ------------------------------------------------------------------

    def update(self, frame: np.ndarray) -> List[TrackedPerson]:
        """
        Run YOLO26 + ByteTrack on *frame* and return a list of
        TrackedPerson objects, one per detected person.

        The tracker maintains state across calls (persist=True), so track
        IDs are stable as long as the object is visible.

        Args:
            frame: BGR image (numpy array)

        Returns:
            List of TrackedPerson, sorted by track_id for determinism.
        """
        tracked_persons: List[TrackedPerson] = []

        try:
            results = self.detector.model.track(
                frame,
                persist=True,
                tracker=self.tracker_cfg,
                verbose=False,
                conf=self.detector.confidence_threshold,
                classes=[0],  # person class only
            )
        except Exception as exc:
            # Tracker can occasionally fail on the very first frame or when
            # the model hasn't seen a track state yet — fall back to predict.
            print(f"⚠️  Tracker error ({exc}), falling back to predict")
            return self._fallback_predict(frame)

        if not results or results[0].boxes is None:
            self._mark_all_lost()
            return tracked_persons

        result = results[0]
        boxes = result.boxes

        if boxes.id is None:
            # ByteTrack sometimes returns None IDs on empty frame
            self._mark_all_lost()
            return tracked_persons

        track_ids = boxes.id.cpu().numpy().astype(int)
        xyxy_boxes = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()

        # Keypoints (YOLO26-pose)
        kpts_data = None
        if hasattr(result, "keypoints") and result.keypoints is not None:
            kpts_data = result.keypoints.data.cpu().numpy()  # (N, 17, 3)

        current_frame_ids = set()

        for i, (tid, box, conf) in enumerate(zip(track_ids, xyxy_boxes, confs)):
            tid = int(tid)
            x1, y1, x2, y2 = map(int, box)
            body_bbox = (x1, y1, x2 - x1, y2 - y1)

            # Keypoints
            kpts = None
            face_bbox = None
            has_face = False
            if kpts_data is not None and i < len(kpts_data):
                kpts = kpts_data[i]  # (17,3)
                face_bbox = self.detector._extract_face_from_keypoints(kpts)
                has_face = face_bbox is not None

            # Update or create track state
            state = self._get_or_create_track(tid)
            state.last_seen = time.time()
            state.frame_count += 1
            state.is_lost = False
            state.lost_time = None

            current_frame_ids.add(tid)

            tp = TrackedPerson(
                track_id=tid,
                body_bbox=body_bbox,
                confidence=float(conf),
                keypoints=kpts,
                face_bbox=face_bbox,
                has_face=has_face,
                person_id=state.person_id,
            )
            tracked_persons.append(tp)

        # Mark tracks absent this frame as lost
        disappeared = self._active_ids - current_frame_ids
        for tid in disappeared:
            if tid in self._tracks:
                state = self._tracks[tid]
                state.is_lost = True
                if state.lost_time is None:
                    state.lost_time = time.time()
                self._lost_ids.add(tid)

        self._active_ids = current_frame_ids

        # Expire stale lost tracks
        self._cleanup_expired_tracks()

        return sorted(tracked_persons, key=lambda t: t.track_id)

    # ------------------------------------------------------------------
    # Re-ID association helpers
    # ------------------------------------------------------------------

    def associate(self, track_id: int, person_id: str):
        """
        Bind a ByteTrack ID to a registered person ID.

        Called by the main system after matching a detection to a person
        in the registry.  This mapping persists even if the track is
        temporarily lost and re-appears.
        """
        state = self._get_or_create_track(track_id)
        old_pid = state.person_id

        # Remove old reverse mapping if person switched tracks
        if old_pid and old_pid in self._person_to_track:
            del self._person_to_track[old_pid]

        state.person_id = person_id
        self._person_to_track[person_id] = track_id

    def dissociate(self, person_id: str):
        """Remove person → track binding (e.g., on exit)."""
        tid = self._person_to_track.pop(person_id, None)
        if tid is not None and tid in self._tracks:
            self._tracks[tid].person_id = None

    def get_person_id(self, track_id: int) -> Optional[str]:
        """Return the registered person_id for a track, or None."""
        state = self._tracks.get(track_id)
        return state.person_id if state else None

    def get_track_id(self, person_id: str) -> Optional[int]:
        """Return the current track_id for a registered person, or None."""
        return self._person_to_track.get(person_id)

    # ------------------------------------------------------------------
    # Feature aggregation
    # ------------------------------------------------------------------

    def add_embedding(self, track_id: int, embedding: np.ndarray):
        """
        Append an OSNet embedding to the per-track ring buffer.
        The mean of the buffer is used for stable re-ID matching.
        """
        state = self._get_or_create_track(track_id)
        state.add_embedding(embedding)

    def get_aggregated_embedding(self, track_id: int) -> Optional[np.ndarray]:
        """
        Return the temporally mean-pooled OSNet embedding for *track_id*.
        Returns None if no embeddings have been collected yet.
        """
        state = self._tracks.get(track_id)
        if state is None:
            return None
        return state.get_mean_embedding()

    def has_enough_frames(self, track_id: int, min_frames: int = 3) -> bool:
        """True once the track has been updated at least *min_frames* times."""
        state = self._tracks.get(track_id)
        return state is not None and state.frame_count >= min_frames

    # ------------------------------------------------------------------
    # Statistics / diagnostics
    # ------------------------------------------------------------------

    def get_active_count(self) -> int:
        """Number of tracks active in the most recent frame."""
        return len(self._active_ids)

    def get_lost_count(self) -> int:
        """Number of tracks that are temporarily lost."""
        return len(self._lost_ids)

    def get_track_duration(self, track_id: int) -> float:
        """Seconds since the track was first seen (0 if unknown)."""
        state = self._tracks.get(track_id)
        if state is None:
            return 0.0
        return time.time() - state.first_seen

    def diagnostics(self) -> dict:
        """Return a snapshot dict for debug overlays and logging."""
        return {
            "active_tracks": len(self._active_ids),
            "lost_tracks": len(self._lost_ids),
            "total_tracks": len(self._tracks),
            "person_map": dict(self._person_to_track),
        }

    def reset(self):
        """
        Hard reset — clear all state and restart the ByteTrack internal
        counter.  Call when clearing all registrations (key 'C' in the UI).
        """
        self._tracks.clear()
        self._active_ids.clear()
        self._lost_ids.clear()
        self._person_to_track.clear()

        # Force ultralytics to restart its tracker state on next call
        try:
            if (
                hasattr(self.detector.model, "predictor")
                and self.detector.model.predictor is not None
            ):
                self.detector.model.predictor.trackers = []
        except Exception:
            pass  # Non-fatal; tracker state will simply re-initialise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_track(self, track_id: int) -> TrackState:
        if track_id not in self._tracks:
            self._tracks[track_id] = TrackState(track_id=track_id)
        return self._tracks[track_id]

    def _mark_all_lost(self):
        """Mark every previously-active track as lost (empty frame)."""
        now = time.time()
        for tid in list(self._active_ids):
            if tid in self._tracks:
                state = self._tracks[tid]
                state.is_lost = True
                if state.lost_time is None:
                    state.lost_time = now
                self._lost_ids.add(tid)
        self._active_ids.clear()
        self._cleanup_expired_tracks()

    def _cleanup_expired_tracks(self):
        """Remove lost tracks that have exceeded the timeout window."""
        now = time.time()
        expired = []
        for tid in list(self._lost_ids):
            state = self._tracks.get(tid)
            if state is None or state.lost_time is None:
                expired.append(tid)
                continue
            if now - state.lost_time > self.lost_track_timeout:
                expired.append(tid)

        for tid in expired:
            self._lost_ids.discard(tid)
            state = self._tracks.pop(tid, None)
            if state and state.person_id:
                self._person_to_track.pop(state.person_id, None)

    def _fallback_predict(self, frame: np.ndarray) -> List[TrackedPerson]:
        """
        Emergency fallback when track() fails — use plain detect() and
        assign temporary negative IDs so the rest of the pipeline still works.
        """
        detections = self.detector.detect(frame)
        result = []
        for i, det in enumerate(detections):
            # Negative IDs signal "no stable track"
            tp = TrackedPerson(
                track_id=-(i + 1),
                body_bbox=det["body_bbox"],
                confidence=det["confidence"],
                keypoints=det.get("keypoints"),
                face_bbox=det.get("face_bbox"),
                has_face=det.get("has_face", False),
            )
            result.append(tp)
        return result
