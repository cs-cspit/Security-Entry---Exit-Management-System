# Quick Test Guide - Updated System (Confidence Gap 0.12)

## What Changed?

We lowered the confidence gap from **0.20 → 0.12** based on your emergency debug results.

**Why?**
- 0.20 was too strict - rejected even legitimate users (you!)
- 0.12 provides better balance - accepts clear matches, rejects ambiguous ones

---

## Quick Test (5 Minutes)

### Step 1: Run Emergency Debug Again

```bash
cd "Security Entry & Exit Management System"
source venv/bin/activate
python3 emergency_debug_false_positives.py
```

### Step 2: Register Two People

**Person A (You):**
1. Stand in front of camera
2. Press `r` to register as TEST_P001

**Person B (Friend):**
1. Have friend stand in front of camera
2. Press `r` to register as TEST_P002

### Step 3: Test Matching

**Test Person A (You):**
1. Stand in front of camera alone
2. Press `SPACE` to test
3. **Expected**: Should see "✅ MATCHED: TEST_P001" (or occasionally rejected if gap < 0.12)

**Test Person B (Friend):**
1. Have friend stand in front of camera alone
2. Press `SPACE` to test
3. **Expected**: Should see "❌ NO MATCH" or "⚠️ AMBIGUOUS" (rejected as unknown)

Press `q` to quit.

---

## Expected Results with 0.12 Gap

### ✅ Success Indicators

1. **Person A (registered user)**: 
   - Matches in ~70-80% of tests
   - Rejected in ~20-30% when gap < 0.12 (acceptable trade-off)

2. **Person B (unregistered)**: 
   - Rejected in ~90-95% of tests
   - May match in ~5-10% if very similar to Person A (this is the trade-off)

3. **Ambiguity detection**: 
   - System prints "⚠️ AMBIGUOUS" when confidence gap is too small
   - This is GOOD - it means the system knows it's uncertain

### ❌ If Something is Wrong

**If Person A never matches (0% success rate):**
- Gap still too high
- Try lowering to 0.10: Edit `src/multi_modal_reid.py` line 26
- Change `confidence_gap: float = 0.12` to `0.10`

**If Person B matches frequently (>20% success rate):**
- Gap too low (false positives)
- Try raising to 0.15: Edit `src/multi_modal_reid.py` line 26
- Change `confidence_gap: float = 0.12` to `0.15`

---

## Full Three-Camera Demo Test

### Test Scenario 1: Normal Flow (You)

```bash
python3 demo_yolo_cameras.py
```

1. **Entry Camera (Webcam 0)**:
   - Press `r` to register yourself
   - Should show "✅ Authorized: [YOUR_ID]"

2. **Room Camera (Webcam 1)**:
   - Walk to room camera view
   - Should recognize you (green box)
   - Status: "ACTIVE session"

3. **Exit Camera (Webcam 2)**:
   - Walk to exit camera
   - Should detect exit
   - Session invalidated

4. **Re-entry Test**:
   - Go back to entry camera
   - Should show "❌ Session expired - please re-register"

### Test Scenario 2: Unauthorized Person (Friend)

1. **Entry Camera**: Friend appears (not registered)
   - Should show "⚠️ UNKNOWN PERSON DETECTED"

2. **Room Camera**: Friend appears
   - Should show "❌ UNAUTHORIZED"
   - OR "⚠️ AMBIGUOUS - Further verification needed"

3. **Exit Camera**: Friend appears
   - Should show "Unrecognized exit"

---

## Understanding the Output

### Debug Output Example

```
================================================================================
🔍 MATCHING TEST #1
================================================================================

📊 SIMILARITY SCORES AGAINST ALL REGISTERED PEOPLE:
--------------------------------------------------------------------------------

TEST_P001:
  Combined similarity: 0.9076        ← Overall match score
  Face similarity:     0.9562        ← Face recognition (high = good)
  Body similarity:     0.8346        ← Body features (moderate)
  ✅ Combined matches (>= 0.65)

TEST_P002:
  Combined similarity: 0.7805        ← Lower score (different person)
  Face similarity:     0.8057
  Body similarity:     0.7426
  ✅ Combined matches (>= 0.65)

--------------------------------------------------------------------------------
🔍 Mode: body_primary | Body: 0.835 | Face: 0.956 | Threshold: 0.600

⚠️ AMBIGUOUS: Best=TEST_P001(0.91) vs 2nd=TEST_P002(0.78), gap=0.13 < 0.12
                                                                    ↑
                                                          Gap is too small!

🎯 FINAL DECISION:
  ❌ NO MATCH (similarity: 0.9076)
  Reason: ambiguous_match
```

