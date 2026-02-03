# Face Re-Identification System - Test Script

A complete Python implementation of the Detect → Align → Encode → Match pipeline for face detection and re-identification in a Security Entry & Exit Management System.

## 🎯 Overview

This script implements a real-time face recognition system that:
1. **Detects** faces using YOLOv8-Face with >80% confidence threshold
2. **Aligns** faces using MTCNN landmark detection to normalize eye positions
3. **Encodes** aligned faces into 512-dimensional vectors using ArcFace/FaceNet
4. **Matches** face signatures using FAISS or cosine similarity (threshold: 0.6)

## 🏗️ System Architecture

```
Webcam Input → Detector (YOLO) → Aligner (MTCNN) → Encoder (ArcFace) → Matcher (FAISS) → Output
                    ↓                  ↓                    ↓                  ↓
              Face Bounding Box   Eye Alignment       512D Vector      Database Search
              Confidence >0.8     Rotation Correction  Face Signature   Distance <0.6
```

### Pipeline Components

| Component | Technology | Purpose | Output |
|-----------|-----------|---------|--------|
| **Detector** | YOLOv8-Face / YOLOv11 | Locate faces in video frames | Bounding boxes, confidence scores |
| **Aligner** | MTCNN | Detect landmarks & align faces | Normalized face images (160x160) |
| **Encoder** | ArcFace / FaceNet512 | Convert faces to vectors | 512D embeddings |
| **Matcher** | FAISS / Cosine Similarity | Compare signatures | Match decisions, distances |

## 📋 Requirements

### System Requirements
- Python 3.8 or higher
- Webcam (USB or built-in)
- 4GB+ RAM recommended
- GPU optional (CPU mode works fine)

### Python Dependencies

```bash
pip install ultralytics mtcnn opencv-python deepface faiss-cpu scipy numpy pillow tensorflow
```

**Dependency Breakdown:**
- `ultralytics` - YOLOv8/YOLOv11 face detection
- `mtcnn` - Face alignment and landmark detection
- `opencv-python` - Video capture and image processing
- `deepface` - ArcFace/FaceNet face encoding
- `faiss-cpu` - Efficient similarity search (use `faiss-gpu` for GPU acceleration)
- `scipy` - Cosine distance calculation (fallback)
- `numpy` - Numerical operations
- `pillow` - Image handling
- `tensorflow` - Deep learning backend for DeepFace

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies
pip install ultralytics mtcnn opencv-python deepface faiss-cpu scipy numpy pillow tensorflow
```

### 2. Run the Script

```bash
python face_reidentification_test.py
```

### 3. First Run - Model Downloads

On first run, the script will automatically download required models:
- YOLOv8n-Face (~6MB) - Face detection
- ArcFace model (~91MB) - Face encoding
- MTCNN weights (~2MB) - Face alignment

**Note:** This may take a few minutes depending on your internet connection.

### 4. Using the System

Once the webcam window opens:
- **Position your face** in front of the camera
- The system will detect, align, encode, and match your face
- **Green box** = Recognized visitor (matched in database)
- **Orange box** = New visitor (added to database)
- Press **'q'** to quit
- Press **'s'** to show statistics

## 🎮 Controls

| Key | Action |
|-----|--------|
| `q` | Quit the application |
| `s` | Show system statistics in console |

## 📊 Understanding the Output

### Visual Display

```
┌─────────────────────────────────┐
│ RECOGNIZED | ID:a3f2b1c8        │  ← Green for recognized
│ Conf: 0.95                      │  ← Detection confidence
│ Dist: 0.3421                    │  ← Cosine distance
│  ┌──────────────────────┐       │
│  │                      │       │
│  │     [Face Image]     │       │  ← Bounding box
│  │                      │       │
│  └──────────────────────┘       │
└─────────────────────────────────┘

