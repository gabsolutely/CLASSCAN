"""
Dashboard server — Pi 3B ↔ Laptop over Wi-Fi / LAN.

Exposes:
  GET  / or /index.html → Serves src/dashboard/index.html
  GET  /styles.css      → Serves src/dashboard/styles.css
  GET  /app.js          → Serves src/dashboard/app.js
  GET  /status          → JSON polling endpoint for app.js
  GET  /stream          → Multipart MJPEG live video stream
  POST /command         → Receives control commands from dashboard UI
"""

import base64
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = (BASE_DIR.parent / "dashboard").resolve()

# ── Shared state across server threads ─────────────────────────────────────────
_command_queue: queue.Queue[str] = queue.Queue()
_state_lock = threading.Lock()
_latest_frame_jpg: bytes | None = None
_latest_telemetry: dict = {
    "count": 0,
    "fps": 0.0,
    "top_conf": 0.0,
    "timestamp": "--:--:--",
    "snapshot": "",
    "zones": None,
    "mode": "SWEEP",
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Silence routine access logs

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        # 1. Static Dashboard Web Assets
        if self.path in ("/", "/index.html"):
            self._serve_file(DASHBOARD_DIR / "index.html", "text/html; charset=utf-8")
        elif self.path == "/styles.css":
            self._serve_file(DASHBOARD_DIR / "styles.css", "text/css; charset=utf-8")
        elif self.path == "/app.js":
            self._serve_file(DASHBOARD_DIR / "app.js", "application/javascript; charset=utf-8")

        # 2. Polling API for dashboard app.js
        elif self.path == "/status":
            with _state_lock:
                payload = dict(_latest_telemetry)
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        # 3. Live MJPEG Video Stream
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self._send_cors_headers()
            self.end_headers()
            try:
                while True:
                    with _state_lock:
                        jpg = _latest_frame_jpg
                    if jpg is None:
                        time.sleep(0.04)
                        continue
                    header = (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
                    )
                    self.wfile.write(header + jpg + b"\r\n")
                    time.sleep(0.04)  # ~25 FPS output cap
            except (BrokenPipeError, ConnectionResetError):
                pass

        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        if self.path == "/command":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                cmd = data.get("command", "").strip()
                if cmd:
                    _command_queue.put(cmd)
                resp = json.dumps({"ok": True, "command": cmd}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(resp)
            except json.JSONDecodeError:
                self.send_error(400, "Bad JSON")
        else:
            self.send_error(404)

    def _serve_file(self, file_path: Path, content_type: str):
        if not file_path.is_file():
            self.send_error(404, f"File not found: {file_path.name}")
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)


class DashboardServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self._host = host
        self._port = port
        self._server = HTTPServer((host, port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[DashboardServer] Listening on http://{host}:{port} (Serving {DASHBOARD_DIR})")

    def push(self, count: int, frame: np.ndarray, fps: float = 0.0, top_conf: float = 0.0,
             zones: dict | None = None, mode: str = "SWEEP"):
        """Store latest count, annotated frame, and telemetry for polling & streaming."""
        global _latest_frame_jpg
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        jpg_bytes = bytes(buf)
        b64 = base64.b64encode(buf).decode("utf-8")
        ts = time.strftime("%H:%M:%S")

        with _state_lock:
            _latest_frame_jpg = jpg_bytes
            _latest_telemetry["count"] = count
            _latest_telemetry["fps"] = round(fps, 1)
            _latest_telemetry["top_conf"] = round(top_conf, 3)
            _latest_telemetry["timestamp"] = ts
            _latest_telemetry["snapshot"] = b64
            _latest_telemetry["zones"] = zones
            _latest_telemetry["mode"] = mode

    def poll_command(self) -> str | None:
        """Non-blocking: returns a command string if one is queued, else None."""
        try:
            return _command_queue.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self._server.shutdown()
