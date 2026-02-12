# Intelligence-Led Entry & Exit Management System

# A Comprehensive Technical Report on CCTV Analytics & Crowd Behavior

## 

**Project Group ID:** CSPIT/CSE/B1-C1

**Student ID:** 23CS043 (Ananya Gupta), 23CS023 (Debdoot Manna)

**Domain:** Computer Vision, AI, Security Systems

## 1. Executive Summary: The Story of the System

Imagine a high-security art gallery housing priceless artifacts. In a traditional setup, security guards watch a wall of monitors, passively observing visitors. If a theft occurs, they can only review the footage *after* the fact. If a fight breaks out, they only react *after* the noise reaches them.

Our project, the **Intelligence-Led Entry & Exit Management System**, changes this dynamic from **Reactive** to **Proactive**.

### The Visitor Journey

1. **The Entry:** A visitor, let's call him "Subject A," arrives at the gallery. He walks through a designated **Tunnel Entry Gate**. As he pauses at the turnstile, an infrared sensor triggers a high-resolution camera. *Snap.* A static photo is taken.
2. **The Digital Twin:** In milliseconds, the system analyzes this photo. It extracts his facial features and the color/texture of his clothing. It fuses these distinct features into a single digital signature—a **UUID**. Subject A is no longer just a face; he is a tracked data point, an "Active Session" in the system's brain.
3. **The Tracking:** Subject A walks into the main hall. He is now moving freely among 50 other people. The overhead CCTV cameras don't need to see his face anymore. They see his movement, his height, and his red jacket. The system instantly recognizes him: *"That is UUID-A45F."*
4. **The Anomaly:** Suddenly, a commotion breaks out in the corner. Subject A and three others start moving erratically, their paths zig-zagging violently. The system's "Tail Analysis" algorithm detects this high-entropy movement. It doesn't just record it; it understands it. *"Alert: Physical Altercation in Zone 2."* Security is notified instantly with the exact coordinates.
5. **The Ghost:** Meanwhile, another individual enters the room through a side fire exit, bypassing the Tunnel. The overhead camera spots him but cannot find a matching UUID in the database. *"Alert: Unauthorized Entry. Subject Unidentified."*
6. **The Exit:** Subject A leaves through the Exit Tunnel. The system logs his departure, calculates that he stayed for exactly 42 minutes, and archives his session for future analytics.

This system does not just record video; it understands **Identity**, **Behavior**, and **Intent**.

## 2. Project Objectives

1. **Automated Identification:** Implement a "Photo-First" entry system to generate robust UUIDs using distinct Face and Body embeddings.
2. **Persistent Session Management:** Maintain a "Live State" database (RAM-based) that tracks visitors across multiple camera views without losing identity.
3. **Behavioral Analytics:** Analyze movement trajectories ("tails") to detect panic, running, or fighting in real-time.
4. **Zero-Trust Security:** Instantly flag individuals who appear in the facility without a valid Entry UUID (Unauthorized Access).
5. **Edge Optimization:** Deploy the entire inference pipeline on the **NVIDIA Jetson Nano** using TensorRT and DeepStream for low-latency performance.

## 3. Physical Infrastructure & Design

To ensure high accuracy on edge hardware, we impose physical constraints on the environment.

### 3.1 The Tunnel Queue System

*Refer to Hand-Drawn Diagram: "Queue System"*

- **Design:** A narrow entry corridor (width: 1.2m) that forces visitors to enter single-file.
- **Purpose:**
    - **Eliminates Occlusion:** No visitor can hide behind another during the initial scan.
    - **Controlled Lighting:** The tunnel is lit consistently, ensuring the "Registration Photo" is perfect regardless of outside weather.
    - **Trigger Mechanism:** An IR Break-beam sensor triggers the camera only when a person is in the "Sweet Spot."

### 3.2 Camera Placement Strategy

| **Camera Type** | **Location** | **Sensor/Resolution** | **Role** |
| --- | --- | --- | --- |
| **Registration Cam** | Inside Entry Tunnel (Eye Level) | 4K Static Capture | Captures high-res photo for UUID generation. |
| **Exit Cam** | Inside Exit Tunnel (Eye Level) | 1080p Stream | Verifies identity for checkout and logging. |
| **Room Cams** | Ceiling Corners (Top-Down) | 720p Wide Angle | Tracks movement trails and body signatures. |

## 4. System Architecture

![image.png](Intelligence-Led%20Entry%20&%20Exit%20Management%20System/image.png)

## 5. detailed Methodology

### Module 1: The "Photo-First" Registration (Entry Tunnel)

Unlike systems that try to grab a face from a moving video, our system uses a **Triggered Static Capture**.

1. **Trigger:** User breaks the IR beam in the tunnel.
2. **Capture:** Camera takes 1 high-quality JPEG.
3. **Inference:**
    - **Face:** `RetinaFace` detects the face landmarks. `ArcFace` extracts a 512-dimensional vector ($V_{face}$).
    - **Body:** The system crops the person's torso and legs. `OSNet` extracts a 512-dimensional vector ($V_{body}$).
4. **Fusion:** The Master Vector $V_{final}$ is created.$$ V_{final} = \alpha (V_{face}) + \beta (V_{body}) $$
    
    *(Where* $\alpha$ *and* $\beta$ *are weights, typically Face has higher weight for registration)*.
    
5. **Registration:** $V_{final}$ is pushed to the FAISS `Index_Active` with a new UUID.

### Module 2: The Multi-Camera Handover (Re-ID)

Once the user leaves the tunnel, they enter the Room Camera's field of view.

1. **Detection:** YOLOv11 detects all persons in the room.
2. **Query:** For every detected person, the system extracts their current Body Vector ($V_{current}$).
3. **Search:** It queries the FAISS `Index_Active` using $V_{current}$.
    - *Metric:* Cosine Similarity.
    - *Threshold:* 0.6.
4. **Match:** If a match is found, the system tags that bounding box with the existing UUID.

### Module 3: Trajectory & "Tail" Analysis

This is the core of the **Crowd Behaviour** component. We do not just track *where* they are, but *how* they move.

- **The Tail Buffer:** For every active UUID, we store the last 30 frames of coordinates:$$ T = \{(x_0,y_0), (x_1,y_1), ..., (x_{30},y_{30})\} $$
- **Metric A: Velocity (Panic Detection)**$$ V_{avg} = \frac{\sum \sqrt{\Delta x^2 + \Delta y^2}}{t} $$
    
    We calculate the displacement over time. If the average velocity exceeds the "Running Threshold" ($V_{run}$), an alert is raised.
    
- **Metric B: Entropy (Struggle Detection)**
    
    If a tail is "jumbled" (high angular variance in a small area), it implies a fight or a seizure. We calculate the sum of angular changes. High cumulative angle change + Low displacement = **Struggle**.
    

### Module 4: Zero-Trust Security (Unauthorized Entry)

- **Scenario:** A thief enters through a window or fire exit, bypassing the Tunnel.
- **Logic:**
    1. Room Camera detects a Person.
    2. System generates Body Vector.
    3. FAISS Search returns **No Match** (Distance > Threshold).
    4. **System Conclusion:** This person did not pass through the Tunnel.
    5. **Action:** Visual Alarm on Dashboard (Red Box) + "UNAUTHORIZED VISITOR" Log.

## 6. Technical Stack & Repositories

### 6.1 Face Identification (3 Sources)

We utilize State-of-the-Art (SOTA) models for facial feature extraction.

