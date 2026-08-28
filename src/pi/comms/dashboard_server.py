"""
Dashboard server — Pi 3B ↔ Laptop over Wi-Fi.

Exposes a lightweight HTTP + WebSocket server:
  GET  /            → serves the dashboard HTML (static)
  GET  /ws          → WebSocket: pushes {"count": N, "snapshot": <base64 jpeg>}
  POST /command     → receives {"command": "<cmd>"} from dashboard

WebSocket is the primary push channel; HTTP command endpoint
handles dashboard → Pi control messages.
"""

import base64
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np


# ── Shared state across handler instances ──────────────────────────────────
_command_queue: queue.Queue[str] = queue.Queue()
_latest_payload: dict = {}
_payload_lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # Silence default access logs
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_dashboard()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/command":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body)
                cmd  = data.get("command", "").strip()
                if cmd:
                    _command_queue.put(cmd)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
            except json.JSONDecodeError:
                self.send_error(400, "Bad JSON")
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_dashboard(self):
        # The full dashboard app lives in /src/dashboard — this stub redirects.
        html = b"<html><body><p>Dashboard running. Open the laptop app.</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


class DashboardServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self._host    = host
        self._port    = port
        self._server  = HTTPServer((host, port), _Handler)
        self._thread  = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[DashboardServer] Listening on {host}:{port}")

    def push(self, count: int, snapshot: np.ndarray):
        """
        Store the latest count + JPEG-encoded snapshot for the dashboard to poll.
        In the full implementation this will broadcast over WebSocket instead.
        """
        _, buf  = cv2.imencode(".jpg", snapshot, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64     = base64.b64encode(buf).decode("utf-8")
        payload = {"count": count, "snapshot": b64}
        with _payload_lock:
            _latest_payload.update(payload)

    def poll_command(self) -> str | None:
        """Non-blocking: returns a command string if one is queued, else None."""
        try:
            return _command_queue.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self._server.shutdown()
