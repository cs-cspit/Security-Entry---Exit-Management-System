#!/usr/bin/env python3
"""
WebSocket & REST API Bridge (Phase 7)
=======================================
FastAPI-based backend bridge that runs as a background thread alongside the
main YOLO26 security system.  The frontend connects here for:

  REST endpoints
  ──────────────
  GET  /api/status          — live system state snapshot
  GET  /api/people          — registered persons list
  GET  /api/alerts          — recent alerts (paginated)
  GET  /api/stats           — cumulative statistics
  GET  /api/sessions        — active sessions
  GET  /api/tracker         — multi-tracker diagnostics
  GET  /api/health          — liveness probe

  WebSocket
  ─────────
  WS   /ws/events           — real-time event stream (JSON frames)

  Camera streams (MJPEG)
  ──────────────────────
  GET  /stream/entry        — entry gate MJPEG stream
  GET  /stream/room         — room monitor MJPEG stream
  GET  /stream/exit         — exit gate MJPEG stream

Event schema (WebSocket JSON frame)
─────────────────────────────────────
{
  "event":     "alert" | "entry" | "exit" | "detection" | "stats_update" | "ping",
  "timestamp": "2026-01-14T12:34:56.789",
  "data":      { ... event-specific payload ... }
}

Usage
─────
From the main system:

    bridge = SecurityAPIBridge(system_ref=self)
    bridge.start()                    # starts FastAPI in a daemon thread
    ...
    bridge.push_event("alert", {...}) # non-blocking event push
    bridge.push_frame("entry", frame) # push latest camera frame (BGR ndarray)
    bridge.stop()

Dependencies
────────────
    pip install fastapi uvicorn websockets

These are NOT installed by default — the bridge is optional.  The main
system catches ImportError and disables the bridge gracefully.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger("api_bridge")

# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------
try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response, StreamingResponse

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    logger.warning(
        "FastAPI / uvicorn not installed.  API bridge disabled.\n"
        "  pip install fastapi uvicorn"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_serial(obj: Any) -> Any:
    """JSON serializer that handles datetime and numpy types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not JSON serializable")


def _dumps(data: Any) -> str:
    return json.dumps(data, default=_json_serial)


# ---------------------------------------------------------------------------
# Connection manager (WebSocket)
# ---------------------------------------------------------------------------


class _ConnectionManager:
    """Manages a set of active WebSocket connections."""

    def __init__(self, history_size: int = 100):
        self._connections: Set[WebSocket] = set()
        self._history: Deque[str] = deque(maxlen=history_size)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        # Replay recent history so new clients catch up
        for msg in list(self._history):
            try:
                await ws.send_text(msg)
            except Exception:
                break

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, message: str):
        self._history.append(message)
        dead: List[WebSocket] = []
        async with self._lock:
            connections = list(self._connections)
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        async with self._lock:
            for ws in dead:
                self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# ---------------------------------------------------------------------------
# Frame store (MJPEG streams)
# ---------------------------------------------------------------------------


class _FrameStore:
    """Thread-safe store for the latest JPEG-encoded camera frame."""

    def __init__(self):
        self._frames: Dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, camera: str, frame_bgr: np.ndarray):
        try:
            import cv2

            ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._lock:
                    self._frames[camera] = bytes(buf)
        except Exception as exc:
            logger.debug(f"Frame encode error for {camera}: {exc}")

    def get(self, camera: str) -> Optional[bytes]:
        with self._lock:
            return self._frames.get(camera)


# ---------------------------------------------------------------------------
# Main bridge class
# ---------------------------------------------------------------------------