### What to Look For

1. **Best match score**: Should be > 0.85 for registered person
2. **2nd best score**: Should be < 0.80 for unregistered person
3. **Gap**: Difference between them (need ≥ 0.12)
4. **Decision**: System accepts only if gap is sufficient

---

## Tuning Guide

### If Too Many False Negatives (Rejecting You)

**Option 1: Lower confidence gap**
```python
# In src/multi_modal_reid.py line 26
confidence_gap: float = 0.10  # Was 0.12
```

**Option 2: Lower similarity threshold**
```python
# In src/multi_modal_reid.py line 25
similarity_threshold: float = 0.60  # Was 0.65
```

### If Too Many False Positives (Accepting Strangers)

**Option 1: Raise confidence gap**
```python
# In src/multi_modal_reid.py line 26
confidence_gap: float = 0.15  # Was 0.12
```

**Option 2: Raise similarity threshold**
```python
# In src/multi_modal_reid.py line 25
similarity_threshold: float = 0.70  # Was 0.65
```

**Option 3: Raise body threshold**
```python
# In src/multi_modal_reid.py line 27
body_only_threshold: float = 0.65  # Was 0.60
```

---

## Performance Metrics to Track

Create a test log:

```
Test Date: [DATE]
Confidence Gap: 0.12
Number of registered people: 2

Person A (Registered) Tests:
- Total tests: 20
- Matched correctly: 14 (70%)
- Rejected incorrectly: 6 (30%)
- False positive: 0 (0%)

Person B (Unregistered) Tests:
- Total tests: 20
- Rejected correctly: 18 (90%)
- Matched incorrectly: 2 (10%)  ← This is concerning if > 10%

Conclusion: Acceptable for demo, needs improvement for production
```

---

## When to Use Current System vs. Upgrade

### ✅ Current System is OK for:
- Proof of concept demos
- Controlled testing (2-5 people)
- Short-term exhibitions
- When you can tolerate 5-10% error rate

### ❌ Need Embedding Upgrade for:
- Production deployments
- >10 registered people
- Security-critical applications (CISF)
- Long-term installations
- When error rate must be < 1%

---

## Troubleshooting

### Issue: "Both persons rejected every time"

**Diagnosis**: Gap still too high or similarity threshold too strict

**Fix**:
```bash
# Edit src/multi_modal_reid.py
confidence_gap = 0.08  # Lower
similarity_threshold = 0.55  # Lower
```

### Issue: "Both persons match to same ID"

**Diagnosis**: Gap too low or they're wearing very similar clothes

**Fix**:
```bash
# Edit src/multi_modal_reid.py
confidence_gap = 0.15  # Higher
body_only_threshold = 0.70  # Higher
```

### Issue: "System is slow"

**Check**: Are you using GPU acceleration?
```bash
python3 -c "import torch; print(torch.backends.mps.is_available())"  # macOS
python3 -c "import torch; print(torch.cuda.is_available())"  # Linux/Windows
```

---

## Next Steps After Testing

1. **Document your results** in a test log
2. **Share metrics** (false positive rate, false negative rate)
3. **Decide**: Is current accuracy acceptable for your use case?
4. **If NO**: I can help implement embedding-based re-ID

---

## Quick Reference

| Metric | Current Value | Tunable? | Impact |
|--------|---------------|----------|--------|
| Confidence Gap | 0.12 | ✅ Yes | Higher = fewer false positives, more false negatives |
| Similarity Threshold | 0.65 | ✅ Yes | Higher = stricter matching |
| Body-only Threshold | 0.60 | ✅ Yes | Higher = stricter room camera matching |
| Face Weight | 0.6 | ✅ Yes | Higher = rely more on face |
| Body Weight | 0.4 | ✅ Yes | Higher = rely more on body |

**Golden Rule**: Security vs. Usability trade-off
- More security → Higher thresholds → More rejections
- More usability → Lower thresholds → More false positives

---

Good luck with your testing! 🚀

Report back with:
1. Person A match rate (should be 70-80%)
2. Person B rejection rate (should be 90%+)
3. Any unexpected behavior