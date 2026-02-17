# Quick Start Guide - YOLO Security System
## Get Up and Running in 5 Minutes

---

## 🚀 Fast Track Setup

### Step 0: Download YOLO Models (1 minute - FIRST TIME ONLY)

**Required before first run:**

```bash
cd "Security Entry & Exit Management System"
source venv/bin/activate
python download_yolo_face.py
```

**Expected Output:**
```
📥 Downloading YOLOv8n-face model (6 MB)...
✅ Download complete!
✅ SETUP COMPLETE!
```

**If auto-download fails:**
1. Visit: https://github.com/derronqi/yolov8-face/releases
2. Download `yolov8n-face.pt` (6 MB)
3. Place it in the project root directory

**OR use Hugging Face:**
1. Visit: https://huggingface.co/Bingsu/yolov8n-face
2. Download `yolov8n-face.pt`
3. Place it in the project root directory

---

### Step 1: Connect Your Cameras (2 minutes)

#### Option A: USB Connection (Recommended)
```bash
1. Connect Phone 1 via USB cable to MacBook
2. Connect Phone 2 via USB cable to MacBook
3. Open Iriun app on both phones
4. Open Iriun app on Mac
5. Verify both phones show "Connected"
```

#### Option B: Wi-Fi Connection
```bash
1. Ensure MacBook and both phones on same Wi-Fi network
2. Open Iriun app on Mac
3. Open Iriun app on Phone 1 - wait for "Connected"
4. Open Iriun app on Phone 2 - wait for "Connected"
```

### Step 2: Verify Cameras (30 seconds)

```bash
cd "Security Entry & Exit Management System"
source venv/bin/activate
python scripts/detect_cameras.py
```

**Expected Output:**
```
✅ Camera 0 FOUND: 1920x1080 @ 30.0 FPS
✅ Camera 1 FOUND: 1920x1080 @ 15.0 FPS
✅ Camera 2 FOUND: 1920x1080 @ 15.0 FPS
Total cameras found: 3
```