class SecurityAPIBridge:
    """
    Optional FastAPI + WebSocket bridge.  Runs in a background daemon thread.

    Parameters
    ----------
    system_ref : YOLO26CompleteSystem or None
        Reference to the main system instance.  Used by REST endpoints to
        read live state.  Can be set later via ``bridge.system = <ref>``.
    host : str
        Bind address.  Default "0.0.0.0".
    port : int
        HTTP / WebSocket port.  Default 8000.
    cors_origins : list[str]
        Allowed CORS origins for the frontend dev server.
    history_size : int
        Number of recent WebSocket events to replay to new connections.
    """

    def __init__(
        self,
        system_ref=None,
        host: str = "0.0.0.0",
        port: int = 8000,
        cors_origins: Optional[List[str]] = None,
        history_size: int = 100,
    ):
        self.system = system_ref
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
        ]
        self._available = _FASTAPI_AVAILABLE

        # Event queue: main thread → async loop
        self._event_queue: queue.Queue = queue.Queue(maxsize=500)

        # Frame store for MJPEG streams
        self._frame_store = _FrameStore()

        # Internal asyncio event loop (created in background thread)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        if self._available:
            self._app = self._build_app()
            self._ws_manager = _ConnectionManager(history_size=history_size)
        else:
            self._app = None
            self._ws_manager = None

    # ------------------------------------------------------------------
    # Public API (called from main thread)
    # ------------------------------------------------------------------

    def start(self):
        """Start the FastAPI server in a daemon background thread."""
        if not self._available:
            logger.warning("API bridge skipped — fastapi/uvicorn not installed.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="api-bridge",
        )
        self._thread.start()
        logger.info(f"🌐 API bridge starting on http://{self.host}:{self.port}")

    def stop(self):
        """Signal the server to stop."""
        self._running = False
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def push_event(self, event_type: str, data: Dict[str, Any]):
        """
        Push an event to all WebSocket clients.
        Non-blocking: if the queue is full, the event is silently dropped.

        Parameters
        ----------
        event_type : str
            e.g. "alert", "entry", "exit", "detection", "stats_update"
        data : dict
            Event payload.
        """
        if not self._available or not self._running:
            return
        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        try:
            self._event_queue.put_nowait(payload)
        except queue.Full:
            pass  # Drop silently — client will catch up via REST polling

    def push_frame(self, camera: str, frame_bgr: np.ndarray):
        """
        Update the latest MJPEG frame for *camera*.
        Call this from process_entry_camera / process_room_camera / process_exit_camera.

        Parameters
        ----------
        camera : str
            "entry" | "room" | "exit"
        frame_bgr : np.ndarray
            Latest processed (annotated) frame in BGR format.
        """
        if not self._available:
            return
        self._frame_store.put(camera, frame_bgr)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"

    # ------------------------------------------------------------------
    # FastAPI app builder
    # ------------------------------------------------------------------

    def _build_app(self) -> "FastAPI":
        app = FastAPI(
            title="Security Entry & Exit Management System API",
            description="Real-time security monitoring API with WebSocket support",
            version="2.0.0",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # ── REST endpoints ──────────────────────────────────────────────

        @app.get("/api/health")
        async def health():
            return {
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "ws_clients": self._ws_manager.connection_count,
            }

        @app.get("/api/status")
        async def status():
            return self._get_system_status()

        @app.get("/api/stats")
        async def stats():
            if self.system is None:
                return {}
            return {
                **self.system.stats,
                "active_sessions": len(self.system.active_sessions),
                "registered": len(self.system.registered_people),
            }

        @app.get("/api/people")
        async def people():
            if self.system is None:
                return []
            out = []
            for pid, profile in self.system.registered_people.items():
                session = self.system.active_sessions.get(pid)
                status_str = self.system.person_status.get(pid, "unknown")
                entry_time = None
                duration = None
                if session:
                    entry_time = session["entry_time"].isoformat()
                    duration = (datetime.now() - session["entry_time"]).total_seconds()
                out.append(
                    {
                        "person_id": pid,
                        "status": status_str,
                        "has_session": session is not None,
                        "entry_time": entry_time,
                        "duration_seconds": duration,
                        "has_face_embedding": profile.get("face_embedding") is not None,
                    }
                )
            return out

        @app.get("/api/sessions")
        async def sessions():
            if self.system is None:
                return []
            out = []
            for pid, session in self.system.active_sessions.items():
                duration = (datetime.now() - session["entry_time"]).total_seconds()
                velocities = self.system.velocity_data.get(pid, [0.0])
                out.append(
                    {
                        "person_id": pid,
                        "session_id": session.get("session_id", ""),
                        "entry_time": session["entry_time"].isoformat(),
                        "duration_seconds": round(duration, 1),
                        "avg_velocity": round(
                            sum(velocities) / len(velocities) if velocities else 0, 3
                        ),
                        "max_velocity": round(max(velocities) if velocities else 0, 3),
                    }
                )
            return out

        @app.get("/api/alerts")
        async def alerts(limit: int = 50, level: Optional[str] = None):
            if self.system is None:
                return []
            alerts_raw = self.system.alert_manager.get_recent_alerts(
                limit=limit,
            )
            if level:
                alerts_raw = [a for a in alerts_raw if a["alert_level"] == level]
            # Serialize datetime objects
            result = []
            for a in alerts_raw:
                item = dict(a)
                if isinstance(item.get("timestamp"), datetime):
                    item["timestamp"] = item["timestamp"].isoformat()
                result.append(item)
            return result

        @app.get("/api/tracker")
        async def tracker_info():
            if self.system is None or not hasattr(self.system, "multi_tracker"):
                return {"available": False}
            diag = self.system.multi_tracker.diagnostics()
            diag["available"] = True
            return diag

        @app.get("/api/trajectories/{person_id}")
        async def trajectories(person_id: str, limit: int = 100):
            if self.system is None:
                return []
            pts = list(self.system.trajectories.get(person_id, []))
            # Return last `limit` points
            pts = pts[-limit:]
            result = []
            for x, y, ts in pts:
                result.append(
                    {
                        "x": x,
                        "y": y,
                        "timestamp": ts.isoformat()
                        if isinstance(ts, datetime)
                        else str(ts),
                    }
                )
            return result

        # ── MJPEG camera streams ────────────────────────────────────────

        def _mjpeg_generator(camera: str):
            """Yield multipart MJPEG frames."""
            while True:
                frame_bytes = self._frame_store.get(camera)
                if frame_bytes is None:
                    time.sleep(0.05)
                    continue
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
                time.sleep(1 / 15)  # Cap at 15 fps to save bandwidth

        @app.get("/stream/entry")
        async def stream_entry():
            return StreamingResponse(
                _mjpeg_generator("entry"),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        @app.get("/stream/room")
        async def stream_room():
            return StreamingResponse(
                _mjpeg_generator("room"),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        @app.get("/stream/exit")
        async def stream_exit():
            return StreamingResponse(
                _mjpeg_generator("exit"),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        # ── WebSocket ───────────────────────────────────────────────────

        @app.websocket("/ws/events")
        async def ws_events(websocket: WebSocket):
            await self._ws_manager.connect(websocket)
            try:
                while True:
                    # Keep alive — also accept any client messages (ignored)
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    except asyncio.TimeoutError:
                        # Send a ping to keep the connection open
                        await websocket.send_text(
                            _dumps(
                                {
                                    "event": "ping",
                                    "timestamp": datetime.now().isoformat(),
                                    "data": {},
                                }
                            )
                        )
            except WebSocketDisconnect:
                pass
            except Exception:
                pass
            finally:
                await self._ws_manager.disconnect(websocket)

        return app

    # ------------------------------------------------------------------
    # Background server runner
    # ------------------------------------------------------------------

    def _run_server(self):
        """
        Entry point for the background daemon thread.
        Creates a new asyncio event loop, starts the event-queue forwarder,
        and runs uvicorn.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Start the queue-to-websocket forwarder coroutine
        self._loop.create_task(self._forward_events())

        # Start periodic stats broadcast
        self._loop.create_task(self._periodic_stats_broadcast())

        config = uvicorn.Config(
            app=self._app,
            host=self.host,
            port=self.port,
            loop="none",  # Use our manually-created loop
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        try:
            self._loop.run_until_complete(server.serve())
        except Exception as exc:
            logger.error(f"API bridge stopped: {exc}")
        finally:
            self._running = False

    async def _forward_events(self):
        """
        Drain the thread-safe event queue and broadcast each event to all
        connected WebSocket clients.  Runs forever in the async event loop.
        """
        while self._running:
            try:
                # Non-blocking get with a short timeout so we don't spin-wait
                payload = self._event_queue.get_nowait()
                msg = _dumps(payload)
                await self._ws_manager.broadcast(msg)
            except queue.Empty:
                await asyncio.sleep(0.02)
            except Exception as exc:
                logger.debug(f"Event forward error: {exc}")
                await asyncio.sleep(0.1)

    async def _periodic_stats_broadcast(self):
        """Broadcast a stats_update event every 2 seconds."""
        while self._running:
            await asyncio.sleep(2.0)
            try:
                stats = self._get_system_status()
                msg = _dumps(
                    {
                        "event": "stats_update",
                        "timestamp": datetime.now().isoformat(),
                        "data": stats,
                    }
                )
                await self._ws_manager.broadcast(msg)
            except Exception as exc:
                logger.debug(f"Stats broadcast error: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_system_status(self) -> dict:
        """Build a system state snapshot dict for REST / WebSocket."""
        if self.system is None:
            return {"available": False}

        # Compute average room velocity across all active persons
        velocities = []
        for pid in self.system.active_sessions:
            vs = self.system.velocity_data.get(pid, [])
            if vs:
                velocities.append(vs[-1])  # most-recent velocity

        avg_velocity = (
            round(sum(velocities) / len(velocities), 3) if velocities else 0.0
        )

        # Recent alert summary
        alert_stats = self.system.alert_manager.get_stats()

        # Tracker info
        tracker_info: dict = {}
        if hasattr(self.system, "multi_tracker"):
            tracker_info = self.system.multi_tracker.diagnostics()

        return {
            "system_running": self.system.running,
            "registered": len(self.system.registered_people),
            "inside": self.system.stats.get("inside", 0),
            "total_entries": self.system.stats.get("registered", 0),
            "total_exits": self.system.stats.get("exited", 0),
            "unauthorized_detections": self.system.stats.get("unauthorized", 0),
            "active_sessions": len(self.system.active_sessions),
            "avg_room_velocity": avg_velocity,
            "face_recognition": getattr(self.system, "use_face_recognition", False),
            "debug_mode": getattr(self.system, "debug_mode", False),
            "alert_stats": alert_stats,
            "tracker": tracker_info,
            "ws_clients": self._ws_manager.connection_count if self._ws_manager else 0,
            "timestamp": datetime.now().isoformat(),
        }
