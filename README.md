# Intelligence-Led Entry & Exit Management System

**Project Group ID:** CSPIT/CSE/B1-C1
**Students:** 23CS023 (Ananya Gupta), 23CS043 (Debdoot Manna)
**Domain:** Computer Vision · AI · Security Systems

---

## Overview

An AI-powered three-camera physical security system that:

1. **Entry Gate** — Detects and registers a person entering, extracts body features + face embedding
2. **Room Monitor** — Tracks all people in the room, measures velocity, flags unauthorized presence
3. **Exit Gate** — Re-identifies the same person using face-first matching (+ body fallback) and logs the full session

---

## Camera Setup

| Role | Device | Resolution | Connection |
|------|--------|-----------|------------|
| **Entry** | iBall Face2Face CHD20.0 | 720p HD | USB |
| **Room** | MacBook FaceTime HD | 720p HD | Built-in |
| **Exit** | Redmi Note 11 (Iriun Webcam) | 720p HD | USB / Wi-Fi |

> All frames are normalised to **640 × 480** internally to ensure consistent detection coordinates and overlay rendering across all three cameras.

### Finding Your Camera Indices

On macOS the built-in webcam is usually index **0**, and USB cameras are assigned sequentially.
A typical layout is:

```
0 → MacBook FaceTime HD   (Room)
1 → iBall CHD20.0         (Entry)
2 → Redmi via Iriun       (Exit)
```

Run the helper to confirm:

```
python scripts/detect_cameras.py
```

or:

```
python yolo26_complete_system.py --list-cameras
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Person detection | YOLO26-pose (`yolo26n-pose.pt`) |
| Body re-ID | OSNet x1_0 — 512-D embeddings |
| Face recognition | InsightFace / ArcFace — 512-D embeddings |
| Appearance features | Hair colour · skin tone · clothing colour |
| Cross-camera normalisation | CLAHE + per-camera colour correction |
| Trajectory smoothing | Kalman filter |
| Database | SQLite via `src/enhanced_database.py` |
| Alerts | `src/alert_manager.py` — console + file |
| Video | OpenCV |

### Matching Strategy

**At Exit (face visible):**
```
score = face_similarity × 0.60 + OSNet_similarity × 0.40
```

**At Exit / Room (no face):**
```
score = OSNet × 0.70 + clothing × 0.20 + hair × 0.05 + skin × 0.05
        (rejected immediately if OSNet < 0.50)
