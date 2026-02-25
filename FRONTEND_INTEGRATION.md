# Frontend Integration — SecureVision Analytics Dashboard

**Date:** 2025  
**Status:** ✅ Active  
**Author:** Integration session with Claude Sonnet 4.6

---

## Overview

This document tracks all integration work done to connect the `analytics-dashboard` (Flask frontend on port 5050) with `yolo26_complete_system.py` (the YOLO26 detection backend + FastAPI on port 8000).

Before this work, the two systems were completely disconnected — the dashboard ran its own independent detection engine writing to a separate database. After this integration, the dashboard reads from the real system database and the "Start/Stop Cameras" button directly controls the YOLO26 system process.

---

## Architecture (After Integration)

```
┌──────────────────────────────────────────────────────────────────┐
│               yolo26_complete_system.py  (main backend)          │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────┐   │
│  │ Entry Cam   │   │  Room Cam    │   │   Exit Cam         │   │
│  │ YOLO26+Pose │   │ ByteTrack+   │   │   YOLO26+Pose      │   │
│  │ OSNet+Face  │   │ OSNet ReID   │   │   OSNet+Face       │   │
│  └──────┬──────┘   └──────┬───────┘   └────────┬───────────┘   │
│         └─────────────────┼──────────────────────┘              │
│                           ▼                                      │
│              ┌────────────────────────┐                          │
│              │  EnhancedDatabase      │                          │
│              │  data/yolo26_complete  │                          │
│              │  _system.db  (SQLite)  │                          │
│              └────────────┬───────────┘                          │
│                           │                                      │
│              ┌────────────▼───────────┐                          │
│              │  SecurityAPIBridge     │                          │
│              │  FastAPI on :8000      │                          │
│              │  REST + WebSocket      │                          │
│              │  MJPEG streams         │                          │
│              └────────────────────────┘                          │
└──────────────────────────────────────────────────────────────────┘
                           │  port 8000
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│               analytics-dashboard/app.py  (Flask :5050)          │
│                                                                  │
│  Reads DB  ────►  data/yolo26_complete_system.db  (same file!)  │
│  Proxies   ────►  http://localhost:8000/stream/{entry|room|exit} │
│  Status    ────►  http://localhost:8000/api/status               │
│  Launches  ────►  subprocess: python yolo26_complete_system.py  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Files Changed

### 1. `analytics-dashboard/app.py`

**Problem:** Was pointing to its own `data/live_security.db` (always empty), running its own standalone `camera_bridge.py` detection engine, and had a broken Ctrl+C handler.

**Changes:**
- **DB path** changed from `analytics-dashboard/data/live_security.db` → `data/yolo26_complete_system.db` (the real database)
- **Camera bridge replaced** with `_FastAPIProxy` class — a thin proxy that queries `http://localhost:8000/api/status` and caches results for 3 seconds (no more standalone detection engine)
- **Video streams** (`/video/entry`, `/video/room`, `/video/exit`) now proxy MJPEG from `http://localhost:8000/stream/{camera}` using `requests` streaming
- **`/api/bridge/status`** now proxies from `http://localhost:8000/api/status`
- **`/api/bridge/start`** now launches `yolo26_complete_system.py` as a real subprocess using `subprocess.Popen`; detects if port 8000 is already in use to avoid double-starting
- **`/api/bridge/stop`** now sends `SIGTERM` to the managed subprocess (with `SIGKILL` fallback after 6s timeout)
- **Ctrl+C fix** — `_cleanup()` was previously a no-op (`pass`), which swallowed all Ctrl+C input. Now calls `stop_system_process()` then `sys.exit(0)` to cleanly terminate Flask
- **CORS** — `http://localhost:5050` and `http://127.0.0.1:5050` added to FastAPI bridge allowlist (in `yolo26_complete_system.py`)

