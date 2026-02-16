# Quick Start Guide - Three Camera System
## Get Up and Running in 5 Minutes

---

## 🚀 Fast Track Setup

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

### Step 3: Run the System (30 seconds)

```bash
python demo_three_cameras.py
```

**You should see 3 windows open:**
- Entry Camera (green labels)
- Exit Camera (yellow labels)
- Room Camera (green/red labels)

### Step 4: Test the System (2 minutes)

1. **Register Yourself:**
   - Position your face in Entry Camera window
   - Press `e` key
   - You should see: "✅ Person P001 registered at ENTRY"

2. **Test Room Tracking:**
   - Move to Room Camera view
   - Your face should have a **GREEN** box (authorized)
   - You should see a **PURPLE** trajectory trail

3. **Test Unauthorized Detection:**
   - Have someone else (not registered) appear in Room Camera
   - Their face should have a **RED** box (unauthorized)
   - Alert should trigger: "UNAUTHORIZED person detected"

4. **Quit and Export:**
   - Press `q` key
   - Session data saved to: `data/session_YYYYMMDD_HHMMSS.json`

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
✅ Camera detection complete
✅ Entry camera (index 0): READY
✅ Exit camera (index 1): READY
✅ Room camera (index 2): READY

[INFO] Person P001 registered at ENTRY
[INFO] Person P001 detected in room
[WARNING] Person P001 running detected (velocity: 2.3 m/s)
[CRITICAL] UNAUTHORIZED person detected in room
```

---

## ⚠️ Troubleshooting

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
# 2-camera mode (Entry + Room only)
python demo_entry_room.py
```

This uses:
- **Camera 0**: Entry registration
- **Camera 1**: Room monitoring (tracking, unauthorized detection)

---

## 📁 Where is Everything?

```
Data Storage:
├── data/three_camera_demo.db          # SQLite database
├── data/three_camera_alerts.log       # Alert history
└── data/session_YYYYMMDD_HHMMSS.json  # Exported session

View Data:
# Database
sqlite3 data/three_camera_demo.db
sqlite> SELECT * FROM entries;

# Alerts
cat data/three_camera_alerts.log

# Session
cat data/session_*.json
```

---

## 🔧 Advanced Options

### Custom Camera Indices

If cameras are detected in different order:

```bash
# Find your camera indices
python scripts/detect_cameras.py

# Edit demo_three_cameras.py line 714:
entry_idx = 0  # Change to your entry camera
exit_idx = 1   # Change to your exit camera
room_idx = 2   # Change to your room camera
```

### Adjust Sensitivity

Edit `demo_three_cameras.py`:

```python
# Line 101 - More strict matching (fewer false positives)
similarity_threshold=0.70  # Default: 0.60

# Line 516 - Velocity threshold for running detection
if velocity > 3.0:  # Default: 2.0 m/s

# Line 446 - Mass gathering threshold
if len(faces) >= 10:  # Default: 5 people
```

---

## ✅ Success Checklist

After running the system, verify:

- [ ] Three windows opened (Entry, Exit, Room)
- [ ] All windows show live video
- [ ] Stats panels display at top of each window
- [ ] Pressing `e` registers a person (UUID assigned)
- [ ] Registered person shows **GREEN** box in Room camera
- [ ] Unregistered person shows **RED** box in Room camera
- [ ] Purple trajectory trails appear
- [ ] Console shows alerts
- [ ] Pressing `q` exports session data
- [ ] JSON file created in `data/` folder

**All checked?** → 🎉 **Phase 2 Complete!** System is working!

---

## 📚 Next Steps

### Learn More:
- **Full Setup Guide:** `CAMERA_SETUP_GUIDE.md`
- **Complete Documentation:** `PHASE2_COMPLETE.md`
- **Usage Guide:** `PHASE2_USAGE_GUIDE.md`

### Improve Accuracy:
- Ensure **good lighting** in all camera views
- Use **USB connection** for stability
- **Calibrate** pixels_per_meter for your room
- **Adjust** similarity_threshold based on testing

### Phase 3 (Coming Next):
- Face embeddings (95%+ accuracy)
- Kalman filtering for smooth trajectories
- Multi-person tracking (ByteTrack)
- Advanced analytics and threat detection

---

## 🆘 Still Having Issues?

1. **Read the detailed guide:**
   ```bash
   cat CAMERA_SETUP_GUIDE.md
   ```

2. **Run interactive debug:**
   ```bash
   python scripts/debug_second_camera.py
   ```

3. **Check Python environment:**
   ```bash
   which python
   python --version
   pip list | grep opencv
   ```

4. **Nuclear option (restart everything):**
   ```bash
   # Close all apps
   # Restart MacBook
   # Reconnect cameras
   # Run: python demo_three_cameras.py
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
Phase 1: Database & Alerts        ✅ COMPLETE
Phase 2: Three-Camera Tracking    ✅ COMPLETE (YOU ARE HERE)
Phase 3: Advanced Analytics       🔄 NEXT
```

**Ready to test?** Run: `python demo_three_cameras.py`

---

*Quick Start Guide | Phase 2 Implementation*
*System: Three-Camera Entry/Exit/Room Monitoring*