# SecureVision Analytics Dashboard — Production Mode

## Overview

A production-grade security analytics dashboard that displays **REAL data from live camera detections only**. No demo data, no fake numbers — tables start empty and fill up as cameras detect people, events, and threats.

### Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Cameras    │ ───► │  Camera Bridge   │ ───► │  SQLite DB   │
│ (entry/room/ │      │  (YOLO/Haar/Raw) │      │  (immediate  │
│  exit)       │      │  Detection +     │      │   writes)    │
└─────────────┘      │  Tracking        │      └──────┬───────┘
                     └──────────────────┘             │
                                                      │ reads
                     ┌──────────────────┐             │
                     │  Flask REST API  │ ◄───────────┘
                     │  /api/*          │
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │  Dashboard UI    │
                     │  (index.html)    │
                     │  Auto-refresh    │
                     └──────────────────┘
```

**Single Database:** `data/live_security.db` — the Camera Bridge writes to it immediately on every detection, and the Dashboard API reads from it. No separate demo database. No in-memory-only data that never reaches SQLite.

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask backend — REST API endpoints, camera bridge control |
| `live_database.py` | Thread-safe SQLite writer — every detection persisted immediately |
| `camera_bridge.py` | Camera manager — captures frames, runs detection, writes to DB |
| `templates/index.html` | Full analytics dashboard |
| `templates/live_monitor.html` | Live camera feeds + real-time analytics |
| `start.sh` | One-command startup script |
| `requirements.txt` | Python dependencies |

---

## Quick Start

```bash
cd Frontend_for_analytics/analytics-dashboard
chmod +x start.sh
./start.sh
```

This will:
1. Create a virtual environment (if needed)
2. Install dependencies
3. Create the database schema (empty tables)
4. Start the Flask server on port 5050

### Pages

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:5050/` | Full analytics dashboard (charts, tables, KPIs) |
| `http://127.0.0.1:5050/monitor` | Live monitor (camera feeds + real-time analytics) |

### Workflow

1. **Open `/monitor`** in your browser
2. **Click "Start Camera System"** — this connects your cameras and starts detection
3. **Watch data flow in** — every person detected, every alert, every trajectory point is written to the database immediately
4. **Open `/`** (the dashboard) — you'll see real analytics based on actual camera detections
5. The dashboard auto-refreshes every 3 seconds when cameras are active

---

## How Data Flows (The Fix)

### Before (Broken)
- Dashboard read from `demo_security.db` (85 fake people, 200 fake alerts)
- Camera Bridge wrote to `live_security.db` (separate database!)
- Even within the bridge, `EnhancedDatabase` kept most data in-memory only
- **Result:** Dashboard always showed random data, completely unrelated to cameras

### After (Fixed)
- **Single database:** `data/live_security.db`
- **`LiveDatabase` class** writes EVERY event to SQLite immediately via a background writer thread
  - `record_entry()` → INSERT into `people` table (state: `inside_now`)
  - `add_trajectory_point()` → INSERT into `trajectory_data` table
  - `create_alert()` → INSERT into `alerts` table
  - `record_threat_event()` → INSERT into `threat_events` table
  - `record_exit()` → UPDATE `people` table (state: `exited`, duration calculated)
- **Dashboard API** reads from the same `live_security.db`
- **Empty state by default** — all tables show "No data yet" with helpful messages
- **Data appears in real-time** as cameras detect activity

---

## API Reference

### Dashboard APIs (read data)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/overview` | GET | KPI numbers + bridge status |
| `/api/people` | GET | People list (filterable by state) |
| `/api/people/<id>` | GET | Person detail with trajectory/alerts |
| `/api/people/states` | GET | People count by state |
| `/api/alerts` | GET | Alert list (filterable by level/type) |
| `/api/alerts/summary` | GET | Alert counts by type/level/camera |
| `/api/alerts/timeline` | GET | Alerts bucketed by hour (7 days) |
| `/api/threats` | GET | Threat events list |
| `/api/threats/summary` | GET | Threat statistics |
| `/api/threats/timeline` | GET | Threats bucketed by hour (7 days) |
| `/api/trajectories/<id>` | GET | Trajectory points for a person |
| `/api/trajectories/heatmap` | GET | Heatmap data for a camera |
| `/api/velocity/distribution` | GET | Velocity distribution |
| `/api/velocity/top` | GET | Highest velocity people |
| `/api/entry-exit/timeline` | GET | Entry/exit counts by hour |
| `/api/entry-exit/duration` | GET | Visit duration distribution |
| `/api/cameras/stats` | GET | Per-camera statistics |
| `/api/live/feed` | GET | Latest events for live panel |
| `/api/search?q=` | GET | Search across all data |

### Camera Bridge APIs (control cameras)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/bridge/start` | POST | Start camera system |
| `/api/bridge/stop` | POST | Stop camera system |
| `/api/bridge/status` | GET | Bridge status + live stats |

### Database Management APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/db/reset` | POST | Clear ALL data (fresh start) |
| `/api/db/stats` | GET | Row counts for all tables |

### Camera Streams

| Endpoint | Description |
|----------|-------------|
| `/video/entry` | MJPEG stream — entry camera |
| `/video/room` | MJPEG stream — room camera |
| `/video/exit` | MJPEG stream — exit camera |
| `/video/<camera>/snapshot` | Single JPEG frame |

---

## Detection Modes

The Camera Bridge auto-detects available dependencies and selects the best mode:

| Mode | Dependencies | Detection Quality |
|------|-------------|-------------------|
| **FULL** | ultralytics + torch + torchvision | YOLO26 + OSNet re-identification |
| **LITE** | opencv-python only | Haar Cascade face detection + histogram tracking |
| **RAW** | opencv-python only | Camera streaming only (no detection) |

### Installing for FULL mode (best accuracy)

```bash
pip install ultralytics torch torchvision
```

### LITE mode (works out of the box)

No extra installation needed beyond `requirements.txt`. Uses OpenCV's built-in Haar Cascade for face detection and color histograms for person re-identification.

---

## Database Schema

All tables in `data/live_security.db`:

### `people`
| Column | Type | Description |
|--------|------|-------------|
| person_id | TEXT (PK) | Unique identifier (e.g., P001) |
| state | TEXT | `inside_now`, `exited`, `unauthorized` |
| entry_time | TIMESTAMP | When person entered |
| exit_time | TIMESTAMP | When person exited |
| duration_seconds | REAL | Time spent inside |
| avg_velocity | REAL | Average movement speed (m/s) |
| max_velocity | REAL | Maximum movement speed (m/s) |
| threat_score | REAL | 0.0–1.0 threat assessment |
| alert_count | INTEGER | Number of alerts for this person |

### `trajectory_data`
| Column | Type | Description |
|--------|------|-------------|
| person_id | TEXT (FK) | Person being tracked |
| camera_source | TEXT | Which camera recorded this |
| x, y | REAL | Position coordinates |
| velocity | REAL | Instantaneous velocity |
| timestamp | TIMESTAMP | When recorded |

### `alerts`
| Column | Type | Description |
|--------|------|-------------|
| alert_type | TEXT | `running`, `unauthorized_entry`, `loitering`, etc. |
| alert_level | TEXT | `info`, `warning`, `critical` |
| person_id | TEXT | Associated person |
| camera_source | TEXT | Which camera triggered it |
| message | TEXT | Human-readable description |

### `threat_events`
| Column | Type | Description |
|--------|------|-------------|
| person_id | TEXT (FK) | Person involved |
| event_type | TEXT | Type of threat |
| threat_score | REAL | 0.0–1.0 severity |
| velocity | REAL | Speed at time of event |
| camera_source | TEXT | Which camera detected it |

### `sessions`
| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT (PK) | Session identifier |
| start_time | TIMESTAMP | When session began |
| end_time | TIMESTAMP | When session ended |
| total_entries | INTEGER | People who entered |
| total_exits | INTEGER | People who exited |
| total_alerts | INTEGER | Alerts generated |

---

## Troubleshooting

### "No data showing on dashboard"
This is expected! Tables start empty. Data appears when:
1. You start the camera system from `/monitor`
2. Cameras detect people/events
3. The dashboard auto-refreshes (every 3 seconds when cameras are active)

### "Want to start fresh"
Click **"Reset Data"** in the dashboard sidebar, or:
```bash
curl -X POST http://127.0.0.1:5050/api/db/reset
```

### "Camera not detected"
- Check that your camera is connected and accessible
- Try specifying camera indices manually:
```bash
curl -X POST http://127.0.0.1:5050/api/bridge/start \
  -H "Content-Type: application/json" \
  -d '{"entry_idx": 0, "room_idx": 0, "exit_idx": 0}'
```

### "Port 5050 already in use"
```bash
PORT=8080 ./start.sh
```

---

## Production Deployment Notes

For production use, consider:

1. **WSGI server:** Replace Flask dev server with Gunicorn
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5050 --threads 8 app:app
   ```

2. **HTTPS:** Put behind nginx with SSL termination

3. **Authentication:** Add login/token auth for dashboard and API endpoints

4. **Database backups:** Periodically backup `data/live_security.db`

5. **Log rotation:** Monitor disk usage for trajectory data (high volume)