# Basic Face Detection Test

## What This Does

This is a **minimal, working face detection script** that:

✅ Uses your Mac's webcam  
✅ Detects faces and assigns a **persistent Unique ID** per person  
✅ Uses a **3-second grace period** so the same person isn't counted multiple times  
✅ Shows **total unique persons** when you press Ctrl+C or 'q'  

## Setup

### 1. Install Dependencies

You only need OpenCV (no TensorFlow, no YOLO):

```bash
pip install opencv-python numpy
```

### 2. Fix macOS Camera Permissions (If Needed)

If you get a black screen or "Cannot open webcam" error:

1. **Grant Camera Permission:**
   - Go to **System Settings → Privacy & Security → Camera**
   - Enable camera access for **Terminal** (or iTerm/VS Code)

2. **Restart Terminal:**
   - Close and reopen your terminal window

3. **If Still Not Working:**
   ```bash
   sudo killall VDCAssistant
   ```
   Then try again.

## How to Run

```bash
cd "Security Entry & Exit Management System"
python test_basic_face_detection.py
```

## Testing Instructions

### Test 1: Single Person
1. Show your face to the camera
2. You should see a **green box** with `ID: xxxxxxxx`
3. Move around, turn your head slightly
4. **The ID should stay the same** (not create new IDs)

### Test 2: Three Different People
1. Show **your face** → Note the ID (e.g., `ID: abc123de`)
2. Show **friend #1's face** → Note the new ID (e.g., `ID: def456gh`)
3. Show **friend #2's face** → Note the new ID (e.g., `ID: ghi789jk`)
4. **Expected result:** Total Unique: 3

### Test 3: Re-identification
1. Show your face → Note the ID
2. Step away from camera (wait 1-2 seconds, but less than 3 seconds)
3. Come back into view
4. **Expected result:** Same ID should reappear (not create a new one)

### Test 4: Grace Period Expiry
1. Show your face → Note the ID
2. Step away for **more than 3 seconds**
3. Come back into view
4. **Expected result:** A new ID will be created (this is expected behavior)

## Understanding the Output

### On Screen:
```
Active: 2 | Total Unique: 3
```
- **Active:** People currently visible in frame
- **Total Unique:** Total different people detected since start

### In Terminal:
```
Frame  120 | Active: 1 | Total Unique: 2
Frame  150 | Active: 2 | Total Unique: 3
```

### On Exit (Ctrl+C or 'q'):
```
============================================================
DETECTION SUMMARY
============================================================
Total Unique Persons Detected: 3

Unique IDs:
  1. abc123de
  2. def456gh
  3. ghi789jk
============================================================
```

## How It Works

1. **Face Detection:** Uses OpenCV Haar Cascade (fast, reliable for frontal faces)
2. **Feature Extraction:** Computes color histogram of face region (simple but effective)
3. **Re-identification:** Compares new faces to recently seen faces using histogram similarity
4. **Grace Period:** Remembers people for 3 seconds after they leave frame
5. **Persistent IDs:** Same person gets same ID as long as they reappear within grace period

## Tuning Parameters

If you get too many or too few unique IDs, edit `test_basic_face_detection.py`:

```python
# Line 147-148
self.tracker = SimpleFaceTracker(
    grace_period_seconds=3.0,      # Increase to 5.0 for longer memory
    similarity_threshold=0.65      # Increase to 0.75 for stricter matching
)
```

### Parameter Guide:
- **grace_period_seconds:**
  - `3.0` = Standard (person must reappear within 3 seconds)
  - `5.0` = Lenient (remembers person for 5 seconds)
  - `1.0` = Strict (short memory, creates new IDs faster)

- **similarity_threshold:**
  - `0.65` = Lenient matching (may merge different people)
  - `0.75` = Stricter matching (less likely to merge, but may create duplicates)
  - `0.85` = Very strict (will create many IDs)

## Troubleshooting

### Problem: "Cannot open webcam"
**Solution:** Fix camera permissions (see Setup #2 above)

### Problem: Too many unique IDs (should be 3 but getting 10+)
**Solutions:**
1. Increase `grace_period_seconds` to 5.0
2. Lower `similarity_threshold` to 0.60
3. Ensure good lighting (not too dark)
4. Face the camera directly (Haar Cascade works best for frontal faces)

### Problem: Different people getting same ID
**Solutions:**
1. Increase `similarity_threshold` to 0.75
2. Ensure faces are clearly visible (no hats, glasses, masks)
3. Keep faces in frame longer (let the system learn)

### Problem: Black window or no video
**Solutions:**
1. Check camera isn't in use by another app (Photo Booth, Zoom, etc.)
2. Try: `sudo killall VDCAssistant`
3. Unplug and replug external webcam (if using one)

## Exit the Program

Press **'q'** key OR **Ctrl+C** to exit and see the summary.

---

## Next Steps

Once this basic test works:
1. ✅ We can integrate this logic into your full pipeline
2. ✅ Replace histogram matching with ArcFace embeddings (more accurate)
3. ✅ Add database persistence (SQLite)
4. ✅ Add entry/exit tracking
5. ✅ Deploy to Raspberry Pi

But for now, **let's make sure this basic version works first!** 🎯