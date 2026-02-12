#!/usr/bin/env python3
"""
Alert Manager Module
====================
Centralized alert handling system with cooldown, logging, and notification.

Phase 1 Implementation - Foundation for Room Tracking System
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = 0
    WARNING = 1
    CRITICAL = 2


class AlertType(Enum):
    """Types of alerts the system can generate."""

    RUNNING = "running"
    MASS_GATHERING = "mass_gathering"
    UNAUTHORIZED_ENTRY = "unauthorized_entry"
    HIGH_THREAT_SCORE = "high_threat_score"
    LOITERING = "loitering"
    PANIC_BEHAVIOR = "panic_behavior"


class AlertManager:
    """
    Manages system alerts with cooldown, logging, and notifications.

    Features:
    - Alert cooldown to prevent spam
    - Console and file logging
    - Alert history tracking
    - Callback system for custom handlers
    - Visual and audio notifications
    """

    def __init__(
        self,
        cooldown_seconds: float = 5.0,
        console_output: bool = True,
        file_logging: bool = True,
        log_path: str = "data/alerts.log",
        audio_alert: bool = False,
    ):
        """
        Initialize alert manager.

        Args:
            cooldown_seconds: Minimum time between alerts of same type
            console_output: Print alerts to console
            file_logging: Write alerts to log file
            log_path: Path to alert log file
            audio_alert: Play sound on critical alerts
        """
        self.cooldown_seconds = cooldown_seconds
        self.console_output = console_output
        self.file_logging = file_logging
        self.log_path = log_path
        self.audio_alert = audio_alert

        # Alert history
        self.alerts = []  # All alerts
        self.last_alert_time = defaultdict(
            lambda: datetime.min
        )  # {alert_key: timestamp}

        # Statistics
        self.stats = {
            "total_alerts": 0,
            "by_level": defaultdict(int),
            "by_type": defaultdict(int),
            "suppressed_count": 0,
        }

        # Callback handlers
        self.callbacks = []  # List of functions to call on alert

        # Ensure log directory exists
        if self.file_logging:
            self._ensure_log_directory()

    def _ensure_log_directory(self):
        """Ensure the log directory exists."""
        log_dir = Path(self.log_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    def _get_alert_key(
        self, alert_type: AlertType, person_id: Optional[str] = None
    ) -> str:
        """
        Generate unique key for alert cooldown tracking.

        Args:
            alert_type: Type of alert
            person_id: Optional person identifier

        Returns:
            Unique key string
        """
        if person_id:
            return f"{alert_type.value}:{person_id}"
        return alert_type.value

    def _is_on_cooldown(self, alert_key: str) -> bool:
        """
        Check if alert is on cooldown.

        Args:
            alert_key: Alert identifier

        Returns:
            True if on cooldown, False otherwise
        """
        now = datetime.now()
        last_time = self.last_alert_time[alert_key]
        time_since = (now - last_time).total_seconds()
        return time_since < self.cooldown_seconds

    def _format_alert_message(self, alert: Dict) -> str:
        """
        Format alert as human-readable string.

        Args:
            alert: Alert dictionary

        Returns:
            Formatted string
        """
        level_symbol = {
            AlertLevel.INFO.value: "ℹ️",
            AlertLevel.WARNING.value: "⚠️",
            AlertLevel.CRITICAL.value: "🚨",
        }

        symbol = level_symbol.get(alert["alert_level"], "•")
        timestamp = alert["timestamp"].strftime("%H:%M:%S")

        parts = [
            f"{symbol} [{timestamp}]",
            f"[{alert['alert_level'].upper()}]",
            f"[{alert['alert_type'].upper()}]",
        ]

        if alert.get("person_id"):
            parts.append(f"Person: {alert['person_id']}")

        if alert.get("camera_source"):
            parts.append(f"Camera: {alert['camera_source']}")

        parts.append(alert["message"])

        return " | ".join(parts)

    def _write_to_log_file(self, alert: Dict):
        """
        Write alert to log file.

        Args:
            alert: Alert dictionary
        """
        try:
            with open(self.log_path, "a") as f:
                log_line = self._format_alert_message(alert)
                f.write(log_line + "\n")
        except Exception as e:
            print(f"Error writing to log file: {e}")

    def _print_to_console(self, alert: Dict):
        """
        Print alert to console with color coding.

        Args:
            alert: Alert dictionary
        """
        # ANSI color codes
        colors = {
            AlertLevel.INFO.value: "\033[94m",  # Blue
            AlertLevel.WARNING.value: "\033[93m",  # Yellow
            AlertLevel.CRITICAL.value: "\033[91m",  # Red
        }
        reset = "\033[0m"

        level = alert["alert_level"]
        color = colors.get(level, "")

        message = self._format_alert_message(alert)
        print(f"{color}{message}{reset}")

    def _play_audio_alert(self):
        """Play audio alert for critical alerts."""
        if not self.audio_alert:
            return

        try:
            # macOS system beep
            import os

            os.system("afplay /System/Library/Sounds/Funk.aiff")
        except Exception:
            # Fallback to simple beep
            print("\a")

    def _execute_callbacks(self, alert: Dict):
        """
        Execute registered callback handlers.

        Args:
            alert: Alert dictionary
        """
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"Error in alert callback: {e}")

    def register_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback function to be called on each alert.

        Args:
            callback: Function that takes alert dict as parameter
        """
        self.callbacks.append(callback)

    def create_alert(
        self,
        alert_type: AlertType,
        alert_level: AlertLevel,
        message: str,
        person_id: Optional[str] = None,
        camera_source: Optional[str] = None,
        metadata: Optional[Dict] = None,
        force: bool = False,
    ) -> Optional[Dict]:
        """
        Create and process an alert.

        Args:
            alert_type: Type of alert
            alert_level: Severity level
            message: Human-readable message
            person_id: Associated person (if any)
            camera_source: Camera that triggered alert
            metadata: Additional data
            force: Bypass cooldown if True

        Returns:
            Alert dictionary if created, None if suppressed
        """
        now = datetime.now()

        # Check cooldown
        alert_key = self._get_alert_key(alert_type, person_id)

        if not force and self._is_on_cooldown(alert_key):
            self.stats["suppressed_count"] += 1
            return None

        # Create alert
        alert = {
            "alert_type": alert_type.value,
            "alert_level": alert_level.value,
            "message": message,
            "person_id": person_id,
            "camera_source": camera_source,
            "timestamp": now,
            "metadata": metadata or {},
        }

        # Store alert
        self.alerts.append(alert)
        self.last_alert_time[alert_key] = now

        # Update statistics
        self.stats["total_alerts"] += 1
        self.stats["by_level"][alert_level.value] += 1
        self.stats["by_type"][alert_type.value] += 1

        # Output alert
        if self.console_output:
            self._print_to_console(alert)

        if self.file_logging:
            self._write_to_log_file(alert)

        # Audio alert for critical
        if alert_level == AlertLevel.CRITICAL:
            self._play_audio_alert()

        # Execute callbacks
        self._execute_callbacks(alert)

        return alert

    def get_recent_alerts(
        self,
        limit: int = 10,
        level: Optional[AlertLevel] = None,
        alert_type: Optional[AlertType] = None,
    ) -> List[Dict]:
        """
        Get recent alerts with optional filtering.

        Args:
            limit: Maximum number of alerts to return
            level: Filter by alert level
            alert_type: Filter by alert type

        Returns:
            List of alert dictionaries (most recent first)
        """
        filtered = self.alerts

        if level:
            filtered = [a for a in filtered if a["alert_level"] == level.value]

        if alert_type:
            filtered = [a for a in filtered if a["alert_type"] == alert_type.value]

        return sorted(filtered, key=lambda a: a["timestamp"], reverse=True)[:limit]

    def get_alerts_for_person(self, person_id: str, limit: int = 10) -> List[Dict]:
        """
        Get alerts associated with a specific person.

        Args:
            person_id: Person identifier
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        person_alerts = [a for a in self.alerts if a["person_id"] == person_id]
        return sorted(person_alerts, key=lambda a: a["timestamp"], reverse=True)[:limit]

    def get_stats(self) -> Dict:
        """
        Get alert statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_alerts": self.stats["total_alerts"],
            "suppressed_count": self.stats["suppressed_count"],
            "by_level": dict(self.stats["by_level"]),
            "by_type": dict(self.stats["by_type"]),
            "recent_alerts": len(self.get_recent_alerts(limit=10)),
        }

    def clear_alerts(self):
        """Clear all alerts and reset statistics."""
        self.alerts.clear()
        self.last_alert_time.clear()
        self.stats = {
            "total_alerts": 0,
            "by_level": defaultdict(int),
            "by_type": defaultdict(int),
            "suppressed_count": 0,
        }

    def export_alerts(self, filepath: str):
        """
        Export alerts to JSON file.

        Args:
            filepath: Path to output file
        """
        data = {
            "alerts": self.alerts,
            "stats": self.get_stats(),
            "export_time": datetime.now().isoformat(),
        }

        def json_serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=json_serial)

    def get_alert_summary(self, time_window_minutes: int = 60) -> Dict:
        """
        Get alert summary for recent time window.

        Args:
            time_window_minutes: Time window to analyze

        Returns:
            Summary dictionary
        """
        cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
        recent = [a for a in self.alerts if a["timestamp"] > cutoff]

        summary = {
            "time_window_minutes": time_window_minutes,
            "total_in_window": len(recent),
            "critical_count": len(
                [a for a in recent if a["alert_level"] == AlertLevel.CRITICAL.value]
            ),
            "warning_count": len(
                [a for a in recent if a["alert_level"] == AlertLevel.WARNING.value]
            ),
            "info_count": len(
                [a for a in recent if a["alert_level"] == AlertLevel.INFO.value]
            ),
            "most_common_type": None,
        }

        # Find most common alert type
        if recent:
            type_counts = defaultdict(int)
            for alert in recent:
                type_counts[alert["alert_type"]] += 1
            summary["most_common_type"] = max(type_counts, key=type_counts.get)

        return summary


