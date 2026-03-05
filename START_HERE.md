# 🚀 START HERE — Running the Security System

This guide explains exactly how to start the system from scratch using two terminals.

---

## What runs where

| Terminal | What it runs | Port | Purpose |
|----------|-------------|------|---------|
| **Terminal 1** | `yolo26_complete_system.py` | 8000 | Main AI engine — camera feeds, YOLO26 detection, re-ID, database writes |
| **Terminal 2** | `analytics-dashboard/app.py` | 5050 | Flask web dashboard — live monitor, charts, analytics UI |

Terminal 1 **must be started first**. Terminal 2 reads data from the database and proxies camera streams from Terminal 1.

---

## Prerequisites

Make sure you have done this once before running:

```bash
cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements_phase5.txt
```

---

## Terminal 1 — Main AI System (start this first)

```bash
cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System
source venv/bin/activate
bash run_system.sh
```

### What you will see on startup

```
=====================================================================
  YOLO26 THREE-CAMERA SECURITY SYSTEM
  Phases 1-7 Active  |  Three-Model YOLO26 Suite
=====================================================================
✅ YOLO26-pose  (yolo26n-pose.pt) — body bbox + 17 keypoints + ByteTrack
✅ YOLO26-det   (yolo26n.pt)      — dedicated face detection on head crops
✅ YOLO26-seg   (yolo26n-seg.pt)  — pixel masks → precise clothing colour
✅ InsightFace ArcFace 512-D face embeddings
...
🌐 Frontend API: http://localhost:8000
   WebSocket:     ws://localhost:8000/ws/events
   Camera feeds:  http://localhost:8000/stream/{entry|room|exit}
=====================================================================
```

Three OpenCV windows will also open on your desktop:
- **Entry Gate** — entry camera feed with skeleton overlay
- **Room Monitoring** — room camera with ByteTrack IDs and trajectory tails
- **Exit Gate** — exit camera feed

### Specifying camera indices

By default the script uses:
- Entry → camera index `1`
- Room  → camera index `0`
- Exit  → camera index `2`

If your cameras are on different indices, override them:

```bash
bash run_system.sh --entry 0 --room 1 --exit 2
```

Not sure which index is which camera? Run:

```bash
bash run_system.sh --list-cameras
```

This will print every detected camera device with a preview so you can identify them.

### Keyboard controls (click any OpenCV window first)

| Key | Action |
|-----|--------|
| `D` | Toggle debug output (verbose per-frame matching scores) |
| `F` | Toggle face recognition on/off |
| `C` | Clear all registrations and reset the session |
| `S` | Print statistics to the terminal |
| `I` | Print cross-camera adapter diagnostics |
| `T` | Print ByteTrack tracker diagnostics |
| `+` | Increase room matching threshold by 0.05 |
| `-` | Decrease room matching threshold by 0.05 |
| `]` | Increase exit matching threshold by 0.05 |
| `[` | Decrease exit matching threshold by 0.05 |
| `Q` | Quit and export session data |

---

## Terminal 2 — Analytics Dashboard (start after Terminal 1 is running)

```bash
cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System/analytics-dashboard
source ../venv/bin/activate
./start.sh
```

Or equivalently without the script:

```bash
cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System/analytics-dashboard
source ../venv/bin/activate
python app.py
```

### What you will see on startup

```
╔══════════════════════════════════════════════════════════╗
║    SecureVision — Live Monitor & Analytics Dashboard    ║
║              PRODUCTION MODE — Real Data Only           ║
╚══════════════════════════════════════════════════════════╝
✓ Found Python 3.x.x
✓ Using project virtual environment
✓ All dependencies satisfied
...
 * Running on http://0.0.0.0:5050
```

### Pages

| URL | What it shows |
|-----|--------------|
| `http://127.0.0.1:5050/` | Full analytics dashboard — charts, tables, session history |
| `http://127.0.0.1:5050/monitor` | **Live monitor** — camera feeds + real-time stats side by side |

Open the **Live Monitor** first. If Terminal 1 is already running you will see the camera feeds immediately. If the YOLO system is not yet running, the dashboard shows an inline error panel with instructions — no blocking popups.

---

## Normal startup sequence (step by step)

```
1. Open Terminal 1
   cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System
   source venv/bin/activate
   bash run_system.sh

2. Wait until you see:
   "✅ System ready!"
   and the three OpenCV windows appear.

3. Open Terminal 2
   cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System/analytics-dashboard
   source ../venv/bin/activate
   ./start.sh

4. Open your browser:
   http://127.0.0.1:5050/monitor

5. The Live Monitor connects automatically.
   Camera feeds stream from Terminal 1 → Terminal 2 → browser.
```

