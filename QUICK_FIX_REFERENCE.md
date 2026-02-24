# Quick Fix Reference Card

## 🚨 Problem: Girl Showing Green (Same ID as You)

### Root Cause:
- **Appearance features (hair/skin) dominated matching**
- **OSNet (body features) had too little weight**
- **No minimum OSNet threshold**

---

## ✅ Changes Made

### 1. Feature Weights (yolo26_complete_system.py, line ~143)
```python
# BEFORE → AFTER
osnet_weight:    0.50 → 0.70  # ✅ Body features now dominant
hair_weight:     0.15 → 0.05  # ✅ Reduced (not discriminative)
skin_weight:     0.15 → 0.05  # ✅ Reduced (not discriminative)
clothing_weight: 0.20 → 0.20  # Same
```

### 2. Hard OSNet Minimum (line ~149)
```python
min_osnet_threshold = 0.50  # ✅ NEW! Rejects if body doesn't match
```

### 3. Cross-Camera Thresholds (src/cross_camera_adapter.py, line ~75)
```python
# BEFORE → AFTER
entry_to_room: 0.38 → 0.50  # ✅ Stricter matching
entry_to_exit: 0.42 → 0.52  # ✅ Stricter matching
room_to_exit:  0.45 → 0.55  # ✅ Stricter matching
```

### 4. Confidence Gaps (line ~86)
```python
# BEFORE → AFTER
entry_to_room: 0.08 → 0.12  # ✅ Need clearer winner
entry_to_exit: 0.10 → 0.12  # ✅ Need clearer winner
room_to_exit:  0.10 → 0.12  # ✅ Need clearer winner
```

---

## 🧪 Testing

### Run System:
```bash
python3 yolo26_complete_system.py
```

### Enable Debug:
Press `D` key

### Expected Results:

**YOU (P001):**
```
✅ AUTHORIZED: P001 (score: 0.575)
   OSNet: 0.650 × 0.70 = 0.455 ✓  # HIGH - Good match!
   Total: 0.575 > 0.50
```

**GIRL (unregistered):**
```
❌ REJECTED - OSNet too low (0.480 < 0.50)
OR
❌ UNAUTHORIZED (score: 0.421)
   OSNet: 0.520 × 0.70 = 0.364 ← LOW!
   Total: 0.421 < 0.50
```

---

## 🎮 Keyboard Controls

| Key | Action |
|-----|--------|
| `D` | Toggle debug (see detailed scores) |
| `I` | Show adapter diagnostics |
| `+` | Increase room threshold (stricter) |
| `-` | Decrease room threshold (lenient) |
| `[` | Decrease exit threshold |
| `]` | Increase exit threshold |
| `C` | Clear all registrations |
| `S` | Show statistics |
| `Q` | Quit |

---

## 🔧 Fine-Tuning (If Needed)

### Girl still GREEN?
**Option 1**: Increase OSNet minimum
```python
# Edit line 149:
self.min_osnet_threshold = 0.60  # Was 0.50
```

**Option 2**: While running, press `+` several times
```
0.50 → 0.55 → 0.60 → 0.65
```

### You getting RED (false negative)?
**Option 1**: Decrease OSNet minimum
```python
# Edit line 149:
self.min_osnet_threshold = 0.45  # Was 0.50
```

**Option 2**: While running, press `-` a few times
```
0.50 → 0.45 → 0.40
```

---

## 📊 Score Interpretation

### Good Match (You):
```
OSNet: 0.60-0.80 (high similarity)
Total: 0.55-0.70 (well above threshold)
Status: ✅ GREEN
```

### Bad Match (Girl):
```
OSNet: 0.35-0.55 (low similarity)
Total: 0.35-0.48 (below threshold)
Status: ❌ RED
```

### Borderline (Adjust thresholds):
```
OSNet: 0.48-0.52 (borderline)
Total: 0.48-0.52 (near threshold)
Action: Use +/- keys or edit min_osnet_threshold
```

---

## ✅ Success Checklist

- [ ] System starts without errors
- [ ] YOU at entry → Auto-registers as P001
- [ ] YOU in room → GREEN box, score ~0.55-0.65
- [ ] GIRL in room → RED box, "UNAUTHORIZED"
- [ ] Debug shows "OSNet × 0.70" (not 0.50)
- [ ] Debug shows rejection message if OSNet < 0.50

---

## 🚀 If Still Not Working

### Immediate Actions:
1. Press `C` to clear registrations
2. Re-register yourself in good lighting
3. Press `I` to check adapter status
4. Share debug output with me

### Advanced Solutions:
1. **Add face embeddings** (InsightFace/ArcFace)
   - Much more discriminative
   - I can implement this!
2. **Fine-tune OSNet** on your cameras
   - Collect 30-100 images per person
   - Train on your specific camera setup
3. **Register multiple people**
   - System works better with 2+ registrations
   - Helps distinguish between people

---

## 📝 Quick Diagnostic

Run with debug (`D`) and check:

```
If girl's OSNet > 0.50:
  → Embeddings too similar (lighting issue?)
  → Need face embeddings OR higher threshold

If girl's OSNet < 0.50 but still GREEN:
  → Bug! Should be rejected
  → Check code was updated correctly

If both get RED:
  → Threshold too strict
  → Press - to lower, or edit min_osnet_threshold
```

---

## 📞 Support

Files to check:
- `yolo26_complete_system.py` (weights, line ~143)
- `src/cross_camera_adapter.py` (thresholds, line ~75)
- `FALSE_POSITIVE_FIX.md` (detailed explanation)
- `BEFORE_AFTER_FIX.md` (visual comparison)

Share with me:
- Debug output (`D` mode) showing the girl's detection
- Adapter diagnostics (`I` key output)
- Any error messages

---

## 💡 Key Takeaway

**Problem**: Matching on hair/skin color (0.18 of score)  
**Solution**: Match on body features (0.46 of score)  
**Safety**: Reject if OSNet < 0.50 (hard minimum)

**Security First**: Better to reject you once than accept a stranger!