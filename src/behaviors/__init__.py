"""
Behavior Analysis Modules - Phase 7
=====================================
Detectors for security-relevant behavior patterns:
  - LoiteringDetector  : zone-based dwell-time analysis
  - TailgatingDetector : rapid successive entry detection
"""

from .loitering_detector import LoiteringDetector
from .tailgating_detector import TailgatingDetector

__all__ = ["LoiteringDetector", "TailgatingDetector"]
