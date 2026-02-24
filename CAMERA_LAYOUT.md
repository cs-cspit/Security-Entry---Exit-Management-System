# 📹 CAMERA LAYOUT & SETUP GUIDE

## 🎯 YOUR CURRENT SETUP

```
┌─────────────────────────────────────────────────────────────────┐
│                    THREE-CAMERA SYSTEM LAYOUT                    │
└─────────────────────────────────────────────────────────────────┘

Camera 0 (External)          Camera 2 (MacBook)         Camera 1 (External)
    ENTRY GATE    ────────>    ROOM MONITOR  ────────>    EXIT GATE
                                                    
┌──────────────┐            ┌──────────────┐            ┌──────────────┐
│              │            │              │            │              │
│   CAMERA 0   │            │   CAMERA 2   │            │   CAMERA 1   │
│              │            │              │            │              │
│  Windows 7   │            │   MacBook    │            │  External    │
│  Old Webcam  │            │   Built-in   │            │   Webcam     │
│  (10+ yrs)   │            │   Webcam     │            │              │
│              │            │              │            │              │
└──────────────┘            └──────────────┘            └──────────────┘
       │                           │                           │
       │                           │                           │
       ▼                           ▼                           ▼
  AUTO-REGISTER              TRACK + VELOCITY              MATCH + EXIT
  New People                 Real-time Tracking            Close Session
```

---

## 🔄 COMPLETE WORKFLOW

### 1️⃣ **ENTRY GATE** (Camera 0 - Windows 7 Webcam)
```
Person approaches → Detected → AUTO-REGISTERED as P001, P002, etc.
                              ↓
                         Session Started
                         Status: "INSIDE"
```

**What happens:**
- YOLO26 detects person
- Extracts OSNet + Hair + Skin + Clothing features
- Auto-assigns ID: P001, P002, P003...
- Creates active session
- Stores in database

**Visual:**
- 🟡 Yellow box during detection
- 🟢 Green "NEW: P001" when registered
- Console: ✅ Registered P001 at entry gate

---

### 2️⃣ **ROOM MONITOR** (Camera 2 - MacBook Webcam)
```
Person enters room → Matched against registered people
                              ↓
                    ┌─────────┴─────────┐
                    │                   │
              AUTHORIZED          UNAUTHORIZED
            (Active Session)     (No Session)
                    │                   │
                    ▼                   ▼
              GREEN BOX               RED BOX
           Velocity Tracked         Alert Triggered
           Trajectory Shown         Security Event
```

**What happens:**
- YOLO26 detects person
- Extracts features
- Compares with all registered people
- Checks if they have active session

**If AUTHORIZED (Active Session):**
- ✅ Show GREEN bounding box
- ✅ Display ID and similarity (e.g., "P001 (0.93)")
- ✅ Track trajectory (yellow line)
- ✅ Calculate velocity (m/s)
- ✅ Color-code velocity:
  - 🟢 GREEN: < 1.0 m/s (walking slowly)
  - 🟠 ORANGE: 1.0-2.0 m/s (fast walking)
  - 🔴 RED: > 2.0 m/s (running - alert!)

**If UNAUTHORIZED (No Active Session):**
- ❌ Show RED bounding box
- ❌ Label: "UNAUTHORIZED"
- ❌ Trigger CRITICAL alert
- ❌ Log security event

**Debug Output (Press D):**
```
🔍 Room Match: P001 (0.933)
   OSNet: 0.936 × 0.50 = 0.468
   Hair:  1.000 × 0.15 = 0.150
   Skin:  0.990 × 0.15 = 0.149
   Cloth: 0.833 × 0.20 = 0.167
```

---

### 3️⃣ **EXIT GATE** (Camera 1 - External Webcam)
```
Person approaches → Matched against inside people
                              ↓
                    ┌─────────┴─────────┐
                    │                   │
              VALID EXIT            NO SESSION
            (Active Session)      (Already Exited)
                    │                   │
                    ▼                   ▼
              GREEN BOX               ORANGE BOX
           Close Session           "NO SESSION"
           Show Stats             Can't exit twice
```

**What happens:**
- YOLO26 detects person
- Extracts features
- Matches against people with active sessions
- Closes session if match found

**If VALID EXIT:**
- ✅ Show GREEN box: "P001 EXITING"
- ✅ Close active session
- ✅ Calculate session statistics:
  - Duration (seconds)
  - Average velocity (m/s)
  - Max velocity (m/s)
- ✅ Update database
- ✅ Remove from "inside" list
- ✅ Status changes to "EXITED"

**Console Output:**
```
✅ P001 exited
   Duration: 45.3s
   Avg velocity: 0.85 m/s
   Max velocity: 1.42 m/s
```

---

## 🎨 COLOR CODES

### Bounding Box Colors:
| Color | Meaning | Location |
|-------|---------|----------|
| 🟡 **Yellow** | Detecting... | Entry (before registration) |
| 🟢 **Green** | Authorized / Registered | All cameras (good status) |
| 🟠 **Orange** | Recognized but no session | Exit (person already exited) |
| 🔴 **Red** | Unauthorized | Room (security threat) |

### Velocity Colors (Room Only):
| Color | Speed Range | Status |
|-------|-------------|--------|
| 🟢 **Green** | < 1.0 m/s | Walking slowly |
| 🟠 **Orange** | 1.0-2.0 m/s | Fast walking |
| 🔴 **Red** | > 2.0 m/s | Running (alert!) |

### Trajectory:
| Color | Meaning |
|-------|---------|
| 🟡 **Yellow** | Movement path (last 50 points) |

---

## 📊 WINDOW LABELS

When you run the system, you'll see **3 windows**:

### Window 1: "Entry Gate"
- Shows Camera 0 feed
- Status overlay (top-left):
  - "ENTRY GATE" (yellow text)
  - Registered count
  - People inside count
  - Detections this frame

### Window 2: "Room Monitoring"
- Shows Camera 2 feed (MacBook!)
- Status overlay (top-left):
  - "ROOM MONITORING" (yellow text)
  - People inside count
  - Authorized count (green)
  - Unauthorized count (red)
  - Detections this frame
  - "DEBUG MODE: ON" (if enabled)

### Window 3: "Exit Gate"
- Shows Camera 1 feed
- Status overlay (top-left):
  - "EXIT GATE" (magenta text)
  - Exited count
  - Still inside count
  - Detections this frame

---

## 🔧 CAMERA NOTES

### Camera 0 (Entry - Windows 7 Webcam)
**Characteristics:**
- 10+ years old
- Inconsistent FPS
- Variable resolution
- May have poor lighting

**Configuration:**
- ✅ NO forced resolution (uses native settings)
- ✅ NO forced FPS (adapts automatically)
- ✅ Auto-registration enabled (no manual control needed)
- ✅ 5-second cooldown prevents duplicate registrations

**Tips:**
- Good lighting helps feature extraction
- Stand 1-2 meters from camera
- Face camera directly for best detection

### Camera 2 (Room - MacBook Built-in)
**Characteristics:**
- Modern camera
- Consistent FPS
- Good resolution
- Built-in lighting adjustment

**Configuration:**
- ✅ Native resolution maintained
- ✅ MPS (Apple Silicon) acceleration
- ✅ Trajectory tracking enabled
- ✅ Velocity calculation active

**Tips:**
- Position MacBook to cover room area
- Height: 1.5-2 meters optimal
- Wide angle preferred

### Camera 1 (Exit - External Webcam)
**Characteristics:**
- External USB webcam
- Moderate quality

**Configuration:**
- ✅ Native resolution maintained
- ✅ Session closure on match
- ✅ Statistics calculation

**Tips:**
- Close-up view (1-2 meters)
- Stable mounting preferred

---

## 🧪 TEST SCENARIOS

### Scenario 1: Normal Entry → Room → Exit
```
1. Stand at Entry (Camera 0)
   → System auto-registers you as P001
   → Session started
   
2. Move to Room (Camera 2)
   → GREEN box appears
   → Velocity tracked
   → Trajectory shown
   
3. Move to Exit (Camera 1)
   → GREEN box "P001 EXITING"
   → Session closed
   → Stats displayed
```

### Scenario 2: Unauthorized Entry
```
1. Stand at Room (Camera 2) WITHOUT going through Entry
   → RED box "UNAUTHORIZED"
   → CRITICAL alert triggered
   → Security event logged
```

### Scenario 3: Double Exit Prevention
```
1. Register at Entry → P001
2. Exit at Exit → Session closed
3. Appear at Exit again
   → ORANGE box "P001 NO SESSION"
   → Can't exit twice
```

### Scenario 4: Multi-Person Tracking
```
1. Person A at Entry → P001 registered
2. Person B at Entry → P002 registered
3. Both in Room
   → P001: GREEN box + velocity
   → P002: GREEN box + velocity
   → Different trajectories shown
4. Person A exits → P001 session closed
5. Person B still in room → P002 still GREEN
```

### Scenario 5: Running Detection
```
1. Register at Entry → P001
2. Walk slowly in Room → GREEN velocity (0.5 m/s)
3. Walk fast → ORANGE velocity (1.5 m/s)
4. RUN across room → RED velocity + "RUNNING!" alert
```

---

## 🎮 CONTROLS REMINDER

| Key | Function |
|-----|----------|
| **D** | Toggle debug (show matching scores) |
| **S** | Show statistics |
| **C** | Clear all registrations |
| **Q** | Quit and save data |

---

## 📈 STATISTICS OUTPUT (Press S)

```
======================================================================
  SYSTEM STATISTICS
======================================================================
Registered People:      5
Currently Inside:       2
Total Exited:           3
Unauthorized Detections: 1

Camera Detections:
  Entry:  12
  Room:   156
  Exit:   8
  Total:  176

Active Sessions:
  P004: 45.3s inside
  P005: 12.8s inside
======================================================================
```

---

## 💾 DATA STORAGE

### Database: `data/yolo26_complete_system.db`
Stores:
- Person profiles (ID, features, timestamps)
- Entry/exit records
- Session durations
- Velocity data (avg/max)
- Trajectory points

### Alerts Log: `data/yolo26_system_alerts.log`
Records:
- Unauthorized entries
- Running detections
- System events
- Timestamps

---

## 🚀 READY TO RUN!

```bash
source venv/bin/activate
python3 yolo26_complete_system.py
```

Everything is configured for YOUR exact camera setup:
- ✅ Old Windows 7 webcam handled gracefully
- ✅ MacBook as room monitor
- ✅ External camera as exit gate
- ✅ All features enabled

**GO TEST IT NOW!** 🔥