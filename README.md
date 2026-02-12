# Intelligence-Led Entry & Exit Management System

**Project Group ID:** CSPIT/CSE/B1-C1  
**Student ID:** 23CS043 (Ananya Gupta), 23CS023 (Debdoot Manna)  
**Domain:** Computer Vision, AI, Security Systems

---

## 📖 Project Overview

An advanced security management system that tracks people through entry gates, monitors their behavior in real-time within a secured area, and logs their exit. The system uses computer vision and AI to detect threats, unauthorized entries, and crowd anomalies.

### Key Features:
- ✅ **Dual-camera entry/exit tracking** (currently operational)
- 🚧 **Room tracking with behavior analysis** (in development)
- 🚧 **Velocity-based threat detection** (planned)
- 🚧 **Mass gathering alerts** (planned)
- 🚧 **Unauthorized entry detection** (planned)

---

## 🎯 System Architecture

```
ENTRY CAMERA (Phone) → ROOM CAMERA (NEW) → EXIT CAMERA (Mac)
     ↓                      ↓                    ↓
  Temp UUID            Track & Analyze      Permanent UUID
```

### Current Implementation (Phase 0):
- **Entry Camera:** Detects faces, generates temporary UUID
- **Exit Camera:** Matches faces, generates permanent UUID, logs to database
- **Matching:** Simple histogram-based face matching with 3s grace period

### Target Implementation (Phase 1-7):
- **Entry Camera:** Same + body feature extraction
- **Room Camera:** Real-time tracking, velocity calculation, threat detection
- **Exit Camera:** Same + threat flag logging

---

## 🚀 Quick Start

### Prerequisites:
- macOS with built-in webcam
- Python 3.9+ with OpenCV
- Iriun app (to use phone as camera)

### Installation:

1. **Clone the repository**
```bash
cd "Security Entry & Exit Management System"
```

2. **Install dependencies**
```bash
bash install_dependencies.sh
```

3. **Run the current system (2 cameras)**
```bash
bash run_entry_exit.sh
```

---

## 📂 Project Structure

```
Security Entry & Exit Management System/
│
├── entry_exit_system.py          # Current 2-camera system (WORKING)
├── config.py                      # Configuration settings
├── requirements.txt               # Python dependencies
├── install_dependencies.sh        # Setup script
├── run_entry_exit.sh             # Runner script
│
├── IMPLEMENTATION_PLAN.md         # 📋 Detailed roadmap (READ THIS!)
├── ENTRY_EXIT_README.md          # Documentation for current system
├── ENTRY_EXIT_QUICKSTART.txt     # Quick start guide
├── CAMERA_SETUP.txt              # Camera setup instructions
│
├── docs/                         # Technical documentation
│   └── Intelligence-Led Entry & Exit Management System.md
│
├── models/                       # Model weights (e.g., yolov8n.pt)
└── venv/                         # Virtual environment
```

---

## 📋 Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 0** | Basic 2-camera entry/exit system | ✅ Complete |
| **Phase 1** | Database & alert system enhancement | ✅ Complete |
| **Phase 2** | Room camera with basic tracking | 🚧 Next |
| **Phase 3** | Trajectory & tail visualization | ⏳ Planned |
| **Phase 4** | Velocity & running detection | ⏳ Planned |
| **Phase 5** | Mass gathering detection | ⏳ Planned |
| **Phase 6** | Multi-camera unified dashboard | ⏳ Planned |
| **Phase 7** | Advanced features & optimization | ⏳ Planned |

---

## 📚 Documentation

- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Complete technical roadmap with all 7 phases
- **[PHASE1_COMPLETE.md](PHASE1_COMPLETE.md)** - Phase 1 completion summary & test results
- **[ENTRY_EXIT_README.md](ENTRY_EXIT_README.md)** - Current system documentation
- **[CAMERA_SETUP.txt](CAMERA_SETUP.txt)** - Camera setup instructions
- **[docs/](docs/)** - Technical papers and research

---

## 🛠️ Current System Usage

### Running the 2-Camera System:

```bash
python entry_exit_system.py
```

### Controls:
- Press **'q'** to quit
- Press **'r'** to reset statistics

### Expected Behavior:
1. Show your face to the **Phone camera (Entry)** → System assigns temporary UUID
2. Show your face to the **Mac camera (Exit)** → System recognizes you and logs exit
3. Statistics update in real-time on the status bar

---

## 🎥 Camera Setup

### Default Configuration:
- **Camera 0:** Mac built-in webcam (EXIT)
- **Camera 1:** Phone via Iriun (ENTRY)
- **Camera 2:** TBD - Second phone/USB webcam (ROOM) - coming in Phase 2

### To use phone as camera:
1. Install Iriun Webcam app on phone and Mac
2. Connect phone and Mac to same WiFi
3. Launch Iriun on both devices
4. Camera will appear as index 1

---

## 🔧 Configuration

Edit `config.py` or modify parameters in `entry_exit_system.py`:

```python
# Matching parameters
grace_period_seconds = 3.0        # Time before creating new ID
similarity_threshold = 0.65       # Face matching threshold

# Camera indices
ENTRY_CAMERA = 1                  # Phone camera
EXIT_CAMERA = 0                   # Mac webcam
```

---

## 🚨 Known Issues & Troubleshooting

### Camera not detected:
```bash
# The system auto-scans indices 0-4
# If phone camera not found, ensure Iriun is running on both devices
```

### Too many IDs for same person:
- Increase `grace_period_seconds` to 5.0
- Lower `similarity_threshold` to 0.60

### Different people get same ID:
- Increase `similarity_threshold` to 0.75
- Ensure good lighting and frontal faces

---

## 📈 Next Steps

### Phase 1: ✅ COMPLETED
- ✅ Enhanced database schema with trajectory tracking
- ✅ Alert system infrastructure with cooldown
- ✅ Person state management (WAITING/INSIDE/EXITED/UNAUTHORIZED)
- ✅ Configuration system with YAML
- ✅ Comprehensive test suite
- ✅ All tests passing

**See [PHASE1_COMPLETE.md](PHASE1_COMPLETE.md) for detailed results.**

### Phase 2: 🚧 NEXT
We will now implement:
1. 3rd camera integration (room monitoring)
2. Person detection using YOLOv8-nano
3. Re-identification logic (match room detections to entry UUIDs)
4. Unauthorized entry detection
5. Unified 3-camera display

**See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for Phase 2 details.**

---

## 🧪 Testing Phase 1

To verify Phase 1 implementation:
```bash
python tests/test_phase1.py
```

Expected: All tests pass with green checkmarks ✅

---

## 🤝 Contributing

This is an academic project for CSPIT/CSE. Internal development only.

---

## 📄 License

Academic Project - CSPIT/CSE/B1-C1

---

## 👥 Team

- **Ananya Gupta** (23CS043)
- **Debdoot Manna** (23CS023)

---

## 📞 Support

For issues or questions, refer to:
1. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Complete roadmap
2. [ENTRY_EXIT_README.md](ENTRY_EXIT_README.md) - System documentation
3. Project documentation in `docs/`

---

**Last Updated:** December 2024  
**Version:** 0.2 (Phase 1 Complete - Ready for Phase 2)