# 🚪 Entry/Exit Tracking System - Dual Camera Setup

## Overview

A **real-time entry/exit tracking system** using two cameras:
- **Camera 1 (Phone via Iriun)** = ENTRY point 🟢
- **Camera 0 (Mac Webcam)** = EXIT point 🔴

**Features:**
- ✅ Tracks who enters and exits
- ✅ Maintains "Currently Inside" database
- ✅ Prevents ID switching with grace period
- ✅ Shows real-time statistics
- ✅ Logs entry/exit timestamps
- ✅ Calculates visit duration

---

## 🚀 Quick Start

### Step 1: Setup Phone Camera (Iriun)

**On Phone (Android/iOS):**
1. Download **Iriun Webcam** app from Play Store/App Store
2. Open the app
3. Connect to same WiFi as your Mac

**On Mac:**
1. Download **Iriun Webcam** from https://iriun.com/
2. Install and run the Iriun app
3. Your phone should automatically connect

**Verify Connection:**
```bash
# Phone camera should appear as additional webcam
ls /dev/video*  # Linux
# Or use Photo Booth on Mac to test
```

### Step 2: Install Dependencies

```bash
pip install opencv-python numpy
```

### Step 3: Run the System

```bash
cd "Security Entry & Exit Management System"
python entry_exit_system.py
```

The system will:
1. **Auto-detect available cameras**
2. **Show you which cameras will be used**
3. **Start tracking after 3 seconds**

---

## 🎬 What You'll See

### Display Layout:

```
┌────────────────────────────────┬────────────────────────────────┐
│   ENTRY CAMERA (Green)         │   EXIT CAMERA (Red)            │
│   [Phone via Iriun]            │   [Mac Webcam]                 │
│                                │                                │
│   ┌──────────────┐             │   ┌──────────────┐             │
│   │ abc123de     │             │   │ def456gh     │             │
│   │              │             │   │              │             │
│   │  Your Face   │             │   │  Your Face   │             │
│   └──────────────┘             │   └──────────────┘             │
│   Detected: 1                  │   Detected: 1                  │
└────────────────────────────────┴────────────────────────────────┘
│ Currently Inside: 5            │ Total Entries: 12              │
│ Total Exits: 7                 │ Unique Visitors: 8             │
└────────────────────────────────────────────────────────────────┘
```

### Terminal Output:

```
============================================================
ENTRY/EXIT TRACKING SYSTEM STARTED
============================================================
Configuration:
  ENTRY Camera: Index 1 (Phone/Iriun)
  EXIT Camera:  Index 0 (Mac Webcam)

Instructions:
  - Show face at ENTRY camera to enter
  - Show face at EXIT camera to exit
  - System tracks who's currently inside
  - Press 'q' or Ctrl+C to exit and see summary
============================================================

✓ ENTRY: abc123de entered
✓ ENTRY: def456gh entered
✗ EXIT:  abc123de exited
Frame   30 | Inside: 1 | Entries: 2 | Exits: 1
```

### Final Summary (Ctrl+C):

```
============================================================
ENTRY/EXIT TRACKING SUMMARY
============================================================
Total Unique Visitors:    8
Total Entries:            12
Total Exits:              10
Currently Inside:         2
============================================================

People Currently Inside:
  1. def456gh (Inside for 125s, seen 3 times)
  2. ghi789jk (Inside for 45s, seen 1 times)

Recent Exits (Last 5):
  1. abc123de (Visit duration: 180s)
  2. jkl012mn (Visit duration: 95s)
  3. opq345rs (Visit duration: 240s)
============================================================
```

---

## 🎯 How It Works

### System Architecture:

```
┌─────────────┐         ┌─────────────┐
│   ENTRY     │         │    EXIT     │
│   Camera    │         │   Camera    │
└──────┬──────┘         └──────┬──────┘
       │                       │
       │  Detect Face          │  Detect Face
       │  (Haar Cascade)       │  (Haar Cascade)
       │                       │
       ▼                       ▼
┌──────────────────────────────────────┐
│        Face Tracker                  │
│  - Extract histogram features        │
│  - Match against global database     │
│  - Assign/reuse UUID                 │
│  - 3-second grace period             │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│      Entry/Exit Database             │
│  - Record entry at ENTRY camera      │
│  - Record exit at EXIT camera        │
│  - Track "Inside_Now" table          │
│  - Calculate visit duration          │
└──────────────────────────────────────┘
```

### Process Flow:

1. **Person shows face at ENTRY camera:**
   - Face detected → Histogram computed
   - Check global database for existing ID
   - If new: Create UUID, add to database
   - If known: Reuse existing UUID
   - Record entry timestamp
   - Add to "Inside_Now" table

2. **Person shows face at EXIT camera:**
   - Face detected → Histogram computed
   - Match against global database
   - Check if person is in "Inside_Now" table
   - If yes: Record exit, calculate duration
   - Remove from "Inside_Now" table

3. **Grace Period (3 seconds):**
   - If person disappears from camera briefly
   - System remembers them for 3 seconds
   - Same ID assigned when they reappear
   - Prevents ID switching

