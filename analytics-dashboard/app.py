#!/usr/bin/env python3
"""
Analytics Dashboard - Flask Backend
====================================
Production-grade backend that reads REAL analytics data from the
YOLO26 complete security system database.

Key principles:
  - Single shared database: ../data/yolo26_complete_system.db
    (written by yolo26_complete_system.py, read by this dashboard)
  - Camera streams / status are proxied from the FastAPI bridge on port 8000
  - No standalone camera_bridge — yolo26_complete_system.py IS the camera system
  - WAL mode SQLite for safe concurrent reads
"""

import atexit
import os
import signal as _signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Shared database written by yolo26_complete_system.py
# ---------------------------------------------------------------------------
LIVE_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "yolo26_complete_system.db")
)

# ---------------------------------------------------------------------------
# FastAPI bridge (yolo26_complete_system.py runs this on port 8000)
# ---------------------------------------------------------------------------
FASTAPI_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Subprocess management — launch / stop yolo26_complete_system.py
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PYTHON_EXEC = os.path.join(_PROJECT_ROOT, "venv", "bin", "python")
_MAIN_SCRIPT = os.path.join(_PROJECT_ROOT, "yolo26_complete_system.py")

_system_process: subprocess.Popen = None  # type: ignore[assignment]
_process_lock = threading.Lock()