**New constants / globals added:**
```
FASTAPI_URL = "http://localhost:8000"
_PROJECT_ROOT   — absolute path to project root
_PYTHON_EXEC    — path to venv/bin/python
_MAIN_SCRIPT    — path to yolo26_complete_system.py
_system_process — subprocess.Popen handle (or None)
_process_lock   — threading.Lock for process handle
_proxy_cache    — {"proxy": _FastAPIProxy|None, "ts": float}
_PROXY_TTL = 3.0 — seconds between FastAPI status probes
```

---

### 2. `analytics-dashboard/camera_bridge.py`

**Problem:** Had a hardcoded sibling-directory path `../Security-Entry---Exit-Management-System/` that was wrong after the folder was moved inside the project.

**Change:** Removed the stale folder name — `..` now correctly resolves to the project root since `analytics-dashboard` is a subdirectory of it.

```python
# Before
SECURITY_SYS_PATH = os.path.join(os.path.dirname(__file__), "..", "Security-Entry---Exit-Management-System")

# After
SECURITY_SYS_PATH = os.path.join(os.path.dirname(__file__), "..")
```

---

### 3. `analytics-dashboard/start.sh`

**Problem:** Was creating a new `.venv` inside `analytics-dashboard/`, ignoring the existing project-level `venv/`.

**Change:** `VENV_DIR` now points to `$SCRIPT_DIR/../venv` (the project root venv). If `flask-cors` is missing, it installs it there. No new venv is ever created.

---

### 4. `analytics-dashboard/templates/live_monitor.html`

**Problem:** Every failure path (system not running, timeout, status error) called `alert()` — a blocking browser popup.

**Change:** All `alert()` calls replaced with a styled inline panel (`#bridge-error-panel`) that appears below the Start button. The panel includes:
- Orange warning header
- Human-readable error body (dynamically populated)
- A pre-formatted code block with the exact terminal commands to run the system manually
- A Dismiss button
- Auto-hides when cameras successfully connect (`onBridgeStarted()`)

New JavaScript function added:
```javascript
function showBridgeError(title, body) { ... }
```

---

### 5. `yolo26_complete_system.py`

#### Fix A — CORS origins
Added `http://localhost:5050` and `http://127.0.0.1:5050` to the FastAPI `SecurityAPIBridge` CORS allowlist so the Flask dashboard can make cross-origin requests.

#### Fix B — Room camera 0 detections (critical bug)
**Root cause:** `multi_tracker` was initialized with `detector=self.detector` — the **same** YOLO model instance used by entry and exit cameras. The run loop calls:
```
process_entry → self.detector.detect() → model.predict()  ← resets predictor state
process_room  → multi_tracker.update() → model.track(persist=True)  ← tracker has no memory
process_exit  → self.detector.detect() → model.predict()  ← resets predictor state again
```
`model.track(persist=True)` stores ByteTrack state in `model.predictor.trackers`. Each `model.predict()` call on the same instance recreates/resets the predictor, wiping that state. Result: ByteTrack could never accumulate track history → returned 0 detections every frame.

**Fix:** A dedicated `self._room_detector = YOLO26BodyDetector(...)` instance is created and passed to `MultiPersonTracker`. Entry/exit cameras continue using `self.detector`. The two model instances are completely isolated — `predict()` and `track()` never interfere.

```python
# Before
self.multi_tracker = MultiPersonTracker(detector=self.detector, ...)

# After
self._room_detector = YOLO26BodyDetector(model_name="yolo26n-pose.pt", ...)
self.multi_tracker = MultiPersonTracker(detector=self._room_detector, ...)
```

---

### 6. `src/enhanced_database.py`

