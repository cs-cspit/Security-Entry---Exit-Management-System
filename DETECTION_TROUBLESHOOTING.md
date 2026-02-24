# 🔍 Detection Troubleshooting Guide

## Quick Status Check

When the system is running, you'll see clear console output for each camera:

### 📹 ENTRY Camera
```
⏳ Auto-registering P001 at entry...
✅ Registered P001 at entry gate
   👤 Hair: brown (conf: 0.85)
   🎨 Skin: 45.2% detected
   👕 Upper: ['blue', 'white']
   👖 Lower: ['black']
```

### 🔍 ROOM Camera
```
🔍 ROOM: Person detected at (320, 240), size: 150x350
   ✅ AUTHORIZED: P001 (score: 0.750)
   Session: ACTIVE ✓
```

### 🚪 EXIT Camera
```
🚪 EXIT: Person detected at (300, 220), size: 160x340
   ✅ VALID EXIT: P001 (score: 0.680)
```

---

## 🚨 Problem: "Room Camera Not Detecting"

### Symptom
- No console output like `🔍 ROOM: Person detected...`
- No bounding boxes in the Room Monitoring window
- Detections count stays at 0

### Possible Causes

#### 1. **Camera is blocked or not working**
   - Check if the room camera window shows live video
   - Make sure nothing is covering the camera lens
   - Try moving in front of the camera

#### 2. **YOLO confidence threshold too high**
   - Person is too far from camera
   - Poor lighting conditions
   - Solution: Check `yolo26_body_detector.py` confidence_threshold (default: 0.5)

#### 3. **Wrong camera index**
   - The system uses: Entry=0, Room=2, Exit=1
   - Your camera indices might be different
   - Solution: Press `S` to check which cameras are active
   - Edit `yolo26_complete_system.py` line ~1200 to change camera indices

---

## 🚨 Problem: "Room Shows UNAUTHORIZED (Red Box)"

### Symptom
```
🔍 ROOM: Person detected at (320, 240), size: 150x350
   ❌ UNAUTHORIZED (best score: 0.650 < threshold: 0.700)
   💡 Close to threshold! Press '-' to lower it
```

### This is a **MATCHING** problem, not a detection problem!

#### Why This Happens
1. **Cross-camera domain shift**: Room camera looks different from entry camera
   - Different lighting, angle, resolution
   - OSNet features don't match perfectly
   
2. **Threshold too strict**: 0.70 is intentionally strict to avoid false positives
   - Prevents random people from being marked as authorized
   - But might reject real people if cameras are very different

#### Solutions

**Option 1: Lower Room Threshold (Interactive)**
- Press `-` key repeatedly while system is running
- Watch console for: `🔧 ROOM Threshold DECREASED to 0.65`
- Keep lowering until your friend is recognized
- Typical working range: 0.60 - 0.75

**Option 2: Enable Debug Mode**
- Press `D` to see full feature breakdown
- Look for which feature is causing the mismatch:
  ```
  P001: 0.650 ❌ BELOW (gap: -0.050)
     OSNet: 0.650 × 0.50 = 0.325  ← Low! Cross-camera issue
     Hair:  0.900 × 0.15 = 0.135  ← Good match
     Skin:  0.850 × 0.15 = 0.128  ← Good match
     Cloth: 0.800 × 0.20 = 0.160  ← Good match
  ```
- If OSNet is low but everything else matches → lower threshold
- If clothing is causing issues → adjust feature weights in code

**Option 3: Adjust Feature Weights** (Code Edit)
Edit `yolo26_complete_system.py` around line 135:
```python
self.osnet_weight = 0.50     # Reduce if cross-camera issues
self.hair_weight = 0.15      # Increase if hair is distinctive
self.skin_weight = 0.15      # Increase if skin tone is distinctive
self.clothing_weight = 0.20  # Reduce if people wear similar clothes
```

---

## 🚨 Problem: "Exit Shows UNKNOWN (Red Box)"

### Symptom
```
🚪 EXIT: Person detected at (300, 220), size: 160x340
   ❌ UNKNOWN PERSON (best score: 0.580 < exit threshold: 0.60)
   💡 Close to threshold! Press '[' to lower exit threshold
```

### Exit Camera Uses More Lenient Threshold!
- **Room threshold**: 0.70 (strict)
- **Exit threshold**: 0.60 (lenient) ← Already more forgiving!
- Exit has separate threshold because it's close-up like entry

#### Solutions

**Option 1: Lower Exit Threshold**
- Press `[` key to lower exit threshold
- Watch for: `🔧 EXIT Threshold DECREASED to 0.55`
- Keep lowering until person is recognized

**Option 2: Look for Exit Override**
- System automatically tries exit threshold even if room threshold fails
- Look for: `🔓 EXIT OVERRIDE: Accepting P001`
- If you don't see this, score is below exit threshold too

