#!/usr/bin/env python3
"""
YOLO26 Complete Three-Camera Security System
============================================
Three-camera security system with full YOLO26 model suite for robust
person detection, face identification, body segmentation, and pose tracking.

Model Roles:
- YOLO26-pose (yolo26n-pose.pt): Body detection + 17 keypoints + ByteTrack.
- YOLO26-face (yolo26n-face.pt): Custom-trained face detection.
- YOLO26-seg (yolo26n-seg.pt): Segmentation masks for color extraction.
- YOLO26-threat (best.pt): Weapon detection.
- YOLO26-clothes (best.pt): Custom clothes detection for re-ID.
"""

import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from alert_manager import AlertLevel, AlertManager, AlertType
    from cross_camera_adapter import CrossCameraAdapter
    from detectors.yolo26_body_detector import YOLO26BodyDetector
    from enhanced_database import EnhancedDatabase
    from features.body_only_analyzer import BodyOnlyAnalyzer
    from features.face_recognition import FaceRecognitionExtractor
    from features.osnet_extractor import OSNetExtractor
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

try:
    from ultralytics import YOLO as _YOLO26
    _YOLO26_AVAILABLE = True
except ImportError:
    _YOLO26_AVAILABLE = False
    _YOLO26 = None

try:
    from tracking.multi_tracker import MultiPersonTracker, TrackedPerson
    _TRACKER_AVAILABLE = True
except ImportError:
    _TRACKER_AVAILABLE = False

try:
    from behaviors.loitering_detector import LoiteringDetector
    from behaviors.tailgating_detector import TailgatingDetector
    _BEHAVIORS_AVAILABLE = True
except ImportError:
    _BEHAVIORS_AVAILABLE = False

try:
    from api.websocket_bridge import SecurityAPIBridge
    _API_BRIDGE_AVAILABLE = True
except ImportError:
    _API_BRIDGE_AVAILABLE = False
    SecurityAPIBridge = None


