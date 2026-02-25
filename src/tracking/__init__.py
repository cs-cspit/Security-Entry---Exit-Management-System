"""
Tracking module for Security Entry & Exit Management System.

Provides multi-person tracking using YOLO26's built-in ByteTrack tracker,
eliminating the need for external tracking libraries (norfair, boxmot, filterpy).

YOLO26 (via ultralytics) ships ByteTrack and BoT-SORT natively through
`model.track(persist=True)` — no separate tracker installation required.
"""

from .multi_tracker import MultiPersonTracker, TrackedPerson

__all__ = ["MultiPersonTracker", "TrackedPerson"]