**Option 3: Check Active Session**
```
⚠️ REGISTERED but NO ACTIVE SESSION: P001
```
- Person was registered but already exited
- Or their session expired
- Solution: Press `C` to clear all data and re-register

---

## 🔧 Interactive Controls

While system is running:

| Key | Action |
|-----|--------|
| `D` | Toggle debug mode (full feature breakdown) |
| `S` | Show statistics (how many inside, exited, etc.) |
| `-` | **Lower ROOM threshold** (more lenient matching) |
| `+` | Raise ROOM threshold (stricter matching) |
| `[` | **Lower EXIT threshold** (more lenient exit) |
| `]` | Raise EXIT threshold (stricter exit) |
| `C` | Clear all registrations (fresh start) |
| `Q` | Quit and save data |

---

## 📊 Understanding Scores

### Score Ranges
- **0.80 - 1.00**: Excellent match ✅ (same person, same camera)
- **0.70 - 0.79**: Good match ✅ (probably same person)
- **0.60 - 0.69**: Moderate match ⚠️ (cross-camera, needs tuning)
- **0.50 - 0.59**: Weak match ❌ (probably different person)
- **0.00 - 0.49**: No match ❌ (definitely different person)

### Cross-Camera Penalty
Expect scores to **drop by 0.05-0.15** when same person appears in different camera:
- Entry camera (Camera 0): Person registers at 1.00 (perfect)
- Room camera (Camera 2): Same person might score 0.68 (cross-camera drop)
- Exit camera (Camera 1): Same person might score 0.65 (different camera again)

This is **NORMAL** and why we have separate thresholds!

---

## 🎯 Recommended Settings

### Conservative (Fewer False Positives)
```python
room_threshold = 0.75      # Strict
exit_threshold = 0.65      # Moderate
confidence_gap = 0.15      # Require clear winner
```

### Balanced (Default)
```python
room_threshold = 0.70      # Good balance
exit_threshold = 0.60      # Lenient for exit
confidence_gap = 0.15      # Room
exit_confidence_gap = 0.10 # Exit - more lenient
```

### Lenient (Fewer False Negatives)
```python
room_threshold = 0.60      # Lenient
exit_threshold = 0.50      # Very lenient
confidence_gap = 0.10      # Accept closer matches
```

---

## 🐛 Still Not Working?

### Check This Debugging Checklist

1. **Is person actually registered?**
   - Look for: `✅ Registered P001 at entry gate`
   - Press `S` to see `Registered People: 1`

2. **Is camera showing video?**
   - Check if Room Monitoring window updates
   - Try waving your hand in front of camera

3. **Is person visible in frame?**
   - Person must be full-body visible
   - Not cut off at edges
   - Face-on or side view OK, back view harder

4. **Is detection count increasing?**
   - Bottom of window shows: `Detections: 3`
   - If 0, YOLO is not finding people → lighting/distance issue
   - If >0, YOLO works → it's a matching issue

5. **Enable debug mode and read console**
   - Press `D` for full details
   - Look at per-feature scores
   - Identify which feature is failing

6. **Check for error messages**
   - Red error text in console
   - `OSNet extraction failed`
   - `Feature extraction failed`

### Common Mistakes

❌ **Person enters, but walks around room BEFORE showing face to entry camera**
   - System never registered them!
   - Solution: Stand in front of entry camera first

❌ **Multiple people with very similar appearance**
   - System shows: `AMBIGUOUS! Best 0.720 vs 2nd 0.710 (gap: 0.010)`
   - Solution: Increase confidence_gap or have only one person at a time

❌ **Cameras swapped**
   - Entry camera sees room, room camera sees entry
   - Solution: Check camera indices in code line ~1200

---

## 💡 Pro Tips

1. **Calibrate once, use forever**: Find your ideal threshold and keep it
2. **One person at a time**: System works best with single person tracking
3. **Good lighting helps**: Well-lit room = better features = better matching
4. **Distinctive clothing helps**: Bright colors, patterns make matching easier
5. **Close-up is better**: Entry and exit work better than room (closer to camera)

---

## 📞 Getting Help

If still stuck, provide this info:

1. **Console output** for the detection (copy/paste)
2. **Screenshot** of the window showing red/green box
3. **What you tried** (which keys pressed, threshold values)
4. **Camera setup** (which camera is which, distances, lighting)

Example good bug report:
```
Room camera not recognizing registered person.

Console output:
🔍 ROOM: Person detected at (320, 240), size: 150x350
   ❌ UNAUTHORIZED (best score: 0.650 < threshold: 0.700)

What I tried:
- Pressed '-' three times, now at 0.65 threshold
- Still showing red box
- Debug mode shows OSNet: 0.600, Clothing: 0.800

Setup:
- Entry: Logitech C920 (good lighting)
- Room: Old Windows 7 webcam (dim lighting, 5 meters away)
- Exit: MacBook camera
```

This gives enough context to help diagnose the issue! 🎯