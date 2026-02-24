# 🚀 YOLO26 ULTIMATE SECURITY SYSTEM
## Complete Three-Camera Entry/Exit/Room Monitoring

---

## 🎯 WHAT IS THIS?

This is the **COMPLETE** security system that does EVERYTHING:

✅ **Entry Gate** - Auto-registers people entering with face + body features  
✅ **Room Monitoring** - Tracks authorized people with real-time velocity  
✅ **Exit Gate** - Matches people exiting and calculates session statistics  
✅ **Multi-Modal Re-ID** - OSNet + Hair + Skin + Clothing analysis  
✅ **Velocity Tracking** - Real-time speed detection with running alerts  
✅ **Unauthorized Detection** - Alerts when unknown people appear  
✅ **Database Logging** - Complete session history with trajectories  

---

## 🏃 QUICK START (3 STEPS!)

### Step 1: Run the Launcher
```bash
cd "Security Entry & Exit Management System"
./RUN_ULTIMATE_SYSTEM.sh
```

### Step 2: Position Yourself
- Stand in front of camera 1 (Entry Gate) to get registered
- Move to camera 2 (Room) - you'll be tracked with GREEN box
- Move to camera 3 (Exit Gate) - your session will close

### Step 3: Watch the Magic! ✨
- **GREEN boxes** = Authorized people with velocity tracking
- **RED boxes** = Unauthorized people (alerts triggered)
- **Trajectories** = Yellow lines showing movement paths
- **Velocity** = Real-time m/s display with color coding

---

## 📹 CAMERA SETUP

### Required: 3 Cameras
1. **Entry Gate** (Camera 0) - Auto-registers new people
2. **Room Monitoring** (Camera 1) - Tracks authorized + detects unauthorized
3. **Exit Gate** (Camera 2) - Matches and closes sessions

### If You Have < 3 Cameras:
The system will reuse available cameras for missing views.  
Even with 1 camera, you can test the re-identification!

### Camera Placement Tips:
- **Entry/Exit**: Close-up view (1-2 meters) for clear face detection
- **Room**: Wide view covering the area you want to monitor
- **Height**: Mount at 1.5-2 meters for best body detection
- **Lighting**: Good lighting helps feature extraction

---

## 🎮 CONTROLS

| Key | Function |
|-----|----------|
| **E** | Force register at entry (auto-register is default) |
| **D** | Toggle debug output (shows detailed matching scores) |
| **C** | Clear all registrations and restart |
| **S** | Show statistics (people inside, exited, velocities) |
| **Q** | Quit and export session data |

---

## 🎨 VISUAL INDICATORS

### Bounding Box Colors:
- **🟢 GREEN** = Authorized person with active session
- **🔴 RED** = Unauthorized person (no active session)
- **🟠 ORANGE** = Person recognized but no active session

### Velocity Colors:
- **🟢 GREEN** = < 1.0 m/s (walking slowly)
- **🟠 ORANGE** = 1.0-2.0 m/s (fast walking)
- **🔴 RED** = > 2.0 m/s (running - triggers alert!)

### Trajectory Lines:
- **Yellow lines** = Path of movement
- **Thickness** = Older → Thinner, Newer → Thicker

---

## 🧠 HOW IT WORKS

### 1️⃣ Entry Gate (Auto-Registration)
```
Person detected → Extract features → Auto-register as P001, P002, etc.
↓
Features extracted:
  • OSNet embedding (512D learned features)
  • Hair color (top 15% of body bbox)
  • Skin tone (HSV analysis from body regions)
  • Upper clothing (top 50% of body)
  • Lower clothing (bottom 50% of body)
↓
Session created → Person marked "INSIDE"
```

### 2️⃣ Room Monitoring (Tracking + Velocity)
```
Person detected → Extract features → Match against registered people
↓
IF MATCH + ACTIVE SESSION:
  ✅ Show GREEN box
  ✅ Update trajectory
  ✅ Calculate velocity
  ✅ Log to database
ELSE:
  🚨 Show RED box
  🚨 Trigger UNAUTHORIZED alert
  🚨 Log security event
```

### 3️⃣ Exit Gate (Session Closure)
```
Person detected → Match against registered people
↓
IF MATCH + ACTIVE SESSION:
  ✅ Calculate duration
  ✅ Calculate avg/max velocity
  ✅ Update database
  ✅ Close session
  ✅ Person marked "EXITED"
```