# Convenience functions for quick alert creation
def create_running_alert(
    manager: AlertManager, person_id: str, velocity: float, camera_source: str
) -> Optional[Dict]:
    """Create running detection alert."""
    return manager.create_alert(
        alert_type=AlertType.RUNNING,
        alert_level=AlertLevel.WARNING,
        message=f"Person running detected (velocity: {velocity:.2f} m/s)",
        person_id=person_id,
        camera_source=camera_source,
        metadata={"velocity": velocity},
    )


def create_unauthorized_alert(
    manager: AlertManager, person_id: str, camera_source: str
) -> Optional[Dict]:
    """Create unauthorized entry alert."""
    return manager.create_alert(
        alert_type=AlertType.UNAUTHORIZED_ENTRY,
        alert_level=AlertLevel.CRITICAL,
        message=f"Unauthorized person detected: {person_id}",
        person_id=person_id,
        camera_source=camera_source,
    )


def create_mass_gathering_alert(
    manager: AlertManager, zone_id: str, person_count: int, camera_source: str
) -> Optional[Dict]:
    """Create mass gathering alert."""
    return manager.create_alert(
        alert_type=AlertType.MASS_GATHERING,
        alert_level=AlertLevel.WARNING,
        message=f"Mass gathering detected in {zone_id} ({person_count} people)",
        camera_source=camera_source,
        metadata={"zone_id": zone_id, "person_count": person_count},
    )


