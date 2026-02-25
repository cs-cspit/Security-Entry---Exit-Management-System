#!/usr/bin/env python3
"""
Live Database Module
====================
Direct SQLite writer that immediately persists all security system data.

Unlike EnhancedDatabase (which keeps most data in-memory and only persists
on exit), this module writes EVERY event directly to SQLite so the dashboard
APIs can read real-time data immediately.

This is the single source of truth shared between:
  - CameraBridge (writes detections, trajectories, alerts, threats)
  - Flask API endpoints (reads for dashboard display)

Thread-safe: uses a dedicated writer thread with a queue to avoid
SQLite "database is locked" errors from concurrent access.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Default database path
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "live_security.db")


class LiveDatabase:
    """
    Thread-safe SQLite database that persists all data immediately.

    All write operations are queued and executed by a dedicated writer thread
    to prevent SQLite locking issues. Reads are done directly with short-lived
    connections (SQLite allows concurrent reads).
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # In-memory tracking (for fast lookups by bridge, NOT the source of truth)
        self.people = {}  # {person_id: dict} — mirrors DB for bridge access
        self._lock = threading.Lock()

        # Write queue + writer thread
        self._write_queue = Queue()
        self._running = True
        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="db-writer"
        )

        # Initialize schema
        self._init_schema()

        # Start writer
        self._writer_thread.start()

    # -----------------------------------------------------------------------
    # Schema
    # -----------------------------------------------------------------------
    def _init_schema(self):
        """Create tables if they don't exist. Does NOT insert any demo data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS people (
                person_id TEXT PRIMARY KEY,
                temp_uuid TEXT,
                permanent_uuid TEXT,
                state TEXT,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                duration_seconds REAL DEFAULT 0,
                avg_velocity REAL DEFAULT 0,
                max_velocity REAL DEFAULT 0,
                threat_score REAL DEFAULT 0,
                alert_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trajectory_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT,
                camera_source TEXT,
                x REAL,
                y REAL,
                timestamp TIMESTAMP,
                velocity REAL,
                FOREIGN KEY (person_id) REFERENCES people(person_id)
            )
        """)

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_entries INTEGER DEFAULT 0,
                total_exits INTEGER DEFAULT 0,
                total_alerts INTEGER DEFAULT 0,
                config_snapshot TEXT
            )
        """)

        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_people_state
            ON people(state)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_people_entry_time
            ON people(entry_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trajectory_person
            ON trajectory_data(person_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trajectory_camera
            ON trajectory_data(camera_source)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
            ON alerts(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_level
            ON alerts(alert_level)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_threats_timestamp
            ON threat_events(timestamp)
        """)

        conn.commit()
        conn.close()

    # -----------------------------------------------------------------------
    # Writer thread (serializes all writes to avoid SQLite locking)
    # -----------------------------------------------------------------------
    def _writer_loop(self):
        """Background thread that processes queued write operations."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read perf
        conn.execute("PRAGMA synchronous=NORMAL")

        batch_size = 50
        flush_interval = 0.1  # seconds

        while self._running or not self._write_queue.empty():
            operations = []

            # Collect operations (up to batch_size or until timeout)
            try:
                op = self._write_queue.get(timeout=flush_interval)
                operations.append(op)
                # Drain more if available
                while len(operations) < batch_size:
                    try:
                        op = self._write_queue.get_nowait()
                        operations.append(op)
                    except Empty:
                        break
            except Empty:
                continue

            # Execute batch
            if operations:
                try:
                    cursor = conn.cursor()
                    for sql, params in operations:
                        try:
                            cursor.execute(sql, params)
                        except sqlite3.Error as e:
                            print(
                                f"[LiveDB] SQL error: {e}\n  SQL: {sql}\n  Params: {params}"
                            )
                    conn.commit()
                except sqlite3.Error as e:
                    print(f"[LiveDB] Batch commit error: {e}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass

        conn.close()

    def _enqueue(self, sql: str, params: tuple):
        """Queue a write operation."""
        if self._running:
            self._write_queue.put((sql, params))

    # -----------------------------------------------------------------------
    # Person Management — IMMEDIATE writes
    # -----------------------------------------------------------------------
    def record_entry(self, person_id: str) -> bool:
        """
        Record a person entering. Immediately persists to SQLite.

        Returns True if this is a new entry, False if person already inside.
        """
        now = datetime.now()

        with self._lock:
            if (
                person_id in self.people
                and self.people[person_id].get("state") == "inside_now"
            ):
                # Already inside — increment encounters but don't re-register
                return False

            person = {
                "person_id": person_id,
                "temp_uuid": person_id,
                "permanent_uuid": None,
                "state": "inside_now",
                "entry_time": now,
                "exit_time": None,
                "duration_seconds": 0.0,
                "avg_velocity": 0.0,
                "max_velocity": 0.0,
                "threat_score": 0.0,
                "alert_count": 0,
                "created_at": now,
            }
            self.people[person_id] = person

        # Persist immediately
        self._enqueue(
            """INSERT OR REPLACE INTO people
               (person_id, temp_uuid, permanent_uuid, state,
                entry_time, exit_time, duration_seconds,
                avg_velocity, max_velocity, threat_score, alert_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                person_id,
                None,
                "inside_now",
                now.isoformat(),
                None,
                0.0,
                0.0,
                0.0,
                0.0,
                0,
                now.isoformat(),
            ),
        )

        return True

    def record_exit(self, person_id: str) -> bool:
        """
        Record a person exiting. Calculates duration. Immediately persists.

        Returns True if exit recorded, False if person wasn't inside.
        """
        now = datetime.now()

        with self._lock:
            person = self.people.get(person_id)
            if not person or person.get("state") != "inside_now":
                return False

            entry_time = person.get("entry_time", now)
            if isinstance(entry_time, str):
                try:
                    entry_time = datetime.fromisoformat(entry_time)
                except ValueError:
                    entry_time = now

            duration = (now - entry_time).total_seconds()
            perm_uuid = str(uuid.uuid4())

            person["state"] = "exited"
            person["exit_time"] = now
            person["duration_seconds"] = duration
            person["permanent_uuid"] = perm_uuid

        avg_vel = person.get("avg_velocity", 0.0)
        max_vel = person.get("max_velocity", 0.0)
        threat = person.get("threat_score", 0.0)
        alert_count = person.get("alert_count", 0)

        self._enqueue(
            """UPDATE people SET
                state = ?, exit_time = ?, duration_seconds = ?,
                permanent_uuid = ?, avg_velocity = ?, max_velocity = ?,
                threat_score = ?, alert_count = ?
               WHERE person_id = ?""",
            (
                "exited",
                now.isoformat(),
                round(duration, 2),
                perm_uuid,
                round(avg_vel, 3),
                round(max_vel, 3),
                round(threat, 3),
                alert_count,
                person_id,
            ),
        )

        return True

    def record_unauthorized(self, person_id: str, camera_source: str = "room_camera"):
        """Record detection of an unauthorized person (no entry record)."""
        now = datetime.now()
        unauth_id = (
            person_id if person_id.startswith("UNAUTH-") else f"UNAUTH-{person_id}"
        )

        with self._lock:
            if unauth_id in self.people:
                return unauth_id  # Already recorded
            self.people[unauth_id] = {
                "person_id": unauth_id,
                "state": "unauthorized",
                "entry_time": None,
                "created_at": now,
            }

        self._enqueue(
            """INSERT OR IGNORE INTO people
               (person_id, temp_uuid, state, created_at)
               VALUES (?, ?, ?, ?)""",
            (unauth_id, unauth_id, "unauthorized", now.isoformat()),
        )

        # Also create an alert
        self.create_alert(
            alert_type="unauthorized_entry",
            alert_level="critical",
            person_id=unauth_id,
            camera_source=camera_source,
            message=f"Unauthorized person detected: {unauth_id}",
        )

        return unauth_id

    def update_person_velocity(
        self, person_id: str, avg_velocity: float, max_velocity: float
    ):
        """Update a person's velocity stats."""
        with self._lock:
            if person_id in self.people:
                self.people[person_id]["avg_velocity"] = avg_velocity
                self.people[person_id]["max_velocity"] = max_velocity

        self._enqueue(
            "UPDATE people SET avg_velocity = ?, max_velocity = ? WHERE person_id = ?",
            (round(avg_velocity, 3), round(max_velocity, 3), person_id),
        )

    def update_person_threat(self, person_id: str, threat_score: float):
        """Update a person's threat score (keeps max)."""
        with self._lock:
            if person_id in self.people:
                current = self.people[person_id].get("threat_score", 0.0)
                if threat_score > current:
                    self.people[person_id]["threat_score"] = threat_score

        self._enqueue(
            "UPDATE people SET threat_score = MAX(threat_score, ?) WHERE person_id = ?",
            (round(threat_score, 3), person_id),
        )

    def increment_alert_count(self, person_id: str):
        """Increment a person's alert count."""
        with self._lock:
            if person_id in self.people:
                self.people[person_id]["alert_count"] = (
                    self.people[person_id].get("alert_count", 0) + 1
                )

        self._enqueue(
            "UPDATE people SET alert_count = alert_count + 1 WHERE person_id = ?",
            (person_id,),
        )

    # -----------------------------------------------------------------------
    # Trajectory — IMMEDIATE writes
    # -----------------------------------------------------------------------
    def add_trajectory_point(
        self,
        person_id: str,
        x: float,
        y: float,
        camera_source: str,
        velocity: float = 0.0,
        timestamp: Optional[datetime] = None,
    ):
        """Record a trajectory point. Immediately queued for SQLite write."""
        if timestamp is None:
            timestamp = datetime.now()

        ts_str = (
            timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
        )

        self._enqueue(
            """INSERT INTO trajectory_data
               (person_id, camera_source, x, y, timestamp, velocity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                camera_source,
                round(x, 1),
                round(y, 1),
                ts_str,
                round(velocity, 3),
            ),
        )

        # Also update person's max velocity in memory
        with self._lock:
            if person_id in self.people:
                if velocity > self.people[person_id].get("max_velocity", 0):
                    self.people[person_id]["max_velocity"] = velocity

    # -----------------------------------------------------------------------
    # Alerts — IMMEDIATE writes
    # -----------------------------------------------------------------------
    def create_alert(
        self,
        alert_type: str,
        alert_level: str,
        person_id: Optional[str] = None,
        camera_source: Optional[str] = None,
        message: str = "",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Create an alert. Immediately persisted to SQLite."""
        now = datetime.now()

        # Accept enum values or strings
        if hasattr(alert_type, "value"):
            alert_type = alert_type.value
        if hasattr(alert_level, "value"):
            alert_level = alert_level.value

        alert = {
            "alert_type": str(alert_type),
            "alert_level": str(alert_level),
            "person_id": person_id,
            "camera_source": camera_source,
            "message": message,
            "timestamp": now.isoformat(),
            "metadata": metadata or {},
        }

        self._enqueue(
            """INSERT INTO alerts
               (alert_type, alert_level, person_id, camera_source,
                message, timestamp, acknowledged, metadata)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
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

        # Increment person's alert count
        if person_id:
            self.increment_alert_count(person_id)

        return alert

    # -----------------------------------------------------------------------
    # Threat Events — IMMEDIATE writes
    # -----------------------------------------------------------------------
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
        """Record a threat event. Immediately persisted to SQLite."""
        now = datetime.now()

        if hasattr(event_type, "value"):
            event_type = event_type.value

        self._enqueue(
            """INSERT INTO threat_events
               (person_id, event_type, threat_score, velocity,
                trajectory_entropy, proximity_density, timestamp,
                camera_source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                str(event_type),
                round(threat_score, 3),
                round(velocity, 3),
                round(trajectory_entropy, 3),
                round(proximity_density, 3),
                now.isoformat(),
                camera_source,
                json.dumps(metadata or {}),
            ),
        )

        # Update person's threat score
        self.update_person_threat(person_id, threat_score)

    # -----------------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------------
    def start_session(self, config: Optional[Dict] = None) -> str:
        """Record a new monitoring session start."""
        session_id = f"SESSION-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        now = datetime.now()

        self._enqueue(
            """INSERT OR REPLACE INTO sessions
               (session_id, start_time, total_entries, total_exits,
                total_alerts, config_snapshot)
               VALUES (?, ?, 0, 0, 0, ?)""",
            (session_id, now.isoformat(), json.dumps(config or {})),
        )

        return session_id

    def end_session(self, session_id: str):
        """Record session end with final stats."""
        now = datetime.now()

        # Get stats via a read connection
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cur = conn.cursor()
            entries = cur.execute(
                "SELECT COUNT(*) FROM people WHERE entry_time IS NOT NULL"
            ).fetchone()[0]
            exits = cur.execute(
                "SELECT COUNT(*) FROM people WHERE state = 'exited'"
            ).fetchone()[0]
            alerts = cur.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            conn.close()

            self._enqueue(
                """UPDATE sessions SET
                    end_time = ?, total_entries = ?, total_exits = ?, total_alerts = ?
                   WHERE session_id = ?""",
                (now.isoformat(), entries, exits, alerts, session_id),
            )
        except Exception as e:
            print(f"[LiveDB] Failed to end session: {e}")

    # -----------------------------------------------------------------------
    # Database management
    # -----------------------------------------------------------------------
    def reset(self):
        """
        Clear ALL data from the database. Used when user wants a fresh start.
        Waits for the write queue to drain first.
        """
        # Wait for pending writes to finish
        timeout = 5.0
        start = time.time()
        while not self._write_queue.empty() and (time.time() - start) < timeout:
            time.sleep(0.05)

        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trajectory_data")
        cursor.execute("DELETE FROM threat_events")
        cursor.execute("DELETE FROM alerts")
        cursor.execute("DELETE FROM people")
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()

        with self._lock:
            self.people.clear()

        print("[LiveDB] Database reset — all tables cleared")

    def get_stats_summary(self) -> Dict:
        """Quick stats from in-memory tracking."""
        with self._lock:
            inside = sum(
                1 for p in self.people.values() if p.get("state") == "inside_now"
            )
            exited = sum(1 for p in self.people.values() if p.get("state") == "exited")
            unauth = sum(
                1 for p in self.people.values() if p.get("state") == "unauthorized"
            )
        return {
            "registered": len(self.people),
            "inside": inside,
            "exited": exited,
            "unauthorized": unauth,
            "queue_size": self._write_queue.qsize(),
        }

    def close(self):
        """Stop the writer thread and flush remaining writes."""
        self._running = False
        if self._writer_thread.is_alive():
            self._writer_thread.join(timeout=5.0)
        print("[LiveDB] Database closed")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