1. **DeepFace:** A lightweight wrapper for Facebook's DeepFace and Google's FaceNet.
    - *Repo:* [https://github.com/serengil/deepface](https://github.com/serengil/deepface)
2. **InsightFace:** currently the industry standard for 2D and 3D face analysis (ArcFace).
    - *Repo:* [https://github.com/deepinsight/insightface](https://github.com/deepinsight/insightface)
3. **Face_Recognition (Dlib):** A robust, easy-to-implement library for lower-end hardware fallbacks.
    - *Repo:* [https://github.com/ageitgey/face_recognition](https://github.com/ageitgey/face_recognition)

### 6.2 Body Re-Identification (1 Source)

For tracking people when their faces are not visible (back turned/overhead view).

1. **Torchreid:** A library for deep learning person re-identification, featuring models like OSNet.
    - *Repo:* [https://github.com/KaiyangZhou/deep-person-reid](https://github.com/KaiyangZhou/deep-person-reid)

### 6.3 Tracking, Trailing & Velocity (4 Sources)

Algorithms to maintain identity across frames and calculate movement vectors.

1. **ByteTrack:** Excellent for handling occlusion (people passing behind each other).
    - *Repo:* [https://github.com/ifzhang/ByteTrack](https://github.com/ifzhang/ByteTrack)
2. **StrongSORT:** An upgrade to DeepSORT with better re-id features.
    - *Repo:* [https://github.com/dyh/StrongSORT](https://www.google.com/search?q=https://github.com/dyh/StrongSORT)
3. **Norfair:** A customizable tracker written in pure Python, excellent for adding custom "Velocity" logic.
    - *Repo:* [https://github.com/tryolabs/norfair](https://github.com/tryolabs/norfair)
4. **FilterPy (Kalman Filters):** The mathematical backbone for smoothing "Jumbled" tails.
    - *Repo:* [https://github.com/rlabbe/filterpy](https://github.com/rlabbe/filterpy)

## 7. Mathematical Model: Threat Detection

To scientifically detect a threat, we define a **Threat Score (**$S_{threat}$**)**.

$$ S_{threat} = (w_1 \times V_{rel}) + (w_2 \times E_{traj}) + (w_3 \times D_{prox}) $$

Where:

- $V_{rel}$ **(Relative Velocity):** Speed of the subject relative to the average crowd speed.
- $E_{traj}$ **(Trajectory Entropy):** A measure of how chaotic the path is (0 = straight line, 1 = chaotic scribble).
- $D_{prox}$ **(Proximity Density):** Inverse distance to other subjects (detecting clumping/fighting).
- $w$**:** Weights assigned to each factor.

**Alert Trigger:**

- If $S_{threat} > 0.8$: **CRITICAL ALERT** (Fight/Panic).
- If $S_{threat} > 0.5$: **WARNING** (Congestion).

## 8. Database Schema Design

### 8.1 SQLite (Metadata)

**Table: Visit_Logs**

| **Column** | **Type** | **Description** |
| --- | --- | --- |
| `session_uuid` | VARCHAR(36) | Primary Key |
| `entry_time` | DATETIME | Timestamp of tunnel trigger |
| `exit_time` | DATETIME | NULL until exit |
| `threat_flag` | BOOLEAN | Did they trigger an alert? |
| `avg_velocity` | FLOAT | Activity level summary |

### 8.2 FAISS (Vector Storage)

FAISS (Facebook AI Similarity Search) is used because standard SQL cannot search "Similarity" between images.

- **Dimension:** 1024 (512 Face + 512 Body).
- **Index Type:** `IndexFlatL2` (Exact Search) or `IndexIVFFlat` (Fast Approx Search for large crowds).

## 9. SWOT Analysis

| **Strengths** | **Weaknesses** |
| --- | --- |
| **"Photo-First" Accuracy:** Using static photos at entry ensures high-quality embeddings. | **Hardware Limit:** Jetson Nano (4GB) struggles with >4 concurrent streams. |
| **Zero-Trust:** Capable of detecting intruders who bypassed the main gate. | **Occlusion Limits:** If a room is totally packed, "tails" may merge/swap. |
| **Passive Security:** No turnstiles or RFID cards needed for tracking. | **Lighting:** Re-ID fails in pitch darkness (requires IR cameras). |

| **Opportunities** | **Threats** |
| --- | --- |
| **Retail Analytics:** Can be sold to shops to analyze "customer dwell time." | **Adversarial Attacks:** Patterns on clothes designed to confuse AI. |
| **Cloud Scaling:** Offload heavy FAISS processing to a cloud server for larger venues. | **GDPR/Privacy:** Strict regulations on storing biometric data. |

## 10. Project Timeline (Gantt Chart)

| **Phase** | **Task** | **Duration** | **Owner** |
| --- | --- | --- | --- |
| **Phase 1** | Tunnel Setup & Photo Trigger Logic | Weeks 1-2 | Ananya |
| **Phase 2** | Face/Body Embedding Pipeline | Weeks 3-4 | Debdoot |
| **Phase 3** | Room Tracking & Velocity Math | Weeks 5-6 | Debdoot |
| **Phase 4** | Database Integration (FAISS+SQL) | Week 7 | Ananya |
| **Phase 5** | Dashboard & Alert System | Week 8 | Both |
| **Phase 6** | Testing & Calibration | Week 9 | Both |

## 11. Conclusion

The **Intelligence-Led Entry & Exit Management System** is not just a surveillance tool; it is a situational awareness engine. By combining the precision of static biometrics in the "Tunnel" with the fluidity of behavioral analytics in the "Room," we bridge the gap between knowing *who* is there and understanding *what* they are doing. This project pushes the boundaries of Edge AI, proving that complex behavioral analysis is possible on accessible hardware like the Jetson Nano.