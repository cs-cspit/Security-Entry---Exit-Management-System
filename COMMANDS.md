# Command Reference 🎯

Quick reference for all commands in the Enhanced Re-ID System.

---

## 🚀 Running the System

### 1. Test Enhanced Re-ID (Start Here!)
```bash
cd "Security Entry & Exit Management System"
source venv/bin/activate
python3 emergency_debug_enhanced.py
```
**What it does:** Interactive testing with OSNet + Clothing + Skin tone  
**Keys:** `r` = register, `SPACE` = test match, `q` = quit

---

### 2. Compare Old vs New Systems
```bash
python3 compare_systems.py
```
**What it does:** Side-by-side comparison of histogram vs enhanced system

---

### 3. Test Old System (Baseline)
```bash
python3 emergency_debug_false_positives.py
```
**What it does:** Shows original histogram-based system and its limitations

---

### 4. Run Full Three-Camera Demo
```bash
python3 demo_yolo_cameras.py
```
**What it does:** Entry/Exit/Room camera monitoring (currently uses old system)

---

## 🔧 Setup & Installation

### Activate Virtual Environment
```bash
source venv/bin/activate
```

### Check System Readiness
```bash
python3 check_system_ready.py
```

### Install/Reinstall Enhanced Dependencies
```bash
./install_enhanced_reid.sh
```

### Install Single Package
```bash
pip install package_name
```

---

## 🧪 Diagnostic Commands

### Check Installed Packages
```bash
pip list
pip list | grep torch
pip list | grep opencv
```

### Check PyTorch/MPS Status
```bash
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'MPS: {torch.backends.mps.is_available()}')"
```

### Check torchreid/OSNet
```bash
python3 -c "import torchreid; print(f'torchreid: {torchreid.__version__}')"
```

### Test OSNet Model Loading
```bash
python3 -c "import torchreid; m = torchreid.models.build_model('osnet_x1_0', 1000, 'softmax', pretrained=True); print('OK')"
```

### Check Camera Access
```bash
python3 scripts/detect_cameras.py
```

### Test Specific Camera Index
```bash
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL'); cap.release()"
```

---

## 📦 Model Management

### Download OSNet Weights
```bash
python3 -c "import torchreid; torchreid.models.build_model('osnet_x1_0', 1000, 'softmax', pretrained=True)"
```

### Clear OSNet Cache
```bash
rm -rf ~/.cache/torch/checkpoints/osnet_*
```

### Check Model Files
```bash
ls -lh ~/.cache/torch/checkpoints/
ls -lh yolo*.pt
```

### Download YOLO Models
```bash
python3 download_yolo_face.py
```

---

## 🗄️ Database & Logs

### View SQLite Database
```bash
sqlite3 data/yolo_camera_demo.db
# Inside sqlite3:
.tables
SELECT * FROM entries;
SELECT * FROM exits;
.exit
```

### View Alert Logs
```bash
cat data/yolo_camera_alerts.log
tail -f data/yolo_camera_alerts.log  # Follow live
```

### View Session JSON
```bash
cat data/yolo_session_*.json | jq .  # If jq installed
cat data/yolo_session_*.json          # Otherwise
```

### Clean Up Old Data
```bash
rm data/yolo_session_*.json
rm data/yolo_camera_alerts.log
```

---

## 🔍 System Information

### Python Version
```bash
python3 --version
```

### System Info
```bash
uname -a
sw_vers  # macOS version
```

### Disk Space
```bash
df -h .
```

### Memory Usage
```bash
top -l 1 | grep PhysMem
```

### Process Monitoring
```bash
ps aux | grep python
```

---

## 🛠️ Troubleshooting

### Fix Camera Permissions (macOS)
```bash
# No command - go to:
# System Preferences → Privacy & Security → Camera → Enable Terminal/VSCode
```

### Kill Stuck Python Process
```bash
ps aux | grep python
kill -9 <PID>
```

### Reset Camera System (macOS)
```bash
sudo killall VDCAssistant
sudo killall AppleCameraAssistant
```

### Reinstall Specific Package
```bash
pip uninstall package_name
pip install package_name
```

### Rebuild Virtual Environment
```bash
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📊 Performance Testing

### Measure Inference Speed
```bash
python3 -c "
import time
import torch
import torchreid
import numpy as np

model = torchreid.models.build_model('osnet_x1_0', 1000, 'softmax', pretrained=True)
model.eval()
device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
model = model.to(device)

