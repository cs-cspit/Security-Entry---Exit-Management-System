# 📁 Project Structure Overview

**Intelligence-Led Entry & Exit Management System**  
**Version:** 0.2 (Phase 1 Complete)  
**Last Updated:** December 2024

---

## 🗂️ Directory Structure

```
Security Entry & Exit Management System/
│
├── 📂 src/                          # Source code modules (Phase 1+)
│   ├── enhanced_database.py         # ✅ Core database with trajectory tracking
│   └── alert_manager.py             # ✅ Alert system with cooldown
│
├── 📂 configs/                      # Configuration files
│   └── system_config.yaml           # ✅ Complete system configuration
│
├── 📂 tests/                        # Test scripts
│   └── test_phase1.py              # ✅ Phase 1 component tests
│
├── 📂 data/                         # Runtime data (created at runtime)
│   ├── security_system.db          # SQLite database
│   ├── alerts.log                  # Alert log file
│   ├── system.log                  # System log file
│   ├── exports/                    # JSON/CSV exports
│   └── debug_frames/               # Debug frame captures
│
├── 📂 models/                       # AI model weights
│   └── yolov8n.pt                  # YOLOv8 nano model
│
├── 📂 scripts/                      # Utility scripts
│   └── (Phase 2+)                  # Calibration, export tools, etc.
│
├── 📂 docs/                         # Documentation & research
│   └── Intelligence-Led Entry & Exit Management System.md
│
├── 📂 venv/                         # Python virtual environment
│
├── 📂 .github/                      # GitHub configuration
│
├── 📄 entry_exit_system.py         # ✅ Current 2-camera system (Phase 0)
├── 📄 config.py                     # Legacy config (will be deprecated)
├── 📄 requirements.txt              # Python dependencies
├── 📄 install_dependencies.sh       # Setup script
├── 📄 run_entry_exit.sh            # Runner script
│
├── 📄 README.md                     # ✅ Main project README
├── 📄 IMPLEMENTATION_PLAN.md        # ✅ Complete 7-phase roadmap
├── 📄 PHASE1_COMPLETE.md            # ✅ Phase 1 completion summary
├── 📄 ENTRY_EXIT_README.md          # Phase 0 system docs
├── 📄 ENTRY_EXIT_QUICKSTART.txt     # Quick start guide
├── 📄 CAMERA_SETUP.txt              # Camera setup instructions
├── 📄 PROJECT_STRUCTURE.md          # This file
│
└── 📄 .gitignore                    # Git ignore rules
```

---

## 📦 Module Descriptions

### Core Modules (Phase 1)

#### `src/enhanced_database.py` (816 lines)
**Purpose:** Advanced database management with trajectory tracking and threat logging

**Key Features:**
- Person state management (WAITING/INSIDE/EXITED/UNAUTHORIZED)
- Entry/exit recording with duration calculation
- Trajectory tracking (stores x, y, timestamp, velocity per frame)
- Threat event logging (velocity, entropy, proximity)
- Alert integration
- SQLite persistence with JSON export
- Automatic data cleanup

**Key Classes:**
- `EnhancedDatabase` - Main database controller
- `PersonState` - Enum for person states
- `AlertLevel` - Enum for alert severity
- `AlertType` - Enum for alert types

**Public API:**
```python
db = EnhancedDatabase("data/security_system.db")
db.add_person(person_id, state, histogram, body_features)
db.record_entry(person_id)
db.add_trajectory_point(person_id, x, y, camera_source, velocity)
db.record_threat_event(person_id, event_type, threat_score, ...)
db.create_alert(alert_type, alert_level, message, ...)
db.get_stats()
db.export_to_json(filepath)
db.close()
```

---

#### `src/alert_manager.py` (560 lines)
**Purpose:** Centralized alert handling with cooldown and multi-channel output

**Key Features:**
- Multi-level alerts (INFO/WARNING/CRITICAL)
- Alert cooldown to prevent spam (5-second default)
- Console output with ANSI color coding
- File logging with timestamps
- Audio alerts for critical events (macOS)
- Callback system for custom handlers
- Alert history and statistics tracking
- Time-windowed summaries

**Key Classes:**
- `AlertManager` - Main alert controller
- `AlertLevel` - Severity enum
- `AlertType` - Type enum