If you see **3 cameras** → Continue to Step 3 ✅  
If you see **2 or fewer** → See [Troubleshooting](#troubleshooting) below ⚠️

### Step 3: Run the YOLO System (30 seconds)

**Option A: Automated Quick Start (Recommended)**
```bash
./quick_start.sh
```

This script will:
- Check and install all dependencies
- Download missing YOLO models
- Run the demo automatically

**Option B: Manual Start**
```bash
python demo_yolo_cameras.py
```

**You should see:**
```
🔧 Initializing YOLO detectors...
✅ YOLOv8-face model loaded successfully
✅ YOLOv11 model loaded successfully
✅ Multi-modal re-ID system initialized
```

**Then 3 windows open:**
- Entry Camera (green labels with face/body detection)
- Exit Camera (yellow labels)
- Room Camera (green/red labels with trajectories)

### Step 4: Test the System (2 minutes)

1. **Register Yourself:**
   - Position your face in Entry Camera window
   - Press `e` key
   - You should see: "✅ Person P001 registered at ENTRY"

2. **Test Room Tracking:**
   - Move to Room Camera view
   - Your face/body should have a **GREEN** box (authorized)
   - You should see:
     - Face detection box (if visible)
     - Body detection box (if visible)
     - **PURPLE** trajectory trail
     - Match score in console (e.g., "Match: 0.72")

3. **Test Unauthorized Detection:**
   - Have someone else (not registered) appear in Room Camera
   - Their face should have a **RED** box (unauthorized)
   - Alert should trigger: "UNAUTHORIZED person detected"

4. **Check Console Output:**
   ```
   [INFO] AUTO-REGISTERED: P001 (face+body profile created)
   [INFO] ROOM MATCH: P001 | Similarity: 0.68 | Mode: both
   [INFO] Detection: face=0.89, body=0.82
   ```

5. **Quit and Export:**
   - Press `q` key
   - Session data saved to: `data/yolo_session_YYYYMMDD_HHMMSS.json`

---

## 🎮 Controls

| Key | Action |
|-----|--------|
| `e` | Register person at **Entry** camera |
| `x` | Test detection at **Exit** camera |
| `q` | **Quit** and export session data |

---

## 📊 What You Should See

### Entry Camera Window
```
┌─────────────────────────────────────┐
│ ENTRY CAMERA                        │
│ Registered: 1 | Inside: 0           │
├─────────────────────────────────────┤
│                                     │
│    ┌─────────┐                      │
│    │ [FACE]  │  ← Green box         │
│    │  ENTRY  │  ← Label             │
│    └─────────┘                      │
│                                     │
│ Press 'e' to register person        │
└─────────────────────────────────────┘
```

### Room Camera Window
```
┌─────────────────────────────────────┐
│ ROOM CAMERA                         │
│ Registered: 1 | Inside: 1           │
├─────────────────────────────────────┤
│                                     │
│    ┌─────────┐                      │
│    │ [FACE]  │  ← Green = Authorized│
│    │  P001   │     Red = Unauthorized
│    └─────────┘                      │
│       ↑                             │
│       └─── Purple trail             │
│           (trajectory)              │
└─────────────────────────────────────┘
```

### Console Output
```
============================================================
YOLO-BASED THREE-CAMERA MONITORING SYSTEM
============================================================
Using YOLOv8-face + YOLOv11 + Multi-Modal Re-ID

🔧 Initializing YOLO detectors...
✅ YOLOv8-face model loaded successfully
✅ YOLOv11 model loaded successfully
✅ Multi-modal re-ID system initialized

✅ Camera detection complete
✅ Entry camera (index 0): READY
✅ Room camera (index 2): READY
✅ Exit camera (index 1): READY

[INFO] AUTO-REGISTERED: P001
  Face features: ✓ | Body features: ✓
[INFO] ROOM MATCH: P001 | Similarity: 0.68 | Mode: both
  Face: 0.72 | Body: 0.65 | Combined: 0.68
[WARNING] UNAUTHORIZED person detected in room
```

---

## ⚠️ Troubleshooting

### Problem: Model Download Failed

**Error:** `Failed to load YOLOv8-face model: [Errno 2] No such file or directory: 'yolov8n-face.pt'`

**Fix:**
```bash
# Run the download script
python download_yolo_face.py

# If that fails, manual download:
# 1. Visit: https://github.com/derronqi/yolov8-face/releases
# 2. Download yolov8n-face.pt
# 3. Place in project root
```

### Problem: Import Error - ultralytics

**Error:** `ultralytics package not found`

**Fix:**
```bash
source venv/bin/activate
pip install ultralytics torch torchvision opencv-python
```

### Problem: Only 2 Cameras Detected

**Quick Fix:**
```bash
# Run the debug script
python scripts/debug_second_camera.py

# Follow the interactive steps
# It will guide you through:
# 1. Checking Iriun connections
# 2. Restarting apps in correct order
# 3. Verifying USB/Wi-Fi setup
```

**Manual Fix:**
```bash
# Close everything
1. Close Iriun on both phones
2. Close Iriun on Mac
3. Wait 5 seconds

# Restart in order
4. Open Iriun on Mac FIRST
5. Wait 5 seconds
6. Open Iriun on Phone 1
7. Wait for "Connected"
8. Open Iriun on Phone 2
9. Wait for "Connected"

# Re-test
10. python scripts/detect_cameras.py
```

### Problem: Camera Opens But Black Screen

**Fix:**
```bash
# Another app is using the camera
# Close these apps:
killall Zoom
killall Skype
killall "Photo Booth"
killall FaceTime

# Try again
python demo_three_cameras.py
```

### Problem: "Failed to open camera" Error

**Fix:**
```bash
# Check camera permissions
System Preferences → Security & Privacy → Camera
# Enable camera access for Terminal/Python

# Or reset camera system
sudo killall VDCAssistant
```

### Problem: Low Frame Rate / Laggy

**Fix:**
1. **Use USB** instead of Wi-Fi
2. **Close other apps** to free CPU
3. **Reduce display size** (edit demo_three_cameras.py line 563):
   ```python
   display_width = 480   # Instead of 640
   display_height = 360  # Instead of 480
   ```

---

## 🎯 Running with Only 2 Cameras

If you can't get the third camera working, you can still run the system:

```bash
# 2-camera mode (Entry + Room only with YOLO)
python demo_yolo_cameras.py
# Will work with 2 cameras, just ignore exit camera
```

This uses:
- **Camera 0**: Entry registration
- **Camera 1**: Room monitoring (tracking, unauthorized detection)

---

## 📁 Where is Everything?

```
Data Storage:
├── data/yolo_camera_demo.db               # SQLite database
├── data/yolo_camera_alerts.log            # Alert history
└── data/yolo_session_YYYYMMDD_HHMMSS.json # Exported session

YOLO Models (6-20 MB each):
├── yolov8n-face.pt    # Face detection model
└── yolo11n.pt         # Body detection model (auto-downloads)

View Data:
# Database
sqlite3 data/yolo_camera_demo.db
sqlite> SELECT * FROM entries;

# Alerts
cat data/yolo_camera_alerts.log

# Session
cat data/yolo_session_*.json
```

---

## 🔧 Advanced Options

### Custom Camera Indices

If cameras are detected in different order:

```bash
# Find your camera indices
python scripts/detect_cameras.py

# Edit demo_yolo_cameras.py line 736:
entry_idx = 0  # Change to your entry camera
exit_idx = 1   # Change to your exit camera
room_idx = 2   # Change to your room camera
```

### Adjust Sensitivity

Edit `demo_yolo_cameras.py`:

```python
# Line 68-70 - YOLO confidence thresholds
face_detector = YOLOv8FaceDetector(
    model_path="yolov8n-face.pt",
    confidence_threshold=0.5,  # Default: 0.5, Range: 0.3-0.7
)
body_detector = YOLOv11BodyDetector(
    model_path="yolo11n.pt",
    confidence_threshold=0.4,  # Default: 0.4, Range: 0.3-0.6
)

# Line 84-87 - Multi-modal re-ID weights
reid_system = MultiModalReID(
    face_weight=0.6,      # Default: 0.6, increase if faces are clear
    body_weight=0.4,      # Default: 0.4, increase for far-away people
    match_threshold=0.45, # Default: 0.45, Range: 0.35-0.60
)
```

---

## ✅ Success Checklist

After running the system, verify:

- [ ] YOLO models downloaded (yolov8n-face.pt present)
- [ ] Three windows opened (Entry, Exit, Room)
- [ ] All windows show live video
- [ ] Console shows "YOLO detectors initialized"
- [ ] Pressing `e` registers a person with face+body profile
- [ ] Console shows "AUTO-REGISTERED: P001"
- [ ] Registered person shows **GREEN** box in Room camera
- [ ] Console shows match scores (e.g., "Similarity: 0.68")
- [ ] Unregistered person shows **RED** box in Room camera
- [ ] Both face and body detection boxes visible
- [ ] Purple trajectory trails appear
- [ ] Console shows detection modes (face_only/body_only/both)
- [ ] Pressing `q` exports session data
- [ ] JSON file created in `data/` folder

**All checked?** → 🎉 **YOLO System Working!** Multi-modal re-ID active!

---

## 📚 Next Steps

### Learn More:
- **YOLO System Documentation:** `RUN_YOLO_SYSTEM.md`
- **Critical Fix & Upgrade Guide:** `CRITICAL_FIX_AND_YOLO_UPGRADE.md`
- **Camera Setup:** `CAMERA_SETUP_GUIDE.md`

### Improve Accuracy:
- Ensure **good lighting** in all camera views (YOLO needs light)
- Use **USB connection** for stability
- **Tune YOLO confidence** thresholds (face: 0.3-0.7, body: 0.3-0.6)
- **Adjust face/body weights** based on your camera positions
  - Close cameras with clear faces: face_weight=0.7, body_weight=0.3
  - Far cameras / body-focused: face_weight=0.4, body_weight=0.6
- **Lower match_threshold** if too many false negatives (0.35-0.40)
- **Raise match_threshold** if too many false positives (0.50-0.55)

### Current System (YOLO-based):
- ✅ YOLOv8-face detection (high accuracy face detection)
- ✅ YOLOv11 body detection (person detection)
- ✅ Multi-modal re-identification (face + body features)
- ✅ Weighted similarity matching
- ✅ Auto-registration at entry
- ✅ Real-time tracking and alerts

### Future Enhancements:
- Face embeddings with ArcFace (98%+ accuracy)
- Kalman filtering for smooth trajectories
- ByteTrack for multi-person occlusion handling
- Advanced threat scoring and behavior analysis

---

## 🆘 Still Having Issues?

1. **Check model files:**
   ```bash
   ls -lh yolov8n-face.pt yolo11n.pt
   # Should see yolov8n-face.pt (~6 MB)
   ```

2. **Re-run download script:**
   ```bash
   python download_yolo_face.py
   ```

3. **Read the detailed guide:**
   ```bash
   cat RUN_YOLO_SYSTEM.md
   cat CRITICAL_FIX_AND_YOLO_UPGRADE.md
   ```

4. **Run interactive debug:**
   ```bash
   python scripts/debug_second_camera.py
   ```

3. **Check Python environment:**
   ```bash
   which python
   python --version
   pip list | grep opencv
   ```

5. **Nuclear option (restart everything):**
   ```bash
   # Close all apps
   # Restart MacBook
   # Reconnect cameras
   # Re-download models: python download_yolo_face.py
   # Run: python demo_yolo_cameras.py
   ```

---

## 💡 Tips for Best Results

1. **Lighting:** Ensure good, consistent lighting in all camera views
2. **Positioning:** Mount cameras at face height (1.5-1.7m)
3. **Distance:** Keep people within 3-5 meters of cameras
4. **Angles:** Front-facing cameras work best (not side angles)
5. **Stability:** Secure camera mounts (no shaking)
6. **Connection:** USB is more stable than Wi-Fi
7. **Resources:** Close unnecessary apps for better FPS

---

## 🎊 System Status

```
Phase 1: Database & Alerts              ✅ COMPLETE
Phase 2: Three-Camera Tracking          ✅ COMPLETE
Phase 2.5: YOLO Multi-Modal Re-ID       ✅ COMPLETE (YOU ARE HERE)
Phase 3: Embeddings & Advanced Tracking 🔄 NEXT
```

**Ready to test?** Run: `./quick_start.sh` or `python demo_yolo_cameras.py`

---

*Quick Start Guide | YOLO System*
*System: Multi-Modal Face+Body Re-Identification with YOLOv8 & YOLOv11*