img = torch.randn(1, 3, 256, 128).to(device)

# Warmup
for _ in range(10):
    with torch.no_grad():
        _ = model(img)

# Benchmark
times = []
for _ in range(100):
    start = time.time()
    with torch.no_grad():
        _ = model(img)
    times.append(time.time() - start)

print(f'Average: {np.mean(times)*1000:.2f}ms')
print(f'Min: {np.min(times)*1000:.2f}ms')
print(f'Max: {np.max(times)*1000:.2f}ms')
"
```

### Monitor GPU/MPS Usage
```bash
# macOS - Activity Monitor
open -a "Activity Monitor"
# Or command line:
powermetrics --samplers gpu_power -i 1000 -n 10
```

---

## 🎨 Configuration

### Edit Feature Weights
```bash
# Open in your editor:
open src/enhanced_reid.py
# Or:
nano src/enhanced_reid.py
vim src/enhanced_reid.py
```

### Edit Detection Thresholds
```bash
# Face detection:
open src/detectors/hybrid_face_detector.py

# Body detection:
open src/detectors/yolov11_body_detector.py
```

### Edit Camera Indices
```bash
open demo_yolo_cameras.py
# Look for line ~736:
# entry_idx = 0
# exit_idx = 1
# room_idx = 2
```

---

## 📚 Documentation

### View Documentation
```bash
cat README.md
cat INSTALLATION_SUCCESS.md
cat ENHANCED_REID_GUIDE.md
cat QUICK_START.md
cat SYSTEM_COMPARISON.md
```

### Open in Browser (macOS)
```bash
open README.md  # Opens in default Markdown viewer
```

### Search Documentation
```bash
grep -r "keyword" *.md
```

---

## 🧹 Cleanup

### Remove Python Cache
```bash
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### Remove Old Sessions
```bash
rm data/yolo_session_*.json
```

### Remove All Generated Data
```bash
rm -rf data/*.db data/*.log data/*.json
```

---

## 📝 Git Commands (If Using Version Control)

### Check Status
```bash
git status
```

### Stage Changes
```bash
git add .
git add specific_file.py
```

### Commit
```bash
git commit -m "Your message"
```

### View History
```bash
git log --oneline
```

---

## 🔄 Updates

### Update All Packages
```bash
pip install --upgrade pip
pip install --upgrade -r requirements.txt
```

### Update Single Package
```bash
pip install --upgrade package_name
```

### Check Outdated Packages
```bash
pip list --outdated
```

---

## 💡 Quick Tips

### One-Liner to Test Everything
```bash
python3 check_system_ready.py && python3 emergency_debug_enhanced.py
```

### Background Process (Run and Detach)
```bash
nohup python3 demo_yolo_cameras.py > output.log 2>&1 &
```

### View Live Logs
```bash
tail -f data/yolo_camera_alerts.log
```

### Find Large Files
```bash
find . -type f -size +10M -exec ls -lh {} \;
```

---

## 🆘 Emergency Commands

### System Completely Stuck
```bash
# Force quit all Python processes
killall -9 Python python3

# Reset cameras
sudo killall VDCAssistant

# Restart terminal
exit
# Then reopen terminal
```

### "Cannot Import" Errors
```bash
# Check if virtual environment is activated
which python3  # Should show path to venv

# If not activated:
source venv/bin/activate

# If still fails, reinstall:
pip install -r requirements.txt
```

### "Model Not Found" Errors
```bash
# Re-download all models
python3 download_yolo_face.py
python3 -c "import torchreid; torchreid.models.build_model('osnet_x1_0', 1000, 'softmax', pretrained=True)"
```

---

## 📞 Support

If you encounter issues not covered here:

1. Check `INSTALLATION_FIXED.md` for resolved issues
2. Check `TROUBLESHOOTING.md` for common problems
3. Review error messages carefully
4. Try restarting everything (cameras, apps, system)

---

**Quick Reference Card:**

| Task | Command |
|------|---------|
| Test enhanced system | `python3 emergency_debug_enhanced.py` |
| Compare systems | `python3 compare_systems.py` |
| Full demo | `python3 demo_yolo_cameras.py` |
| Check setup | `python3 check_system_ready.py` |
| Activate venv | `source venv/bin/activate` |
| View logs | `tail -f data/yolo_camera_alerts.log` |
| Kill Python | `killall -9 python3` |

---

*Command Reference | Enhanced Re-ID System*  
*Last Updated: January 2025*