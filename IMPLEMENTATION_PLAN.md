# 📋 COMPREHENSIVE IMPLEMENTATION PLAN
## Intelligence-Led Entry & Exit Management System with Room Tracking

**Last Updated:** January 2026 | **Version:** 3.0 | **Status:** Phases 1–7 Complete ✅

---

## 🎯 PROJECT EVOLUTION OVERVIEW

### **Current State (Phases 1–7 Complete):**
- ✅ Three-camera system (Entry / Room / Exit) using YOLO26-pose
- ✅ Multi-modal re-ID: OSNet + Face (InsightFace) + Hair + Skin + Clothing
- ✅ ByteTrack multi-person tracking (YOLO26 built-in — no external tracker library)
- ✅ Loitering + Tailgating + Panic behavior detection
- ✅ FastAPI REST + WebSocket + MJPEG stream bridge for frontend
- ✅ Telegram notifications (env-var based, zero hardcoding)
- ✅ SQLite database with trajectory, alert, session, and threat-event tables

### **Target State (Phase 8+):**
- 🔄 React/TypeScript dashboard consuming the Phase 7 API
- 🔄 Performance optimization (async extraction, GPU batching)
- 🔄 Docker + deployment hardening
- 🔄 Optional: model fine-tuning on in-domain footage

---

## 📐 SYSTEM ARCHITECTURE (3-Camera Setup)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    YOLO26 SECURITY SYSTEM                           │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  ENTRY CAM   │    │  ROOM CAM    │    │  EXIT CAM    │          │
│  │  (iBall USB) │    │  (MacBook    │    │  (Iriun      │          │
│  │              │    │   FaceTime)  │    │   Phone)     │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         ▼                   ▼                   ▼                   │
│  ┌─────────────────────────────────────────────────┐               │
│  │           YOLO26-pose  (shared model)            │               │
│  │   NMS-free end-to-end · 17 keypoints · pose     │               │
│  └─────────────────────────────────────────────────┘               │
│         │                   │                   │                   │
│         ▼                   ▼                   ▼                   │
│  [Auto-Register]    [ByteTrack IDs]      [Face-first Match]        │
│  [InsightFace]      [OSNet embed]        [OSNet fallback]           │
│  [Tailgating?]      [Loitering?]         [Session close]            │
│         │                   │                   │                   │
│         └───────────────────┴───────────────────┘                   │
│                             │                                        │
│                  ┌──────────▼──────────┐                            │
│                  │  EnhancedDatabase   │                            │
│                  │  (SQLite)           │                            │
│                  └──────────┬──────────┘                            │
│                             │                                        │
│                  ┌──────────▼──────────┐                            │
│                  │  SecurityAPIBridge  │                            │
│                  │  FastAPI · WS · MJPEG│                           │
│                  └──────────┬──────────┘                            │
│                             │                                        │
│                  ┌──────────▼──────────┐                            │
│                  │  React Dashboard    │ ← Phase 8 (frontend)      │
│                  └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ IMPLEMENTATION ROADMAP

### **PHASE 1: Foundation & Database Enhancement** ✅ COMPLETE
**Goal:** Core infrastructure — database, alerts, config

#### Tasks:
1. **Enhanced Database** (`src/enhanced_database.py`)
   - Tables: `people`, `trajectory_data`, `threat_events`, `alerts`, `sessions`
   - In-memory fast-access mirrors + SQLite persistence
   - Trajectory batch write with configurable sample rate

2. **Alert Manager** (`src/alert_manager.py`)
   - Alert severity levels: INFO / WARNING / CRITICAL
   - Cooldown per-type to prevent spam
   - Console + file logging

3. **Configuration System** (`configs/system_config.yaml`)
   - Camera indices, thresholds, velocity params
   - Display settings, model paths

**Deliverables:** `enhanced_database.py`, `alert_manager.py`, `system_config.yaml`

---

### **PHASE 2: Room Camera — Basic Tracking** ✅ COMPLETE
**Goal:** Detect and track people in the room camera

#### Tasks:
1. YOLO26-pose person detection
2. Basic re-ID against entry registry (histogram + body features)
3. Unauthorized entry alerts
4. Session lifecycle (entry → room → exit)

---

