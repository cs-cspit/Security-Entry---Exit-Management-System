#!/usr/bin/env python3
"""
Enhanced Database Module
========================
Manages visitor entry/exit records, trajectory data, threat events, and alerts.
Supports person state tracking and comprehensive logging.

Phase 1 Implementation - Foundation for Room Tracking System
"""

import json
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


class PersonState(Enum):
    """Person state in the system."""

    WAITING_TO_ENTER = "waiting_to_enter"
    INSIDE_NOW = "inside_now"
    EXITED = "exited"
    UNAUTHORIZED = "unauthorized"


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts the system can generate."""

    RUNNING = "running"
    MASS_GATHERING = "mass_gathering"
    UNAUTHORIZED_ENTRY = "unauthorized_entry"
    HIGH_THREAT_SCORE = "high_threat_score"
    LOITERING = "loitering"
    PANIC_BEHAVIOR = "panic_behavior"


class EnhancedDatabase:
    """
    Enhanced database for tracking visitors, trajectories, and threats.

    Features:
    - Person state management (WAITING/INSIDE/EXITED/UNAUTHORIZED)
    - Trajectory tracking with position history
    - Threat event logging
    - Alert management
    - SQLite persistence
    - Export to JSON/CSV
    """

    def __init__(self, db_path: str = "data/security_system.db"):
        """
        Initialize enhanced database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory_exists()

        # In-memory data structures for fast access
        self.people = {}  # {person_id: PersonRecord}
        self.inside_now = {}  # {person_id: PersonRecord} - subset of people
        self.trajectories = defaultdict(list)  # {person_id: [TrajectoryPoint]}
        self.alerts = []  # List of Alert objects
        self.threat_events = []  # List of ThreatEvent objects

        # Global feature database (histograms, embeddings, etc.)
        self.global_features = {}  # {person_id: FeatureData}

        # Statistics
        self.stats = {
            "total_entries": 0,
            "total_exits": 0,
            "total_unauthorized": 0,
            "total_alerts": 0,
            "session_start": datetime.now(),
        }

        # Initialize database schema
        self._init_database()

    def _ensure_directory_exists(self):
        """Ensure the data directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _init_database(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # People table - main records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS people (
                person_id TEXT PRIMARY KEY,
                temp_uuid TEXT,
                permanent_uuid TEXT,
                state TEXT,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                duration_seconds REAL,
                avg_velocity REAL,
                max_velocity REAL,
                threat_score REAL,
                alert_count INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                last_seen TIMESTAMP,
                encounters INTEGER DEFAULT 1,
                face_embedding BLOB
            )
        """)

        # Trajectory data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trajectory_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT,
                camera_source TEXT,
                x REAL,
                y REAL,
                timestamp TIMESTAMP,
                velocity REAL,
                track_id INTEGER,
                FOREIGN KEY (person_id) REFERENCES people(person_id)
            )
        """)

        # Migration: add track_id column if it doesn't exist (for existing DBs)
        try:
            cursor.execute("ALTER TABLE trajectory_data ADD COLUMN track_id INTEGER")
        except Exception:
            pass  # Column already exists — safe to ignore

        # Migration: add people columns missing from older DB schemas
        _people_migrations = [
            "ALTER TABLE people ADD COLUMN last_seen TIMESTAMP",
            "ALTER TABLE people ADD COLUMN encounters INTEGER DEFAULT 1",
            "ALTER TABLE people ADD COLUMN face_embedding BLOB",
        ]
        for _stmt in _people_migrations:
            try:
                cursor.execute(_stmt)
            except Exception:
                pass  # Column already exists — safe to ignore

        # Threat events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threat_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT,
                event_type TEXT,
                threat_score REAL,
                velocity REAL,
                trajectory_entropy REAL,
                proximity_density REAL,
                timestamp TIMESTAMP,
                camera_source TEXT,
                metadata TEXT,
                FOREIGN KEY (person_id) REFERENCES people(person_id)
            )
        """)

        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                alert_level TEXT,
                person_id TEXT,
                camera_source TEXT,
                message TEXT,
                timestamp TIMESTAMP,
                acknowledged BOOLEAN DEFAULT 0,
                metadata TEXT
            )
        """)

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_entries INTEGER,
                total_exits INTEGER,
                total_alerts INTEGER,
                config_snapshot TEXT
            )
        """)

        conn.commit()
        conn.close()

    # ========================================================================
    # Person Management
    # ========================================================================

    def add_person(
        self,
        person_id: str,
        state: PersonState = PersonState.WAITING_TO_ENTER,
        histogram=None,
        body_features=None,
        face_embedding=None,
    ) -> Dict:
        """
        Add a new person to the database.

        Args:
            person_id: Unique identifier (temporary UUID)
            state: Initial state
            histogram: Face histogram for matching
            body_features: Body feature vector for matching
            face_embedding: Face embedding from InsightFace (512D numpy array)

        Returns:
            Person record dictionary
        """
        now = datetime.now()

        person_record = {
            "person_id": person_id,
            "temp_uuid": person_id,
            "permanent_uuid": None,
            "state": state.value,
            "entry_time": None,
            "exit_time": None,
            "duration_seconds": 0.0,
            "avg_velocity": 0.0,
            "max_velocity": 0.0,
            "threat_score": 0.0,
            "alert_count": 0,
            "created_at": now,
            "last_seen": now,
            "last_position": None,
            "encounters": 0,
        }

        self.people[person_id] = person_record

        # Store features (includes face embedding for later BLOB serialization)
        self.global_features[person_id] = {
            "histogram": histogram,
            "body_features": body_features,
            "face_embedding": face_embedding,
            "first_seen": now,
        }

        # Persist initial record to SQLite right away
        self._persist_person_to_db(person_record)

        return person_record

    def update_person_state(self, person_id: str, state: PersonState):
        """Update person's state."""
        if person_id in self.people:
            self.people[person_id]["state"] = state.value

    def get_person(self, person_id: str) -> Optional[Dict]:
        """Get person record by ID."""
        return self.people.get(person_id)

    def get_people_by_state(self, state: PersonState) -> List[Dict]:
        """Get all people in a specific state."""
        return [
            person for person in self.people.values() if person["state"] == state.value
        ]

    # ========================================================================
    # Entry/Exit Management
    # ========================================================================

    def record_entry(self, person_id: str) -> bool:
        """
        Record a person entering through the entry gate.
        Immediately persists the entry record to SQLite.

        Args:
            person_id: Person identifier

        Returns:
            True if new entry, False if already inside
        """
        now = datetime.now()

        if person_id not in self.people:
            self.add_person(person_id)

        person = self.people[person_id]

        if person["state"] != PersonState.INSIDE_NOW.value:
            # New entry
            person["entry_time"] = now
            person["state"] = PersonState.INSIDE_NOW.value
            person["encounters"] = 1
            self.inside_now[person_id] = person
            self.stats["total_entries"] += 1

            # Persist entry to SQLite immediately (don't wait for exit)
            self._persist_person_to_db(person)

            return True
        else:
            # Already inside, increment encounters
            person["encounters"] += 1
            self._persist_person_to_db(person)
            return False

    def record_exit(self, person_id: str) -> bool:
        """
        Record a person exiting through the exit gate.

        Args:
            person_id: Person identifier

        Returns:
            True if successful exit, False if not inside
        """
        now = datetime.now()

        if person_id not in self.inside_now:
            return False

        person = self.inside_now[person_id]

        # Calculate duration
        if person["entry_time"]:
            duration = (now - person["entry_time"]).total_seconds()
            person["duration_seconds"] = duration

        person["exit_time"] = now
        person["state"] = PersonState.EXITED.value

        # Generate permanent UUID
        person["permanent_uuid"] = str(uuid.uuid4())

        # Remove from inside_now
        del self.inside_now[person_id]

        self.stats["total_exits"] += 1

        # Persist to database
        self._persist_person_to_db(person)

        return True

    def record_unauthorized_entry(self, temp_id: str, camera_source: str) -> str:
        """
        Record detection of unauthorized person (no entry gate record).

        Args:
            temp_id: Temporary identifier for tracking
            camera_source: Which camera detected them

        Returns:
            Person ID for tracking
        """
        person_id = f"UNAUTH-{temp_id}"

        if person_id not in self.people:
            self.add_person(person_id, state=PersonState.UNAUTHORIZED)
            self.stats["total_unauthorized"] += 1

            # Create alert
            self.create_alert(
                alert_type=AlertType.UNAUTHORIZED_ENTRY,
                alert_level=AlertLevel.CRITICAL,
                person_id=person_id,
                camera_source=camera_source,
                message=f"Unauthorized person detected: {person_id}",
            )

        return person_id

    # ========================================================================
    # Trajectory Tracking
    # ========================================================================

    def add_trajectory_point(
        self,
        person_id: str,
        x: float,
        y: float,
        camera_source: str,
        velocity: float = 0.0,
        timestamp: Optional[datetime] = None,
        track_id: Optional[int] = None,
    ):
        """
        Add a trajectory point for a person.

        Args:
            person_id: Person identifier
            x: X coordinate (pixels or meters)
            y: Y coordinate (pixels or meters)
            camera_source: Which camera recorded this
            velocity: Instantaneous velocity (m/s)
            timestamp: Time of observation (default: now)
            track_id: ByteTrack stable track ID (Phase 6, optional)
        """
        if timestamp is None:
            timestamp = datetime.now()

        trajectory_point = {
            "x": x,
            "y": y,
            "timestamp": timestamp,
            "velocity": velocity,
            "camera_source": camera_source,
            "track_id": track_id,
        }

        self.trajectories[person_id].append(trajectory_point)

        # Update person's position and velocity
        if person_id in self.people:
            person = self.people[person_id]
            person["last_position"] = (x, y)
            person["last_seen"] = timestamp

            # Update max velocity
            if velocity > person["max_velocity"]:
                person["max_velocity"] = velocity

    def get_trajectory(self, person_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get trajectory history for a person.

        Args:
            person_id: Person identifier
            limit: Max number of points to return (most recent)

        Returns:
            List of trajectory points
        """
        trajectory = self.trajectories.get(person_id, [])
        if limit:
            return trajectory[-limit:]
        return trajectory

    def calculate_avg_velocity(self, person_id: str, window: int = 10) -> float:
        """
        Calculate average velocity over last N trajectory points.

        Args:
            person_id: Person identifier
            window: Number of points to average over

        Returns:
            Average velocity in m/s
        """
        trajectory = self.get_trajectory(person_id, limit=window)

        if len(trajectory) < 2:
            return 0.0

        velocities = [
            point["velocity"] for point in trajectory if point["velocity"] > 0
        ]

        if not velocities:
            return 0.0

        return sum(velocities) / len(velocities)

    # ========================================================================
    # Threat & Alert Management
    # ========================================================================

    def create_alert(
        self,
        alert_type: AlertType,
        alert_level: AlertLevel,
        person_id: Optional[str] = None,
        camera_source: Optional[str] = None,
        message: str = "",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Create and log an alert.

        Args:
            alert_type: Type of alert
            alert_level: Severity level
            person_id: Associated person (if any)
            camera_source: Camera that triggered alert
            message: Human-readable message
            metadata: Additional data

        Returns:
            Alert record
        """
        now = datetime.now()

        alert = {
            "alert_type": alert_type.value,
            "alert_level": alert_level.value,
            "person_id": person_id,
            "camera_source": camera_source,
            "message": message,
            "timestamp": now,
            "acknowledged": False,
            "metadata": metadata or {},
        }

        self.alerts.append(alert)
        self.stats["total_alerts"] += 1

        # Update person's alert count
        if person_id and person_id in self.people:
            self.people[person_id]["alert_count"] += 1

        # Persist to database
        self._persist_alert_to_db(alert)

        return alert

    def record_threat_event(
        self,
        person_id: str,
        event_type: str,
        threat_score: float,
        velocity: float = 0.0,
        trajectory_entropy: float = 0.0,
        proximity_density: float = 0.0,
        camera_source: str = "unknown",
        metadata: Optional[Dict] = None,
    ):
        """
        Record a threat detection event.

        Args:
            person_id: Person identifier
            event_type: Type of threat (e.g., "running", "fighting")
            threat_score: Overall threat score (0-1)
            velocity: Current velocity
            trajectory_entropy: Path chaos measure
            proximity_density: Crowding measure
            camera_source: Which camera detected it
            metadata: Additional data
        """
        now = datetime.now()

        threat_event = {
            "person_id": person_id,
            "event_type": event_type,
            "threat_score": threat_score,
            "velocity": velocity,
            "trajectory_entropy": trajectory_entropy,
            "proximity_density": proximity_density,
            "timestamp": now,
            "camera_source": camera_source,
            "metadata": metadata or {},
        }

        self.threat_events.append(threat_event)

        # Update person's threat score
        if person_id in self.people:
            self.people[person_id]["threat_score"] = max(
                self.people[person_id]["threat_score"], threat_score
            )

        # Persist to database
        self._persist_threat_event_to_db(threat_event)

    def get_recent_alerts(
        self, limit: int = 10, level: Optional[AlertLevel] = None
    ) -> List[Dict]:
        """
        Get recent alerts.

        Args:
            limit: Max number of alerts to return
            level: Filter by alert level (optional)

        Returns:
            List of alert records
        """
        alerts = self.alerts

        if level:
            alerts = [a for a in alerts if a["alert_level"] == level.value]

        return sorted(alerts, key=lambda a: a["timestamp"], reverse=True)[:limit]

    # ========================================================================
    # Statistics & Reporting
    # ========================================================================

    def get_stats(self) -> Dict:
        """Get current system statistics."""
        return {
            "currently_inside": len(self.inside_now),
            "total_entries": self.stats["total_entries"],
            "total_exits": self.stats["total_exits"],
            "total_unauthorized": self.stats["total_unauthorized"],
            "total_alerts": self.stats["total_alerts"],
            "unique_visitors": len(self.people),
            "session_duration": (
                datetime.now() - self.stats["session_start"]
            ).total_seconds(),
        }

    def get_person_summary(self, person_id: str) -> Optional[Dict]:
        """Get comprehensive summary for a person."""
        if person_id not in self.people:
            return None

        person = self.people[person_id]
        trajectory = self.get_trajectory(person_id)

        return {
            "person": person,
            "trajectory_points": len(trajectory),
            "avg_velocity": self.calculate_avg_velocity(person_id),
            "alerts": len([a for a in self.alerts if a["person_id"] == person_id]),
            "threat_events": len(
                [t for t in self.threat_events if t["person_id"] == person_id]
            ),
        }

    # ========================================================================
    # Database Persistence
    # ========================================================================

    def _persist_person_to_db(self, person: Dict):
        """Save person record to SQLite database, including face embedding BLOB."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Serialize face embedding as BLOB if available
        face_embedding_blob = None
        person_id = person["person_id"]
        if person_id in self.global_features:
            face_emb = self.global_features[person_id].get("face_embedding")
            if face_emb is not None:
                try:
                    face_embedding_blob = np.array(face_emb, dtype=np.float32).tobytes()
                except Exception:
                    face_embedding_blob = None

        now = datetime.now()
        cursor.execute(
            """
            INSERT OR REPLACE INTO people (
                person_id, temp_uuid, permanent_uuid, state,
                entry_time, exit_time, duration_seconds,
                avg_velocity, max_velocity, threat_score, alert_count,
                created_at, last_seen,
                face_embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                person["person_id"],
                person["temp_uuid"],
                person["permanent_uuid"],
                person["state"],
                person.get("entry_time"),
                person.get("exit_time"),
                person.get("duration_seconds", 0.0),
                person.get("avg_velocity", 0.0),
                person.get("max_velocity", 0.0),
                person.get("threat_score", 0.0),
                person.get("alert_count", 0),
                person.get("created_at", now),
                person.get("last_seen", now),
                face_embedding_blob,
            ),
        )

        conn.commit()
        conn.close()

    def _persist_alert_to_db(self, alert: Dict):
        """Save alert to SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO alerts (
                alert_type, alert_level, person_id, camera_source,
                message, timestamp, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                alert["alert_type"],
                alert["alert_level"],
                alert["person_id"],
                alert["camera_source"],
                alert["message"],
                alert["timestamp"],
                json.dumps(alert["metadata"]),
            ),
        )

        conn.commit()
        conn.close()

    def _persist_threat_event_to_db(self, event: Dict):
        """Save threat event to SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO threat_events (
                person_id, event_type, threat_score, velocity,
                trajectory_entropy, proximity_density, timestamp,
                camera_source, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                event["person_id"],
                event["event_type"],
                event["threat_score"],
                event["velocity"],
                event["trajectory_entropy"],
                event["proximity_density"],
                event["timestamp"],
                event["camera_source"],
                json.dumps(event["metadata"]),
            ),
        )

        conn.commit()
        conn.close()

    def persist_trajectory_batch(self, person_id: str, sample_rate: int = 5):
        """
        Save trajectory data to database (sampled).

        Args:
            person_id: Person identifier
            sample_rate: Save every Nth point
        """
        trajectory = self.trajectories.get(person_id, [])

        if not trajectory:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sample trajectory points
        sampled = trajectory[::sample_rate]

        for point in sampled:
            cursor.execute(
                """
                INSERT INTO trajectory_data (
                    person_id, camera_source, x, y, timestamp, velocity, track_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    person_id,
                    point["camera_source"],
                    point["x"],
                    point["y"],
                    point["timestamp"],
                    point["velocity"],
                    point.get("track_id"),
                ),
            )

        conn.commit()
        conn.close()

    # ========================================================================
    # Export & Cleanup
    # ========================================================================

    def export_to_json(self, filepath: str):
        """Export all data to JSON file."""
        data = {
            "people": list(self.people.values()),
            "alerts": self.alerts,
            "threat_events": self.threat_events,
            "stats": self.get_stats(),
            "export_time": datetime.now().isoformat(),
        }

        # Convert datetime objects to strings
        def json_serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=json_serial)

    def cleanup_old_data(self, retention_days: int = 30):
        """
        Remove old data from database.

        Args:
            retention_days: Keep data newer than this many days
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete old records
        cursor.execute("DELETE FROM people WHERE created_at < ?", (cutoff_date,))
        cursor.execute(
            "DELETE FROM trajectory_data WHERE timestamp < ?", (cutoff_date,)
        )
        cursor.execute("DELETE FROM threat_events WHERE timestamp < ?", (cutoff_date,))
        cursor.execute("DELETE FROM alerts WHERE timestamp < ?", (cutoff_date,))

        conn.commit()
        conn.close()

    def close(self):
        """Close database connections and save state."""
        # Persist all trajectories
        for person_id in self.trajectories.keys():
            self.persist_trajectory_batch(person_id)

        # Export to JSON
        export_path = Path(self.db_path).parent / "last_session.json"
        self.export_to_json(str(export_path))


if __name__ == "__main__":
    # Test the enhanced database
    print("Testing Enhanced Database...")

    db = EnhancedDatabase("data/test_security.db")

    # Test person management
    person_id = "test-123"
    db.add_person(person_id)
    db.record_entry(person_id)

    # Test trajectory
    db.add_trajectory_point(person_id, 100, 200, "room_camera", velocity=1.5)
    db.add_trajectory_point(person_id, 110, 210, "room_camera", velocity=2.0)

    # Test alert
    db.create_alert(
        alert_type=AlertType.RUNNING,
        alert_level=AlertLevel.WARNING,
        person_id=person_id,
        camera_source="room_camera",
        message="Person running detected",
    )

    # Test stats
    stats = db.get_stats()
    print(f"\nStats: {stats}")

    # Test exit
    db.record_exit(person_id)

    print("\n✅ Enhanced Database tests passed!")
    db.close()