**Problem:** `yolo26_complete_system.db` was created by an earlier schema version (or by the dashboard's `ensure_db_schema()`) without the `last_seen`, `encounters`, and `face_embedding` columns. `EnhancedDatabase._persist_person_to_db()` tried to INSERT into those columns and crashed immediately on first person registration:

```
sqlite3.OperationalError: table people has no column named last_seen
```

**Fix:** Added safe `ALTER TABLE` migrations after the `CREATE TABLE IF NOT EXISTS` block, using the same pattern already used for `track_id` on `trajectory_data`:

```python
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
```

These run on every startup, succeed when the column is absent, and silently skip when already present.

---

## Startup Workflow

### Normal workflow (recommended)

1. Open Warp (or any terminal).
2. Start the Flask dashboard:
   ```bash
   cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System/analytics-dashboard
   ./start.sh
   ```
3. Open browser → `http://127.0.0.1:5050/monitor`
4. Click **"Start Camera System"** in the UI.
   - Flask launches `yolo26_complete_system.py` as a subprocess automatically.
   - YOLO26 OpenCV windows appear on screen.
   - Dashboard polls `http://localhost:8000/api/status` every 1.5 s.
   - Once the FastAPI bridge is up, live camera feeds appear in the dashboard.
5. Click **"Stop Cameras"** to terminate the camera process.
6. Ctrl+C in the Flask terminal to stop the dashboard.

### Manual workflow (alternative)

1. Start the Flask dashboard (Tab 1):
   ```bash
   cd <project_root>/analytics-dashboard && ./start.sh
   ```
2. Start the camera system manually (Tab 2):
   ```bash
   cd <project_root>
   source venv/bin/activate
   python yolo26_complete_system.py
   ```
3. In the browser, click **"Start Camera System"** — the dashboard detects port 8000 is already in use and connects without spawning a second instance.

---

## Port Map

| Port | Service | Started by |
|------|---------|-----------|
| 5050 | Flask analytics dashboard | `start.sh` / `app.py` |
| 8000 | FastAPI bridge (REST + WebSocket + MJPEG) | `yolo26_complete_system.py` |

---

## Database

| Path | Owner | Used by |
|------|-------|---------|
| `data/yolo26_complete_system.db` | `EnhancedDatabase` (written by main system) | Both Flask dashboard (reads) and YOLO26 system (writes) |
| `analytics-dashboard/data/live_security.db` | Abandoned — no longer used | — |

### Schema — `people` table (after migrations)

| Column | Type | Notes |
|--------|------|-------|
| person_id | TEXT PK | e.g. P001 |
| temp_uuid | TEXT | |
| permanent_uuid | TEXT | |
| state | TEXT | `inside_now` / `exited` / `unauthorized` |
| entry_time | TIMESTAMP | |
| exit_time | TIMESTAMP | |
| duration_seconds | REAL | |
| avg_velocity | REAL | m/s |
| max_velocity | REAL | m/s |
| threat_score | REAL | 0.0–1.0 |
| alert_count | INTEGER | |
| created_at | TIMESTAMP | |
| last_seen | TIMESTAMP | **added by migration** |
| encounters | INTEGER | **added by migration** |
| face_embedding | BLOB | **added by migration** |

---

## Known Limitations / Next Steps

- **OpenCV windows** appear as separate desktop windows when the camera system is launched via the dashboard button (subprocess). This is expected on macOS — the process inherits the display.
- **Subprocess stdout** from `yolo26_complete_system.py` appears in the same terminal where `start.sh` is running (inherited fd). This is intentional for debugging.
- **WebSocket live feed** — the dashboard currently uses polling (REST `/api/bridge/status` every 3 s). A future improvement would connect directly to `ws://localhost:8000/ws/events` from the browser for truly real-time updates without polling.
- **Re-ID cross-camera thresholds** — the entry→room domain shift causes some authorized persons to show as "UNAUTHORIZED" in the room camera. Threshold tuning via the `+`/`-` keys in the YOLO26 terminal is the current workaround. Automated threshold calibration is a future Phase 8 item.
- **Face detection warning** — `FutureWarning: estimate is deprecated` from InsightFace is a library-level deprecation in scikit-image 0.26. Safe to ignore; does not affect functionality.