**Public API:**
```python
manager = AlertManager(cooldown_seconds=5.0, console_output=True, ...)
manager.create_alert(alert_type, alert_level, message, person_id, ...)
manager.register_callback(callback_function)
manager.get_recent_alerts(limit=10, level=None, alert_type=None)
manager.get_stats()
manager.export_alerts(filepath)
```

**Convenience Functions:**
```python
create_running_alert(manager, person_id, velocity, camera_source)
create_unauthorized_alert(manager, person_id, camera_source)
create_mass_gathering_alert(manager, zone_id, person_count, camera_source)
create_high_threat_alert(manager, person_id, threat_score, camera_source)
```

---

### Configuration

#### `configs/system_config.yaml` (265 lines)
**Purpose:** Centralized configuration for all system parameters

**Sections:**
- **cameras:** Entry, exit, and room camera settings
- **tracking:** Grace period, similarity threshold, trajectory buffer
- **reid:** Re-identification method and weights
- **velocity:** Walking/running thresholds, calibration
- **density:** Grid size, zone capacity, crowd thresholds
- **threat:** Scoring weights and alert thresholds
- **alerts:** Types, levels, cooldown, output options
- **database:** Path, logging, retention policy
- **display:** Visual options, colors, trail rendering
- **performance:** Threading, GPU, frame skipping
- **models:** Detector settings (YOLO, Haar)
- **logging:** Levels, file rotation
- **export:** Format, paths, auto-export
- **debug:** Development options

**Usage (Phase 2+):**
```python
import yaml
with open('configs/system_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
```

---

### Current System (Phase 0)

#### `entry_exit_system.py`
**Purpose:** Working 2-camera entry/exit tracking system

**Features:**
- Entry camera (Phone via Iriun) - generates temporary UUID
- Exit camera (Mac webcam) - matches and generates permanent UUID
- Simple histogram-based face matching
- Grace period to reduce ID switching
- Real-time statistics display

**Status:** ✅ Working - Will be refactored in Phase 2

---

### Tests

#### `tests/test_phase1.py` (393 lines)
**Purpose:** Comprehensive test suite for Phase 1 components

**Test Coverage:**
1. Enhanced Database
   - Person management
   - Entry/exit recording
   - Trajectory tracking
   - Alert creation
   - Threat event logging
   - Statistics and summaries
   - Export to JSON

2. Alert Manager
   - Alert creation at all levels
   - Cooldown system
   - Console and file output
   - Statistics and queries
   - Alert filtering
   - Export functionality

3. Integration Tests
   - Database + Alert Manager workflow
   - End-to-end person tracking scenario
   - Running detection and alerting

**Running Tests:**
```bash
python tests/test_phase1.py
```

**Expected:** All tests pass with ✅ green checkmarks

---

## 📊 Database Schema

### SQLite Tables

**people**
- person_id (PK), temp_uuid, permanent_uuid
- state, entry_time, exit_time, duration_seconds
- avg_velocity, max_velocity, threat_score, alert_count
- created_at

**trajectory_data**
- id (PK), person_id (FK)
- camera_source, x, y, timestamp, velocity

**threat_events**
- id (PK), person_id (FK)
- event_type, threat_score
- velocity, trajectory_entropy, proximity_density
- timestamp, camera_source, metadata

**alerts**
- id (PK)
- alert_type, alert_level
- person_id, camera_source
- message, timestamp, acknowledged, metadata

**sessions**
- session_id (PK)
- start_time, end_time
- total_entries, total_exits, total_alerts
- config_snapshot

---

## 🔄 Phase Status

| Phase | Status | Files Created |
|-------|--------|---------------|
| **Phase 0** | ✅ Complete | `entry_exit_system.py` |
| **Phase 1** | ✅ Complete | `src/enhanced_database.py`<br>`src/alert_manager.py`<br>`configs/system_config.yaml`<br>`tests/test_phase1.py` |
| **Phase 2** | 🚧 Next | `src/room_tracker.py`<br>`src/person_matcher.py`<br>`src/camera_manager.py` |
| **Phase 3** | ⏳ Planned | `src/trajectory_tracker.py`<br>`src/kalman_smoother.py` |
| **Phase 4** | ⏳ Planned | `src/velocity_calculator.py`<br>`src/threat_scorer.py` |
| **Phase 5** | ⏳ Planned | `src/density_analyzer.py`<br>`src/crowd_behavior.py` |
| **Phase 6** | ⏳ Planned | `src/integrated_system.py`<br>`src/dashboard_ui.py` |
| **Phase 7** | ⏳ Planned | `src/advanced_reid.py`<br>`src/logger.py`<br>`src/optimize.py` |

