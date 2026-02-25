#!/usr/bin/env python3
"""
Loitering Detector (Phase 7)
==============================
Zone-based dwell-time analysis.  A person is flagged as loitering when
they remain within the same spatial zone for longer than a configurable
threshold.

Design
------
- The frame is divided into a coarse grid of cells (zone_size × zone_size
  pixels).  Each cell is a "zone".
- For each tracked person we record when they FIRST entered their current
  zone.  If they stay in that zone beyond ``loitering_threshold`` seconds
  the detector fires.
- Moving to an adjacent zone resets the zone timer for that person.
- Zones are identified by their (col, row) grid coordinate so the detector
  is resolution-independent once zone_size is set appropriately.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ZoneVisit:
    """Records when a person entered a particular grid zone."""

    zone: Tuple[int, int]  # (col, row) grid coordinate
    enter_time: float  # time.time() stamp
    last_seen: float  # updated every frame the person is in zone

    @property
    def dwell_seconds(self) -> float:
        return time.time() - self.enter_time


@dataclass
class PersonZoneState:
    """All zone-tracking data for a single person."""

    person_id: str
    current_visit: Optional[ZoneVisit] = None
    # History of (zone, dwell_seconds) for post-incident review
    zone_history: list = field(default_factory=list)
    MAX_HISTORY: int = 50

    # Alert suppression — track when we last raised a loitering alert
    last_alert_time: float = 0.0

    def enter_zone(self, zone: Tuple[int, int]):
        if self.current_visit is None or self.current_visit.zone != zone:
            # Archive old visit
            if self.current_visit is not None:
                self.zone_history.append(
                    (self.current_visit.zone, self.current_visit.dwell_seconds)
                )
                if len(self.zone_history) > self.MAX_HISTORY:
                    self.zone_history.pop(0)
            # Start new visit
            now = time.time()
            self.current_visit = ZoneVisit(zone=zone, enter_time=now, last_seen=now)
        else:
            # Still in same zone — just update last_seen
            self.current_visit.last_seen = time.time()

    def dwell_seconds(self) -> float:
        if self.current_visit is None:
            return 0.0
        return self.current_visit.dwell_seconds

    def current_zone(self) -> Optional[Tuple[int, int]]:
        return self.current_visit.zone if self.current_visit else None


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class LoiteringDetector:
    """
    Detects persons loitering (staying in the same zone too long).

    Parameters
    ----------
    loitering_threshold : float
        Seconds a person must dwell in one zone before the detector fires.
        Default 60 s (1 minute).
    zone_size : int
        Pixel size of each grid cell.  Smaller = finer resolution, more
        zones.  Default 100 px.
    alert_cooldown : float
        Minimum seconds between repeated loitering alerts for the same
        person.  Default 30 s.
    stale_timeout : float
        Seconds of inactivity before a person's state is removed from
        memory.  Default 120 s.
    """

    def __init__(
        self,
        loitering_threshold: float = 60.0,
        zone_size: int = 100,
        alert_cooldown: float = 30.0,
        stale_timeout: float = 120.0,
    ):
        self.loitering_threshold = loitering_threshold
        self.zone_size = zone_size
        self.alert_cooldown = alert_cooldown
        self.stale_timeout = stale_timeout

        # {person_id: PersonZoneState}
        self._states: Dict[str, PersonZoneState] = {}

        # Lightweight statistics
        self.total_loitering_events: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        person_id: str,
        x: int,
        y: int,
    ) -> Tuple[bool, float]:
        """
        Update the position of *person_id* and check for loitering.

        Parameters
        ----------
        person_id : str
            Unique identifier for the person (track_id or registered ID).
        x, y : int
            Current centre-pixel position of the person in the frame.

        Returns
        -------
        is_loitering : bool
            True if the person has been in the same zone longer than the
            threshold AND the alert cooldown has elapsed.
        dwell_seconds : float
            How long (in seconds) the person has been in their current zone
            (regardless of whether the cooldown allows an alert).
        """
        state = self._get_or_create(person_id)
        zone = self._pixel_to_zone(x, y)
        state.enter_zone(zone)

        dwell = state.dwell_seconds()
        is_loitering = False

        if dwell >= self.loitering_threshold:
            now = time.time()
            if now - state.last_alert_time >= self.alert_cooldown:
                is_loitering = True
                state.last_alert_time = now
                self.total_loitering_events += 1

        return is_loitering, dwell

    def remove_person(self, person_id: str):
        """
        Remove tracking state for a person (e.g. when they exit the room).
        """
        self._states.pop(person_id, None)

    def get_dwell_time(self, person_id: str) -> float:
        """
        Return how many seconds *person_id* has been in their current zone.
        Returns 0.0 if the person is not being tracked.
        """
        state = self._states.get(person_id)
        return state.dwell_seconds() if state else 0.0

    def get_current_zone(self, person_id: str) -> Optional[Tuple[int, int]]:
        """Return the current grid zone for *person_id*, or None."""
        state = self._states.get(person_id)
        return state.current_zone() if state else None

    def get_zone_history(self, person_id: str) -> list:
        """
        Return the list of (zone, dwell_seconds) visited by *person_id*.
        """
        state = self._states.get(person_id)
        return list(state.zone_history) if state else []

    def cleanup_stale(self):
        """
        Remove persons who haven't been updated within *stale_timeout* seconds.
        Call periodically (e.g. once per second) to avoid memory growth.
        """
        now = time.time()
        to_remove = []
        for pid, state in self._states.items():
            if state.current_visit is None:
                to_remove.append(pid)
                continue
            if now - state.current_visit.last_seen > self.stale_timeout:
                to_remove.append(pid)
        for pid in to_remove:
            del self._states[pid]

    def reset(self):
        """Hard reset — clears all tracking state."""
        self._states.clear()
        self.total_loitering_events = 0

    def diagnostics(self) -> dict:
        """
        Return a snapshot dict suitable for debug overlays / logging.
        Keys: active_persons, loitering_persons, total_events.
        """
        loitering_now = [
            pid
            for pid, state in self._states.items()
            if state.dwell_seconds() >= self.loitering_threshold
        ]
        return {
            "active_persons": len(self._states),
            "loitering_persons": loitering_now,
            "total_events": self.total_loitering_events,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pixel_to_zone(self, x: int, y: int) -> Tuple[int, int]:
        """Map a pixel coordinate to a (col, row) grid cell."""
        return (max(0, x) // self.zone_size, max(0, y) // self.zone_size)

    def _get_or_create(self, person_id: str) -> PersonZoneState:
        if person_id not in self._states:
            self._states[person_id] = PersonZoneState(person_id=person_id)
        return self._states[person_id]