```

---

## Project Structure

```
Security Entry & Exit Management System/
│
├── yolo26_complete_system.py   ← MAIN SYSTEM — run this
├── config.py                   ← Legacy config (kept for reference)
│
├── src/
│   ├── enhanced_database.py    ← SQLite session, trajectory & alert DB
│   ├── alert_manager.py        ← Multi-level alert system
│   ├── cross_camera_adapter.py ← CLAHE + adaptive thresholds per camera pair
│   ├── enhanced_reid.py        ← Multi-modal re-ID logic
│   ├── kalman_tracker.py       ← Trajectory smoothing
│   ├── multi_modal_reid.py     ← Feature fusion utilities
│   ├── room_tracker.py         ← Room camera tracking helpers
│   ├── detectors/
│   │   ├── yolo26_body_detector.py  ← YOLO26-pose wrapper (primary)
│   │   ├── yolo26_body_detector.py
│   │   ├── yolov8_face_detector.py  ← (legacy, not used in main system)
│   │   └── hybrid_face_detector.py
│   └── features/
│       ├── face_recognition.py      ← InsightFace / ArcFace (Phase 5)
│       ├── osnet_extractor.py       ← OSNet body embeddings
│       ├── body_only_analyzer.py    ← Hair / skin / clothing
│       └── clothing_analyzer.py
│
├── configs/
│   └── system_config.yaml      ← All tunable parameters
│
├── models/
│   └── yolov8n.pt              ← YOLOv8n weights (kept for reference)
│
├── scripts/
│   ├── detect_cameras.py       ← Find which index = which camera
│   ├── system_check.py         ← Pre-flight dependency check
│   └── test_cameras_simple.py  ← Quick camera sanity test
│
├── tests/
│   └── test_phase1.py          ← Unit tests for DB + alert manager
│
├── data/                       ← Created at runtime
│   ├── yolo26_complete_system.db   ← SQLite database
│   ├── yolo26_system_alerts.log    ← Alert log
│   └── exports/                    ← JSON session exports
│
├── yolo26n-pose.pt             ← YOLO26 pose model weights
├── requirements.txt
├── requirements_phase5.txt     ← InsightFace + onnxruntime
├── run_system.sh               ← Launch script (recommended)
└── venv/                       ← Python virtual environment
```

---

## Installation

### 1. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install core dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install Phase 5 (face recognition)

```bash
pip install -r requirements_phase5.txt
```

> InsightFace downloads the `buffalo_sc` model (~60 MB) automatically on first run.

### 4. Verify setup

```bash
python scripts/system_check.py
```

---

## Running the System

### Quick start (recommended)

```bash
bash run_system.sh
```

The script activates the virtual environment, checks dependencies, and launches the system with the default camera indices (`--entry 1 --room 0 --exit 2`).

### Manual launch

```bash
source venv/bin/activate
python yolo26_complete_system.py --entry 1 --room 0 --exit 2
```

### Override camera indices

```bash
python yolo26_complete_system.py --entry 2 --room 0 --exit 1
```

### List detected cameras

```bash
python yolo26_complete_system.py --list-cameras
```

---

## Keyboard Controls (while running)

| Key | Action |
|-----|--------|
| `D` | Toggle debug output (verbose scores per detection) |
| `F` | Toggle face recognition ON / OFF |
| `C` | Clear all registrations and sessions |
| `S` | Print session statistics to console |
| `I` | Print cross-camera adapter diagnostics |
| `+` | Increase room matching threshold (+0.05) |
| `-` | Decrease room matching threshold (−0.05) |
| `]` | Increase exit matching threshold (+0.05) |
| `[` | Decrease exit matching threshold (−0.05) |
| `Q` | Quit and export session data |

---

## Database Schema (SQLite)

All data is persisted to `data/yolo26_complete_system.db`.

| Table | Contents |
|-------|---------|
| `people` | Person ID, state, entry/exit times, velocity stats, face embedding BLOB |
| `trajectory_data` | Per-frame (x, y, velocity, camera, timestamp) per person |
| `threat_events` | Running / crowd / unauthorised events with scores |
| `alerts` | All raised alerts with level, type, message, timestamp |
| `sessions` | Per-run session summaries |

---

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core detection & body re-ID (YOLO26 + OSNet) | ✅ Complete |
| 2 | Cross-camera adaptation (CLAHE, adaptive thresholds) | ✅ Complete |
| 3 | False-positive prevention (OSNet hard floor, rebalanced weights) | ✅ Complete |
| 4 | SQLite database & session management | ✅ Complete |
| 5 | Face recognition integration (InsightFace / ArcFace) | ✅ Complete |
| 6 | Multi-person tracking (ByteTrack / BoT-SORT) | ⏳ Planned |
| 7 | Alert notifications (email / SMS / Telegram) | ⏳ Planned |
| 8 | Advanced behaviour analysis (loitering, heatmaps) | ⏳ Planned |
| 9 | Performance optimisation (async, GPU) | ⏳ Planned |
| 10 | Configuration & deployment hardening | ⏳ Planned |
| 11 | Web dashboard frontend | 🔀 Separate repo |

> **Note:** Phases 1–5 cover the backend pipeline.  The web dashboard (Phase 11) is being developed in a separate repository and will connect via a REST / WebSocket API.

---

## Known Issues & Current Limitations

- **False positives in room camera:** Cross-camera domain shift (iBall → MacBook) causes OSNet scores to drop significantly.  The adaptive threshold system partially compensates, but improvements are ongoing.
- **Single-person sessions only:** The current pipeline handles one person at a time through the entry gate.  Phase 6 (multi-person tracking) will address crowded scenarios.
- **Face occlusion:** If a person wears a mask or turns away at the exit gate, the system automatically falls back to body-only matching.
- **Iriun resolution:** Ensure the Iriun app on the Redmi is set to the same resolution as the other cameras (640 × 480 or 720p) for best results.

---

## Authors

- **Ananya Gupta** — 23CS043
- **Debdoot Manna** — 23CS023

CSPIT / CSE / B1-C1
```

Now back to continuing the work: