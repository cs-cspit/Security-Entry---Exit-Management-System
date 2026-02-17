# Security Model Documentation
## Session-Based Authorization System

---

## 🔒 Security Vulnerability - FIXED

### The Problem (CRITICAL)

**Scenario:**
1. Person enters through ENTRY camera → Registered as `P001` ✅
2. Person moves to ROOM → Tracked as authorized ✅
3. Person exits through EXIT camera → Recorded as exited ✅
4. **SECURITY BREACH:** Person re-enters directly to ROOM (bypassing ENTRY)
5. System still recognizes `P001` as authorized ✅ **← WRONG!**
6. Person can now perform malicious activities undetected 🚨

**Why this is critical:**
- Attackers can register once, exit, then re-enter bypassing entry security
- No audit trail for subsequent unauthorized entries
- System thinks they're still authorized from original entry
- Defeats the entire purpose of entry/exit monitoring

---

## ✅ The Solution: Session-Based Authorization

### Core Concept

**Every entry creates a NEW session. Exits INVALIDATE sessions.**

```
Entry → Session Created → Active Authorization → Exit → Session Ended
   ↓                           ↓                            ↓
 P001                    Can access room             Authorization REVOKED
Session S0001                                        Status: "exited"
```

---

## 🎯 How It Works

### 1. Entry Registration

**First-time entry:**
```python
Person detected at ENTRY camera
  ↓
New person ID created: P001
  ↓
New session created: S0001
  ↓
Status set: "active"
  ↓
Database: record_entry(P001)
  ↓
Result: P001 is AUTHORIZED (Session S0001 active)
```

**Console output:**
```
🤖 AUTO-REGISTERED: P001 (Session S0001) | Face conf: 0.78
🔒 Active session created: S0001 for P001
```

---

### 2. Room Tracking (Authorization Check)

**When person detected in ROOM camera:**

```python
Step 1: Detect person
Step 2: Match to registered profiles → P001 (similarity: 0.72)
Step 3: 🔒 SECURITY CHECK:
        - Does P001 have active session? 
        - Is P001 status "active"?

IF YES → AUTHORIZED (Green box, track normally)
IF NO  → UNAUTHORIZED / THREAT (Red box, alert!)
```

**Authorized person (has active session):**
```
🟢 GREEN BOX
   P001 (0.72)
   Mode: both
   🟣 Trajectory trail
```

**Console:**
```
✅ ROOM MATCH: P001 | Similarity: 0.68 | Session: S0001 active
```

---

### 3. Exit Detection

**When person detected at EXIT camera:**

```python
Person matched to P001 (similarity: 0.61)
  ↓
Record exit in database
  ↓
🔒 SECURITY: Invalidate session
  - Delete from active_sessions
  - Set status to "exited"
  - Remove from inside_people
  ↓
Result: P001 is NO LONGER AUTHORIZED
```

**Console output:**
```
👋 EXIT DETECTED: P001 (Session S0001 ended) | Similarity: 0.606
🔒 Authorization revoked for P001 - must re-enter through ENTRY camera
```

---

### 4. Re-Entry (After Exit)

**Scenario A: Person re-enters through ENTRY camera (CORRECT)**

```python
P001 detected at ENTRY camera
  ↓
System checks: P001 exists but status = "exited"
  ↓
Create NEW session: S0002
  ↓
Set status: "active"
  ↓
Record new entry in database
  ↓
Result: P001 is AUTHORIZED again (New Session S0002)
```

**Console:**
```
↩️ RE-ENTRY: P001 (New Session S0002) | Previous session was closed
🔒 New active session created: S0002 for P001
```

**Scenario B: Person re-enters directly to ROOM (BYPASSING ENTRY) 🚨**

```python
P001 detected in ROOM camera
  ↓
System matches to P001 (similarity: 0.72)
  ↓
🔒 SECURITY CHECK:
  - P001 exists in registered_people ✓
  - P001 status = "exited" ✗
  - P001 NOT in active_sessions ✗
  ↓
Result: UNAUTHORIZED / SECURITY BREACH
```

