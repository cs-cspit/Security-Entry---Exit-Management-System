#!/usr/bin/env python3
"""
Tailgating Detector (Phase 7)
================================
Detects tailgating — multiple persons entering through the entry gate in
rapid succession within a configurable time window.

Security context
----------------
Tailgating (also called "piggybacking") is when an unauthorised person
follows an authorised person through a controlled entry before the gate
closes.  This detector flags when ≥ N persons are registered at the entry
camera within a short time window, which is a strong signal of tailgating.

Two complementary checks are performed:
  1. **Time-window burst**: ≥ min_persons entries within time_window seconds.
  2. **Spatial proximity**: The bounding boxes of rapid entrants overlap
     significantly (they are in the same physical space → likely tailgating).

Design
------
- Entry events are stored in a ring buffer (deque) and trimmed to only keep
  events within the rolling time window.
- On every new entry, the recent-entry count is checked against the threshold.
- Spatial proximity is an optional secondary check controlled by
  ``check_proximity``.  When enabled, at least one pair of recent entries
  must have overlapping bounding boxes to confirm tailgating.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class EntryEvent:
    """Represents a single person entering at the entry gate."""

    person_id: str
    timestamp: float  # time.time()
    bbox: Optional[Tuple[int, int, int, int]]  # (x, y, w, h) or None
    is_authorized: bool = True


@dataclass
class TailgatingEvent:
    """Describes a detected tailgating incident."""

    timestamp: float
    person_count: int
    person_ids: List[str]
    # Pair that triggered the spatial proximity check (if any)
    proximity_pair: Optional[Tuple[str, str]] = None
    overlap_score: float = 0.0

    def __str__(self) -> str:
        ids = ", ".join(self.person_ids)
        return (
            f"TAILGATING @ t={self.timestamp:.1f}s | "
            f"{self.person_count} persons in window [{ids}]"
        )


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class TailgatingDetector:
    """
    Detects tailgating (rapid successive entries) at the entry gate.

    Parameters
    ----------
    time_window : float
        Rolling time window in seconds.  All entries within this window are
        compared against the person threshold.  Default 5 s.
    min_persons : int
        Minimum number of persons in the time window to trigger an alert.
        Default 2.
    check_proximity : bool
        When True, also require that at least one pair of recent entrants had
        overlapping bounding boxes (they were physically close together at
        entry).  This reduces false positives when two people arrive
        independently within the window.  Default True.
    min_overlap : float
        Minimum IoU-like overlap score (0–1) between two entry bboxes to be
        considered spatially close.  Default 0.10 (generous — even partial
        overlap counts).
    alert_cooldown : float
        Minimum seconds between consecutive tailgating alerts.  Default 10 s.
    """

    def __init__(
        self,
        time_window: float = 5.0,
        min_persons: int = 2,
        check_proximity: bool = True,
        min_overlap: float = 0.10,
        alert_cooldown: float = 10.0,
    ):
        self.time_window = time_window
        self.min_persons = min_persons
        self.check_proximity = check_proximity
        self.min_overlap = min_overlap
        self.alert_cooldown = alert_cooldown

        # Ring buffer of recent entry events (auto-trimmed)
        self._events: Deque[EntryEvent] = deque()

        # Alert suppression
        self._last_alert_time: float = 0.0

        # Statistics
        self.total_tailgating_events: int = 0
        self._event_history: List[TailgatingEvent] = []  # for audit / export

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_entry(
        self,
        person_id: str,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        is_authorized: bool = True,
        timestamp: Optional[float] = None,
    ) -> Optional[TailgatingEvent]:
        """
        Record a new entry event and check for tailgating.

        Call this every time the entry camera registers a new person.

        Parameters
        ----------
        person_id : str
            The registered person ID (e.g. "P001") or an anonymous label.
        bbox : tuple or None
            Body bounding box at time of entry: (x, y, w, h).
        is_authorized : bool
            Whether the person was successfully matched in the registry.
        timestamp : float or None
            Override the event timestamp (seconds since epoch).  If None,
            ``time.time()`` is used — the normal case.

        Returns
        -------
        TailgatingEvent or None
            A TailgatingEvent if tailgating is detected and the alert
            cooldown has elapsed, otherwise None.
        """
        ts = timestamp if timestamp is not None else time.time()
        event = EntryEvent(
            person_id=person_id,
            timestamp=ts,
            bbox=bbox,
            is_authorized=is_authorized,
        )
        self._events.append(event)
        self._trim_window(ts)

        return self._check_tailgating(ts)

    def check_only(self) -> Optional[TailgatingEvent]:
        """
        Re-evaluate tailgating with the current window without adding a new
        entry event.  Useful for periodic background polling.
        """
        now = time.time()
        self._trim_window(now)
        return self._check_tailgating(now, suppress_cooldown_update=True)

    def get_recent_entries(self, window: Optional[float] = None) -> List[EntryEvent]:
        """
        Return the entry events within the last *window* seconds
        (defaults to ``self.time_window``).
        """
        cutoff = time.time() - (window or self.time_window)
        return [e for e in self._events if e.timestamp >= cutoff]

    def get_event_history(self) -> List[TailgatingEvent]:
        """Return all recorded tailgating incidents (for audit / export)."""
        return list(self._event_history)

    def reset(self):
        """Hard reset — clear all state."""
        self._events.clear()
        self._last_alert_time = 0.0
        self.total_tailgating_events = 0
        self._event_history.clear()

    def diagnostics(self) -> dict:
        """Return a snapshot dict for debug overlays / logging."""
        now = time.time()
        recent = self.get_recent_entries()
        return {
            "entries_in_window": len(recent),
            "window_seconds": self.time_window,
            "min_persons_threshold": self.min_persons,
            "total_tailgating_events": self.total_tailgating_events,
            "cooldown_remaining": max(
                0.0, self.alert_cooldown - (now - self._last_alert_time)
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim_window(self, now: float):
        """Remove events that have fallen outside the rolling time window."""
        cutoff = now - self.time_window
        while self._events and self._events[0].timestamp < cutoff:
            self._events.popleft()

    def _check_tailgating(
        self,
        now: float,
        suppress_cooldown_update: bool = False,
    ) -> Optional[TailgatingEvent]:
        """
        Core detection logic.

        Returns a TailgatingEvent if the burst threshold is met (and spatial
        proximity if enabled), and the alert cooldown has elapsed.
        """
        recent = list(self._events)

        # ── Step 1: burst threshold ─────────────────────────────────────
        if len(recent) < self.min_persons:
            return None

        # ── Step 2: cooldown gate ───────────────────────────────────────
        if now - self._last_alert_time < self.alert_cooldown:
            return None

        # ── Step 3: optional proximity check ───────────────────────────
        proximity_pair: Optional[Tuple[str, str]] = None
        overlap_score: float = 0.0

        if self.check_proximity:
            # Look for any pair of events with overlapping bboxes
            found_proximity = False
            for i in range(len(recent)):
                for j in range(i + 1, len(recent)):
                    a, b = recent[i], recent[j]
                    if a.bbox is not None and b.bbox is not None:
                        iou = self._bbox_overlap(a.bbox, b.bbox)
                        if iou >= self.min_overlap:
                            found_proximity = True
                            proximity_pair = (a.person_id, b.person_id)
                            overlap_score = iou
                            break
                if found_proximity:
                    break

            if not found_proximity:
                # Burst of entries but they were well-separated spatially —
                # not tailgating (e.g. two people arriving at different times
                # still within the window but from different entry angles).
                return None

        # ── Step 4: build and record the event ─────────────────────────
        tailgating = TailgatingEvent(
            timestamp=now,
            person_count=len(recent),
            person_ids=[e.person_id for e in recent],
            proximity_pair=proximity_pair,
            overlap_score=overlap_score,
        )

        if not suppress_cooldown_update:
            self._last_alert_time = now

        self.total_tailgating_events += 1
        self._event_history.append(tailgating)

        # Keep history bounded
        if len(self._event_history) > 500:
            self._event_history.pop(0)

        return tailgating

    @staticmethod
    def _bbox_overlap(
        a: Tuple[int, int, int, int],
        b: Tuple[int, int, int, int],
    ) -> float:
        """
        Compute the intersection-over-union (IoU) of two bounding boxes.

        Parameters
        ----------
        a, b : (x, y, w, h) tuples

        Returns
        -------
        float
            IoU in [0, 1].  0 = no overlap, 1 = identical boxes.
        """
        ax, ay, aw, ah = a
        bx, by, bw, bh = b

        # Convert to (x1, y1, x2, y2)
        ax2, ay2 = ax + aw, ay + ah
        bx2, by2 = bx + bw, by + bh

        # Intersection
        ix1 = max(ax, bx)
        iy1 = max(ay, by)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        inter = (ix2 - ix1) * (iy2 - iy1)
        union = aw * ah + bw * bh - inter

        return inter / union if union > 0 else 0.0
