# Camera Setup Guide for Three-Camera System
## Complete Phase 2 Implementation

This guide will help you set up and troubleshoot three cameras (Entry, Exit, Room) for the security monitoring system.

---

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Camera Configuration Options](#camera-configuration-options)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Troubleshooting](#troubleshooting)
5. [Testing the System](#testing-the-system)
6. [Camera Index Assignment](#camera-index-assignment)

---

## System Requirements

### Hardware
- **MacBook** with built-in webcam (1 camera)
- **2 smartphones** with Iriun Webcam app installed (2 cameras)
- **Total: 3 cameras**

### Software
- **macOS** (your current system)
- **Python 3.8+** with virtual environment
- **Iriun Webcam** app (on phones and Mac)
- **OpenCV** (already installed in your venv)

### Network
- All devices on the **same Wi-Fi network** (for wireless Iriun)
- OR USB connection (more stable, recommended)

---

## Camera Configuration Options

### Option 1: USB Connection (RECOMMENDED)
**Most stable and reliable**

1. Connect both phones via USB to your MacBook
2. Enable USB debugging/tethering on phones
3. Open Iriun app on both phones
4. Open Iriun on Mac - it should detect both phones

**Advantages:**
- More stable connection
- Better frame rates
- No network issues
- Lower latency

**Disadvantages:**
- Need USB cables
- Phones must stay connected

### Option 2: Wi-Fi Connection
**More flexible positioning**

1. Connect all devices to same Wi-Fi network
2. Open Iriun app on both phones
3. Open Iriun on Mac
4. Phones will appear as network cameras

**Advantages:**
- Wireless - more flexibility
- Can position cameras anywhere

**Disadvantages:**
- Less stable
- Network-dependent
- Lower frame rates possible

---

## Step-by-Step Setup

### Step 1: Install Iriun on Phones
1. Download **Iriun Webcam** from:
   - iOS: App Store
   - Android: Play Store
2. Install on **both** phones
3. Open the app on each phone

### Step 2: Install Iriun on Mac
1. Download from: https://iriun.com
2. Install and open the application
3. Keep it running in the background

### Step 3: Connect Cameras

#### USB Method (Recommended):
```bash
# For iPhone:
1. Connect via Lightning cable
2. Trust the computer if prompted
3. Open Iriun app on iPhone
4. You should see "Connected" status

# For Android:
1. Connect via USB cable
2. Enable USB Debugging in Developer Options
3. Enable USB Tethering
4. Open Iriun app
5. You should see "Connected" status
```

#### Wi-Fi Method:
```bash
1. Ensure Mac and phones on same network
2. Open Iriun on Mac (keeps running)
3. Open Iriun on first phone - wait for "Connected"
4. Open Iriun on second phone - wait for "Connected"
5. Both should appear in Iriun Mac app
```

### Step 4: Verify Camera Detection

Run the detection script:
```bash
cd "Security Entry & Exit Management System"
source venv/bin/activate
python scripts/detect_cameras.py
```

Expected output:
```
✅ Camera 0 FOUND:
   - Resolution: 1920x1080
   - FPS: 30.0
   - Backend: AVFoundation

✅ Camera 1 FOUND:
   - Resolution: 1920x1080
   - FPS: 15.0
   - Backend: AVFoundation

✅ Camera 2 FOUND:
   - Resolution: 1920x1080
   - FPS: 15.0
   - Backend: AVFoundation

Total cameras found: 3
```

### Step 5: Test Camera Preview

Preview all cameras:
```bash
python scripts/detect_cameras.py
# When prompted, type 'y' to preview
```

You should see three windows showing:
- Camera 0: Usually MacBook webcam
- Camera 1: First phone camera
- Camera 2: Second phone camera

**Label each camera:**
- Press `0` to label Camera 0
- Press `1` to label Camera 1
- Press `2` to label Camera 2
- Press `q` to quit

---

## Troubleshooting

### Problem 1: Only 2 Cameras Detected

**Symptoms:**
```
✅ Camera 0 FOUND
✅ Camera 1 FOUND
Total cameras found: 2
```

**Solutions:**

#### Solution A: Check Iriun Connection
```bash
# 1. Close Iriun completely on Mac
killall Iriun  # If needed

# 2. Close Iriun apps on both phones

# 3. Restart Iriun on Mac first

# 4. Open Iriun on first phone, wait 5 seconds

# 5. Open Iriun on second phone

# 6. Check Iriun Mac app - both phones should show "Connected"

# 7. Run detection again
python scripts/detect_cameras.py
```

#### Solution B: USB Connection Issues
```bash
# For iPhone:
1. Unplug and replug cable
2. Select "Trust This Computer" again
3. Close and reopen Iriun app on phone

# For Android:
1. Settings → Developer Options → Enable USB Debugging
2. Settings → Network → USB Tethering (ON)
3. Unplug and replug cable
4. Select "Allow USB debugging"
5. Close and reopen Iriun app
```

#### Solution C: Reset Camera Indices
```bash
# Sometimes macOS caches camera devices
# Restart your Mac to reset camera indices
sudo reboot
```

### Problem 2: Camera Opens But Shows Black Screen

**Cause:** Another app is using the camera

**Solutions:**
```bash
# 1. Close all apps that might use camera:
- Zoom
- Skype
- FaceTime
- Photo Booth
- Any browser tabs with camera access

# 2. Check what's using the camera:
lsof | grep -i camera

# 3. Kill processes if needed:
killall "VDCAssistant"  # Camera daemon
```

### Problem 3: "Failed to open camera" Error

**Solutions:**

#### Check Camera Permissions:
```bash
System Preferences → Security & Privacy → Camera
# Ensure Terminal/Python has camera access
```

#### Verify Camera Availability:
```bash
# Try opening with system_profiler
system_profiler SPCameraDataType
```

#### Reinstall Iriun:
```bash
1. Uninstall Iriun from Mac
2. Uninstall from both phones
3. Restart Mac
4. Reinstall everything
5. Try again
```

### Problem 4: Low Frame Rate / Laggy Video

**Solutions:**

1. **Use USB instead of Wi-Fi**
   - Much more stable
   - Better frame rates

2. **Reduce Resolution:**
   ```python
   # Edit demo_three_cameras.py
   # Change display size:
   display_width = 480   # Instead of 640
   display_height = 360  # Instead of 480
   ```

3. **Close Other Apps:**
   - Free up CPU and memory
   - Close browser tabs
   - Close unnecessary applications

4. **Check Network (if using Wi-Fi):**
   ```bash
   # Test network speed
   ping 192.168.1.1  # Your router IP
   # Should have <10ms latency
   ```

### Problem 5: Cameras Swap Indices

**Symptom:** Camera 0 becomes Camera 1, etc.

**Solution:** 
This is normal when connecting/disconnecting. The system auto-detects and adapts.

**To fix assignment:**
```bash
# Run the detection script with preview
python scripts/detect_cameras.py

# Press 0, 1, 2 to label cameras as:
# - ENTRY
# - EXIT  
# - ROOM

# Note the indices, then run demo with correct mapping
```

---

## Testing the System

### Quick Test: Simple Camera Preview
```bash
python scripts/test_cameras_simple.py
```

### Full Test: Three-Camera Demo
```bash
python demo_three_cameras.py
```

**Expected behavior:**
- Three windows open (Entry, Exit, Room)
- All show live video feed
- Stats panels display at top
- No error messages in terminal

### Controls:
- **Press 'e'**: Register person at Entry camera
- **Press 'x'**: Test detection at Exit camera  
- **Press 'q'**: Quit and save session data

---

## Camera Index Assignment

### Default Configuration:
```
Camera 0 → MacBook webcam → ENTRY camera
Camera 1 → Phone 1 (Iriun) → EXIT camera
Camera 2 → Phone 2 (Iriun) → ROOM camera
```

### Custom Configuration:
Edit `demo_three_cameras.py`:
```python
# Around line 714, in main():
entry_idx = 0  # Change to your entry camera index
exit_idx = 1   # Change to your exit camera index
room_idx = 2   # Change to your room camera index
```

### Verify Your Configuration:
```bash
# 1. Run detection script
python scripts/detect_cameras.py

# 2. Preview and label cameras
# Press 'y' when prompted

# 3. Note which camera is which:
#    - Camera showing entry area → Note the index
#    - Camera showing exit area → Note the index
#    - Camera showing room → Note the index

# 4. Update demo_three_cameras.py with correct indices
```

---

## Common Scenarios

### Scenario 1: Using 2 Cameras Only
If you only have 2 cameras available:
```bash
python demo_entry_room.py
# Uses Entry + Room (no Exit camera)
```

### Scenario 2: Using MacBook + 1 Phone
```bash
# System will auto-detect and use 2-camera mode
python demo_three_cameras.py
# Entry and Exit will use same camera
```

### Scenario 3: All 3 Cameras Working
```bash
# Full system functionality
python demo_three_cameras.py
# All three windows operational
```

---

## Performance Tips

### Optimize for Speed:
1. **USB connection** (not Wi-Fi)
2. **Close unnecessary apps**
3. **Lower display resolution** (640x480 instead of 1920x1080)
4. **Reduce trajectory history** (25 points instead of 50)

### Optimize for Accuracy:
1. **Good lighting** in all camera views
2. **Stable camera mounting**
3. **Calibrate pixels_per_meter** in config
4. **Adjust similarity_threshold** (0.60-0.70 range)

---

## Next Steps

### After Setup:
1. ✅ Verify all 3 cameras detected
2. ✅ Run demo_three_cameras.py
3. ✅ Test person registration (press 'e')
4. ✅ Test unauthorized detection
5. ✅ Verify trajectory tracking
6. ✅ Check alerts in terminal
7. ✅ Export session data (press 'q')

### Phase 3 Features (Coming Next):
- Kalman filter trajectory smoothing
- Velocity-based threat detection
- Mass gathering alerts
- Improved re-identification
- Multi-person tracking

---

## Quick Reference Commands

```bash
# Activate environment
cd "Security Entry & Exit Management System"
source venv/bin/activate

# Detect cameras
python scripts/detect_cameras.py

# Simple camera test
python scripts/test_cameras_simple.py

# Run 3-camera system
python demo_three_cameras.py

# Run 2-camera system  
python demo_entry_room.py

# View database
sqlite3 data/three_camera_demo.db

# View alerts
cat data/three_camera_alerts.log
```

---

## Support

If you encounter issues not covered here:

1. **Check Python environment:**
   ```bash
   which python
   pip list | grep opencv
   ```

2. **Check OpenCV installation:**
   ```bash
   python -c "import cv2; print(cv2.__version__)"
   ```

3. **Check camera permissions:**
   ```bash
   System Preferences → Security & Privacy → Camera
   ```

4. **Restart everything:**
   ```bash
   # Close all apps
   # Restart Mac
   # Reconnect cameras
   # Try again
   ```

---

## Summary Checklist

- [ ] Iriun installed on both phones
- [ ] Iriun installed on Mac  
- [ ] Both phones connected (USB or Wi-Fi)
- [ ] Iriun Mac app shows both phones "Connected"
- [ ] Camera detection script finds 3 cameras
- [ ] Camera preview shows all 3 feeds
- [ ] demo_three_cameras.py runs without errors
- [ ] Can register person at entry (press 'e')
- [ ] Person detected in room camera
- [ ] Unauthorized person shows red bounding box
- [ ] Session data exports on quit (press 'q')

**If all checkboxes complete → Phase 2 is COMPLETE! 🎉**

---

*Last Updated: Phase 2 Implementation*
*System: Three-Camera Entry/Exit/Room Monitoring*