def _is_port_in_use(port: int) -> bool:
    """Quick check — returns True if something is already listening on port."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_system_process(**kwargs) -> dict:
    """
    Launch yolo26_complete_system.py as a background subprocess.
    If the FastAPI port (8000) is already in use we assume it's already
    running and return 'already_running' without spawning a second instance.
    """
    global _system_process

    # If the FastAPI bridge is already answering, nothing to do.
    if _is_port_in_use(8000):
        return {
            "status": "already_running",
            "message": "Camera system already running on port 8000.",
        }

    with _process_lock:
        # Reap any finished previous process
        if _system_process is not None and _system_process.poll() is not None:
            _system_process = None

        if _system_process is not None:
            return {"status": "already_running", "message": "Process already launched."}

        if not os.path.isfile(_MAIN_SCRIPT):
            return {
                "status": "error",
                "message": f"Main script not found: {_MAIN_SCRIPT}",
            }

        python = _PYTHON_EXEC if os.path.isfile(_PYTHON_EXEC) else sys.executable

        # Build CLI args — forward any camera index overrides passed from UI
        cmd = [python, _MAIN_SCRIPT]
        if "entry_idx" in kwargs:
            cmd += ["--entry", str(kwargs["entry_idx"])]
        if "room_idx" in kwargs:
            cmd += ["--room", str(kwargs["room_idx"])]
        if "exit_idx" in kwargs:
            cmd += ["--exit", str(kwargs["exit_idx"])]

        try:
            _system_process = subprocess.Popen(
                cmd,
                cwd=_PROJECT_ROOT,
                # Inherit stdout/stderr so output appears in the terminal
                # where start.sh is running — useful for debugging.
                stdout=None,
                stderr=None,
            )
            print(
                f"[Dashboard] Launched yolo26_complete_system.py  PID={_system_process.pid}"
            )
            return {
                "status": "starting",
                "pid": _system_process.pid,
                "message": "Camera system is starting up…",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}


def stop_system_process() -> dict:
    """Terminate yolo26_complete_system.py if we launched it."""
    global _system_process

    with _process_lock:
        if _system_process is None:
            return {"status": "not_running", "message": "No managed process to stop."}

        if _system_process.poll() is not None:
            # Already exited on its own
            _system_process = None
            return {"status": "stopped", "message": "Process had already exited."}

        try:
            _system_process.terminate()
            try:
                _system_process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                _system_process.kill()
                _system_process.wait(timeout=3)
            print("[Dashboard] yolo26_complete_system.py terminated.")
        except Exception as exc:
            print(f"[Dashboard] Error stopping process: {exc}")
        finally:
            _system_process = None

    # Invalidate proxy cache so next status check reflects the stopped state
    _proxy_cache["ts"] = 0.0
    return {"status": "stopped", "message": "Camera system stopped."}


def is_system_process_running() -> bool:
    """True if we have a live managed subprocess."""
    with _process_lock:
        return _system_process is not None and _system_process.poll() is None


def ensure_db_schema():
    """Create the database schema (empty tables) if it doesn't exist."""
    os.makedirs(os.path.dirname(LIVE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(LIVE_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_state ON people(state)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_entry ON people(entry_time)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_traj_person ON trajectory_data(person_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_traj_camera ON trajectory_data(camera_source)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_level ON alerts(alert_level)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_threats_ts ON threat_events(timestamp)"
    )

    conn.commit()
    conn.close()
    print(f"[DB] Schema ready: {LIVE_DB_PATH}")


def get_db():
    """Get a read-only database connection with row factory."""
    conn = sqlite3.connect(LIVE_DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ---------------------------------------------------------------------------
# FastAPI bridge proxy
# Replaces the old standalone CameraBridge.
# yolo26_complete_system.py runs the real detection engine and exposes
# a FastAPI server on port 8000 — we just talk to that.
# ---------------------------------------------------------------------------


class _FastAPIProxy:
    """
    Thin object that mimics the old CameraBridge interface so the rest of
    app.py (overview, bridge/status, etc.) keeps working without changes.
    """

    def __init__(self, status: dict):
        self._status = status
        # Map FastAPI status fields → dashboard-expected attributes
        self.mode = "FULL — YOLO26" if status.get("system_running") else "OFF"
        self.stats = {
            "registered": status.get("registered", 0),
            "inside": status.get("inside", 0),
            "exited": status.get("total_exits", 0),
            "unauthorized": status.get("unauthorized_detections", 0),
            "total_detections": status.get("total_entries", 0),
            "entry_detections": 0,
            "room_detections": 0,
            "exit_detections": 0,
            "fps_entry": 0.0,
            "fps_room": 0.0,
            "fps_exit": 0.0,
            "mode": self.mode,
            "cameras_connected": 3 if status.get("system_running") else 0,
            "start_time": None,
        }

    def is_running(self) -> bool:
        return bool(self._status.get("system_running", False))

    def get_stats(self) -> dict:
        return self.stats

    def get_active_people(self) -> list:
        return []


# Cache so we don't hit the FastAPI bridge on every Flask request
_proxy_cache: dict = {"proxy": None, "ts": 0.0}
_PROXY_TTL = 3.0  # seconds


def get_bridge():
    """
    Return a _FastAPIProxy if yolo26_complete_system.py's API is reachable,
    otherwise None.  Result is cached for _PROXY_TTL seconds.
    """
    now = time.time()
    if now - _proxy_cache["ts"] < _PROXY_TTL:
        return _proxy_cache["proxy"]

    proxy = None
    try:
        r = requests.get(f"{FASTAPI_URL}/api/status", timeout=1.5)
        if r.status_code == 200:
            proxy = _FastAPIProxy(r.json())
    except Exception:
        pass

    _proxy_cache["proxy"] = proxy
    _proxy_cache["ts"] = now
    return proxy


def is_bridge_running() -> bool:
    bridge = get_bridge()
    return bridge is not None and bridge.is_running()


def stop_bridge():
    """No-op — lifecycle is controlled by yolo26_complete_system.py."""
    pass


# ---------------------------------------------------------------------------
# Helper: safe table count (returns 0 if table is empty or doesn't exist)
# ---------------------------------------------------------------------------
def safe_count(cur, query, params=None):
    try:
        row = cur.execute(query, params or []).fetchone()
        return row[0] if row and row[0] else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve main dashboard page."""
    bridge_running = is_bridge_running()
    bridge = get_bridge()
    bridge_mode = bridge.mode if bridge_running and bridge else "OFF"
    return render_template(
        "index.html",
        bridge_running=bridge_running,
        bridge_mode=bridge_mode,
    )


@app.route("/monitor")
def live_monitor():
    """Serve the live monitor page — cameras + analytics side by side."""
    bridge = get_bridge()
    bridge_running = bridge is not None and bridge.is_running()
    bridge_mode = bridge.mode if bridge_running else "OFF"
    return render_template(
        "live_monitor.html",
        bridge_running=bridge_running,
        bridge_mode=bridge_mode,
    )


# ---------------------------------------------------------------------------
# API: Overview / KPI
# ---------------------------------------------------------------------------


@app.route("/api/overview")
def api_overview():
    """Return high-level KPI numbers — all from REAL data only."""
    conn = get_db()
    cur = conn.cursor()

    total_people = safe_count(cur, "SELECT COUNT(*) FROM people")
    currently_inside = safe_count(
        cur, "SELECT COUNT(*) FROM people WHERE state = 'inside_now'"
    )
    total_entries = safe_count(
        cur, "SELECT COUNT(*) FROM people WHERE entry_time IS NOT NULL"
    )
    total_exits = safe_count(cur, "SELECT COUNT(*) FROM people WHERE state = 'exited'")
    total_unauthorized = safe_count(
        cur, "SELECT COUNT(*) FROM people WHERE state = 'unauthorized'"
    )
    total_alerts = safe_count(cur, "SELECT COUNT(*) FROM alerts")
    critical_alerts = safe_count(
        cur, "SELECT COUNT(*) FROM alerts WHERE alert_level = 'critical'"
    )
    total_threats = safe_count(cur, "SELECT COUNT(*) FROM threat_events")

    avg_duration_row = cur.execute(
        "SELECT AVG(duration_seconds) FROM people WHERE duration_seconds > 0"
    ).fetchone()
    avg_duration = (
        avg_duration_row[0] if avg_duration_row and avg_duration_row[0] else 0
    )

    avg_threat_row = cur.execute(
        "SELECT AVG(threat_score) FROM people WHERE threat_score > 0"
    ).fetchone()
    avg_threat = avg_threat_row[0] if avg_threat_row and avg_threat_row[0] else 0

    max_threat_row = cur.execute("SELECT MAX(threat_score) FROM people").fetchone()
    max_threat = max_threat_row[0] if max_threat_row and max_threat_row[0] else 0

    avg_velocity_row = cur.execute(
        "SELECT AVG(avg_velocity) FROM people WHERE avg_velocity > 0"
    ).fetchone()
    avg_velocity = (
        avg_velocity_row[0] if avg_velocity_row and avg_velocity_row[0] else 0
    )

    conn.close()

    bridge = get_bridge()
    bridge_running = bridge is not None and bridge.is_running()

    return jsonify(
        {
            "total_people": total_people,
            "currently_inside": currently_inside,
            "total_entries": total_entries,
            "total_exits": total_exits,
            "total_unauthorized": total_unauthorized,
            "total_alerts": total_alerts,
            "critical_alerts": critical_alerts,
            "total_threats": total_threats,
            "avg_duration_seconds": round(avg_duration, 1),
            "avg_threat_score": round(avg_threat, 3),
            "max_threat_score": round(max_threat, 3),
            "avg_velocity": round(avg_velocity, 2),
            "bridge_running": bridge_running,
            "bridge_mode": bridge.mode if bridge_running else "OFF",
            "has_data": total_people > 0,
        }
    )


# ---------------------------------------------------------------------------
# API: People
# ---------------------------------------------------------------------------


@app.route("/api/people")
def api_people():
    """Return list of people with optional filtering."""
    state = request.args.get("state")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    sort_by = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    allowed_sort = {
        "created_at",
        "entry_time",
        "exit_time",
        "duration_seconds",
        "threat_score",
        "avg_velocity",
        "max_velocity",
        "alert_count",
    }
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    order_sql = "DESC" if order == "desc" else "ASC"

    conn = get_db()
    cur = conn.cursor()

    query = "SELECT * FROM people"
    params = []
    if state:
        query += " WHERE state = ?"
        params.append(state)

    query += f" ORDER BY {sort_by} {order_sql} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = cur.execute(query, params).fetchall()
    total = safe_count(
        cur,
        "SELECT COUNT(*) FROM people" + (" WHERE state = ?" if state else ""),
        [state] if state else [],
    )

    conn.close()
    return jsonify(
        {
            "people": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@app.route("/api/people/<person_id>")
def api_person_detail(person_id):
    """Return full detail for a single person."""
    conn = get_db()
    cur = conn.cursor()

    person = cur.execute(
        "SELECT * FROM people WHERE person_id = ?", (person_id,)
    ).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Person not found"}), 404

    trajectory = cur.execute(
        "SELECT * FROM trajectory_data WHERE person_id = ? ORDER BY timestamp",
        (person_id,),
    ).fetchall()

    alerts = cur.execute(
        "SELECT * FROM alerts WHERE person_id = ? ORDER BY timestamp DESC",
        (person_id,),
    ).fetchall()

    threats = cur.execute(
        "SELECT * FROM threat_events WHERE person_id = ? ORDER BY timestamp DESC",
        (person_id,),
    ).fetchall()

    conn.close()
    return jsonify(
        {
            "person": dict(person),
            "trajectory": [dict(t) for t in trajectory],
            "alerts": [dict(a) for a in alerts],
            "threat_events": [dict(t) for t in threats],
        }
    )


@app.route("/api/people/states")
def api_people_states():
    """Return people count grouped by state."""
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT state, COUNT(*) as count FROM people GROUP BY state"
    ).fetchall()
    conn.close()
    return jsonify({r["state"]: r["count"] for r in rows})


# ---------------------------------------------------------------------------
# API: Alerts
# ---------------------------------------------------------------------------


@app.route("/api/alerts")
def api_alerts():
    """Return alerts with optional filtering."""
    level = request.args.get("level")
    alert_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []
    if level:
        conditions.append("alert_level = ?")
        params.append(level)
    if alert_type:
        conditions.append("alert_type = ?")
        params.append(alert_type)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"SELECT * FROM alerts{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = cur.execute(query, params).fetchall()
    total = safe_count(
        cur,
        f"SELECT COUNT(*) FROM alerts{where}",
        params[:-2] if conditions else [],
    )
    conn.close()

    return jsonify(
        {
            "alerts": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@app.route("/api/alerts/summary")
def api_alerts_summary():
    """Return alert counts grouped by type and level."""
    conn = get_db()
    cur = conn.cursor()

    by_type = cur.execute(
        "SELECT alert_type, COUNT(*) as count FROM alerts GROUP BY alert_type"
    ).fetchall()
    by_level = cur.execute(
        "SELECT alert_level, COUNT(*) as count FROM alerts GROUP BY alert_level"
    ).fetchall()
    by_camera = cur.execute(
        "SELECT camera_source, COUNT(*) as count FROM alerts GROUP BY camera_source"
    ).fetchall()

    conn.close()
    return jsonify(
        {
            "by_type": {r["alert_type"]: r["count"] for r in by_type},
            "by_level": {r["alert_level"]: r["count"] for r in by_level},
            "by_camera": {r["camera_source"]: r["count"] for r in by_camera},
        }
    )


@app.route("/api/alerts/timeline")
def api_alerts_timeline():
    """Return alert counts bucketed by hour for the last 7 days."""
    conn = get_db()
    cur = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    rows = cur.execute(
        """
        SELECT
            strftime('%%Y-%%m-%%dT%%H:00:00', timestamp) as bucket,
            alert_level,
            COUNT(*) as count
        FROM alerts
        WHERE timestamp >= ?
        GROUP BY bucket, alert_level
        ORDER BY bucket
    """,
        (cutoff,),
    ).fetchall()
    conn.close()

    timeline = defaultdict(lambda: {"info": 0, "warning": 0, "critical": 0})
    for r in rows:
        if r["bucket"]:
            timeline[r["bucket"]][r["alert_level"]] = r["count"]

    return jsonify(
        {
            "buckets": sorted(timeline.keys()),
            "data": {k: dict(v) for k, v in sorted(timeline.items())},
        }
    )


# ---------------------------------------------------------------------------
# API: Threat Events
# ---------------------------------------------------------------------------


@app.route("/api/threats")
def api_threats():
    """Return threat events with optional filtering."""
    event_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = (
        f"SELECT * FROM threat_events{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    rows = cur.execute(query, params).fetchall()
    total_params = params[:-2] if conditions else []
    total = safe_count(cur, f"SELECT COUNT(*) FROM threat_events{where}", total_params)
    conn.close()

    return jsonify(
        {
            "threats": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@app.route("/api/threats/summary")
def api_threats_summary():
    """Return threat event statistics."""
    conn = get_db()
    cur = conn.cursor()

    by_type = cur.execute(
        "SELECT event_type, COUNT(*) as count, AVG(threat_score) as avg_score, "
        "MAX(threat_score) as max_score FROM threat_events GROUP BY event_type"
    ).fetchall()

    by_camera = cur.execute(
        "SELECT camera_source, COUNT(*) as count FROM threat_events GROUP BY camera_source"
    ).fetchall()

    score_dist = cur.execute("""
        SELECT
            CASE
                WHEN threat_score < 0.3 THEN 'low'
                WHEN threat_score < 0.6 THEN 'medium'
                WHEN threat_score < 0.8 THEN 'high'
                ELSE 'critical'
            END as severity,
            COUNT(*) as count
        FROM threat_events
        GROUP BY severity
    """).fetchall()

    conn.close()
    return jsonify(
        {
            "by_type": [dict(r) for r in by_type],
            "by_camera": {r["camera_source"]: r["count"] for r in by_camera},
            "score_distribution": {r["severity"]: r["count"] for r in score_dist},
        }
    )


@app.route("/api/threats/timeline")
def api_threats_timeline():
    """Return threat events bucketed by hour for the last 7 days."""
    conn = get_db()
    cur = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    rows = cur.execute(
        """
        SELECT
            strftime('%%Y-%%m-%%dT%%H:00:00', timestamp) as bucket,
            COUNT(*) as count,
            AVG(threat_score) as avg_score
        FROM threat_events
        WHERE timestamp >= ?
        GROUP BY bucket
        ORDER BY bucket
    """,
        (cutoff,),
    ).fetchall()
    conn.close()

    return jsonify(
        {
            "buckets": [r["bucket"] for r in rows if r["bucket"]],
            "counts": [r["count"] for r in rows if r["bucket"]],
            "avg_scores": [round(r["avg_score"], 3) for r in rows if r["bucket"]],
        }
    )


# ---------------------------------------------------------------------------
# API: Trajectories
# ---------------------------------------------------------------------------


@app.route("/api/trajectories/<person_id>")
def api_trajectory(person_id):
    """Return trajectory data for a specific person."""
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM trajectory_data WHERE person_id = ? ORDER BY timestamp",
        (person_id,),
    ).fetchall()
    conn.close()
    return jsonify({"person_id": person_id, "points": [dict(r) for r in rows]})


@app.route("/api/trajectories/heatmap")
def api_heatmap():
    """Return aggregated position data for heatmap visualization."""
    camera = request.args.get("camera", "room_camera")
    conn = get_db()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT x, y, velocity FROM trajectory_data
        WHERE camera_source = ?
        ORDER BY timestamp DESC
        LIMIT 5000
    """,
        (camera,),
    ).fetchall()
    conn.close()

    return jsonify(
        {
            "camera": camera,
            "points": [{"x": r["x"], "y": r["y"], "v": r["velocity"]} for r in rows],
        }
    )


# ---------------------------------------------------------------------------
# API: Velocity analytics
# ---------------------------------------------------------------------------


@app.route("/api/velocity/distribution")
def api_velocity_distribution():
    """Return velocity distribution across all people."""
    conn = get_db()
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            CASE
                WHEN avg_velocity < 1.0 THEN 'Stationary (<1 m/s)'
                WHEN avg_velocity < 2.0 THEN 'Walking (1-2 m/s)'
                WHEN avg_velocity < 4.0 THEN 'Fast Walk (2-4 m/s)'
                ELSE 'Running (>4 m/s)'
            END as category,
            COUNT(*) as count
        FROM people
        WHERE avg_velocity > 0
        GROUP BY category
        ORDER BY MIN(avg_velocity)
    """).fetchall()

    conn.close()
    return jsonify({"distribution": [dict(r) for r in rows]})


@app.route("/api/velocity/top")
def api_velocity_top():
    """Return people with highest velocities."""
    limit = int(request.args.get("limit", 10))
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT person_id, avg_velocity, max_velocity, threat_score, state "
        "FROM people ORDER BY max_velocity DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return jsonify({"top_velocities": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# API: Entry / Exit timeline
# ---------------------------------------------------------------------------


@app.route("/api/entry-exit/timeline")
def api_entry_exit_timeline():
    """Return entry and exit counts bucketed by hour."""
    conn = get_db()
    cur = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=7)).isoformat()

    entries = cur.execute(
        """
        SELECT strftime('%%Y-%%m-%%dT%%H:00:00', entry_time) as bucket, COUNT(*) as count
        FROM people
        WHERE entry_time IS NOT NULL AND entry_time >= ?
        GROUP BY bucket ORDER BY bucket
    """,
        (cutoff,),
    ).fetchall()

    exits = cur.execute(
        """
        SELECT strftime('%%Y-%%m-%%dT%%H:00:00', exit_time) as bucket, COUNT(*) as count
        FROM people
        WHERE exit_time IS NOT NULL AND exit_time >= ?
        GROUP BY bucket ORDER BY bucket
    """,
        (cutoff,),
    ).fetchall()

    conn.close()

    all_buckets = sorted(
        set(
            [r["bucket"] for r in entries if r["bucket"]]
            + [r["bucket"] for r in exits if r["bucket"]]
        )
    )
    entry_map = {r["bucket"]: r["count"] for r in entries if r["bucket"]}
    exit_map = {r["bucket"]: r["count"] for r in exits if r["bucket"]}

    return jsonify(
        {
            "buckets": all_buckets,
            "entries": [entry_map.get(b, 0) for b in all_buckets],
            "exits": [exit_map.get(b, 0) for b in all_buckets],
        }
    )


@app.route("/api/entry-exit/duration")
def api_duration_distribution():
    """Return duration distribution of visits."""
    conn = get_db()
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            CASE
                WHEN duration_seconds < 300 THEN '< 5 min'
                WHEN duration_seconds < 900 THEN '5-15 min'
                WHEN duration_seconds < 1800 THEN '15-30 min'
                WHEN duration_seconds < 3600 THEN '30-60 min'
                ELSE '> 60 min'
            END as bucket,
            COUNT(*) as count,
            AVG(duration_seconds) as avg_duration
        FROM people
        WHERE duration_seconds > 0
        GROUP BY bucket
        ORDER BY MIN(duration_seconds)
    """).fetchall()
    conn.close()

    return jsonify({"distribution": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# API: Sessions
# ---------------------------------------------------------------------------


@app.route("/api/sessions")
def api_sessions():
    """Return recorded sessions."""
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM sessions ORDER BY start_time DESC").fetchall()
    conn.close()
    return jsonify({"sessions": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# API: Search
# ---------------------------------------------------------------------------


@app.route("/api/search")
def api_search():
    """Search across people, alerts, and threat events."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"people": [], "alerts": [], "threats": []})

    conn = get_db()
    cur = conn.cursor()
    wild = f"%{q}%"

    people = cur.execute(
        "SELECT * FROM people WHERE person_id LIKE ? OR state LIKE ? LIMIT 20",
        (wild, wild),
    ).fetchall()

    alerts = cur.execute(
        "SELECT * FROM alerts WHERE message LIKE ? OR person_id LIKE ? OR alert_type LIKE ? "
        "ORDER BY timestamp DESC LIMIT 20",
        (wild, wild, wild),
    ).fetchall()

    threats = cur.execute(
        "SELECT * FROM threat_events WHERE person_id LIKE ? OR event_type LIKE ? "
        "ORDER BY timestamp DESC LIMIT 20",
        (wild, wild),
    ).fetchall()

    conn.close()
    return jsonify(
        {
            "people": [dict(r) for r in people],
            "alerts": [dict(r) for r in alerts],
            "threats": [dict(r) for r in threats],
        }
    )


# ---------------------------------------------------------------------------
# API: Camera-level stats
# ---------------------------------------------------------------------------


@app.route("/api/cameras/stats")
def api_camera_stats():
    """Return per-camera statistics."""
    conn = get_db()
    cur = conn.cursor()

    alert_cam = cur.execute(
        "SELECT camera_source, COUNT(*) as count FROM alerts GROUP BY camera_source"
    ).fetchall()

    traj_cam = cur.execute(
        "SELECT camera_source, COUNT(*) as count FROM trajectory_data GROUP BY camera_source"
    ).fetchall()

    threat_cam = cur.execute(
        "SELECT camera_source, COUNT(*) as count, AVG(threat_score) as avg_threat "
        "FROM threat_events GROUP BY camera_source"
    ).fetchall()

    conn.close()
    return jsonify(
        {
            "alerts_by_camera": {r["camera_source"]: r["count"] for r in alert_cam},
            "trajectory_points_by_camera": {
                r["camera_source"]: r["count"] for r in traj_cam
            },
            "threats_by_camera": [dict(r) for r in threat_cam],
        }
    )


# ---------------------------------------------------------------------------
# API: Real-time feed
# ---------------------------------------------------------------------------


@app.route("/api/live/feed")
def api_live_feed():
    """Return latest events for live-updating panel."""
    conn = get_db()
    cur = conn.cursor()

    latest_alerts = cur.execute(
        "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()

    latest_entries = cur.execute(
        "SELECT person_id, entry_time, state FROM people "
        "WHERE entry_time IS NOT NULL ORDER BY entry_time DESC LIMIT 10"
    ).fetchall()

    inside_count = safe_count(
        cur, "SELECT COUNT(*) FROM people WHERE state = 'inside_now'"
    )

    conn.close()
    return jsonify(
        {
            "latest_alerts": [dict(r) for r in latest_alerts],
            "latest_entries": [dict(r) for r in latest_entries],
            "currently_inside": inside_count,
            "timestamp": datetime.now().isoformat(),
            "bridge_running": is_bridge_running(),
        }
    )


# ---------------------------------------------------------------------------
# API: Database management
# ---------------------------------------------------------------------------


@app.route("/api/db/reset", methods=["POST"])
def api_db_reset():
    """
    Clear ALL data from the database.
    Used when user wants a fresh start without old detection data.
    """
    bridge = get_bridge()
    if bridge and bridge.is_running():
        # Tell the bridge's LiveDatabase to reset
        if hasattr(bridge, "live_db") and bridge.live_db:
            bridge.live_db.reset()
        else:
            # Manual reset
            _reset_database()
    else:
        _reset_database()

    return jsonify(
        {"status": "ok", "message": "Database cleared. All tables are empty."}
    )


def _reset_database():
    """Directly clear all tables."""
    conn = sqlite3.connect(LIVE_DB_PATH, timeout=10)
    cursor = conn.cursor()
    for table in ["trajectory_data", "threat_events", "alerts", "people", "sessions"]:
        cursor.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    print("[DB] Database reset — all tables cleared")


@app.route("/api/db/stats")
def api_db_stats():
    """Return row counts for all tables — useful for debugging."""
    conn = get_db()
    cur = conn.cursor()
    stats = {}
    for table in ["people", "trajectory_data", "threat_events", "alerts", "sessions"]:
        stats[table] = safe_count(cur, f"SELECT COUNT(*) FROM {table}")
    conn.close()
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# ---------------------------------------------------------------------------
# Camera MJPEG Streaming Routes
# Proxy frames from the FastAPI bridge (port 8000) so the dashboard HTML
# doesn't need to know about two different servers.
# ---------------------------------------------------------------------------


@app.route("/video/<camera_name>")
def video_stream(camera_name):
    """Proxy the MJPEG stream from the FastAPI bridge (port 8000)."""
    if camera_name not in ("entry", "room", "exit"):
        return "Invalid camera name", 404

    upstream = f"{FASTAPI_URL}/stream/{camera_name}"

    def _proxy():
        try:
            with requests.get(upstream, stream=True, timeout=(3, None)) as r:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        yield chunk
        except Exception:
            # Yield a blank MJPEG frame so the browser img tag doesn't error
            yield b""

    return Response(
        _proxy(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/video/<camera_name>/snapshot")
def video_snapshot(camera_name):
    """Proxy a single JPEG snapshot from the FastAPI bridge."""
    if camera_name not in ("entry", "room", "exit"):
        return "Invalid camera name", 404

    try:
        r = requests.get(
            f"{FASTAPI_URL}/stream/{camera_name}",
            stream=True,
            timeout=(3, 5),
        )
        # Read one MJPEG frame and return it as a JPEG
        boundary = b"--frame"
        buf = b""
        for chunk in r.iter_content(chunk_size=4096):
            buf += chunk
            start = buf.find(b"\r\n\r\n")
            end = buf.find(boundary, start + 4) if start != -1 else -1
            if start != -1 and end != -1:
                jpeg = buf[start + 4 : end].strip()
                return Response(jpeg, mimetype="image/jpeg")
            if len(buf) > 200_000:
                break
    except Exception:
        pass

    return "No frame available", 503


# ---------------------------------------------------------------------------
# Camera Bridge Control API
# ---------------------------------------------------------------------------


@app.route("/api/bridge/start", methods=["POST"])
def api_bridge_start():
    """
    Launch yolo26_complete_system.py as a subprocess (if not already running)
    and return the startup status so the dashboard JS can poll until ready.
    """
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "entry_idx" in data:
        kwargs["entry_idx"] = int(data["entry_idx"])
    if "room_idx" in data:
        kwargs["room_idx"] = int(data["room_idx"])
    if "exit_idx" in data:
        kwargs["exit_idx"] = int(data["exit_idx"])

    # Invalidate proxy cache so the next status poll is fresh
    _proxy_cache["ts"] = 0.0

    # If FastAPI is already up and answering, just confirm it
    bridge = get_bridge()
    if bridge is not None and bridge.is_running():
        return jsonify(
            {
                "status": "running",
                "mode": bridge.mode,
                "cameras_connected": bridge.stats.get("cameras_connected", 0),
                "message": "Camera system is already running.",
            }
        )

    result = start_system_process(**kwargs)

    if result["status"] == "starting":
        return jsonify(result)  # JS will call pollUntilBridgeReady()
    elif result["status"] == "already_running":
        return jsonify({"status": "starting", **result})  # let JS poll once
    else:
        # error
        return jsonify(result), 500


@app.route("/api/bridge/stop", methods=["POST"])
def api_bridge_stop():
    """Terminate yolo26_complete_system.py."""
    _proxy_cache["ts"] = 0.0
    result = stop_system_process()
    return jsonify(result)


@app.route("/api/bridge/status")
def api_bridge_status():
    """Proxy the FastAPI bridge status from yolo26_complete_system.py."""
    try:
        r = requests.get(f"{FASTAPI_URL}/api/status", timeout=2.0)
        data = r.json()
        return jsonify(
            {
                "running": data.get("system_running", False),
                "starting": False,
                "mode": "FULL — YOLO26" if data.get("system_running") else "OFF",
                "cameras_connected": 3 if data.get("system_running") else 0,
                "stats": {
                    "registered": data.get("registered", 0),
                    "inside": data.get("inside", 0),
                    "exited": data.get("total_exits", 0),
                    "unauthorized": data.get("unauthorized_detections", 0),
                    "total_detections": data.get("total_entries", 0),
                    "mode": "FULL — YOLO26",
                    "cameras_connected": 3,
                },
                "active_people": [],
                "fastapi_url": FASTAPI_URL,
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "running": False,
                "starting": False,
                "mode": "OFF",
                "cameras_connected": 0,
                "stats": {},
                "active_people": [],
                "error": (
                    f"FastAPI bridge unreachable ({exc}). "
                    "Run yolo26_complete_system.py to start the camera system."
                ),
                "fastapi_url": FASTAPI_URL,
            }
        )


# ---------------------------------------------------------------------------
# Startup & Cleanup
# ---------------------------------------------------------------------------


def _cleanup(signum=None, frame=None):
    """Stop any managed subprocess then exit the Flask process."""
    stop_system_process()
    # Re-raise a clean exit so Flask's dev server actually stops.
    sys.exit(0)


atexit.register(stop_system_process)
_signal.signal(_signal.SIGINT, _cleanup)
_signal.signal(_signal.SIGTERM, _cleanup)


if __name__ == "__main__":
    # Always initialize schema (creates empty tables if DB doesn't exist)
    ensure_db_schema()

    print()
    print("=" * 60)
    print("  SECURITY ANALYTICS DASHBOARD — PRODUCTION MODE")
    print("=" * 60)
    print(f"  Database: {LIVE_DB_PATH}")
    print()
    print("  All data comes from REAL camera detections.")
    print("  Tables start empty. Data flows in when cameras are active.")
    print()
    print("  Pages:")
    print("    Dashboard:    http://127.0.0.1:5050/")
    print("    Live Monitor: http://127.0.0.1:5050/monitor")
    print()
    print("  Controls:")
    print("    Start cameras: POST http://127.0.0.1:5050/api/bridge/start")
    print("    Stop cameras:  POST http://127.0.0.1:5050/api/bridge/stop")
    print("    Reset data:    POST http://127.0.0.1:5050/api/db/reset")
    print()

    app.run(debug=False, host="0.0.0.0", port=5050, threaded=True)
