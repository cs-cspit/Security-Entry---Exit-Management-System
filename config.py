#!/usr/bin/env python3
"""
Configuration File for Face Re-Identification System
Security Entry & Exit Management System

This file contains all configurable parameters for the system.
Modify these values to tune performance and behavior without changing the main code.
"""

# ============================================================================
# MODEL CONFIGURATION — YOLO26 Multi-Model Architecture
# ============================================================================

# YOLO26 Pose Model — body detection + 17 COCO keypoints + ByteTrack
YOLO_MODEL_PATH = "yolo26n-pose.pt"  # Primary person detector (pose variant)

# YOLO26 Face Model — CUSTOM-TRAINED dedicated face detector
# Trained on face data; outputs class 0 = "face".
# Dramatically reduces false positives vs the generic COCO model (yolo26n.pt)
# which could only detect "person" class and wasn't designed for face localisation.
# Fallback chain: yolo26n-face.pt → custom_models/.../best.pt → yolo26n.pt
YOLO_FACE_MODEL_PATH = "yolo26n-face.pt"
YOLO_FACE_MODEL_FALLBACK = "custom_models/yolo26_face_results/weights/best.pt"

# YOLO26 Segmentation Model — pixel-level instance masks for clothing colour
YOLO_SEG_MODEL_PATH = "yolo26n-seg.pt"

# YOLO26 Body Detection Model — generic COCO detector for body-level re-ID
YOLO_BODY_MODEL_PATH = "yolo26n.pt"

# YOLO26 Threat Detection Model — CUSTOM-TRAINED for guns/knives (room camera)
# Not yet integrated into main pipeline; available for future use.
YOLO_THREAT_MODEL_PATH = "custom_models/yolov26n-threat_detection/weights/best.pt"

# ============================================================================
# DETECTION CONFIGURATION
# ============================================================================

DETECTION_CONFIDENCE_THRESHOLD = 0.8  # Minimum confidence score (0.0 to 1.0)
# Lower = more detections, Higher = fewer false positives
# Recommended: 0.6 (lenient) to 0.9 (strict)

# Detection Performance Settings
DETECT_EVERY_N_FRAMES = (
    1  # Process every Nth frame (1 = every frame, 3 = every 3rd frame)
)
# Higher values = faster FPS but may miss quick movements
# Recommended: 1 for accuracy, 3-5 for performance

MAX_FACES_PER_FRAME = 10  # Maximum number of faces to process per frame
# Reduces computation when multiple people are in frame


# Face Detection Confidence (for custom YOLO26-face model)
FACE_DETECTION_CONFIDENCE = (
    0.30  # Custom face model — lower is fine (trained for faces)
)
FACE_DETECTION_CONFIDENCE_GENERIC = (
    0.45  # Generic COCO fallback — higher to reduce noise
)

# Minimum head crop size before upscaling (pixels)
MIN_HEAD_CROP_SIZE = 80  # Crops smaller than this are upscaled for the face model


# ============================================================================
# ALIGNMENT CONFIGURATION
# ============================================================================

# Face Alignment Settings
USE_MTCNN_ALIGNMENT = True  # Use MTCNN for face alignment
# False = simple resize (faster but less accurate)

ALIGNED_FACE_SIZE = (160, 160)  # Size of aligned face image (width, height)
# Recommended: (160, 160) for most models

MTCNN_MIN_FACE_SIZE = 40  # Minimum face size in pixels for MTCNN detection
# Smaller = detect distant faces, but slower


# ============================================================================
# ENCODING CONFIGURATION
# ============================================================================

# Face Recognition Model
FACE_ENCODER_MODEL = (
    "ArcFace"  # Options: "ArcFace", "Facenet512", "Facenet", "VGG-Face", "OpenFace"
)
# ArcFace: Most accurate, slower (512D)
# Facenet512: Good balance (512D)
# Facenet: Faster, less accurate (128D)
# OpenFace: Fastest, least accurate (128D)

EMBEDDING_DIMENSION = 512  # Dimension of face embeddings
# 512 for ArcFace/Facenet512
# 128 for Facenet/OpenFace

SKIP_DETECTION_IN_ENCODING = True  # Skip face detection in DeepFace
# True = faster (we already detected with YOLO)
# False = safer but redundant


# ============================================================================
# MATCHING CONFIGURATION
# ============================================================================