---

## 📚 Documentation Files

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Main project overview and quickstart | ✅ Updated |
| `IMPLEMENTATION_PLAN.md` | Complete 7-phase roadmap (537 lines) | ✅ Complete |
| `PHASE1_COMPLETE.md` | Phase 1 summary and test results | ✅ Complete |
| `PROJECT_STRUCTURE.md` | This file - directory overview | ✅ Complete |
| `ENTRY_EXIT_README.md` | Phase 0 system documentation | ✅ Legacy |
| `ENTRY_EXIT_QUICKSTART.txt` | Quick start for current system | ✅ Legacy |
| `CAMERA_SETUP.txt` | Camera setup instructions | ✅ Valid |

---

## 🚀 Getting Started

### For Development:
1. Read `README.md` for project overview
2. Read `IMPLEMENTATION_PLAN.md` for complete roadmap
3. Review `PHASE1_COMPLETE.md` for current status
4. Run `python tests/test_phase1.py` to verify Phase 1
5. Check `configs/system_config.yaml` for all parameters

### For Testing Current System:
1. Read `ENTRY_EXIT_README.md`
2. Follow `CAMERA_SETUP.txt` for camera setup
3. Run `bash run_entry_exit.sh`

### For Phase 2 Development:
1. Review Phase 2 in `IMPLEMENTATION_PLAN.md`
2. Study `src/enhanced_database.py` API
3. Study `src/alert_manager.py` API
4. Begin implementing `src/room_tracker.py`

---

## 📦 Dependencies

**Current (Phase 0-1):**
- `opencv-python` - Computer vision
- `numpy` - Numerical operations
- `PyYAML` (Phase 2+) - Configuration loading

**Planned (Phase 2+):**
- `ultralytics` - YOLOv8 for person detection
- `norfair` - Multi-object tracking
- `filterpy` - Kalman filters for smoothing
- `DeepFace` or `insightface` (Phase 7) - Face embeddings
- `torchreid` (Phase 7) - Body re-identification

**Install:**
```bash
bash install_dependencies.sh
```

---

## 🔧 Configuration Management

### Current Approach (Phase 0):
- Hardcoded in `config.py` and `entry_exit_system.py`

### New Approach (Phase 1+):
- Centralized in `configs/system_config.yaml`
- Runtime loading with YAML parser
- Environment variable overrides
- Command-line argument overrides

### Configuration Hierarchy:
1. Default values in `system_config.yaml`
2. Environment variables (e.g., `ENTRY_CAMERA_INDEX`)
3. Command-line arguments (e.g., `--entry-camera 1`)

---

## 🧪 Testing Strategy

### Unit Tests:
- Each module has isolated tests
- Mock external dependencies
- Focus on core logic

### Integration Tests:
- Test module interactions
- Use real database (test instance)
- Verify end-to-end workflows

### System Tests (Phase 6+):
- Full 3-camera system
- Real camera feeds
- Performance benchmarking

---

## 📊 Code Statistics (Phase 1)

| Category | Files | Lines | Status |
|----------|-------|-------|--------|
| **Source Code** | 2 | 1,376 | ✅ |
| **Tests** | 1 | 393 | ✅ |
| **Configuration** | 1 | 265 | ✅ |
| **Documentation** | 4 | ~2,000 | ✅ |
| **Legacy System** | 1 | ~400 | ✅ |
| **Total** | 9 | ~4,434 | ✅ |

---

## 🎯 Next Milestone: Phase 2

**Goal:** Add 3rd camera for room monitoring with basic tracking

**Key Tasks:**
1. Create `src/room_tracker.py` - Room camera module
2. Integrate YOLOv8 for person detection
3. Implement re-identification matching
4. Detect unauthorized entries
5. Create unified 3-camera display

**Target Date:** TBD  
**Prerequisites:** ✅ Phase 1 Complete

---

## 📝 Notes

- All Phase 1 components are tested and working ✅
- Database schema supports full trajectory tracking ✅
- Alert system is production-ready ✅
- Configuration system is comprehensive ✅
- Ready to proceed with Phase 2 implementation ✅

---

**Maintained by:** Ananya Gupta (23CS043), Debdoot Manna (23CS023)  
**Last Updated:** December 2024  
**Version:** 0.2