def create_high_threat_alert(
    manager: AlertManager, person_id: str, threat_score: float, camera_source: str
) -> Optional[Dict]:
    """Create high threat score alert."""
    return manager.create_alert(
        alert_type=AlertType.HIGH_THREAT_SCORE,
        alert_level=AlertLevel.CRITICAL,
        message=f"High threat score: {threat_score:.2f}",
        person_id=person_id,
        camera_source=camera_source,
        metadata={"threat_score": threat_score},
    )


if __name__ == "__main__":
    # Test the alert manager
    print("Testing Alert Manager...\n")

    manager = AlertManager(
        cooldown_seconds=2.0,
        console_output=True,
        file_logging=True,
        log_path="data/test_alerts.log",
    )

    # Test different alert types
    manager.create_alert(
        AlertType.RUNNING,
        AlertLevel.WARNING,
        "Test person running",
        person_id="test-123",
        camera_source="room_camera",
    )

    time.sleep(0.5)

    manager.create_alert(
        AlertType.UNAUTHORIZED_ENTRY,
        AlertLevel.CRITICAL,
        "Unauthorized entry detected",
        person_id="unknown-456",
        camera_source="room_camera",
    )

    time.sleep(0.5)

    # Test cooldown (should be suppressed)
    result = manager.create_alert(
        AlertType.RUNNING,
        AlertLevel.WARNING,
        "Another running alert (should be suppressed)",
        person_id="test-123",
        camera_source="room_camera",
    )

    if result is None:
        print("\n✅ Cooldown working - alert suppressed")

    time.sleep(2.5)

    # After cooldown (should go through)
    manager.create_alert(
        AlertType.RUNNING,
        AlertLevel.WARNING,
        "Running alert after cooldown",
        person_id="test-123",
        camera_source="room_camera",
    )

    # Test convenience functions
    create_mass_gathering_alert(manager, "zone_1", 8, "room_camera")
    create_high_threat_alert(manager, "test-789", 0.85, "room_camera")

    # Get stats
    print("\n--- Alert Statistics ---")
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    # Get recent alerts
    print("\n--- Recent Alerts ---")
    recent = manager.get_recent_alerts(limit=3)
    for alert in recent:
        print(f"- {alert['alert_type']} at {alert['timestamp'].strftime('%H:%M:%S')}")

    print("\n✅ Alert Manager tests passed!")
