# Camera Detection Colors Guide

## 🎨 What Do All These Colors Mean?

### Entry Camera (Camera 0)
**Purpose:** Auto-register people entering the facility

| Color | Shape | Meaning |
|-------|-------|---------|
| **🟢 GREEN** | Rectangle (face) | Face detected - ready to register |
| **🔵 BLUE** | Rectangle (body) | Body detected |
| **🟣 PURPLE** | Filled box with text | Registration notification |

**What to do:**
- Position your face in view
- Press **'e'** to register
- You'll see: "🤖 AUTO-REGISTERED: P001"

---

### Room Camera (Camera 2)
**Purpose:** Track authorized people and detect unauthorized entries

| Color | Shape | Meaning |
|-------|-------|---------|
| **🟢 GREEN** | Thick rectangle | **AUTHORIZED** - Person is registered |
| **🔴 RED** | Thick rectangle | **UNAUTHORIZED** - Person not registered! |
| **🟣 PURPLE** | Trail line | Movement trajectory |
| **🟡 YELLOW** | Thin rectangle | Face detection |
| **🔵 BLUE** | Thin rectangle | Body detection |

**Labels on boxes:**
- `P001 (0.72)` = Person ID + match confidence
- `Mode: both` = Using face + body for matching
- `Mode: face_only` = Only face visible
- `Mode: body_only` = Only body visible (face not clear)

---

### Exit Camera (Camera 1)
**Purpose:** Detect when registered people leave

| Color | Shape | Meaning |
|-------|-------|---------|
| **🟡 YELLOW** | Thin rectangle | Face detected (scanning for match) |
| **🔵 BLUE** | Thin rectangle | Body detected (scanning for match) |
| **🟢 GREEN** | Thick rectangle | **MATCHED EXIT** - Registered person leaving |

**Labels on boxes:**
- `Face: 0.89` = Face detection confidence
- `Body: 0.82` = Body detection confidence
- `P001 EXITING` = Identified person exiting

**Color Legend (shown on screen):**
```
EXIT DETECTION:
Yellow=Face | Blue=Body | GREEN=MATCHED EXIT
```

---

## 🎬 Complete Workflow Example

### Step 1: Entry
```
ENTRY CAMERA:
┌─────────────────────────┐
│ 🟢 GREEN box (face)     │ ← Face detected
│ 🔵 BLUE box (body)      │ ← Body detected
│                         │
│ Press 'e' to register   │
│                         │
│ 🟣 "P001 REGISTERED"    │ ← Confirmation
└─────────────────────────┘
```

### Step 2: Inside Room
```
ROOM CAMERA:
┌─────────────────────────┐
│ 🟢 GREEN thick box      │ ← AUTHORIZED
│    P001 (0.72)          │ ← Person ID + confidence
│    Mode: both           │ ← Detection mode
│                         │
│ 🟣🟣🟣 Purple trail     │ ← Movement history
└─────────────────────────┘
```

**Console output:**
```
[INFO] ROOM MATCH: P001 | Similarity: 0.68 | Mode: both
  Face: 0.72 | Body: 0.65 | Combined: 0.68
```

### Step 3: Exit
```
EXIT CAMERA (before match):
┌─────────────────────────┐
│ 🟡 Yellow box (face)    │ ← Scanning...
│    Face: 0.85           │
│ 🔵 Blue box (body)      │ ← Scanning...
│    Body: 0.78           │
└─────────────────────────┘
```

```
EXIT CAMERA (after match):
┌─────────────────────────┐
│ 🟢 GREEN thick box      │ ← MATCH FOUND!
│    P001 EXITING         │ ← Identified
└─────────────────────────┘
```

**Console output:**
```
👋 EXIT DETECTED: P001 | Similarity: 0.606
```

---

## 🚨 Unauthorized Person Detection

### What You'll See in Room Camera:

```
ROOM CAMERA:
┌─────────────────────────┐
│ 🔴 RED thick box        │ ← ALERT!
│    UNAUTHORIZED         │ ← Not registered
│    (0.15)               │ ← Low match score
└─────────────────────────┘
```

**Console output:**
```
⚠️  [21:45:32] | [WARNING] | [UNAUTHORIZED_ENTRY] | 
Person: UNKNOWN | Camera: room | UNAUTHORIZED person detected
```

**What happens:**
- Red box around detected person
- Alert logged to database
- Notification appears on screen
- `unauthorized_detections` counter increases

---

## 🎮 Quick Reference Card

### Colors at a Glance

| Camera | Green | Red | Yellow | Blue | Purple |
|--------|-------|-----|--------|------|--------|
| **Entry** | Face ready | - | - | Body | Notification |
| **Room** | Authorized | Unauthorized | Face scan | Body scan | Trajectory |
| **Exit** | Matched exit | - | Face scan | Body scan | - |

### Box Thickness

| Thickness | Meaning |
|-----------|---------|
| **Thin (2px)** | Detection only (scanning) |
| **Thick (3px)** | Matched/Identified person |

### Label Format

```
P001 (0.72)
└─┬─┘ └──┬──┘
  │      └─ Match confidence (0-1)
  └──────── Person ID
```

---

## 💡 Troubleshooting Colors

### "I don't see ANY colors in Exit camera"

**Problem:** Exit camera showing blank/no detections

**Fix:** Now fixed in latest version!
- Exit camera now shows:
  - 🟡 Yellow boxes for ALL faces
  - 🔵 Blue boxes for ALL bodies
  - 🟢 Green when match found

**Test:** Wave your hand in front of exit camera - you should see blue body box

---

### "Room camera shows RED but I'm registered"

**Problem:** Match confidence too low

**Possible causes:**
1. Lighting changed between entry and room camera
2. Different camera angle/resolution
3. Face partially occluded
4. Person too far from camera

**Fix:**
- Ensure good lighting in all cameras
- Lower match threshold in code (default: 0.45)
- Move closer to camera
- Look directly at camera

---

### "Green boxes everywhere but nothing happens"

**Problem:** Detections working but no registration

**Remember:**
- Press **'e'** key to register at entry camera
- Registration only works at ENTRY camera
- Room camera only matches, doesn't register

---

## 📊 Stats Panel Colors

Top of each window shows stats panel:

```
┌────────────────────────────────────┐
│ ENTRY CAMERA - YOLO                │ ← Camera name
│ Registered: 1 | Inside: 0          │ ← Counts
│ FPS: 3.2                            │ ← Performance
└────────────────────────────────────┘
```

**Colors:**
- Panel background: Dark gray (40, 40, 40)
- Text: Green (0, 255, 0)
- FPS: Cyan (0, 255, 255)

---

## 🎯 Performance Indicators

### FPS (Frames Per Second)

| FPS Range | Performance | What to do |
|-----------|-------------|------------|
| **25-30+** | ✅ Excellent | No action needed |
| **15-25** | 🟡 Good | Consider closing other apps |
| **10-15** | 🟠 Fair | Reduce camera resolution |
| **< 10** | 🔴 Poor | USB connection, reduce quality |

---

## 🔧 Customizing Colors

Want different colors? Edit `demo_yolo_cameras.py`:

```python
# Entry camera face detection
color = (0, 255, 0)  # GREEN (B, G, R)

# Room authorized person
color = (0, 255, 0)  # GREEN

# Room unauthorized person  
color = (0, 0, 255)  # RED

# Exit face detection
color = (0, 255, 255)  # YELLOW

# Exit body detection
color = (255, 150, 0)  # BLUE

# Exit matched person
color = (0, 255, 0)  # GREEN

# Trajectory trail
color = (255, 0, 255)  # PURPLE
```

**Note:** OpenCV uses BGR format (Blue, Green, Red), not RGB!

---

## 📸 Example Screenshots

### Normal Operation (All Cameras):
```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ ENTRY   │  │  ROOM   │  │  EXIT   │
│         │  │         │  │         │
│ 🟢 Face │  │ 🟢 P001 │  │ 🟡 Face │
│ 🔵 Body │  │ 🟣 Trail│  │ 🔵 Body │
└─────────┘  └─────────┘  └─────────┘
```

### Alert State (Unauthorized in Room):
```
┌─────────┐  ┌─────────────┐  ┌─────────┐
│ ENTRY   │  │    ROOM     │  │  EXIT   │
│         │  │             │  │         │
│ 🟢 Face │  │ 🔴 UNAUTHORIZED! │  │         │
│         │  │ ⚠️  ALERT   │  │         │
└─────────┘  └─────────────┘  └─────────┘
```

### Exit Detection:
```
┌─────────┐  ┌─────────┐  ┌──────────────┐
│ ENTRY   │  │  ROOM   │  │     EXIT     │
│         │  │         │  │              │
│         │  │ Empty   │  │ 🟢 P001 EXITING │
│         │  │         │  │ ✅ Match!    │
└─────────┘  └─────────┘  └──────────────┘
```

---

## ✅ Color System Summary

**Entry Camera:**
- Detect → Green/Blue boxes
- Register → Purple notification

**Room Camera:**  
- Match registered → Green (authorized)
- No match → Red (unauthorized)
- Track movement → Purple trail

**Exit Camera:**
- Detect → Yellow (face) + Blue (body)
- Match → Green (confirmed exit)

**Console:**
- Info → White text
- Success → Green ✅
- Warning → Orange ⚠️
- Error → Red ❌

---

*Last Updated: February 2024*  
*System Version: YOLO Multi-Modal v2.5*  
*Color Detection Status: ✅ All cameras working*