---

## 📊 MATCHING ALGORITHM

### Feature Weights:
- **OSNet**: 50% (learned body embeddings - most important!)
- **Clothing**: 20% (upper + lower clothing colors)
- **Hair**: 15% (dominant hair color)
- **Skin**: 15% (skin tone from body regions)

### Similarity Calculation:
```
Total Score = OSNet×0.50 + Hair×0.15 + Skin×0.15 + Clothing×0.20
```

### Threshold:
- **Match threshold**: 0.75 (strict - prevents false positives)
- **Below threshold**: Marked as UNAUTHORIZED

---

## 🐛 DEBUG MODE

Press **D** to enable debug output in console:

```
🔍 Room Match: P001 (0.933)
   OSNet: 0.936 × 0.50 = 0.468
   Hair:  1.000 × 0.15 = 0.150
   Skin:  0.990 × 0.15 = 0.149
   Cloth: 0.833 × 0.20 = 0.167
```

This shows you:
- Which person was matched
- Overall similarity score
- Individual feature contributions
- How each feature is weighted

**Use debug mode to:**
- Understand why matches succeed/fail
- Tune weights if needed
- Identify which features are most discriminative

---

## 📈 STATISTICS (Press S)

Example output:
```
==================================================================
  SYSTEM STATISTICS
==================================================================
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
  P001: 45.3s inside
  P004: 12.8s inside
==================================================================
```

---

## 💾 DATA STORAGE

### Database: `data/yolo26_complete_system.db`
Tables:
- **people** - Person profiles with entry/exit times, durations, velocities
- **trajectory_data** - (x, y, timestamp, velocity) for each detection
- **alerts** - Security alerts with timestamps

### Alerts Log: `data/yolo26_system_alerts.log`
All security events:
- Unauthorized entries
- Running detected (velocity > 2.0 m/s)
- System events

---

## 🔧 CALIBRATION

### Adjust Pixels Per Meter (Room Camera):
Edit line 78 in `yolo26_complete_system.py`:
```python
self.pixels_per_meter = 100.0  # Adjust this!
```

**How to calibrate:**
1. Measure a known distance in your room (e.g., 1 meter)
2. Run the system and note pixel distance in trajectory
3. Calculate: `pixels_per_meter = pixel_distance / meter_distance`

### Adjust Matching Threshold:
Edit line 126 in `yolo26_complete_system.py`:
```python
self.similarity_threshold = 0.75  # Lower = more lenient, Higher = stricter
```

**Guidelines:**
- **0.65-0.70**: More lenient (fewer false negatives, more false positives)
- **0.75**: Balanced (default)
- **0.80-0.85**: Stricter (fewer false positives, more false negatives)

### Adjust Feature Weights:
Edit lines 118-121:
```python
self.osnet_weight = 0.50      # Learned embeddings
self.hair_weight = 0.15       # Hair color
self.skin_weight = 0.15       # Skin tone
self.clothing_weight = 0.20   # Clothing colors
```

---

## 🚨 TROUBLESHOOTING

### "No cameras found!"
- Check camera connections
- Try different USB ports
- Run: `ls /dev/video*` (Linux) or check System Preferences (Mac)

### "Registration failed: OSNet extraction failed"
- OSNet model is downloading (wait ~1 minute first time)
- Or torchreid not installed: `pip install torchreid`

### Person not being matched in room
1. Press **D** to enable debug mode
2. Check similarity scores in console
3. If all scores < 0.75, person is genuinely different
4. If scores ~0.70-0.74, lower threshold slightly

### Too many false positives (wrong person matched)
1. Press **D** to enable debug mode
2. Check which feature is causing confusion
3. Increase threshold (e.g., 0.80)
4. Or adjust feature weights

### Velocity seems wrong
1. Calibrate `pixels_per_meter` for your camera height/distance
2. Walk a known distance and compare
3. Adjust the calibration value

### System is slow
- Lower camera resolution (edit line 161-162)
- Process every Nth frame (add frame skipping)
- Use smaller OSNet model: `osnet_x0_5` instead of `osnet_x1_0`

---

## 🎓 ADVANCED USAGE

### Multi-Person Testing
1. Register person A at entry
2. Have person B appear in room (should be RED - unauthorized)
3. Register person B at entry
4. Now both should be GREEN in room!

### Velocity Testing
1. Register at entry
2. Walk slowly in room → GREEN velocity text
3. Walk fast → ORANGE velocity text
4. Run → RED velocity text + "RUNNING!" alert

### Session Duration Testing
1. Register at entry (note time)
2. Walk around room (velocity tracked)
3. Exit at exit gate
4. Check console for duration + avg/max velocity

### Unauthorized Entry Test
1. Register person A at entry
2. Have person A exit at exit gate (session closed)
3. Have person A reappear in room → RED (no active session!)
4. Person A must re-enter through entry gate

---

## 📝 EXAMPLE SESSION

```
🚀 Starting system...

⏳ Auto-registering P001 at entry...
✅ Registered P001 at entry gate

🔍 Room Match: P001 (0.933)
   OSNet: 0.936 × 0.50 = 0.468
   Hair:  1.000 × 0.15 = 0.150
   Skin:  0.990 × 0.15 = 0.149
   Cloth: 0.833 × 0.20 = 0.167

[Person walking in room - velocity tracked]

✅ P001 exited
   Duration: 45.3s
   Avg velocity: 0.85 m/s
   Max velocity: 1.42 m/s
```

---

## 🎯 SYSTEM REQUIREMENTS

### Hardware:
- **CPU**: Any modern processor (Apple Silicon optimized!)
- **RAM**: 4GB minimum, 8GB recommended
- **Cameras**: 3× USB webcams or built-in + external
- **Storage**: 500MB for models + database

### Software:
- **Python**: 3.8 or higher
- **OS**: macOS, Linux, or Windows
- **GPU**: Optional (MPS for Mac, CUDA for NVIDIA)

### Dependencies (auto-installed):
- ultralytics >= 8.3.0
- opencv-python >= 4.8.0
- torch >= 2.0.0
- torchvision >= 0.15.0
- torchreid (for OSNet)
- numpy, pillow, pyyaml

---

## 🏆 SUCCESS CHECKLIST

- [ ] Run `./RUN_ULTIMATE_SYSTEM.sh` successfully
- [ ] All 3 camera windows open
- [ ] Person auto-registered at entry (GREEN box)
- [ ] Person tracked in room with velocity (GREEN box + m/s)
- [ ] Trajectory line visible in room
- [ ] Person matched at exit with duration printed
- [ ] Debug mode shows similarity scores
- [ ] Statistics display correctly
- [ ] Database file created in `data/` folder

---

## 💡 TIPS FOR BEST RESULTS

1. **Good Lighting**: Crucial for feature extraction
2. **Stable Position**: Mount cameras, don't hand-hold
3. **Clear View**: Minimize occlusions and background clutter
4. **Consistent Clothing**: Feature extraction works best when clothes don't change
5. **Face Entry/Exit**: Stand close to entry/exit cameras for face visibility
6. **Calibrate Velocity**: Measure actual distances for accurate m/s readings
7. **Test with 2+ People**: Best way to see re-identification in action!

---

## 🎉 YOU'RE READY!

Run this command and watch the magic happen:

```bash
./RUN_ULTIMATE_SYSTEM.sh
```

The system will:
1. ✅ Check all dependencies
2. ✅ Download models if needed
3. ✅ Detect cameras
4. ✅ Launch three-camera interface
5. ✅ Start tracking immediately!

---

## 📞 QUICK REFERENCE

| What You Want | How To Do It |
|---------------|--------------|
| Start system | `./RUN_ULTIMATE_SYSTEM.sh` |
| Register person | Stand at entry (auto) or press E |
| See tracking | Move to room camera |
| Check velocity | Look at text below bounding box |
| Exit session | Stand at exit camera |
| See scores | Press D (debug mode) |
| See stats | Press S |
| Restart | Press C |
| Quit | Press Q |

---

## 🚀 ENJOY YOUR COMPLETE SECURITY SYSTEM!

You now have a production-ready security system with:
- ✅ Entry gate auto-registration
- ✅ Multi-modal re-identification
- ✅ Real-time velocity tracking
- ✅ Unauthorized entry detection
- ✅ Complete session management
- ✅ Database persistence
- ✅ Alert logging

**BROTHER, IT'S WORKING! NOW GO TEST EVERYTHING! 🎉**

---

*Built with YOLO26-pose, OSNet, and lots of ❤️*