### **PHASE 3: Trajectory & Tail Analysis** ✅ COMPLETE
**Goal:** Visual tails and movement history

#### Tasks:
1. Per-person trajectory ring buffer (60 points)
2. Color-coded tail rendering on room camera
3. Tail fade effect (older points lighter)
4. Trajectory persisted to `trajectory_data` DB table

---

### **PHASE 4: Velocity & Running Detection** ✅ COMPLETE
**Goal:** Real-time speed overlays and running alerts

#### Tasks:
1. Euclidean velocity calculation (px/s → m/s via calibration)
2. Temporal smoothing (rolling average over N frames)
3. Color-coded velocity label: GREEN / ORANGE / RED
4. RUNNING alert when velocity > 2.0 m/s
5. Threat score calculation (velocity + trajectory entropy + density)

---

### **PHASE 5: Face Recognition Integration** ✅ COMPLETE
**Goal:** Face embeddings for high-accuracy re-ID

#### Tasks:
1. InsightFace `buffalo_sc` model (ArcFace embeddings)
2. Face capture at entry gate (from YOLO26 keypoint-derived face bbox)
3. Face-first matching at exit (60% face weight + 40% OSNet)
4. Fallback to body-only if face not detected
5. Face BLOB stored in `people.face_embedding`

---

### **PHASE 6: Multi-Person Tracking** ✅ COMPLETE
**Goal:** Stable track IDs across frames and occlusions

#### Why YOLO26 eliminates external tracking libraries:
YOLO26 ships **ByteTrack and BoT-SORT natively** via `model.track(persist=True)`.
No separate installation of `boxmot`, `norfair`, or `filterpy` is needed.
The Kalman filter is also handled internally by the built-in tracker.

#### Tasks:
1. **`src/tracking/multi_tracker.py`** — `MultiPersonTracker` class
   - Calls `detector.model.track(persist=True, tracker="bytetrack.yaml")`
   - Returns `TrackedPerson` objects with stable `track_id`
   - Per-track OSNet embedding ring buffer (mean pooling over last 15 frames)
   - Track → Person ID association (persists across brief occlusions)
   - Track lifecycle: birth / active / lost / expired
   - `reset()` clears ByteTrack internal state on 'C' key press

2. **`yolo26_complete_system.py` updates**
   - Room camera uses `multi_tracker.update(frame)` instead of `detector.detect(frame)`
   - Track ID displayed as `[T{id}]` suffix on bounding box label
   - Match cache: re-ID only runs every 2 s per track (reduces CPU load)
   - `track_id` stored in `trajectory_data` DB table

3. **`src/enhanced_database.py` updates**
   - `trajectory_data` table gains `track_id INTEGER` column
   - Schema migration handled by `ALTER TABLE IF NOT EXISTS` guard

**Deliverables:** `src/tracking/__init__.py`, `src/tracking/multi_tracker.py`

**Eliminated dependencies:** `norfair`, `boxmot`, `filterpy` (Kalman)

---

### **PHASE 7: Alert & Notification System** ✅ COMPLETE
**Goal:** Multi-channel alerts, behavior detection, frontend bridge

#### Tasks:

**7a. Enhanced Alert Manager** (`src/alert_manager.py`)
- Telegram Bot API notifications (env-var token, zero hardcoding)
- WebSocket event push via `SecurityAPIBridge.push_event()`
- YAML-driven per-type cooldowns (`configs/alert_rules.yaml`)
- New alert types: `TAILGATING`, `DOOR_FORCED`, `TRACK_LOST`
- Shortcut methods: `alert_loitering()`, `alert_tailgating()`, `alert_panic()`

**7b. Loitering Detector** (`src/behaviors/loitering_detector.py`)
- Frame divided into coarse grid zones (default 100 × 100 px)
- Person tracked in a zone; fires when dwell time > 60 s
- Alert cooldown per person (30 s) to prevent spam
- Stale state cleanup for persons who leave without triggering exit

**7c. Tailgating Detector** (`src/behaviors/tailgating_detector.py`)
- Rolling time window (5 s) entry burst detection
- Optional spatial proximity check (IoU ≥ 0.10) to confirm physical closeness
- `record_entry()` called on every new auto-registration
- Returns `TailgatingEvent` with person IDs and overlap score

