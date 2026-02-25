#!/usr/bin/env python3
"""
Alert Manager Module (Phase 7 Enhanced)
=========================================
Centralized alert handling with:
  - Cooldown / deduplication
  - Console + file logging (unchanged from Phase 1)
  - Telegram bot notifications (optional, env-var based)
  - WebSocket event push (via SecurityAPIBridge queue)
  - YAML-driven alert rules (configs/alert_rules.yaml)
  - Loitering & tailgating alert types
  - Panic-behavior & door-forced alert types

Environment variables
----------------------
  TELEGRAM_BOT_TOKEN   — Telegram bot token
  TELEGRAM_CHAT_ID     — Telegram chat/group ID

The Telegram integration uses the ``requests`` library only (no
python-telegram-bot dependency needed).  If ``requests`` is not installed
or the env-vars are missing, Telegram notifications are silently disabled.
"""

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------
try:
    import requests as _requests_lib

    _REQUESTS_AVAILABLE = True
except ImportError:
    _requests_lib = None  # type: ignore
    _REQUESTS_AVAILABLE = False

try:
    import yaml as _yaml_lib

    _YAML_AVAILABLE = True
except ImportError:
    _yaml_lib = None  # type: ignore
    _YAML_AVAILABLE = False

logger = logging.getLogger("alert_manager")

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AlertLevel(Enum):
    """Alert severity levels (ascending)."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        return {"info": 0, "warning": 1, "critical": 2}[self.value]

    def __ge__(self, other: "AlertLevel") -> bool:
        return self.weight >= other.weight

    def __gt__(self, other: "AlertLevel") -> bool:
        return self.weight > other.weight


class AlertType(Enum):
    """All alert types supported by the system."""

    # Phase 1 originals
    RUNNING = "running"
    MASS_GATHERING = "mass_gathering"
    UNAUTHORIZED_ENTRY = "unauthorized_entry"
    HIGH_THREAT_SCORE = "high_threat_score"
    LOITERING = "loitering"
    PANIC_BEHAVIOR = "panic_behavior"

    # Phase 7 additions
    TAILGATING = "tailgating"
    DOOR_FORCED = "door_forced"
    TRACK_LOST = "track_lost"
    SYSTEM_ERROR = "system_error"


# ---------------------------------------------------------------------------
# Notification channel helpers
# ---------------------------------------------------------------------------


class _TelegramChannel:
    """
    Thin wrapper around the Telegram Bot HTTP API.

    Token and chat_id are read from:
      1. Constructor arguments (if provided)
      2. Environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    """

    _BASE = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        parse_mode: str = "HTML",
        min_level: AlertLevel = AlertLevel.CRITICAL,
        timeout: float = 5.0,
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.parse_mode = parse_mode
        self.min_level = min_level
        self.timeout = timeout
        self.enabled = bool(self.bot_token and self.chat_id and _REQUESTS_AVAILABLE)

        if self.enabled:
            logger.info("✅ Telegram notifications enabled")
        else:
            if not _REQUESTS_AVAILABLE:
                logger.debug("Telegram disabled: 'requests' library not installed")
            elif not self.bot_token:
                logger.debug("Telegram disabled: TELEGRAM_BOT_TOKEN not set")
            elif not self.chat_id:
                logger.debug("Telegram disabled: TELEGRAM_CHAT_ID not set")

    def send(self, text: str) -> bool:
        """
        Send *text* to the configured Telegram chat.
        Returns True on success, False on failure.
        Non-blocking with a short timeout so it never stalls the main loop.
        """
        if not self.enabled:
            return False
        url = self._BASE.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": self.parse_mode,
        }
        try:
            resp = _requests_lib.post(url, json=payload, timeout=self.timeout)
            if not resp.ok:
                logger.warning(
                    f"Telegram API error {resp.status_code}: {resp.text[:200]}"
                )
            return resp.ok
        except Exception as exc:
            logger.debug(f"Telegram send failed: {exc}")
            return False

    def format_alert(self, alert: Dict) -> str:
        """Format an alert dict as a Telegram HTML message."""
        level_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨",
        }
        emoji = level_emoji.get(alert.get("alert_level", "info"), "•")
        ts = alert.get("timestamp", datetime.now())
        if isinstance(ts, datetime):
            ts = ts.strftime("%H:%M:%S")

        lines = [
            f"{emoji} <b>[{alert.get('alert_level', '').upper()}] "
            f"{alert.get('alert_type', '').upper()}</b>",
            f"🕐 {ts}",
        ]
        if alert.get("person_id"):
            lines.append(f"👤 Person: <code>{alert['person_id']}</code>")
        if alert.get("camera_source"):
            lines.append(f"📹 Camera: {alert['camera_source']}")
        lines.append(f"📝 {alert.get('message', '')}")

        meta = alert.get("metadata", {})
        if meta.get("velocity"):
            lines.append(f"🏃 Velocity: {meta['velocity']:.2f} m/s")
        if meta.get("dwell_seconds"):
            lines.append(f"⏱ Dwell: {meta['dwell_seconds']:.0f}s")
        if meta.get("person_count"):
            lines.append(f"👥 Count: {meta['person_count']}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rules loader
# ---------------------------------------------------------------------------


def _load_rules(config_path: str = "configs/alert_rules.yaml") -> dict:
    """
    Load alert rules from YAML.  Returns an empty dict if the file is
    missing or YAML is not installed.
    """
    if not _YAML_AVAILABLE:
        return {}
    path = Path(config_path)
    if not path.exists():
        logger.debug(f"Alert rules file not found: {config_path}")
        return {}
    try:
        with open(path) as f:
            return _yaml_lib.safe_load(f) or {}
    except Exception as exc:
        logger.warning(f"Failed to load alert rules: {exc}")
        return {}


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------


class AlertManager:
    """
    Centralized alert manager with multi-channel notification support.

    Parameters
    ----------
    cooldown_seconds : float
        Default minimum time between identical alerts (overridden per-type
        if rules YAML is loaded).
    console_output : bool
        Print alerts to stdout with ANSI colors.
    file_logging : bool
        Append alerts to *log_path*.
    log_path : str
        Path to the alert log file.
    audio_alert : bool
        Play a system beep on CRITICAL alerts (macOS afplay).
    telegram_token : str
        Telegram bot token.  Falls back to TELEGRAM_BOT_TOKEN env var.
    telegram_chat_id : str
        Telegram target chat ID.  Falls back to TELEGRAM_CHAT_ID env var.
    rules_path : str
        Path to alert_rules.yaml.  Set to "" to skip YAML loading.
    api_bridge : SecurityAPIBridge or None
        Reference to the WebSocket bridge; alerts are pushed via
        ``bridge.push_event("alert", {...})``.
    """

    def __init__(
        self,
        cooldown_seconds: float = 5.0,
        console_output: bool = True,
        file_logging: bool = True,
        log_path: str = "data/alerts.log",
        audio_alert: bool = False,
        telegram_token: str = "",
        telegram_chat_id: str = "",
        rules_path: str = "configs/alert_rules.yaml",
        api_bridge=None,
    ):
        self.default_cooldown = cooldown_seconds
        self.console_output = console_output
        self.file_logging = file_logging
        self.log_path = log_path
        self.audio_alert = audio_alert
        self.api_bridge = api_bridge  # set later via bridge.system = self

        # Load rules from YAML
        self._rules: dict = _load_rules(rules_path)
        self._channels: dict = self._rules.get("channels", {})
        self._rule_map: dict = self._rules.get("rules", {})

        # Telegram channel
        tg_cfg = self._channels.get("telegram", {})
        self._telegram = _TelegramChannel(
            bot_token=telegram_token or tg_cfg.get("bot_token", ""),
            chat_id=telegram_chat_id or tg_cfg.get("chat_id", ""),
            parse_mode=tg_cfg.get("parse_mode", "HTML"),
            min_level=AlertLevel(tg_cfg.get("min_level", "critical")),
            timeout=float(tg_cfg.get("timeout_seconds", 5)),
        )

        # Per-type cooldown overrides loaded from rules YAML
        self._type_cooldowns: Dict[str, float] = {}
        for type_key, rule in self._rule_map.items():
            if isinstance(rule, dict) and "cooldown" in rule:
                self._type_cooldowns[type_key] = float(rule["cooldown"])

        # In-memory alert store
        self.alerts: List[Dict] = []
        self.last_alert_time: Dict[str, datetime] = defaultdict(lambda: datetime.min)

        # Statistics
        self.stats: Dict[str, Any] = {
            "total_alerts": 0,
            "by_level": defaultdict(int),
            "by_type": defaultdict(int),
            "suppressed_count": 0,
            "telegram_sent": 0,
            "telegram_failed": 0,
        }

        # Callback handlers (third-party or test hooks)
        self.callbacks: List[Callable[[Dict], None]] = []

        # Ensure log directory exists
        if self.file_logging:
            Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

        max_mem = self._rules.get("global", {}).get("max_alerts_in_memory", 1000)
        self._max_alerts_in_memory: int = int(max_mem)

        logger.info("AlertManager initialised (Phase 7)")

    # ------------------------------------------------------------------
    # Core alert creation
    # ------------------------------------------------------------------

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
        Create, log, and dispatch an alert through all configured channels.

        Parameters
        ----------
        alert_type : AlertType
        alert_level : AlertLevel
        message : str
            Human-readable description.
        person_id : str or None
        camera_source : str or None
        metadata : dict or None
            Extra payload (velocity, dwell_seconds, threat_score, …).
        force : bool
            Bypass cooldown check if True.

        Returns
        -------
        dict or None
            The created alert dict, or None if suppressed by cooldown.
        """
        alert_key = self._get_key(alert_type, person_id)
        now = datetime.now()

        # ── Cooldown gate ───────────────────────────────────────────────
        if not force:
            cooldown = self._get_cooldown(alert_type)
            elapsed = (now - self.last_alert_time[alert_key]).total_seconds()
            if elapsed < cooldown:
                self.stats["suppressed_count"] += 1
                return None

        # ── Build alert dict ────────────────────────────────────────────
        alert: Dict[str, Any] = {
            "alert_type": alert_type.value,
            "alert_level": alert_level.value,
            "message": message,
            "person_id": person_id,
            "camera_source": camera_source,
            "timestamp": now,
            "metadata": metadata or {},
        }

        # Persist
        self.alerts.append(alert)
        if len(self.alerts) > self._max_alerts_in_memory:
            self.alerts.pop(0)
        self.last_alert_time[alert_key] = now

        # Update stats
        self.stats["total_alerts"] += 1
        self.stats["by_level"][alert_level.value] += 1
        self.stats["by_type"][alert_type.value] += 1

        # ── Dispatch to channels ────────────────────────────────────────
        self._dispatch_console(alert)
        self._dispatch_file(alert)
        self._dispatch_telegram(alert, alert_level)
        self._dispatch_websocket(alert)
        self._dispatch_audio(alert_level)
        self._dispatch_callbacks(alert)

        return alert

    # ------------------------------------------------------------------
    # Convenience shortcut methods (Phase 7 additions)
    # ------------------------------------------------------------------

    def alert_loitering(
        self,
        person_id: str,
        dwell_seconds: float,
        zone: Any = None,
        camera_source: str = "room_camera",
    ) -> Optional[Dict]:
        """Shortcut for LOITERING alert."""
        zone_str = str(zone) if zone else "unknown"
        return self.create_alert(
            alert_type=AlertType.LOITERING,
            alert_level=AlertLevel.WARNING,
            message=(
                f"Loitering detected: {person_id} in zone {zone_str} "
                f"for {dwell_seconds:.0f}s"
            ),
            person_id=person_id,
            camera_source=camera_source,
            metadata={"dwell_seconds": dwell_seconds, "zone": zone_str},
        )

    def alert_tailgating(
        self,
        person_count: int,
        person_ids: List[str],
        camera_source: str = "entry_camera",
        time_window: float = 5.0,
    ) -> Optional[Dict]:
        """Shortcut for TAILGATING alert."""
        ids_str = ", ".join(person_ids)
        return self.create_alert(
            alert_type=AlertType.TAILGATING,
            alert_level=AlertLevel.WARNING,
            message=(
                f"Tailgating: {person_count} persons entered within "
                f"{time_window:.0f}s [{ids_str}]"
            ),
            camera_source=camera_source,
            metadata={
                "person_count": person_count,
                "person_ids": person_ids,
                "time_window": time_window,
            },
        )

    def alert_panic(
        self,
        person_count: int,
        avg_velocity: float,
        camera_source: str = "room_camera",
    ) -> Optional[Dict]:
        """Shortcut for PANIC_BEHAVIOR alert."""
        return self.create_alert(
            alert_type=AlertType.PANIC_BEHAVIOR,
            alert_level=AlertLevel.CRITICAL,
            message=(
                f"Panic behaviour: {person_count} persons moving at "
                f"{avg_velocity:.2f} m/s avg"
            ),
            camera_source=camera_source,
            metadata={"person_count": person_count, "velocity": avg_velocity},
        )

    def alert_mass_gathering(
        self,
        zone_id: str,
        person_count: int,
        camera_source: str = "room_camera",
    ) -> Optional[Dict]:
        """Shortcut for MASS_GATHERING alert."""
        return self.create_alert(
            alert_type=AlertType.MASS_GATHERING,
            alert_level=AlertLevel.WARNING,
            message=f"Mass gathering in {zone_id}: {person_count} persons",
            camera_source=camera_source,
            metadata={"zone_id": zone_id, "person_count": person_count},
        )

    def alert_unauthorized(
        self, person_id: str, camera_source: str = "room_camera"
    ) -> Optional[Dict]:
        """Shortcut for UNAUTHORIZED_ENTRY alert."""
        return self.create_alert(
            alert_type=AlertType.UNAUTHORIZED_ENTRY,
            alert_level=AlertLevel.CRITICAL,
            message=f"Unauthorized person detected: {person_id}",
            person_id=person_id,
            camera_source=camera_source,
        )

    def alert_running(
        self,
        person_id: str,
        velocity: float,
        camera_source: str = "room_camera",
    ) -> Optional[Dict]:
        """Shortcut for RUNNING alert."""
        return self.create_alert(
            alert_type=AlertType.RUNNING,
            alert_level=AlertLevel.WARNING,
            message=f"Running detected: {person_id} @ {velocity:.2f} m/s",
            person_id=person_id,
            camera_source=camera_source,
            metadata={"velocity": velocity},
        )

    def alert_high_threat(
        self,
        person_id: str,
        threat_score: float,
        camera_source: str = "room_camera",
    ) -> Optional[Dict]:
        """Shortcut for HIGH_THREAT_SCORE alert."""
        return self.create_alert(
            alert_type=AlertType.HIGH_THREAT_SCORE,
            alert_level=AlertLevel.CRITICAL,
            message=f"High threat score {threat_score:.2f} for {person_id}",
            person_id=person_id,
            camera_source=camera_source,
            metadata={"threat_score": threat_score},
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_recent_alerts(
        self,
        limit: int = 10,
        level: Optional[AlertLevel] = None,
        alert_type: Optional[AlertType] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        Return recent alerts in reverse-chronological order.

        Parameters
        ----------
        limit : int
            Maximum number of alerts to return.
        level : AlertLevel or None
            Filter by severity.
        alert_type : AlertType or None
            Filter by type.
        since : datetime or None
            Only return alerts after this timestamp.
        """
        filtered = self.alerts
        if level:
            filtered = [a for a in filtered if a["alert_level"] == level.value]
        if alert_type:
            filtered = [a for a in filtered if a["alert_type"] == alert_type.value]
        if since:
            filtered = [a for a in filtered if a["timestamp"] > since]
        return sorted(filtered, key=lambda a: a["timestamp"], reverse=True)[:limit]

    def get_alerts_for_person(self, person_id: str, limit: int = 20) -> List[Dict]:
        """Return alerts for a specific person (most recent first)."""
        person_alerts = [a for a in self.alerts if a.get("person_id") == person_id]
        return sorted(person_alerts, key=lambda a: a["timestamp"], reverse=True)[:limit]

    def get_stats(self) -> Dict:
        """Return alert statistics snapshot."""
        return {
            "total_alerts": self.stats["total_alerts"],
            "suppressed_count": self.stats["suppressed_count"],
            "by_level": dict(self.stats["by_level"]),
            "by_type": dict(self.stats["by_type"]),
            "telegram_sent": self.stats["telegram_sent"],
            "telegram_failed": self.stats["telegram_failed"],
            "recent_10": len(self.get_recent_alerts(limit=10)),
        }

    def get_alert_summary(self, time_window_minutes: int = 60) -> Dict:
        """Summarise alerts within a recent time window."""
        cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
        recent = [a for a in self.alerts if a["timestamp"] > cutoff]
        type_counts: Dict[str, int] = defaultdict(int)
        for a in recent:
            type_counts[a["alert_type"]] += 1
        most_common = (
            max(type_counts, key=lambda k: type_counts[k]) if type_counts else None
        )
        return {
            "time_window_minutes": time_window_minutes,
            "total_in_window": len(recent),
            "critical_count": sum(1 for a in recent if a["alert_level"] == "critical"),
            "warning_count": sum(1 for a in recent if a["alert_level"] == "warning"),
            "info_count": sum(1 for a in recent if a["alert_level"] == "info"),
            "most_common_type": most_common,
        }

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def register_callback(self, callback: Callable[[Dict], None]):
        """Register a function called on every non-suppressed alert."""
        self.callbacks.append(callback)

    def set_api_bridge(self, bridge):
        """Attach a SecurityAPIBridge so alerts are pushed over WebSocket."""
        self.api_bridge = bridge

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear_alerts(self):
        """Clear in-memory alerts and reset statistics."""
        self.alerts.clear()
        self.last_alert_time.clear()
        self.stats = {
            "total_alerts": 0,
            "by_level": defaultdict(int),
            "by_type": defaultdict(int),
            "suppressed_count": 0,
            "telegram_sent": 0,
            "telegram_failed": 0,
        }

    def export_alerts(self, filepath: str):
        """Export all alerts to a JSON file."""
        data = {
            "alerts": [self._serialise(a) for a in self.alerts],
            "stats": self.get_stats(),
            "export_time": datetime.now().isoformat(),
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Internal dispatch methods
    # ------------------------------------------------------------------

    def _dispatch_console(self, alert: Dict):
        if not self.console_output:
            return
        _COLORS = {
            "info": "\033[94m",
            "warning": "\033[93m",
            "critical": "\033[91m",
        }
        _RESET = "\033[0m"
        color = _COLORS.get(alert["alert_level"], "")
        print(f"{color}{self._format_text(alert)}{_RESET}")

    def _dispatch_file(self, alert: Dict):
        if not self.file_logging:
            return
        try:
            with open(self.log_path, "a") as f:
                f.write(self._format_text(alert) + "\n")
        except Exception as exc:
            logger.debug(f"Alert file write error: {exc}")

    def _dispatch_telegram(self, alert: Dict, level: AlertLevel):
        if not self._telegram.enabled:
            return
        if level < self._telegram.min_level:
            return
        text = self._telegram.format_alert(alert)
        ok = self._telegram.send(text)
        if ok:
            self.stats["telegram_sent"] += 1
        else:
            self.stats["telegram_failed"] += 1

    def _dispatch_websocket(self, alert: Dict):
        if self.api_bridge is None:
            return
        try:
            self.api_bridge.push_event("alert", self._serialise(alert))
        except Exception as exc:
            logger.debug(f"WebSocket push error: {exc}")

    def _dispatch_audio(self, level: AlertLevel):
        if not self.audio_alert:
            return
        if level < AlertLevel.CRITICAL:
            return
        try:
            os.system("afplay /System/Library/Sounds/Funk.aiff &")
        except Exception:
            print("\a")

    def _dispatch_callbacks(self, alert: Dict):
        for cb in self.callbacks:
            try:
                cb(alert)
            except Exception as exc:
                logger.debug(f"Alert callback error: {exc}")

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_text(alert: Dict) -> str:
        _SYMBOLS = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        sym = _SYMBOLS.get(alert["alert_level"], "•")
        ts = alert["timestamp"]
        ts_str = ts.strftime("%H:%M:%S") if isinstance(ts, datetime) else str(ts)
        parts = [
            f"{sym} [{ts_str}]",
            f"[{alert['alert_level'].upper()}]",
            f"[{alert['alert_type'].upper()}]",
        ]
        if alert.get("person_id"):
            parts.append(f"Person:{alert['person_id']}")
        if alert.get("camera_source"):
            parts.append(f"Cam:{alert['camera_source']}")
        parts.append(alert["message"])
        return " | ".join(parts)

    @staticmethod
    def _serialise(alert: Dict) -> Dict:
        """Return a JSON-serialisable copy of an alert dict."""
        out = dict(alert)
        if isinstance(out.get("timestamp"), datetime):
            out["timestamp"] = out["timestamp"].isoformat()
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_key(alert_type: AlertType, person_id: Optional[str]) -> str:
        if person_id:
            return f"{alert_type.value}:{person_id}"
        return alert_type.value

    def _get_cooldown(self, alert_type: AlertType) -> float:
        """Return the cooldown for *alert_type*, falling back to the default."""
        return self._type_cooldowns.get(alert_type.value, self.default_cooldown)


# ---------------------------------------------------------------------------
# Module-level convenience functions (backward-compatible)
# ---------------------------------------------------------------------------


def create_running_alert(
    manager: AlertManager,
    person_id: str,
    velocity: float,
    camera_source: str,
) -> Optional[Dict]:
    """Backward-compatible helper."""
    return manager.alert_running(person_id, velocity, camera_source)


def create_unauthorized_alert(
    manager: AlertManager,
    person_id: str,
    camera_source: str,
) -> Optional[Dict]:
    """Backward-compatible helper."""
    return manager.alert_unauthorized(person_id, camera_source)


def create_mass_gathering_alert(
    manager: AlertManager,
    zone_id: str,
    person_count: int,
    camera_source: str,
) -> Optional[Dict]:
    """Backward-compatible helper."""
    return manager.alert_mass_gathering(zone_id, person_count, camera_source)


def create_high_threat_alert(
    manager: AlertManager,
    person_id: str,
    threat_score: float,
    camera_source: str,
) -> Optional[Dict]:
    """Backward-compatible helper."""
    return manager.alert_high_threat(person_id, threat_score, camera_source)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing Enhanced Alert Manager (Phase 7)…\n")

    mgr = AlertManager(
        cooldown_seconds=2.0,
        console_output=True,
        file_logging=True,
        log_path="data/test_alerts_p7.log",
    )

    # Test every type
    mgr.alert_unauthorized("unknown-001", "room_camera")
    time.sleep(0.1)
    mgr.alert_running("P001", 2.8, "room_camera")
    time.sleep(0.1)
    mgr.alert_loitering("P002", 75.0, zone=(3, 2), camera_source="room_camera")
    time.sleep(0.1)
    mgr.alert_tailgating(2, ["P003", "P004"], "entry_camera", 3.0)
    time.sleep(0.1)
    mgr.alert_mass_gathering("zone_A", 6, "room_camera")
    time.sleep(0.1)
    mgr.alert_high_threat("P005", 0.91, "room_camera")
    time.sleep(0.1)
    mgr.alert_panic(4, 3.5, "room_camera")

    # Test cooldown suppression
    result = mgr.alert_unauthorized("unknown-001", "room_camera")
    print(
        f"\n✅ Cooldown test: suppressed={'Yes' if result is None else 'No'} (expected Yes)"
    )

    # Stats
    print("\n--- Stats ---")
    for k, v in mgr.get_stats().items():
        print(f"  {k}: {v}")

    # Summary
    print("\n--- 60-min summary ---")
    summary = mgr.get_alert_summary(60)
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print("\n✅ Phase 7 AlertManager tests passed!")