**Console:**
```
🚨 CRITICAL: P001 detected in room WITHOUT re-entry! Previous session ended.
[CRITICAL] [UNAUTHORIZED_ENTRY] SECURITY BREACH: P001 bypassed entry after exit
```

**Room camera display:**
```
🔴 RED BOX
   THREAT: P001 (BYPASSED ENTRY)
   ⚠️ CRITICAL ALERT
```

---

## 📊 Data Structures

### Person Status Tracking

```python
# Person profiles (persistent)
registered_people = {
    "P001": {
        "person_id": "P001",
        "face_features": [...],
        "body_features": [...],
        "registration_time": 1234567890.0
    }
}

# Active sessions (cleared on exit)
active_sessions = {
    "P001": "S0001"  # Only present when person has active entry
}

# Person status (persistent)
person_status = {
    "P001": "active"  # or "exited"
}

# Currently inside (cleared on exit)
inside_people = {
    "P001": 1234567890.0  # last_seen_time
}
```

---

## 🔐 Security States

### Person Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│                    PERSON LIFECYCLE                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [NEW]                                                   │
│    ↓                                                     │
│  ENTRY → [REGISTERED] + Session S0001 + Status: active  │
│    ↓                                                     │
│  ROOM → ✅ AUTHORIZED (has active session)              │
│    ↓                                                     │
│  EXIT → Session ended + Status: exited                  │
│    ↓                                                     │
│  [EXITED STATE]                                          │
│    ↓                                                     │
│  ├─→ Re-enter via ENTRY → New Session S0002 ✅          │
│  │      Status: active                                  │
│  │      Result: AUTHORIZED                              │
│  │                                                       │
│  └─→ Appear in ROOM directly → 🚨 THREAT               │
│         No active session                                │
│         Result: UNAUTHORIZED / BREACH                    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🎮 Testing the Security Model

### Test Case 1: Normal Entry/Exit Flow

```bash
# Step 1: Entry
Position at ENTRY camera → Press 'e'
Expected: "🤖 AUTO-REGISTERED: P001 (Session S0001)"

# Step 2: Room
Move to ROOM camera
Expected: Green box, "P001 (0.72)", trajectory trail

# Step 3: Exit
Move to EXIT camera
Expected: "👋 EXIT DETECTED: P001 (Session S0001 ended)"
Expected: "🔒 Authorization revoked"

# Step 4: Verify room shows 0 inside
Stats should show: "Inside: 0"
```

---

### Test Case 2: Re-Entry Through ENTRY (Correct)

```bash
# After Test Case 1 (person exited):

# Step 1: Re-enter at ENTRY
Position at ENTRY camera → Press 'e'
Expected: "↩️ RE-ENTRY: P001 (New Session S0002)"
Expected: "🔒 New active session created: S0002"

# Step 2: Room
Move to ROOM camera
Expected: Green box, "P001", authorized again

# Result: ✅ PASS - System allows proper re-entry
```

---

### Test Case 3: 🚨 Bypass Attempt (Security Test)

```bash
# After Test Case 1 (person exited):

# Step 1: Do NOT go to ENTRY camera
# Step 2: Go directly to ROOM camera
Expected: Red box, "THREAT: P001 (BYPASSED ENTRY)"
Expected: "🚨 CRITICAL: P001 detected in room WITHOUT re-entry!"
Expected: CRITICAL alert logged

# Result: ✅ PASS - Security breach detected!
```

---

## 📈 Database Schema Updates

### Entries Table

```sql
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    person_id TEXT NOT NULL,
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,  -- NEW: Track which session
    camera_source TEXT DEFAULT 'entry'
);
```

**Multiple entries for same person:**
```
| id | person_id | entry_time          | session_id |
|----|-----------|---------------------|------------|
| 1  | P001      | 2024-01-01 10:00:00 | S0001      |
| 2  | P001      | 2024-01-01 14:30:00 | S0002      | ← Re-entry
| 3  | P001      | 2024-01-02 09:15:00 | S0003      | ← Next day
```

---

### Exits Table