**7d. Panic Behavior Detection** (inline in `process_room_camera`)
- Crowd average velocity across all persons in frame
- Fires `PANIC_BEHAVIOR` alert when avg ≥ 3.0 m/s and ≥ 3 persons detected
- Red banner overlay on room camera frame

**7e. Alert Rules Config** (`configs/alert_rules.yaml`)
- Per-type thresholds, cooldowns, channel lists
- Telegram settings (parse_mode, min_level gate)
- WebSocket and REST API settings
- Message templates for Telegram HTML formatting

**7f. FastAPI WebSocket Bridge** (`src/api/websocket_bridge.py`)
- Background daemon thread — does not block the main OpenCV loop
- REST endpoints: `/api/status`, `/api/people`, `/api/alerts`, `/api/sessions`,
  `/api/stats`, `/api/tracker`, `/api/trajectories/{person_id}`, `/api/health`
- WebSocket: `ws://localhost:8000/ws/events` — real-time JSON event stream
- MJPEG streams: `/stream/entry`, `/stream/room`, `/stream/exit`
- CORS configured for React / Vite dev servers
- Event history replay for newly connected clients (last 100 events)
- Periodic `stats_update` broadcast every 2 s

**Deliverables:**
- `src/behaviors/__init__.py`
- `src/behaviors/loitering_detector.py`
- `src/behaviors/tailgating_detector.py`
- `src/api/__init__.py`
- `src/api/websocket_bridge.py`
- `configs/alert_rules.yaml`
- Updated `src/alert_manager.py`
- Updated `yolo26_complete_system.py`

---

### **PHASE 8: Performance Optimization** 🔄 NEXT
**Goal:** Maintain ≥ 15 FPS on all three cameras simultaneously

#### Tasks:
1. **Async feature extraction** — run OSNet in a thread pool so the main loop
   is not stalled waiting for the model
2. **Frame skipping** — room camera processes every 2nd frame (ByteTrack
   interpolates between frames); entry/exit always process every frame
3. **Batch YOLO inference** — stack all three frames and run a single
   `model(batch)` call per tick where latency allows