---

## 🔧 Configuration

### Camera Indices

If auto-detection doesn't work, manually specify cameras:

Edit `entry_exit_system.py` (bottom of file):

```python
# Change these lines (around line 600):
app = EntryExitApp(
    entry_camera_index=1,  # Phone/Iriun (try 0 if 1 doesn't work)
    exit_camera_index=0    # Mac webcam
)
```

### Tracking Parameters

Edit lines 237-238 to adjust tracking behavior:

```python
self.entry_tracker = SimpleFaceTracker(
    grace_period_seconds=5.0,     # Increase for longer memory
    similarity_threshold=0.60     # Lower for more lenient matching
)
self.exit_tracker = SimpleFaceTracker(
    grace_period_seconds=5.0,
    similarity_threshold=0.60
)
```

**Parameter Guide:**

| Parameter | Description | Recommended Values |
|-----------|-------------|-------------------|
| `grace_period_seconds` | Memory duration | 3.0-5.0 seconds |
| `similarity_threshold` | Match strictness | 0.60-0.75 |

**Adjust if:**
- **Too many duplicate IDs:** Increase grace period, lower threshold
- **Different people same ID:** Increase threshold
- **Same person multiple IDs:** Lower threshold, increase grace period

---

## 🧪 Testing Scenarios

### Test 1: Basic Entry/Exit
1. Show **your face** at ENTRY camera (Phone)
2. Terminal shows: `✓ ENTRY: abc123de entered`
3. Stats show: `Currently Inside: 1`
4. Show **your face** at EXIT camera (Mac)
5. Terminal shows: `✗ EXIT: abc123de exited`
6. Stats show: `Currently Inside: 0`

**Expected:** Same ID used at both cameras ✅

### Test 2: Multiple People
1. **Person A** at ENTRY → `✓ ENTRY: abc123de`
2. **Person B** at ENTRY → `✓ ENTRY: def456gh`
3. **Person C** at ENTRY → `✓ ENTRY: ghi789jk`
4. Stats: `Currently Inside: 3`
5. **Person A** at EXIT → `✗ EXIT: abc123de`
6. Stats: `Currently Inside: 2`

**Expected:** 3 unique IDs, correct tracking ✅

### Test 3: Re-identification
1. **Your face** at ENTRY → Gets ID `abc123de`
2. Move away briefly (< 3 seconds)
3. **Your face** at ENTRY again
4. **Expected:** Same ID `abc123de` (not new ID) ✅

### Test 4: Visit Duration
1. Note entry time when you enter
2. Wait 30 seconds
3. Exit via EXIT camera
4. Check summary: Should show ~30s duration ✅

---

## 🐛 Troubleshooting

### ❌ "Need at least 2 cameras!"

**Problem:** System can't find phone camera

**Solutions:**

1. **Check Iriun is running:**
   - Open Iriun app on phone
   - Open Iriun on Mac
   - Verify connection (green checkmark)

2. **Check WiFi connection:**
   - Phone and Mac must be on **same WiFi network**
   - Restart Iriun on both devices

3. **Manually find camera index:**
   ```python
   # Run camera scanner
   python -c "
   import cv2
   for i in range(5):
       cap = cv2.VideoCapture(i)
       if cap.isOpened():
           print(f'Camera {i}: Available')
       cap.release()
   "
   ```

4. **Try different indices:**
   - Edit `entry_exit_system.py`
   - Try `entry_camera_index=0` or `2`

---

### ❌ "Cannot open ENTRY/EXIT camera"

**Solutions:**

1. **Grant camera permissions:**
   - System Settings → Privacy & Security → Camera
   - Enable for Terminal/iTerm/VS Code

2. **Close other apps using camera:**
   - Photo Booth, Zoom, Teams, etc.

3. **Reset camera daemon (Mac):**
   ```bash
   sudo killall VDCAssistant
   ```

4. **Test cameras individually:**
   ```bash
   python test_basic_face_detection.py
   ```

---

### ❌ Getting wrong IDs at EXIT

**Problem:** Person enters as `abc123de` but exits as `def456gh`

**Solutions:**

1. **Lower similarity threshold:**
   ```python
   similarity_threshold=0.60  # Was 0.65
   ```

2. **Increase grace period:**
   ```python
   grace_period_seconds=5.0  # Was 3.0
   ```

3. **Ensure consistent lighting:**
   - Both cameras should have similar lighting
   - Avoid backlighting (windows behind person)

4. **Face camera directly:**
   - Look straight at camera (not sideways)
   - Give system 2-3 seconds to capture features

---

### ❌ Different people getting same ID

**Problem:** Your friend enters as your ID

**Solutions:**

1. **Increase similarity threshold:**
   ```python
   similarity_threshold=0.75  # Was 0.65
   ```

2. **Better lighting and positioning:**
   - Ensure faces are clearly visible
   - Face cameras directly
   - Remove hats/sunglasses

---

### ❌ Stats not updating

**Problem:** "Currently Inside" count wrong

**Possible causes:**

1. **Person entered but didn't exit via EXIT camera**
   - They must physically show face at EXIT camera
   - Just leaving the area doesn't count as exit

2. **ID mismatch between cameras**
   - Lower similarity threshold
   - Ensure consistent lighting

3. **Grace period expired**
   - If person takes >3 seconds between cameras
   - They get new ID at second camera
   - Increase grace period

---

## 📊 Statistics Explained

### Currently Inside
Number of people who entered but haven't exited yet.

**Formula:** `Total Entries - Total Exits`

### Total Entries
How many times anyone entered via ENTRY camera.

**Note:** Same person can enter multiple times.

### Total Exits
How many times anyone exited via EXIT camera.

### Unique Visitors
Number of distinct people (unique IDs).

**Example:**
- Person A enters 3 times, exits 3 times
- Person B enters 1 time, exits 1 time
- **Unique Visitors = 2** (not 4)

---

## 🎓 Advanced Usage

### Persistent Database

To save entry/exit records to a file:

Add to `EntryExitDatabase.__init__`:

```python
import json

def save_to_file(self, filename="entry_exit_log.json"):
    data = {
        "entries": [
            {
                "person_id": e["person_id"],
                "time": e["time"].isoformat()
            }
            for e in self.all_entries
        ],
        "exits": [
            {
                "person_id": e["person_id"],
                "time": e["time"].isoformat(),
                "duration": e["duration_seconds"]
            }
            for e in self.all_exits
        ]
    }
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
```

Call on exit:
```python
self.database.save_to_file()
```

### Alert on Capacity

Add capacity warning:

```python
MAX_CAPACITY = 50

if stats['currently_inside'] > MAX_CAPACITY:
    print(f"⚠️  WARNING: Capacity exceeded! ({stats['currently_inside']}/{MAX_CAPACITY})")
```

### Export Reports

Generate daily report:

```python
from datetime import date

def generate_report(self):
    today = date.today()
    entries_today = [e for e in self.all_entries if e["time"].date() == today]
    
    print(f"Daily Report - {today}")
    print(f"Total visitors: {len(set([e['person_id'] for e in entries_today]))}")
    print(f"Total entries: {len(entries_today)}")
```

---

## 💡 Best Practices

### Camera Placement

1. **ENTRY Camera (Phone via Iriun):**
   - Face entrance door
   - Height: Eye level (~1.5-1.8m)
   - Distance: 1-2 meters from door
   - Lighting: Well-lit, no backlighting

2. **EXIT Camera (Mac Webcam):**
   - Face exit door
   - Same height as entry camera
   - Same distance from door
   - Consistent lighting with entry

### Workflow

1. **Person enters:**
   - Must look at ENTRY camera (Phone)
   - Wait 1-2 seconds for detection
   - Green box with ID appears
   - Proceed inside

2. **Person exits:**
   - Must look at EXIT camera (Mac)
   - Wait 1-2 seconds for detection
   - Red box with ID appears
   - Can leave

### Performance

- **FPS:** System should run at 15-30 FPS
- **Latency:** Detection within 1-2 seconds
- **Memory:** ~2KB per person tracked
- **Capacity:** Can handle 1000+ unique visitors

---

## 🔄 Integration with Full Pipeline

To use ArcFace instead of histograms:

1. Replace `SimpleFaceTracker` with your existing `FaceReIdentificationSystem`
2. Update matching logic to use embeddings
3. Keep the entry/exit database structure
4. Maintain grace period logic

See `face_reidentification_test.py` for ArcFace implementation.

---

## 📝 Known Limitations

1. **Single face per camera:** Only tracks one face at a time per camera
2. **Manual exit required:** Person must show face at EXIT camera
3. **Network dependency:** Iriun requires WiFi connection
4. **Lighting sensitive:** Works best in consistent lighting
5. **Frontal faces only:** Haar Cascade requires facing camera

**Future improvements:**
- Multiple face tracking
- Body detection fallback
- Offline mode with USB cameras
- Better handling of varied lighting
- Profile face detection

---

## 🎯 Success Criteria

- [x] Both cameras detected and opened
- [x] Entry camera shows green boxes
- [x] Exit camera shows red boxes
- [x] Same person gets same ID at both cameras
- [x] "Currently Inside" count accurate
- [x] Entry/exit events logged correctly
- [x] Visit duration calculated correctly
- [x] Summary shows all statistics

**If all checked → System working correctly!** ✅

---

## 📞 Need Help?

- **RUN_THIS_FIRST.md** - Basic face detection test
- **BASIC_TEST_README.md** - Troubleshooting guide
- **README.md** - Full system documentation
- **START_HERE.md** - General overview

---

## 🚀 Quick Commands

```bash
# Install
pip install opencv-python numpy

# Find cameras
python entry_exit_system.py  # Auto-detects

# Run system
python entry_exit_system.py

# Exit
Press 'q' or Ctrl+C
```

---

**Ready to track entries and exits!** 🚪✨

*Version 1.0 | Dual-Camera Entry/Exit System*