# GEMINI.md - System Audit & Feature Updates

## Status: UPDATED (2026-03-17)

### ✅ Bug Fixes
- **Person Counter Increment Bug**: Fixed the issue where "number of people inside" and "unauthorized" counts would increment every frame when a person was stationary.
    - **Room Camera**: Integrated ByteTrack ID-based tracking for unauthorized persons. The `unauthorized` statistic now only increments once per unique track.
    - **Entry Camera**: Added a pre-registration check that matches detections against active sessions. If a person is already inside, the system skips re-registration, even if they stay in the entry area for an extended period.
- **Improved Cooldown Logic**: Standardized cooldowns using `datetime` objects to prevent duplicate registrations within a 10-second window.

### 🚀 New Features
- **Weapon & Threat Detection**: Integrated a dedicated YOLOv26 threat detection model (`custom_models/yolov26n-threat_detection/weights/best.pt`) for the Room Camera.
    - **Real-time Detection**: Identifies guns, pistols, knives, and other weapons with high confidence (>0.45).
    - **Visual Alerts**: Draws red bounding boxes and a prominent "⚠️ WEAPON DETECTED ⚠️" banner on the monitoring display.
    - **System Alerts**: Automatically triggers `CRITICAL` severity alerts via the `AlertManager`, which are pushed to the Analytics Dashboard and logged.

### 🛠️ Technical Implementation
- **AlertManager**: Added `WEAPON_DETECTED` alert type and `alert_weapon()` helper method.
- **YOLO26CompleteSystem**: 
    - Parallelized threat detection alongside person tracking.
    - Optimized `Inside Now` display to use the actual `active_sessions` count for 100% accuracy.
    - Refactored `process_room_camera` and `process_entry_camera` for cleaner logic and better state management.

### 📊 Dashboard Integration
- The "Currently Inside" KPI now reflects real-time tracked sessions.
- Weapon alerts appear instantly in the live event feed with a high-priority visual indicator.