```sql
CREATE TABLE exits (
    id INTEGER PRIMARY KEY,
    person_id TEXT NOT NULL,
    exit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,  -- NEW: Which session ended
    duration_seconds REAL
);
```

---

### Alerts Table (Security Breaches)

```sql
-- Example security breach alert:
INSERT INTO alerts (
    alert_type, 
    level, 
    person_id, 
    description,
    camera_source
) VALUES (
    'UNAUTHORIZED_ENTRY',
    'CRITICAL',
    'P001',
    'SECURITY BREACH: P001 bypassed entry after exit',
    'room'
);
```

---

## 🔍 Monitoring & Analytics

### Active Session Monitoring

**Dashboard view:**
```
============================================================
SYSTEM STATUS
============================================================
Registered People:    5
Active Sessions:      2  ← Currently authorized
People Inside:        2
People Exited:        3
Unauthorized:         1
============================================================

ACTIVE SESSIONS:
  P001 → S0005 (entered 5 mins ago)
  P003 → S0007 (entered 2 mins ago)

EXITED (No Authorization):
  P002 → Last session S0006 (ended 10 mins ago)
  P004 → Last session S0004 (ended 1 hour ago)
  P005 → Last session S0003 (ended 2 hours ago)
```

---

### Security Breach Queries

**Find all bypass attempts:**
```sql
SELECT * FROM alerts 
WHERE description LIKE '%bypassed entry%'
AND level = 'CRITICAL'
ORDER BY alert_time DESC;
```

**Find people with multiple sessions (frequent visitors):**
```sql
SELECT person_id, COUNT(*) as visit_count, 
       MIN(entry_time) as first_visit,
       MAX(entry_time) as last_visit
FROM entries
GROUP BY person_id
HAVING visit_count > 1;
```

---

## ⚙️ Configuration

### Adjust Security Levels

**Strict mode (current):**
```python
# Exit immediately revokes authorization
# Re-entry through ENTRY camera required
STRICT_MODE = True
```

**Lenient mode (optional):**
```python
# Allow grace period after exit before revoking
EXIT_GRACE_PERIOD_SECONDS = 60  # 1 minute

# Allow same-day re-entries without new session
SAME_DAY_RE_ENTRY = True
```

---

## 🚨 Alert Levels

| Level | Trigger | Action |
|-------|---------|--------|
| **INFO** | Normal entry/exit | Log only |
| **WARNING** | Unauthorized person (unknown) | Log + alert |
| **CRITICAL** | Bypass attempt (known person, no session) | Log + alert + notify security |

---

## 📝 Security Best Practices

### For System Operators:

1. **Monitor active sessions:**
   - Number should match physical people in room
   - Investigate if mismatch occurs

2. **Review CRITICAL alerts daily:**
   - All bypass attempts should be investigated
   - Check camera footage for confirmed breaches

3. **Session audit trail:**
   - Keep entry/exit records for compliance
   - Track session duration for analytics

4. **Regular testing:**
   - Run bypass test (Test Case 3) weekly
   - Verify alerts trigger correctly

---

## 🎯 Summary

### Before (Vulnerable):
```
Entry → P001 created → Exit → P001 still authorized ✗
                                Re-enter room → Still authorized ✗
                                SECURITY BREACH POSSIBLE 🚨
```

### After (Secure):
```
Entry → P001 + Session S0001 → Exit → Session ended ✅
                                        Status: "exited" ✅
                                        Authorization revoked ✅
                                        
Re-enter via ENTRY → New Session S0002 ✅
Re-enter via ROOM → 🚨 THREAT DETECTED ✅
```

---

## 🔐 Security Guarantees

✅ **No bypass:** Exited people cannot re-enter without going through ENTRY  
✅ **Session tracking:** Every entry creates unique audit trail  
✅ **Status validation:** Room camera checks active session before authorization  
✅ **Alert system:** Security breaches trigger CRITICAL alerts  
✅ **Database integrity:** Complete history of all entries, exits, and sessions  

---

*Last Updated: February 2024*  
*Security Model Version: 2.0*  
*Status: ✅ Vulnerability Patched*  
*Critical Security Level: ENABLED*