# Similarity Matching Settings
SIMILARITY_THRESHOLD = 0.6  # Cosine distance threshold for face matching
# Lower = stricter matching (fewer false positives)
# Higher = looser matching (more false positives)
# Recommended ranges:
#   0.4-0.5: Very strict (high security)
#   0.6: Balanced (recommended)
#   0.7-0.8: Lenient (convenience)

USE_FAISS = True  # Use FAISS for efficient similarity search
# True = faster for large databases (>100 signatures)
# False = use simple cosine similarity

FAISS_INDEX_TYPE = "FlatL2"  # FAISS index type
# Options: "FlatL2" (exact search), "IVFFlat" (faster for >10k)

# Match Confidence Thresholds (based on distance)
MATCH_CONFIDENCE_HIGH = 0.4  # Distance < 0.4 = High confidence match
MATCH_CONFIDENCE_MEDIUM = 0.6  # Distance 0.4-0.6 = Medium confidence match
MATCH_CONFIDENCE_LOW = 0.8  # Distance 0.6-0.8 = Low confidence match (reject)

# ============================================================================
# RE-IDENTIFICATION WEIGHTS (used by yolo26_complete_system.py)
# ============================================================================
# These control how much each signal contributes to the final match score.
# With the custom yolo26n-face.pt model, face is the primary discriminator.

# Face recognition (InsightFace ArcFace via YOLO26-face crop)
FACE_WEIGHT = 0.70  # Face is most discriminative when available (custom model)
FACE_THRESHOLD = 0.40  # InsightFace cosine threshold (lower OK with custom model)
FACE_MISMATCH_PENALTY = 0.85  # Penalty factor when face is visible but doesn't match

# OSNet body embedding (secondary signal)
OSNET_WEIGHT = 0.65  # Strong body-level signal
MIN_OSNET_THRESHOLD = 0.45  # Hard floor — reject if OSNet alone is below this

# Appearance features (weak signals — especially for uniformed scenarios)
HAIR_WEIGHT = 0.05  # Too similar across uniformed people
SKIN_WEIGHT = 0.05  # Too similar across people
CLOTHING_WEIGHT = 0.25  # Moderate — helps when face is unavailable

# Track cache settings (ByteTrack room camera)
TRACK_CACHE_TTL = 30.0  # Seconds before a cached track→person match expires


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# In-Memory Database Settings
MAX_DATABASE_SIZE = 10000  # Maximum number of signatures to store in memory
# Set to -1 for unlimited
# Recommended: 1000-10000 for testing

AUTO_CLEANUP_THRESHOLD = 100  # Remove oldest signatures when DB exceeds this size
# Only applies if MAX_DATABASE_SIZE is exceeded

# Visitor Metadata
TRACK_ENCOUNTER_HISTORY = True  # Track first_seen, last_seen, encounter_count
STORE_FACE_THUMBNAILS = False  # Store thumbnail images (increases memory usage)


# ============================================================================
# CAMERA CONFIGURATION
# ============================================================================

# Camera Input Settings
CAMERA_INDEX = 0  # Camera device index (0 = default, 1 = external USB camera)
# Try 0, 1, 2 if camera not found

CAMERA_WIDTH = 640  # Camera capture width in pixels
CAMERA_HEIGHT = 480  # Camera capture height in pixels
CAMERA_FPS = 30  # Camera capture frame rate

# Camera Auto-Detection
AUTO_SELECT_CAMERA = (
    False  # Automatically try different camera indices if default fails
)


# ============================================================================
# VISUALIZATION CONFIGURATION
# ============================================================================

# Display Settings
SHOW_VIDEO_FEED = True  # Display real-time video feed with annotations
WINDOW_NAME = "Face Re-Identification System"

# Bounding Box Colors (BGR format)
COLOR_RECOGNIZED = (0, 255, 0)  # Green for recognized visitors
COLOR_NEW_VISITOR = (0, 165, 255)  # Orange for new visitors
COLOR_LOW_CONFIDENCE = (0, 0, 255)  # Red for low confidence detections

# Text Display
FONT_SCALE = 0.5
FONT_THICKNESS = 1
SHOW_CONFIDENCE = True
SHOW_DISTANCE = True
SHOW_VISITOR_ID = True
SHOW_FPS = True
SHOW_STATS = True

# Label Format
LABEL_RECOGNIZED = "RECOGNIZED"
LABEL_NEW_VISITOR = "NEW VISITOR"
LABEL_LOW_CONFIDENCE = "LOW CONF"


# ============================================================================
# PERFORMANCE CONFIGURATION
# ============================================================================

# Processing Optimization
USE_GPU = False  # Use GPU acceleration if available
# Requires: pip install faiss-gpu tensorflow-gpu

FRAME_BUFFER_SIZE = 3  # Number of frames to buffer for processing
# Larger = smoother but more memory

ASYNC_PROCESSING = False  # Process frames asynchronously (experimental)
# May improve FPS but requires threading

# Memory Management
ENABLE_MEMORY_OPTIMIZATION = True  # Release unused memory periodically
MEMORY_CHECK_INTERVAL = 100  # Check memory every N frames


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Console Logging
LOG_DETECTIONS = True  # Print detection messages
LOG_ALIGNMENTS = True  # Print alignment messages
LOG_ENCODINGS = True  # Print encoding messages
LOG_MATCHES = True  # Print match results
LOG_PERFORMANCE = True  # Print performance metrics

LOG_LEVEL = "INFO"  # Options: "DEBUG", "INFO", "WARNING", "ERROR"

# Debug Output
PRINT_VECTOR_SHAPES = False  # Print embedding vector dimensions
PRINT_DISTANCES = True  # Print similarity distances
PRINT_TIMING = False  # Print timing for each pipeline step


# ============================================================================
# ADVANCED CONFIGURATION
# ============================================================================

# YOLO26 Detection Advanced
# Note: YOLO26 is NMS-free (end-to-end detection), these are kept for compatibility
YOLO_IOU_THRESHOLD = 0.45  # IoU threshold (legacy; YOLO26 does not use NMS)
YOLO_MAX_DETECTIONS = 300  # Maximum detections per frame

# Custom Model Paths (absolute fallbacks)
CUSTOM_FACE_MODEL_DIR = "custom_models/yolo26_face_results"
CUSTOM_THREAT_MODEL_DIR = "custom_models/yolov26n-threat_detection"

# Face Encoding Advanced
NORMALIZE_EMBEDDINGS = True  # Normalize embeddings to unit length
# Required for cosine similarity

# Multi-Face Handling
PRIORITIZE_LARGEST_FACE = True  # Process largest face first
PRIORITIZE_CENTER_FACE = False  # Process face closest to center first
PROCESS_ALL_FACES = True  # Process all detected faces (not just primary)

# Temporal Smoothing
ENABLE_TEMPORAL_SMOOTHING = False  # Average embeddings across frames (experimental)
TEMPORAL_WINDOW_SIZE = 5  # Number of frames to average


# ============================================================================
# SAFETY & PRIVACY CONFIGURATION
# ============================================================================

# Privacy Settings
BLUR_UNRECOGNIZED_FACES = False  # Blur faces that don't match (privacy mode)
MASK_VISITOR_IDS = False  # Show only partial IDs (e.g., first 8 chars)

# Data Retention
AUTO_DELETE_OLD_SIGNATURES = False  # Delete signatures not seen recently
RETENTION_PERIOD_DAYS = 30  # Days to keep signatures (if auto-delete enabled)

# Security
REQUIRE_MINIMUM_QUALITY = False  # Reject low-quality face images
MIN_FACE_SIZE_PIXELS = 80  # Minimum face size for processing
MIN_FACE_CONFIDENCE = 0.8  # Minimum detection confidence


# ============================================================================
# TESTING & DEBUGGING CONFIGURATION
# ============================================================================

# Test Mode Settings
TEST_MODE = False  # Enable test mode with verbose output
SAVE_TEST_IMAGES = False  # Save detected faces to disk for analysis
TEST_IMAGE_DIR = "./test_faces/"

# Benchmark Mode
BENCHMARK_MODE = False  # Run in benchmark mode (no video display)
BENCHMARK_FRAMES = 1000  # Number of frames to process in benchmark

# Mock Data
USE_MOCK_DATABASE = False  # Pre-populate database with test signatures
MOCK_DATABASE_SIZE = 50  # Number of mock signatures to generate


# ============================================================================
# EXPORT CONFIGURATION
# ============================================================================

# Data Export Settings
EXPORT_DATABASE_ON_EXIT = False  # Save database to file on exit
EXPORT_FORMAT = "json"  # Options: "json", "csv", "pickle"
EXPORT_PATH = "./database_export.json"

# Statistics Export
SAVE_STATISTICS = False
STATISTICS_PATH = "./statistics.json"


# ============================================================================
# KEYBOARD SHORTCUTS
# ============================================================================

# Interactive Controls
KEY_QUIT = ord("q")  # Quit application
KEY_STATS = ord("s")  # Show statistics
KEY_RESET = ord("r")  # Reset database
KEY_SAVE = ord("w")  # Save database
KEY_PAUSE = ord("p")  # Pause/resume processing
KEY_SCREENSHOT = ord("c")  # Capture screenshot


# ============================================================================
# VALIDATION
# ============================================================================


def validate_config():
    """
    Validate configuration parameters.
    Raises ValueError if configuration is invalid.
    """
    import os

    if not 0.0 <= DETECTION_CONFIDENCE_THRESHOLD <= 1.0:
        raise ValueError("DETECTION_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")

    if not 0.0 <= SIMILARITY_THRESHOLD <= 2.0:
        raise ValueError("SIMILARITY_THRESHOLD must be between 0.0 and 2.0")

    if DETECT_EVERY_N_FRAMES < 1:
        raise ValueError("DETECT_EVERY_N_FRAMES must be at least 1")

    if EMBEDDING_DIMENSION not in [128, 512, 2048, 4096]:
        print(f"WARNING: Unusual EMBEDDING_DIMENSION: {EMBEDDING_DIMENSION}")

    if FACE_ENCODER_MODEL not in [
        "ArcFace",
        "Facenet512",
        "Facenet",
        "VGG-Face",
        "OpenFace",
        "Dlib",
    ]:
        print(f"WARNING: Unknown FACE_ENCODER_MODEL: {FACE_ENCODER_MODEL}")

    # Validate model files
    _models = {
        "Pose model": YOLO_MODEL_PATH,
        "Face model (primary)": YOLO_FACE_MODEL_PATH,
        "Face model (fallback)": YOLO_FACE_MODEL_FALLBACK,
        "Seg model": YOLO_SEG_MODEL_PATH,
        "Body model": YOLO_BODY_MODEL_PATH,
    }
    for label, path in _models.items():
        if os.path.exists(path):
            print(f"  ✓ {label}: {path}")
        else:
            print(f"  ⚠ {label}: {path} (NOT FOUND)")

    # Validate re-ID weights sum reasonably
    _body_only_sum = OSNET_WEIGHT + HAIR_WEIGHT + SKIN_WEIGHT + CLOTHING_WEIGHT
    if abs(_body_only_sum - 1.0) > 0.05:
        print(
            f"  ⚠ Body-only weights sum to {_body_only_sum:.2f} (expected ~1.0): "
            f"osnet={OSNET_WEIGHT} + hair={HAIR_WEIGHT} + skin={SKIN_WEIGHT} + clothing={CLOTHING_WEIGHT}"
        )

    print("✓ Configuration validated successfully")


if __name__ == "__main__":
    # Validate configuration when run directly
    validate_config()
    print("\nCurrent Configuration:")
    print(f"  Detection Threshold: {DETECTION_CONFIDENCE_THRESHOLD}")
    print(f"  Similarity Threshold: {SIMILARITY_THRESHOLD}")
    print(f"  Face Encoder: {FACE_ENCODER_MODEL}")
    print(f"  Embedding Dimension: {EMBEDDING_DIMENSION}")
    print(f"  Use FAISS: {USE_FAISS}")
    print(f"  Camera Index: {CAMERA_INDEX}")
    print(f"  Camera Resolution: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
    print(f"  Process Every N Frames: {DETECT_EVERY_N_FRAMES}")
    print("\nYOLO26 Model Suite:")
    print(f"  Pose:   {YOLO_MODEL_PATH}")
    print(f"  Face:   {YOLO_FACE_MODEL_PATH} (custom-trained)")
    print(f"  Seg:    {YOLO_SEG_MODEL_PATH}")
    print(f"  Body:   {YOLO_BODY_MODEL_PATH}")
    print(f"  Threat: {YOLO_THREAT_MODEL_PATH} (room camera, future)")
    print("\nRe-ID Weights:")
    print(f"  Face weight:     {FACE_WEIGHT} (threshold: {FACE_THRESHOLD})")
    print(f"  OSNet weight:    {OSNET_WEIGHT} (min threshold: {MIN_OSNET_THRESHOLD})")
    print(f"  Hair weight:     {HAIR_WEIGHT}")
    print(f"  Skin weight:     {SKIN_WEIGHT}")
    print(f"  Clothing weight: {CLOTHING_WEIGHT}")