Top-left stats:
FPS: 12.3              ← Processing speed
Detections: 45         ← Total faces detected
Recognitions: 32       ← Re-identified faces
DB Size: 5             ← Unique visitors stored
```

### Console Output

```
[DETECT] Found 1 face(s) with confidence >0.8
[ALIGN] Face aligned (rotation: -2.34°)
[ENCODE] Generated 512D embedding using ArcFace
[MATCH] Recognized visitor: a3f2b1c8... (Distance: 0.3421, Encounters: 3)
```

### Distance Interpretation

| Distance | Meaning | Action |
|----------|---------|--------|
| < 0.4 | Very similar (same person) | High confidence match |
| 0.4 - 0.6 | Similar (likely same person) | Match accepted |
| > 0.6 | Different (different person) | New visitor registered |

## 🔧 Configuration

### Adjusting Detection Threshold

Edit in `face_reidentification_test.py`:

```python
system = FaceReIdentificationSystem(
    yolo_model="yolov8n-face.pt",
    confidence_threshold=0.8  # Change to 0.6 for more detections, 0.9 for higher precision
)
```

### Adjusting Matching Threshold

```python
self.database = FaceDatabase(
    use_faiss=FAISS_AVAILABLE,
    dimension=512,
    similarity_threshold=0.6  # Lower = stricter matching, Higher = more lenient
)
```

**Threshold Guidelines:**
- **0.4-0.5**: Very strict (fewer false matches, may miss some correct matches)
- **0.6**: Balanced (recommended)
- **0.7-0.8**: Lenient (more matches, higher false positive rate)

### Performance Optimization

```python
# Process every N frames instead of all frames
if frame_count % 3 == 0:  # Process every 3rd frame (10 FPS if camera is 30 FPS)
    annotated_frame, results = system.process_frame(frame)
```

## 🐛 Troubleshooting

### Issue: "Could not open webcam"

**Solutions:**
1. Check if another application is using the webcam
2. Try different camera index:
   ```python
   cap = cv2.VideoCapture(1)  # Try 1, 2, 3, etc.
   ```
3. On Linux, install v4l-utils: `sudo apt-get install v4l-utils`
4. Check camera permissions (especially on macOS)

### Issue: "YOLO model not found"

**Solutions:**
1. The script auto-downloads on first run - wait for download
2. Manually download YOLOv8n-face:
   ```python
   from ultralytics import YOLO
   model = YOLO('yolov8n-face.pt')  # Auto-downloads
   ```
3. Use standard YOLOv8n (not face-specific):
   ```python
   system = FaceReIdentificationSystem(yolo_model="yolov8n.pt")
   ```

### Issue: Low FPS / Slow Performance

**Solutions:**
1. **Process fewer frames:**
   ```python
   if frame_count % 5 == 0:  # Process every 5th frame
   ```
2. **Reduce camera resolution:**
   ```python
   cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
   cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
   ```
3. **Use GPU acceleration:**
   ```bash
   pip install faiss-gpu
   ```
4. **Switch to lighter encoder:**
   ```python
   # In encode_face(), use Facenet instead of ArcFace
   embedding = DeepFace.represent(
       img_path=aligned_face,
       model_name="Facenet",  # Lighter than ArcFace
       enforce_detection=False
   )
   ```

### Issue: "No module named 'tensorflow'"

**Solution:**
```bash
pip install tensorflow
# Or for Apple Silicon Macs:
pip install tensorflow-macos tensorflow-metal
```

### Issue: Too many false matches / New visitors not recognized

**Solution:** Adjust similarity threshold:
```python
# In FaceDatabase.__init__():
similarity_threshold=0.5  # Stricter (was 0.6)
```

### Issue: Faces not detected

**Solutions:**
1. **Lower confidence threshold:**
   ```python
   confidence_threshold=0.6  # Was 0.8
   ```
2. **Improve lighting** - ensure face is well-lit
3. **Check camera focus** - move closer or adjust focus
4. **Verify YOLO model** is face-specific (yolov8n-face.pt)

## 📈 Performance Benchmarks

### Expected Performance (CPU - Intel i7 / M1)

| Configuration | FPS | Latency | Accuracy |
|--------------|-----|---------|----------|
| Process every frame | 8-12 | ~100ms | High |
| Process every 3rd frame | 20-25 | ~120ms | High |
| Process every 5th frame | 25-30 | ~150ms | Medium |

### Memory Usage

- Base system: ~500MB
- Per face signature: ~2KB
- 1000 visitors: ~502MB
- 10,000 visitors: ~520MB

## 🧪 Testing Scenarios

### Scenario 1: Single Person Entry/Exit
1. Stand in front of camera
2. First detection → "NEW VISITOR" (orange box)
3. Move away and return
4. Second detection → "RECOGNIZED" (green box)

### Scenario 2: Multiple People
1. Person A enters → Registered as Visitor 1
2. Person B enters → Registered as Visitor 2
3. Person A returns → Recognized as Visitor 1
4. Both in frame → Both recognized simultaneously

### Scenario 3: Edge Cases
- **Glasses/No glasses** - Should still match (ArcFace handles this)
- **Different angles** - Alignment helps maintain consistency
- **Lighting changes** - May affect detection confidence but encoding is robust
- **Facial hair** - Minor changes should still match within threshold

## 🔬 Technical Details

### Face Embedding Dimensionality
- **ArcFace**: 512 dimensions
- **FaceNet512**: 512 dimensions
- **FaceNet**: 128 dimensions (lighter alternative)

### Database Structure (In-Memory)

```python
{
    "visitor_id": "a3f2b1c8-1234-5678-90ab-cdef12345678",
    "first_seen": datetime(2024, 1, 15, 10, 30, 0),
    "last_seen": datetime(2024, 1, 15, 14, 20, 15),
    "encounter_count": 5,
    "signature": [0.123, -0.456, 0.789, ...]  # 512D vector
}
```

### FAISS Index Type
- **IndexFlatL2**: Exact L2 distance search
- Normalized vectors: L²/2 ≈ cosine distance
- Query time: O(N) where N = number of stored signatures
- For >100k signatures, consider IndexIVFFlat for faster search

## 📝 API Reference

### FaceReIdentificationSystem

```python
system = FaceReIdentificationSystem(
    yolo_model="yolov8n-face.pt",  # Path to YOLO model
    confidence_threshold=0.8         # Min confidence for detection
)
```

**Methods:**
- `detect_faces(frame)` → List of face detections
- `align_face(face_crop)` → Aligned face image
- `encode_face(aligned_face)` → 512D embedding vector
- `match_face(embedding)` → Match result dict
- `process_frame(frame)` → (annotated_frame, results)
- `get_statistics()` → Performance metrics dict

### FaceDatabase

```python
database = FaceDatabase(
    use_faiss=True,           # Use FAISS for search
    dimension=512,            # Embedding dimension
    similarity_threshold=0.6  # Match threshold
)
```

**Methods:**
- `add_signature(signature, visitor_id=None)` → visitor_id
- `search(signature)` → (is_match, visitor_id, distance, index)

## 🚧 Limitations & Future Improvements

### Current Limitations
1. **In-memory storage** - Data lost on restart
2. **No persistence** - No database backup
3. **Single camera** - No multi-camera support
4. **No tracking** - Doesn't track movement between frames
5. **No entry/exit logic** - Just detection and matching

### Planned Improvements
1. **SQLite/PostgreSQL** integration for persistent storage
2. **Object tracking** (DeepSORT) to maintain identity across frames
3. **Multi-camera support** with synchronized timestamps
4. **Entry/exit detection** using virtual lines or zones
5. **Web dashboard** for monitoring and analytics
6. **REST API** for integration with other systems
7. **Alert system** for unauthorized access

## 📚 References

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [MTCNN Paper](https://arxiv.org/abs/1604.02878)
- [ArcFace Paper](https://arxiv.org/abs/1801.07698)
- [FaceNet Paper](https://arxiv.org/abs/1503.03832)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [DeepFace Library](https://github.com/serengil/deepface)

## 📄 License

This is a test script for educational and demonstration purposes. Ensure compliance with privacy laws and regulations when deploying face recognition systems in production environments.

## 🤝 Contributing

This is a test script. For production deployment:
1. Implement proper data privacy measures
2. Add consent mechanisms
3. Secure database with encryption
4. Implement audit logging
5. Follow GDPR/CCPA guidelines
6. Add authentication and authorization

## ⚠️ Privacy Notice

This system processes biometric data (facial features). When deploying in production:
- Obtain informed consent from all individuals
- Implement data retention policies
- Provide opt-out mechanisms
- Encrypt stored biometric data
- Comply with local privacy regulations (GDPR, CCPA, etc.)
- Regular security audits

---

**Version:** 1.0.0  
**Last Updated:** 2024  
**Author:** Security Entry & Exit Management System Team, none of your business