---

## Stopping the system

**Terminal 2 (dashboard) first:**
```
Ctrl+C
```
This terminates the Flask server cleanly.

**Terminal 1 (main system) second:**
- Either press `Q` inside one of the OpenCV windows, or
- Press `Ctrl+C` in the terminal

Both methods export session data to `data/` before exiting.

---

## Model files required

The following `.pt` files must be present in the project root. They are downloaded automatically on first run if missing:

| File | Size | Purpose |
|------|------|---------|
| `yolo26n-pose.pt` | ~6 MB | Body detection + 17 keypoints + ByteTrack |
| `yolo26n.pt` | ~5 MB | Dedicated face detection on head crops |
| `yolo26n-seg.pt` | ~7 MB | Instance segmentation masks for clothing colour |

InsightFace models (`buffalo_sc`) are downloaded automatically to `~/.insightface/models/` on first run.

---

## Troubleshooting

### "Camera not found" / black window

```bash
# List available cameras
bash run_system.sh --list-cameras

# Then specify the correct indices
bash run_system.sh --entry 0 --room 1 --exit 2
```

If you only have one physical camera (e.g. MacBook built-in), all three indices will map to the same feed. That is fine for testing — the system will just process the same feed three times.

### "Module not found" errors in Terminal 1

```bash
cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements_phase5.txt
```

### Dashboard shows "Bridge unreachable"

Terminal 1 is not running or hasn't finished starting up yet. Wait for the `"✅ System ready!"` message in Terminal 1, then refresh the browser.

### Room camera keeps showing UNAUTHORIZED (red box)

This happens when:
1. **Face not visible at entry** — make sure you look directly at the entry camera when registering. The system uses InsightFace ArcFace embeddings as the primary re-ID signal.
2. **Too far from room camera** — the face crop needs to be large enough for InsightFace to embed. Move closer.
3. **Threshold too high** — press `-` in an OpenCV window to lower the room matching threshold in 0.05 steps.
4. **Debug mode** — press `D` to see per-frame scores and find out which part of the pipeline is failing.

### Port 8000 already in use

Another process is using port 8000. Kill it:

```bash
lsof -ti:8000 | xargs kill -9
```

### Port 5050 already in use

```bash
lsof -ti:5050 | xargs kill -9
```

---

## File layout reference

```
Security Entry & Exit Management System/
├── run_system.sh                  ← Terminal 1 entry point
├── yolo26_complete_system.py      ← Main AI engine
├── yolo26n-pose.pt                ← YOLO26 pose model (auto-downloaded)
├── yolo26n.pt                     ← YOLO26 detection model (auto-downloaded)
├── yolo26n-seg.pt                 ← YOLO26 seg model (auto-downloaded)
├── venv/                          ← Shared Python virtual environment
├── data/
│   └── yolo26_complete_system.db  ← Shared SQLite database (written by T1, read by T2)
├── src/
│   ├── detectors/
│   │   ├── yolo26_body_detector.py  ← Pose model wrapper
│   │   ├── yolov8_face_detector.py  ← YOLO26-detect face wrapper (migrated)
│   │   └── hybrid_face_detector.py  ← YOLO26 → MediaPipe → Haar fallback chain
│   ├── features/
│   │   ├── face_recognition.py      ← InsightFace ArcFace embeddings
│   │   ├── osnet_extractor.py       ← OSNet body appearance embeddings
│   │   └── body_only_analyzer.py    ← Hair / skin / clothing colour
│   └── tracking/
│       └── multi_tracker.py         ← ByteTrack multi-person tracker
└── analytics-dashboard/
    ├── start.sh                   ← Terminal 2 entry point
    ├── app.py                     ← Flask server
    └── templates/
        ├── index.html             ← Analytics dashboard
        └── live_monitor.html      ← Live camera + stats monitor
```

---

## Quick reference card

```
TERMINAL 1 (main system)
  cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System
  source venv/bin/activate
  bash run_system.sh [--entry N] [--room N] [--exit N]

TERMINAL 2 (dashboard)
  cd ~/VSCode/ML/Security\ Entry\ \&\ Exit\ Management\ System/analytics-dashboard
  source ../venv/bin/activate
  ./start.sh

BROWSER
  http://127.0.0.1:5050/monitor   ← live feeds
  http://127.0.0.1:5050/          ← analytics
```
