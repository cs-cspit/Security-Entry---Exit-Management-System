# 🎯 JUST TEST THIS - Single Webcam Multi-Person Detection

## What This Does

Uses your **MacBook webcam** to detect and identify **MULTIPLE people at the same time**.

- Detects everyone in frame simultaneously
- Each person gets a unique ID
- GREEN box = Person you registered
- RED box = Unknown person
- Uses OSNet + clothing analysis to tell people apart

---

## Run This Command

```bash
cd "Security Entry & Exit Management System"
source venv/bin/activate
python3 simple_room_test.py
```

---

## How To Use It

### Step 1: Register Yourself
1. Stand alone in front of webcam
2. Wait for green face box to appear
3. Press **`r`** key
4. You'll see: "✅ Registered: PERSON_1"
5. Now you have a GREEN box with "PERSON_1" label

### Step 2: Register Your Friend
1. Have your friend stand next to you in frame
2. Both of you should be visible
3. Make sure your friend is the BIGGER detection (stand closer to camera)
4. Press **`r`** key again
5. You'll see: "✅ Registered: PERSON_2"
6. Now you BOTH have GREEN boxes with different IDs

### Step 3: Watch It Work
- Walk around, change positions
- System identifies BOTH of you in real-time
- Each person keeps their own ID
- Different colors, different clothing, different body features = different IDs

---

## Expected Behavior

**GOOD (What Should Happen):**
- Person 1 always gets labeled "PERSON_1" (green box)
- Person 2 always gets labeled "PERSON_2" (green box)
- System doesn't confuse them even if they wear similar clothes
- Works even when you move around or change angles

**BAD (What We're Fixing):**
- If both people get labeled "PERSON_1" → FALSE POSITIVE (this is the bug we're solving)
- If system says "UNKNOWN" for someone already registered → FALSE NEGATIVE

---

## What to Test

1. **Basic test**: Register 2 different people, verify they get different IDs
2. **Similar clothing**: Both wear dark colors - should still work (OSNet helps)
3. **Movement test**: Walk around - IDs should stay consistent
4. **Angle test**: Turn to side - should still recognize
5. **Distance test**: Move closer/farther - should still work

---

## Keyboard Controls

- **`r`** = Register whoever is LARGEST in frame
- **`q`** = Quit

---

## What You'll See On Screen

```
┌─────────────────────────────────────────────────┐
│ Registered: 2 | Detected: 2                     │
│ Known: 2 | Unknown: 0                           │
│ Press 'r' to register | 'q' to quit             │
├─────────────────────────────────────────────────┤
│                                                 │
│     ┌──────────┐        ┌──────────┐           │
│     │ PERSON_1 │        │ PERSON_2 │           │
│     │  (0.87)  │        │  (0.91)  │           │
│     └──────────┘        └──────────┘           │
│          ↑                    ↑                 │
│       GREEN BOX            GREEN BOX            │
│                                                 │
└─────────────────────────────────────────────────┘
```

Numbers like (0.87) = similarity score (higher = more confident)

---

## Alternative: More Detailed Test

If you want to see MORE information about what's being detected:

```bash
python3 multi_person_room_test.py
```

This shows:
- Detailed clothing colors
- Pattern detection (stripes, solid, etc.)
- Skin tone features
- OSNet embedding info

Press **`s`** to see summary of all registered people.

---

## Troubleshooting

### "No face detected"
- Move closer to camera
- Improve lighting
- Face the camera directly

### "Need face + body in frame"
- Stand back a bit so your full upper body is visible
- Make sure camera can see from head to waist

### Both people get same ID (FALSE POSITIVE)
- This is what we're testing! Report this.
- Try the enhanced system - it should handle this better than old system

### Camera won't open
```bash
# Check permissions:
System Preferences → Security & Privacy → Camera → Enable Terminal
```

---

## Why This Test Matters

The **old system** used simple color histograms and often confused people wearing similar clothing.

The **new system** uses:
- OSNet deep learning embeddings (512-dimensional features)
- Advanced clothing analysis (patterns, textures, styles)
- Skin tone detection
- Multi-modal fusion

Result: Should be **MUCH BETTER** at telling people apart, even with similar clothing.

---

## Success Criteria

✅ You register yourself → Get PERSON_1 label
✅ Friend registers → Get PERSON_2 label  
✅ Both visible at once → Both labeled correctly
✅ Move around → Labels stay consistent
✅ No false positives (Person A labeled as Person B)
✅ No false negatives (registered person showing as UNKNOWN)

---

## Questions to Answer

After testing, you should be able to answer:

1. Does it correctly identify 2 different people?
2. Does it confuse them if they wear similar colors?
3. What's the similarity score range for correct matches? (should be 0.70-0.95)
4. What's the similarity score for wrong person? (should be below 0.70)
5. Does it work from different angles/distances?

---

## Next Steps After Testing

If this works well:
- Integrate into full 3-camera demo
- Add entry/exit tracking
- Deploy with your external cameras

If this doesn't work:
- Tune thresholds in `src/enhanced_reid.py`
- Check what features are being extracted
- Report specific failure cases

---

**TL;DR: Run `python3 simple_room_test.py`, register 2 people with 'r' key, verify they get different IDs.**

That's it. No entry/exit cameras needed. Just test multi-person detection with your webcam.