class YOLO26CompleteSystem:
    def __init__(
        self,
        entry_idx="obs",
        room_idx=2,
        exit_idx=1,
        enable_api: bool = True,
        api_port: int = 8000,
    ):
        """Initialize the complete system."""
        print("\n" + "=" * 70)
        print("  YOLO26 COMPLETE THREE-CAMERA SECURITY SYSTEM")
        print("=" * 70)

        self.running = True
        self.entry_idx = entry_idx
        self.room_idx = room_idx
        self.exit_idx = exit_idx

        # System settings
        self.debug_mode = False
        self.auto_register = True
        self.pixels_per_meter = 100.0

        import torch as _torch
        _dev = "cuda" if _torch.cuda.is_available() else "mps" if _torch.backends.mps.is_available() else "cpu"

        # ── Model 1: YOLO26-pose (Body + Pose) ───────────────────────────────
        print("🔧 Loading YOLO26-pose model...")
        self.detector = YOLO26BodyDetector(model_name="yolo26n-pose.pt", device=_dev)

        # ── Model 2: YOLO26-face (Custom Face Detection) ─────────────────────
        self.face_detect_model = None
        if _YOLO26_AVAILABLE:
            _face_path = "yolo26n-face.pt"
            if os.path.exists(_face_path):
                print(f"🔧 Loading YOLO26-face model: {_face_path}...")
                self.face_detect_model = _YOLO26(_face_path)
                self.face_detect_model.to(_dev)
                self._face_model_is_custom = True
            else:
                self._face_model_is_custom = False

        # ── Model 3: YOLO26-seg (Segmentation) ───────────────────────────────
        self.seg_model = None
        if _YOLO26_AVAILABLE:
            if os.path.exists("yolo26n-seg.pt"):
                print("🔧 Loading YOLO26-seg model...")
                self.seg_model = _YOLO26("yolo26n-seg.pt")
                self.seg_model.to(_dev)

        # ── Model 4: YOLO26-threat (Weapon Detection) ────────────────────────
        self.threat_model = None
        if _YOLO26_AVAILABLE:
            _threat_path = os.path.join("custom_models", "yolov26n-threat_detection", "weights", "best.pt")
            if os.path.exists(_threat_path):
                try:
                    print(f"🔧 Loading YOLO26-threat model (weapons): {_threat_path}...")
                    self.threat_model = _YOLO26(_threat_path)
                    self.threat_model.to(_dev)
                    print(f"✅ YOLO26-threat model loaded on {_dev}")
                except Exception as _e:
                    print(f"⚠️  YOLO26-threat model unavailable: {_e}")

        # ── Model 5: YOLO26-clothes (Custom Clothes Detection) ───────────────
        self.clothes_model = None
        if _YOLO26_AVAILABLE:
            _clothes_path = os.path.join("custom_models", "yolov26n-clothes_detection", "weights", "best.pt")
            if os.path.exists(_clothes_path):
                try:
                    print(f"🔧 Loading YOLO26-clothes model: {_clothes_path}...")
                    self.clothes_model = _YOLO26(_clothes_path)
                    self.clothes_model.to(_dev)
                    print(f"✅ YOLO26-clothes model loaded on {_dev}")
                except Exception as _e:
                    print(f"⚠️  YOLO26-clothes model unavailable: {_e}")

        # Multi-person tracker
        if _TRACKER_AVAILABLE:
            self._room_detector = YOLO26BodyDetector(model_name="yolo26n-pose.pt", device=_dev)
            self.multi_tracker = MultiPersonTracker(detector=self._room_detector)
        else:
            self.multi_tracker = None

        # Feature extractors
        self.osnet = OSNetExtractor(device=_dev)
        # self.body_analyzer = BodyOnlyAnalyzer()  # Replaced by clothes_model for color/features
        self.face_recognizer = FaceRecognitionExtractor(model_name="buffalo_sc")
        self.use_face_recognition = self.face_recognizer.is_initialized()
        self.cross_camera = CrossCameraAdapter()
        self.database = EnhancedDatabase("data/yolo26_complete_system.db")

        # API Bridge
        self.api_bridge = None
        if enable_api and _API_BRIDGE_AVAILABLE:
            self.api_bridge = SecurityAPIBridge(system_ref=self, port=api_port)
            self.api_bridge.start()

        # Alert Manager
        self.alert_manager = AlertManager(api_bridge=self.api_bridge)

        # Registry & Stats
        self.registered_people = {}
        self.active_sessions = {}
        self.person_status = {}
        self.person_counter = 0
        self.trajectories = defaultdict(list)
        self.velocity_data = defaultdict(list)
        self.stats = {
            "registered": 0, "inside": 0, "exited": 0, "unauthorized": 0,
            "total_detections": 0, "entry_detections": 0, "room_detections": 0, "exit_detections": 0,
        }

        # Track management
        self._track_match_cache = {}
        self._track_cache_ttl = 30.0
        self._face_confirmed_tracks = set()
        self._unauthorized_track_ids = set()

        # Behavior detectors
        if _BEHAVIORS_AVAILABLE:
            self.loitering = LoiteringDetector()
            self.tailgating = TailgatingDetector()
        else:
            self.loitering = self.tailgating = None

        self._panic_person_threshold = 3
        self._panic_velocity_threshold = 3.0

        # Entry cooldown
        self.entry_cooldown = {}
        self.entry_cooldown_seconds = 10.0
        self.last_entry_person_bbox = None
        self.entry_area_threshold = 0.2

        # Matching Weights & Thresholds
        self.osnet_weight = 0.50
        self.clothes_weight = 0.25  # From YOLO26-clothes
        self.face_weight = 0.80     # Heavily weighted
        
        self.face_threshold = 0.35  # More lenient for re-ID
        self.min_osnet_threshold = 0.40
        self.similarity_threshold = 0.35  # MANAGED BY ADAPTER - fallback
        self.exit_threshold = 0.40
        self.exit_confidence_gap = 0.10

        self._init_cameras()
        signal.signal(signal.SIGINT, self.signal_handler)
    @staticmethod
    def _parse_camera_source(source):
        """Allow camera source to be either integer index or string stream source."""
        if isinstance(source, int):
            return source
        if source is None:
            return 0
        source_str = str(source).strip()
        if source_str.lstrip("+-").isdigit():
            return int(source_str)
        return source_str

    def _open_camera_capture(self, source, role, reserved_indices=None):
        """Open camera source, with special handling for OBS/DroidCam entry camera."""
        reserved_indices = {
            idx for idx in (reserved_indices or []) if isinstance(idx, int) and idx >= 0
        }
        normalized_source = self._parse_camera_source(source)

        obs_aliases = {
            "obs",
            "obs_virtual",
            "obs-virtual",
            "virtualcam",
            "virtual_cam",
            "droidcam",
            "phone",
        }
        if (
            role == "entry"
            and isinstance(normalized_source, str)
            and normalized_source.lower() in obs_aliases
        ):
            print("📹 Entry camera configured for OBS/DroidCam source.")

            candidate_indices = []
            obs_candidates_env = os.getenv("YOLO26_OBS_ENTRY_CANDIDATES", "3,2,1,0,4,5")
            for token in obs_candidates_env.split(","):
                token = token.strip()
                if token.lstrip("+-").isdigit():
                    idx = int(token)
                    if (
                        idx >= 0
                        and idx not in reserved_indices
                        and idx not in candidate_indices
                    ):
                        candidate_indices.append(idx)
            for idx in range(8):
                if idx not in reserved_indices and idx not in candidate_indices:
                    candidate_indices.append(idx)

            for idx in candidate_indices:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    ok, _ = cap.read()
                    if ok:
                        print(f"✅ Entry camera opened from OBS candidate index {idx}")
                        return cap, idx
                cap.release()

            droidcam_url = os.getenv("YOLO26_DROIDCAM_URL", "").strip()
            if droidcam_url:
                cap = cv2.VideoCapture(droidcam_url)
                if cap.isOpened():
                    print(f"✅ Entry camera opened from YOLO26_DROIDCAM_URL: {droidcam_url}")
                    return cap, droidcam_url
                cap.release()

            fallback_idx = 0
            while fallback_idx in reserved_indices:
                fallback_idx += 1
            print(
                f"⚠️  OBS/DroidCam source not auto-detected; falling back to camera index {fallback_idx}"
            )
            return cv2.VideoCapture(fallback_idx), fallback_idx

        return cv2.VideoCapture(normalized_source), normalized_source

    def _init_cameras(self):
        self.FRAME_WIDTH = 640
        self.FRAME_HEIGHT = 480
        room_source = self._parse_camera_source(self.room_idx)
        exit_source = self._parse_camera_source(self.exit_idx)
        reserved_for_entry = [
            src for src in (room_source, exit_source) if isinstance(src, int) and src >= 0
        ]

        self.cap_entry, self.entry_idx = self._open_camera_capture(
            self.entry_idx, "entry", reserved_indices=reserved_for_entry
        )
        self.cap_room, self.room_idx = self._open_camera_capture(room_source, "room")
        self.cap_exit, self.exit_idx = self._open_camera_capture(exit_source, "exit")

        for name, cap in [
            ("entry", self.cap_entry),
            ("room", self.cap_room),
            ("exit", self.cap_exit),
        ]:
            if cap is None or not cap.isOpened():
                print(
                    f"⚠️  Could not open {name} camera source: {getattr(self, f'{name}_idx')}"
                )
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

    def signal_handler(self, sig, frame):
        self.running = False

    def _extract_clothes_features(self, frame, body_bbox):
        """Use custom YOLO26-clothes model to get precise clothing features."""
        if self.clothes_model is None:
            return {}
        
        bx, by, bw, bh = body_bbox
        x1, y1 = max(0, bx), max(0, by)
        x2, y2 = min(frame.shape[1], bx + bw), min(frame.shape[0], by + bh)
        crop = frame[y1:y2, x1:x2]
        
        if crop.size == 0: return {}
        
        results = self.clothes_model(crop, verbose=False)
        features = []
        for r in results:
            for box in r.boxes:
                features.append({
                    "cls": int(box.cls[0]),
                    "conf": float(box.conf[0]),
                    "name": self.clothes_model.names[int(box.cls[0])]
                })
        return {"clothes": features}

    def _detect_face_on_head_crop(self, frame, detection):
        if not self.use_face_recognition: return None
        body_bbox = detection["body_bbox"]
        bx, by, bw, bh = body_bbox
        keypoints = detection.get("keypoints")
        head_crop = None
        
        # Primary: Use Pose Keypoints for head crop
        if keypoints is not None:
            # 0=nose, 1=l_eye, 2=r_eye, 3=l_ear, 4=r_ear
            pts = [keypoints[i] for i in range(5) if keypoints[i][2] > 0.2]
            if len(pts) >= 2:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                hx1, hy1 = max(0, int(min(xs) - 40)), max(0, int(min(ys) - 40))
                hx2, hy2 = min(frame.shape[1], int(max(xs) + 40)), min(frame.shape[0], int(max(ys) + 60))
                head_crop = frame[hy1:hy2, hx1:hx2]
        
        # Fallback: Top of body box
        if head_crop is None or head_crop.size == 0:
            head_crop = frame[max(0, by):min(frame.shape[0], by + int(bh * 0.25)), max(0, bx):min(frame.shape[1], bx + bw)]
            
        if head_crop is None or head_crop.size == 0: return None
        
        # Refine with YOLO26-face custom model
        if self.face_detect_model:
            res = self.face_detect_model(head_crop, verbose=False, conf=0.3)
            if res and len(res[0].boxes) > 0:
                fx1, fy1, fx2, fy2 = map(int, res[0].boxes.xyxy[0])
                # Add some padding
                pad = 10
                fx1, fy1 = max(0, fx1-pad), max(0, fy1-pad)
                fx2, fy2 = min(head_crop.shape[1], fx2+pad), min(head_crop.shape[0], fy2+pad)
                return head_crop[fy1:fy2, fx1:fx2]
        
        return head_crop

    def register_person(self, person_id, frame, detection):
        try:
            body_bbox = detection["body_bbox"]
            osnet_features = self.osnet.extract_features(frame, body_bbox)
            if osnet_features is None: return False
            
            clothes_features = self._extract_clothes_features(frame, body_bbox)
            
            face_embedding = None
            if self.use_face_recognition:
                face_crop = self._detect_face_on_head_crop(frame, detection)
                if face_crop is not None:
                    face_embedding = self.face_recognizer.extract_face_embedding(face_crop, (0, 0, face_crop.shape[1], face_crop.shape[0]))
            
            self.registered_people[person_id] = {
                "osnet": osnet_features, 
                "clothes": clothes_features,
                "face_embedding": face_embedding,
                "body_bbox": body_bbox, 
                "registered_at": datetime.now(),
            }
            return True
        except Exception as e:
            print(f"❌ Reg error: {e}")
            return False

    def match_person(self, frame, detection, target_camera="room"):
        if not self.registered_people: return None, 0.0, {}
        body_bbox = detection["body_bbox"]
        
        osnet_query = self.osnet.extract_features(frame, body_bbox)
        if osnet_query is None: return None, 0.0, {}
        
        clothes_query = self._extract_clothes_features(frame, body_bbox)
        
        face_query = None
        if self.use_face_recognition:
            face_crop = self._detect_face_on_head_crop(frame, detection)
            if face_crop is not None:
                face_query = self.face_recognizer.extract_face_embedding(face_crop, (0, 0, face_crop.shape[1], face_crop.shape[0]))
        
        best_id, best_score, second_best_score = None, 0.0, 0.0
        all_scores = {}
        
        for pid, pdata in self.registered_people.items():
            # 1. OSNet Score
            osnet_sim = float(np.dot(osnet_query, pdata["osnet"]) / (np.linalg.norm(osnet_query) * np.linalg.norm(pdata["osnet"]) + 1e-6))
            
            # 2. Face Score
            face_sim = 0.0
            if face_query is not None and pdata["face_embedding"] is not None:
                face_sim = self.face_recognizer.compare_faces(face_query, pdata["face_embedding"])
            
            # 3. Clothes Score (Intersection over Union of class IDs)
            clothes_sim = 0.0
            q_cl = set([c['cls'] for c in clothes_query.get('clothes', [])])
            r_cl = set([c['cls'] for c in pdata.get('clothes', {}).get('clothes', [])])
            if q_cl and r_cl:
                clothes_sim = len(q_cl & r_cl) / len(q_cl | r_cl)

            # Combined Score
            if face_sim > self.face_threshold:
                # If face matches, trust it!
                score = face_sim * 0.8 + osnet_sim * 0.2
            else:
                # Fallback to body + clothes
                score = osnet_sim * 0.7 + clothes_sim * 0.3
            
            # Adapter adjustment
            score = self.cross_camera.adjust_similarity_score(score, "entry", target_camera, osnet_query, pdata["osnet"])
            
            all_scores[pid] = {"total": score, "face": face_sim, "osnet": osnet_sim, "clothes": clothes_sim}
            if score > best_score: second_best_score, best_score, best_id = best_score, score, pid
            elif score > second_best_score: second_best_score = score

        # Using adapter for final decision
        should_match, reason = self.cross_camera.should_match(best_score, second_best_score, len(self.registered_people), "entry", target_camera)
        
        if not should_match and best_score < 0.3: # Hard minimum
            return None, best_score, {"all_scores": all_scores, "reason": "score_too_low"}
            
        return best_id, best_score, {"all_scores": all_scores, "face_confirmed": face_sim >= self.face_threshold}

    def _calculate_velocity(self, person_id):
        traj = self.trajectories.get(person_id, [])
        if len(traj) < 2: return 0.0
        (x1, y1, t1), (x2, y2, t2) = traj[-2], traj[-1]
        dt = (t2 - t1).total_seconds()
        if dt < 0.001: return 0.0
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2) / (self.pixels_per_meter * dt)

    def _bbox_overlap(self, b1, b2):
        x1, y1, w1, h1 = b1
        x2, y2, w2, h2 = b2
        xi1, yi1, xi2, yi2 = max(x1, x2), max(y1, y2), min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
        if xi2 <= xi1 or yi2 <= yi1: return 0.0
        inter = (xi2 - xi1) * (yi2 - yi1)
        return inter / (w1 * h1 + w2 * h2 - inter)

    def _draw_skeletons(self, frame, keypoints):
        """Draw 17-point pose skeleton."""
        if keypoints is None: return
        skeleton = [
            (0,1), (0,2), (1,3), (2,4), (5,6), (5,7), (7,9), (6,8), (8,10),
            (5,11), (6,12), (11,12), (11,13), (13,15), (12,14), (14,16)
        ]
        for s1, s2 in skeleton:
            x1, y1, c1 = keypoints[s1]
            x2, y2, c2 = keypoints[s2]
            if c1 > 0.3 and c2 > 0.3:
                cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)
        for x, y, c in keypoints:
            if c > 0.3:
                cv2.circle(frame, (int(x), int(y)), 4, (0, 255, 0), -1)

    def process_entry_camera(self, frame):
        display = frame.copy()
        current_time = datetime.now()
        detections = self.detector.detect(frame)
        self.stats["entry_detections"] += len(detections)
        for d in detections:
            bbox = d["body_bbox"]
            bx, by, bw, bh = bbox
            self._draw_skeletons(display, d.get("keypoints"))
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), (0, 255, 255), 2)
            
            skip = False
            p_id, _, _ = self.match_person(frame, d, "entry")
            if p_id and p_id in self.active_sessions:
                skip = True
                cv2.putText(display, f"ALREADY INSIDE ({p_id})", (bx, by - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            if not skip and self.last_entry_person_bbox:
                overlap = self._bbox_overlap(bbox, self.last_entry_person_bbox)
                last_reg = self.entry_cooldown.get("last_registration", current_time - timedelta(seconds=100))
                if overlap > self.entry_area_threshold and (current_time - last_reg).total_seconds() < self.entry_cooldown_seconds:
                    skip = True
                    cv2.putText(display, "REGISTERED", (bx, by - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            if self.auto_register and not skip:
                self.person_counter += 1
                pid = f"P{self.person_counter:03d}"
                if self.register_person(pid, frame, d):
                    self.entry_cooldown["last_registration"] = current_time
                    self.last_entry_person_bbox = bbox
                    self.stats["registered"] += 1
                    self.stats["inside"] += 1
                    self.active_sessions[pid] = {"entry_time": current_time}
                    if self.api_bridge: self.api_bridge.push_event("entry", {"person_id": pid, "timestamp": current_time.isoformat()})
                    self.database.add_person(pid)
                    self.database.record_entry(pid)
        if self.api_bridge: self.api_bridge.push_frame("entry", display)
        return display

    def process_room_camera(self, frame):
        frame_p = self.cross_camera.preprocess_frame(frame, "room")
        display = frame_p.copy()
        current_time = datetime.now()
        
        if self.multi_tracker:
            raw = self.multi_tracker.update(frame_p)
            detections = [tp.to_detection_dict() for tp in raw]
            track_ids = [tp.track_id for tp in raw]
        else:
            detections = self.detector.detect(frame_p)
            track_ids = [None] * len(detections)
        
        self.stats["room_detections"] += len(detections)
        self._release_lost_tracks()
        auth_cnt, unauth_cnt = 0, 0

        # Weapon detection
        weapon_detected = False
        if self.threat_model:
            res = self.threat_model(frame, verbose=False)
            for r in res:
                for b in r.boxes:
                    if b.conf[0] > 0.45:
                        weapon_detected = True
                        lbl = self.threat_model.names[int(b.cls[0])]
                        wx1, wy1, wx2, wy2 = map(int, b.xyxy[0])
                        cv2.rectangle(display, (wx1, wy1), (wx2, wy2), (0, 0, 255), 3)
                        cv2.putText(display, f"WEAPON: {lbl.upper()}", (wx1, wy1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                        self.alert_manager.alert_weapon(lbl, float(b.conf[0]))

        for d, tid in zip(detections, track_ids):
            bbox = d["body_bbox"]
            bx, by, bw, bh = bbox
            cx, cy = bx + bw//2, by + bh//2
            self._draw_skeletons(display, d.get("keypoints"))
            
            pid, sim, debug = None, 0.0, {}
            cached = self._track_match_cache.get(tid) if tid else None
            if cached and (time.time() - cached[2]) < self._track_cache_ttl:
                pid, sim = cached[0], cached[1]
            else:
                pid, sim, debug = self.match_person(frame_p, d, "room")
                if tid: self._track_match_cache[tid] = (pid, sim, time.time())
            
            tkey = f"t{tid}" if tid else (pid or f"u{cx//60}")
            self.trajectories[tkey].append((cx, cy, current_time))
            if len(self.trajectories[tkey]) > 60: self.trajectories[tkey].pop(0)
            vel = self._calculate_velocity(tkey)
            
            if pid and pid in self.active_sessions:
                auth_cnt += 1
                color, lbl = (0, 255, 0), f"{pid} ({sim:.2f})"
                if vel > 2.0: self.alert_manager.alert_running(pid, vel)
            else:
                unauth_cnt += 1
                ukey = tid if tid else f"u{cx//60}_{cy//60}"
                if ukey not in self._unauthorized_track_ids:
                    self.stats["unauthorized"] += 1
                    self._unauthorized_track_ids.add(ukey)
                color, lbl = (0, 0, 255), f"UNAUTHORIZED ({sim:.2f})"
                self.alert_manager.alert_unauthorized(f"unauth_{ukey}")
            
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), color, 2)
            cv2.putText(display, lbl, (bx, by-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        if weapon_detected:
            h, w = display.shape[:2]
            cv2.rectangle(display, (0, 110), (w, 150), (0, 0, 200), -1)
            cv2.putText(display, "⚠️ WEAPON DETECTED ⚠️", (w//2-150, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

        h, w = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w, 80), (0, 0, 0), -1)
        cv2.putText(display, f"Inside: {len(self.active_sessions)} | Auth: {auth_cnt} | Unauth: {unauth_cnt}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        if self.api_bridge: self.api_bridge.push_frame("room", display)
        return display

    def process_exit_camera(self, frame):
        display = frame.copy()
        current_time = datetime.now()
        detections = self.detector.detect(frame)
        self.stats["exit_detections"] += len(detections)
        for d in detections:
            bbox = d["body_bbox"]
            bx, by, bw, bh = bbox
            self._draw_skeletons(display, d.get("keypoints"))
            pid, sim, _ = self.match_person(frame, d, "exit")
            if pid and pid in self.active_sessions:
                self.stats["inside"] -= 1
                self.stats["exited"] += 1
                del self.active_sessions[pid]
                self.database.record_exit(pid)
                if self.api_bridge: self.api_bridge.push_event("exit", {"person_id": pid})
                cv2.rectangle(display, (bx, by), (bx+bw, by+bh), (0, 255, 0), 2)
                cv2.putText(display, f"EXIT: {pid}", (bx, by-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                cv2.rectangle(display, (bx, by), (bx+bw, by+bh), (0, 0, 255), 2)
                cv2.putText(display, "UNKNOWN", (bx, by-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        if self.api_bridge: self.api_bridge.push_frame("exit", display)
        return display

    def _release_lost_tracks(self):
        if not self.multi_tracker: return
        active = set(self.multi_tracker.diagnostics().get("active_track_ids", []))
        stale = [tid for tid in self._track_match_cache if tid not in active]
        for tid in stale:
            if tid in self._track_match_cache: del self._track_match_cache[tid]
            self._face_confirmed_tracks.discard(tid)

    def _draw_trajectory(self, frame, pid):
        pts = self.trajectories.get(pid, [])
        for i in range(1, len(pts)):
            cv2.line(frame, (int(pts[i-1][0]), int(pts[i-1][1])), (int(pts[i][0]), int(pts[i][1])), (0, 255, 255), 2)

    def run(self):
        while self.running:
            re, fe = self.cap_entry.read()
            rr, fr = self.cap_room.read()
            rx, fx = self.cap_exit.read()
            if not (re and rr and rx): break
            de, dr, dx = self.process_entry_camera(fe), self.process_room_camera(fr), self.process_exit_camera(fx)
            cv2.imshow("Entry", de); cv2.imshow("Room", dr); cv2.imshow("Exit", dx)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
        self.cleanup()

    def cleanup(self):
        self.database.close()
        if self.api_bridge: self.api_bridge.stop()
        self.cap_entry.release(); self.cap_room.release(); self.cap_exit.release()
        cv2.destroyAllWindows()

def main():
    import argparse

    def _parse_cli_camera_source(value):
        value = str(value).strip()
        if value.lstrip("+-").isdigit():
            return int(value)
        return value
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--entry",
        type=str,
        default="obs",
        help="Entry camera source: index, URL, or 'obs' for OBS/DroidCam virtual camera",
    )
    parser.add_argument("--room", type=str, default="2")
    parser.add_argument("--exit", type=str, default="1")
    args = parser.parse_args()
    system = YOLO26CompleteSystem(
        _parse_cli_camera_source(args.entry),
        _parse_cli_camera_source(args.room),
        _parse_cli_camera_source(args.exit),
    )
    system.run()

if __name__ == "__main__":
    main()