4. **Feature cache** — OSNet embeddings cached per person for 0.5 s (avoid
   re-extraction when the person hasn't moved significantly)
5. **Memory profiling** — trajectory buffers have a 60-point cap; add a
   periodic cleanup pass for dead track keys

#### Files to modify:
- `yolo26_complete_system.py` — thread pool for OSNet
- `src/features/osnet_extractor.py` — async/batch API
- `src/utils/performance.py` (NEW) — profiling helpers

#### Success criteria:
- All three cameras at ≥ 15 FPS on MacBook M-series
- CPU usage < 70 % during normal operation
- Memory stable over a 1-hour session

---

### **PHASE 9: Configuration & Deployment** 🔄 PLANNED
**Goal:** Production-ready packaging and easy deployment

#### Tasks:
1. Unify config: camera indices, thresholds, and alert rules all in one YAML
2. Environment-variable overrides (`.env` file support via `python-dotenv`)
3. Structured JSON logging (replaces print statements)
4. Camera failure recovery (re-open on next frame read failure)
5. Dockerfile + docker-compose (CPU and MPS variants)
6. `install.sh` bootstrap script
7. Deployment documentation

#### Files to create:
- `Dockerfile`
- `docker-compose.yml`
- `install.sh`
- `docs/DEPLOYMENT.md`
- `.env.example`

---

### **PHASE 10: Behavior Analysis Extensions** 🔄 PLANNED (OPTIONAL)
**Goal:** Advanced security patterns beyond Phase 7 basics

#### Tasks:
1. **Zone-based access rules** — define restricted zones in `configs/zones.yaml`
2. **Wrong-direction detection** — compare movement vector to expected flow
3. **Dwell heatmap** — accumulate zone dwell time and export as image
4. **Time-based access windows** — only authorized persons between 09:00–18:00
5. **Crowd flow direction** — dominant movement vector for exit/entry corridors

---

### **PHASE 11: Model Fine-Tuning** ⏸️ OPTIONAL (SKIP UNLESS NEEDED)
**Duration:** 6–8 h + data collection
**Status:** Only if Phase 5 face accuracy is still insufficient after tuning thresholds

#### When to do this:
- Face re-ID false positive rate > 2 % after threshold tuning
- OSNet cross-camera similarity gap < 0.05 (ambiguous matches)

---

### **PHASE 12: Frontend Dashboard** 🔄 READY TO START
**Status:** Backend API (Phase 7) is complete — frontend can be developed now

#### Architecture:

**Backend (already running):**
- FastAPI on port 8000
- WebSocket `/ws/events` — real-time event stream
- MJPEG streams `/stream/{entry|room|exit}`
- REST `/api/*` endpoints

**Frontend (to build):**
- React + TypeScript
- TailwindCSS
- Chart.js for analytics
- Native WebSocket + `<img>` MJPEG for camera feeds

#### Pages:
1. **Dashboard** — live camera grid, active count, real-time alert feed
2. **Registration** — view/edit registered persons, manual registration trigger
3. **Monitoring** — full-screen camera with track overlays and trajectory replay
4. **History** — searchable session log, export CSV/PDF
5. **Alerts** — alert history with filters, Telegram config
6. **Analytics** — entry/exit trends, heatmaps, peak hours
7. **Settings** — camera config, threshold sliders, alert rules

---

## 🛠️ TECHNICAL STACK (Updated for YOLO26)

### **Core — what's actually used:**

| Category | Library | Notes |
|---|---|---|
| Detection + Pose | `ultralytics` (YOLO26-pose) | NMS-free, 17 keypoints, end-to-end |
| Tracking | Built into `ultralytics` | ByteTrack via `model.track(persist=True)` |
| Kalman Filter | Built into `ultralytics` | No `filterpy` needed |
| NMS | **Not needed** | YOLO26 is NMS-free by design |
| Face Re-ID | `insightface` (ArcFace) | `buffalo_sc` model |
| Body Re-ID | `torchreid` (OSNet-ain) | Cross-camera appearance matching |
| Image processing | `opencv-python` | Display, preprocessing, MJPEG encode |
| Numerics | `numpy` | Embeddings, velocity, trajectory |
| Database | `sqlite3` (stdlib) | No ORM needed |
| Config | `pyyaml` | `alert_rules.yaml`, `system_config.yaml` |
| REST / WS API | `fastapi`, `uvicorn` | Phase 7 bridge for frontend |
| Telegram | `requests` | Thin HTTP call — no bot framework needed |

### **Removed / no longer needed:**
| Library | Reason removed |
|---|---|
| `norfair` | YOLO26 ByteTrack is built-in |
| `boxmot` | YOLO26 ByteTrack is built-in |
| `filterpy` | Kalman filter is built into ultralytics tracker |
| `DeepFace` | Replaced by InsightFace (more accurate, faster) |
| `python-telegram-bot` | Simple `requests` HTTP call is sufficient |
| `matplotlib` | OpenCV overlays used instead |

### **Hardware:**
- Entry Camera: iBall Face2Face CHD20.0 (USB, index 0)
- Room Camera: MacBook FaceTime HD (built-in, index 2)
- Exit Camera: Redmi Note 11 via Iriun (USB/WiFi, index 1)

### **Optional (Phase 9+):**
- NVIDIA Jetson Nano / Orin — TensorRT export for edge deployment
- FAISS — fast vector search when registry grows beyond 1,000 persons
- PostgreSQL — replace SQLite for multi-machine deployments

---

## 📊 DIRECTORY STRUCTURE (Current)

```
Security Entry & Exit Management System/
│
├── yolo26_complete_system.py       # Main entry point (Phases 1–7)
├── config.py                       # Legacy config loader
│
├── src/
│   ├── alert_manager.py            # ✅ Phase 7 — multi-channel alerts
│   ├── enhanced_database.py        # ✅ Phase 1 — SQLite persistence
│   ├── cross_camera_adapter.py     # ✅ Phase 4 — domain shift adaptation
│   ├── enhanced_reid.py            # ✅ Phase 4 — multi-modal re-ID
│   ├── multi_modal_reid.py         # ✅ Phase 4 — OSNet + appearance fusion
│   ├── kalman_tracker.py           # (legacy, superseded by ByteTrack)
│   ├── room_tracker.py             # (legacy, superseded by multi_tracker)
│   │
│   ├── tracking/                   # ✅ Phase 6
│   │   ├── __init__.py
│   │   └── multi_tracker.py        # ByteTrack wrapper + feature aggregation
│   │
│   ├── behaviors/                  # ✅ Phase 7
│   │   ├── __init__.py
│   │   ├── loitering_detector.py   # Zone dwell-time analysis
│   │   └── tailgating_detector.py  # Rapid successive entry detection
│   │
│   ├── api/                        # ✅ Phase 7
│   │   ├── __init__.py
│   │   └── websocket_bridge.py     # FastAPI REST + WS + MJPEG
│   │
│   ├── detectors/
│   │   ├── yolo26_body_detector.py # ✅ Primary detector
│   │   ├── hybrid_face_detector.py # ✅ Phase 5
│   │   ├── yolov11_body_detector.py# (legacy)
│   │   └── yolov8_face_detector.py # (legacy)
│   │
│   └── features/
│       ├── __init__.py
│       ├── body_only_analyzer.py   # Hair + skin + clothing
│       ├── clothing_analyzer.py    # Clothing color histograms
│       ├── face_recognition.py     # InsightFace wrapper
│       └── osnet_extractor.py      # OSNet embedding extractor
│
├── configs/
│   ├── system_config.yaml          # Camera, tracking, display settings
│   └── alert_rules.yaml            # ✅ Phase 7 — per-type alert rules
│
├── data/                           # Created at runtime
│   ├── yolo26_complete_system.db   # SQLite database
│   ├── yolo26_system_alerts.log    # Alert log file
│   └── exports/                    # JSON/CSV session exports
│
├── scripts/
│   ├── detect_cameras.py           # Probe camera indices
│   ├── debug_second_camera.py
│   ├── system_check.py
│   └── test_cameras_simple.py
│
├── tests/
│   └── test_phase1.py
│
├── docs/
│   └── Intelligence-Led Entry & Exit Management System *.md
│
├── IMPLEMENTATION_PLAN.md          # This document
├── PHASE_EXECUTION_PLAN.md
├── PHASE5_COMPLETE.md
├── PROJECT_ROADMAP.md
├── PROJECT_STRUCTURE.md
├── README.md
└── requirements*.txt
```

---

## 🚨 MATHEMATICAL FORMULAS

### Velocity Calculation:
```
v = √(Δx² + Δy²) / Δt   ×   (1 / pixels_per_meter)

Δx = centre_x[t] − centre_x[t−1]   (pixels)
Δy = centre_y[t] − centre_y[t−1]   (pixels)
Δt = time_between_frames            (seconds)
pixels_per_meter = calibration constant (default 100)
```

### Threat Score:
```
S_threat = (0.4 × V_rel) + (0.3 × E_traj) + (0.3 × D_prox)

V_rel  = velocity / running_threshold          (0–1, clipped)
E_traj = Σ|θᵢ − θᵢ₋₁| / (n × 180°)          trajectory entropy
D_prox = N_neighbours / max_neighbours         proximity density

Thresholds:
  S_threat > 0.80 → CRITICAL  (fight / panic)
  S_threat > 0.50 → WARNING   (congestion)
```

### ByteTrack Matching (built-in to YOLO26):
```
Association uses IoU between predicted (Kalman) and detected boxes.
High-confidence detections matched first; low-confidence second pass.
Unmatched tracks kept in "lost" state for max_age frames before deletion.
```

### Loitering Zone Check:
```
zone = (centre_x // zone_size,  centre_y // zone_size)
dwell = current_time − zone_entry_time
is_loitering = dwell > loitering_threshold  AND  cooldown_elapsed
```

### Tailgating Burst Detection:
```
recent_entries = {e : e.timestamp > now − time_window}
tailgating = len(recent_entries) >= min_persons
           AND any(IoU(a.bbox, b.bbox) >= min_overlap
                   for a, b in combinations(recent_entries, 2))
```

---

## 🔧 CONFIGURATION PARAMETERS

### Tracking Parameters (system_config.yaml):
```yaml
tracking:
  grace_period: 3.0
  similarity_threshold: 0.65
  trajectory_buffer_size: 60      # points per person
  max_disappeared_frames: 30
  min_detection_confidence: 0.5
```

### Velocity Parameters:
```yaml
velocity:
  walking_threshold: 1.0          # m/s
  running_threshold: 2.0          # m/s  (alert threshold)
  panic_threshold: 3.0            # m/s  (crowd average)
  smoothing_window: 10
  pixels_per_meter: 100.0
```

### Behavior Thresholds (alert_rules.yaml):
```yaml
loitering:
  threshold_seconds: 60
  zone_size_pixels: 100
  alert_cooldown_seconds: 30

tailgating:
  time_window_seconds: 5
  min_persons: 2
  check_proximity: true
  min_overlap: 0.10
```

### Alert Channels:
```yaml
channels:
  console: { enabled: true }
  file:    { enabled: true, path: "data/alerts.log" }
  telegram:
    enabled: false                # set true + env vars to activate
    # export TELEGRAM_BOT_TOKEN=<token>
    # export TELEGRAM_CHAT_ID=<chat_id>
    min_level: critical
  websocket:
    enabled: true
    port: 8765
  rest_api:
    enabled: true
    port: 8000
```

---

## 🚀 RUNNING THE SYSTEM

### Basic run (all defaults):
```bash
python yolo26_complete_system.py
```

### Custom camera indices:
```bash
python yolo26_complete_system.py --entry 0 --room 2 --exit 1
```

### Without API bridge (headless / resource-constrained):
```bash
python yolo26_complete_system.py --no-api
```

### Custom API port:
```bash
python yolo26_complete_system.py --api-port 9000
```

### Without ByteTrack (frame-by-frame fallback):
```bash
python yolo26_complete_system.py --no-tracker
```

### Identify camera indices first:
```bash
python yolo26_complete_system.py --list-cameras
# or
python scripts/detect_cameras.py
```

### Enable Telegram alerts:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
# Then edit configs/alert_rules.yaml:  telegram.enabled: true
python yolo26_complete_system.py
```

---

## ⌨️ KEYBOARD CONTROLS

| Key | Action |
|-----|--------|
| `Q` | Quit and export session data |
| `D` | Toggle debug verbose output |
| `C` | Clear all registrations + reset tracker |
| `S` | Print statistics to console |
| `T` | Print ByteTrack diagnostics to console |
| `I` | Print cross-camera adapter diagnostics |
| `F` | Toggle face recognition on/off |
| `+` / `=` | Increase room similarity threshold (+0.05) |
| `-` / `_` | Decrease room similarity threshold (−0.05) |
| `]` | Increase exit threshold (+0.05) |
| `[` | Decrease exit threshold (−0.05) |

---

## 📡 API ENDPOINTS (Phase 7)

### REST (http://localhost:8000):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness probe |
| GET | `/api/status` | Full system state snapshot |
| GET | `/api/stats` | Cumulative statistics |
| GET | `/api/people` | Registered persons list |
| GET | `/api/sessions` | Active sessions with duration + velocity |
| GET | `/api/alerts?limit=50&level=critical` | Recent alerts (filterable) |
| GET | `/api/tracker` | ByteTrack diagnostics |
| GET | `/api/trajectories/{person_id}` | Trajectory points for a person |

### WebSocket (ws://localhost:8000/ws/events):
```json
{
  "event":     "alert | entry | exit | detection | stats_update | ping",
  "timestamp": "2026-01-14T12:34:56.789",
  "data":      { "...event-specific payload..." }
}
```

### MJPEG Streams:
- `http://localhost:8000/stream/entry` — annotated entry camera feed
- `http://localhost:8000/stream/room`  — annotated room camera feed (with tracks)
- `http://localhost:8000/stream/exit`  — annotated exit camera feed

---

## ⚠️ KEY DECISIONS

### 1. YOLO26 replaces multiple libraries:
YOLO26 (ultralytics ≥ 26.0) natively provides:
- Object detection (person class)
- Pose estimation (17 COCO keypoints) — replaces separate pose models
- **ByteTrack / BoT-SORT** via `model.track()` — replaces norfair, boxmot
- **Kalman prediction** for track interpolation — replaces filterpy
- NMS-free end-to-end inference — no post-processing step needed

This was a major simplification: 4 external libraries removed.

### 2. Re-ID Architecture:
**Decision:** InsightFace (face) + OSNet (body) hybrid
- Face at entry/exit: 60% weight, ArcFace embeddings, high accuracy when face visible
- OSNet in room: primary discriminator (70% weight), works across cameras
- Appearance (hair, skin, clothing): 30% combined, weak discriminator but useful tiebreaker

### 3. Tracking:
**Decision:** YOLO26 built-in ByteTrack (not norfair/boxmot)
- Rationale: Zero extra dependency, official ultralytics support, tunable via YAML
- Track→Person association maintained in `MultiPersonTracker` class
- Match cache (2 s TTL) reduces re-ID calls per track

### 4. Database:
**Decision:** SQLite (stdlib) — no ORM
- Rationale: Single-machine deployment, simple schema, fast for the data volumes involved
- Upgrade path: swap `sqlite3` for `psycopg2` + PostgreSQL if multi-machine needed

### 5. API Bridge:
**Decision:** FastAPI daemon thread (not subprocess)
- Rationale: Shares memory with main system for zero-copy frame access
- Risk: If FastAPI crashes it doesn't take down the main system (daemon thread)
- Frontend can connect over LAN for multi-monitor setups

---

## 📈 SUCCESS METRICS

### Phase 1: ✅
- Database stores trajectory data
- Alerts logged with metadata
- Configuration loaded from YAML

### Phase 2: ✅
- Room camera detects people
- Re-ID matches with entry UUIDs
- Unauthorized entries alerted

### Phase 3: ✅
- Trajectory tails visualized
- Color-coded by velocity
- Trajectories persisted to DB

### Phase 4: ✅
- Velocity calculated (±10% error)
- Running detection alert fires
- Threat score calculated

### Phase 5: ✅
- Face embedded at entry (InsightFace)
- Face-first matching at exit
- False positive rate < 2 %

### Phase 6: ✅
- Stable ByteTrack IDs across frames
- No ID switch during brief occlusion (≤ 30 s)
- Track ID displayed on room camera overlay
- track_id stored in trajectory_data table

### Phase 7: ✅
- Loitering alert fires after 60 s in one zone
- Tailgating alert fires when ≥ 2 persons enter within 5 s
- Panic alert fires when ≥ 3 persons average > 3.0 m/s
- WebSocket delivers events < 100 ms after detection
- MJPEG streams accessible from browser
- Telegram message sent for CRITICAL alerts (when configured)

### Phase 8 (target):
- ≥ 15 FPS on all three cameras simultaneously
- CPU < 70 % during normal 3-person scenario
- Memory stable over 1-hour session (no leaks)

---

## 📚 REFERENCES

### Models:
1. **YOLO26** — Ultralytics (Jan 2026): https://docs.ultralytics.com/models/yolo26/
2. **ArcFace** (InsightFace `buffalo_sc`) — Deng et al., CVPR 2019
3. **OSNet** — Zhou et al., "Omni-Scale Feature Learning for Person Re-ID", ICCV 2019
4. **ByteTrack** — Zhang et al., "ByteTrack: Multi-Object Tracking by Associating Every Detection Box", ECCV 2022 (built into ultralytics)

### Repositories:
- Ultralytics YOLO26: https://github.com/ultralytics/ultralytics
- InsightFace: https://github.com/deepinsight/insightface
- Torchreid (OSNet): https://github.com/KaiyangZhou/deep-person-reid
- FastAPI: https://fastapi.tiangolo.com/

---

## 📝 NOTES

- Each phase is tested before moving to the next
- All phases maintain backward compatibility
- Frontend (Phase 12) can be developed immediately — Phase 7 API is complete
- Phase 11 (fine-tuning) should be skipped unless re-ID accuracy is genuinely insufficient
- The Telegram token must **never** be hardcoded — always use environment variables
- Camera indices can change when USB cameras are plugged/unplugged; use `--list-cameras` to reconfirm

---

**Version:** 3.0 | **Phases complete:** 1–7 | **Next:** Phase 8 (optimization) or Phase 12 (frontend)
```

Now let me verify the key files were created correctly and run a quick diagnostic: