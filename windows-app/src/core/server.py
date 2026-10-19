"""
Seamless Core HTTP Server
Zero-dependency HTTP server handling API routes, file streaming, and static UI delivery.
"""
import os
import sys
import json
import time
import urllib.parse
import hashlib
import mimetypes
from io import BytesIO
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

import qrcode
from qrcode.image.svg import SvgPathImage

from .config import load_config, save_config, get_local_ip
from .security import SecurityManager
from .history import HistoryManager
from .transfer_engine import TransferEngine
from .discovery import DiscoveryService


def create_pairing_qr_payload(host: str, port: int, device_id: str, pairing_token: str = "") -> str:
    payload = {
        "app": "seamless",
        "version": 1,
        "host": host,
        "port": port,
        "device_id": device_id
    }
    if pairing_token:
        payload["pairing_token"] = pairing_token
    return json.dumps(payload, separators=(",", ":"))


def create_pairing_qr_svg(payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4
    )
    qr.add_data(payload)
    qr.make(fit=True)
    output = BytesIO()
    qr.make_image(image_factory=SvgPathImage).save(output)
    return output.getvalue()


class SeamlessHandler(BaseHTTPRequestHandler):
    # Injected dependencies from server instance
    security: SecurityManager = None
    history: HistoryManager = None
    transfer: TransferEngine = None
    discovery: DiscoveryService = None
    config: Dict[str, Any] = None
    renderer_dir: Path = None

    def log_message(self, format, *args):
        # Clean logging: suppress noisy polling requests
        if "/api/transfer/status" not in self.path and "/api/devices" not in self.path:
            sys.stdout.write(f"[HTTP] {self.command} {self.path} - {args[1]}\n")

    def _send_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Seamless-Filename, X-Seamless-Filesize, X-Seamless-Sender-Id, X-Seamless-Sender-Name, X-Seamless-Token, X-Seamless-SHA256")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # API Routes
        if path == "/api/pair/qr":
            # A fresh short-lived token is embedded every time the code is rendered,
            # so a scanned code can be redeemed exactly once and only while valid.
            pairing_token = self.security.generate_pairing_token()
            payload = create_pairing_qr_payload(
                get_local_ip(),
                self.config.get("http_port", 5173),
                self.config.get("device_id", ""),
                pairing_token
            )
            body = create_pairing_qr_svg(payload)
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/device/info":
            self._send_json({
                "device_id": self.config.get("device_id"),
                "device_name": self.config.get("device_name"),
                "device_type": "windows",
                "ip": get_local_ip(),
                "port": self.config.get("http_port", 5173),
                "download_dir": self.config.get("download_dir"),
                "clipboard_sync": self.config.get("clipboard_sync_enabled", True),
                "paired_count": len(self.config.get("paired_devices", {}))
            })
            return

        if path == "/api/devices":
            discovered = self.discovery.get_discovered_devices() if self.discovery else []
            paired = self.config.get("paired_devices", {})
            self._send_json({
                "discovered": discovered,
                "paired": paired
            })
            return

        if path == "/api/transfer/status":
            self._send_json(self.transfer.get_status())
            return

        if path == "/api/history":
            entries = self.history.get_entries(limit=50)
            self._send_json({"history": entries})
            return

        if path == "/api/pair/active_pin":
            # Returns active PIN if one was generated recently
            self._send_json({
                "pin": self.security.active_pin,
                "has_active_pin": self.security.active_pin is not None
            })
            return

        # Static Web UI Delivery
        self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. Device Pairing Endpoints
        if path == "/api/pair/request":
            pin = self.security.generate_pin()
            self._send_json({
                "pin": pin,
                "expires_in": 300
            })
            return

        if path == "/api/pair/exchange":
            # Zero-touch pairing: the phone redeems the short-lived token that was
            # embedded in the QR code and receives a durable device token.
            body = self._read_json_body()
            pairing_token = body.get("pairing_token", "")
            device_id = body.get("device_id", "")
            device_name = body.get("device_name", "Android Device")
            device_ip = body.get("device_ip") or self.client_address[0]

            if not device_id:
                self._send_json({"success": False, "error": "A device id is required."}, 400)
                return

            if not self.security.verify_pairing_token(pairing_token):
                self._send_json({
                    "success": False,
                    "error": "This pairing code has expired. Scan the QR code shown on the laptop again."
                }, 401)
                return

            token = self.security.generate_token()
            paired = self.config.setdefault("paired_devices", {})
            paired[device_id] = {
                "name": device_name,
                "token": token,
                "ip": device_ip,
                "paired_at": int(time.time())
            }
            save_config(self.config)
            self._send_json({
                "success": True,
                "token": token,
                "device_name": self.config.get("device_name")
            })
            return

        if path == "/api/pair/verify":
            body = self._read_json_body()
            pin = body.get("pin", "")
            device_id = body.get("device_id", "")
            device_name = body.get("device_name", "Remote Device")
            device_ip = body.get("device_ip") or self.client_address[0]

            if self.security.verify_pin(pin):
                token = self.security.generate_token()
                paired = self.config.setdefault("paired_devices", {})
                paired[device_id] = {
                    "name": device_name,
                    "token": token,
                    "ip": device_ip,
                    "paired_at": int(time.time())
                }
                save_config(self.config)
                self._send_json({
                    "success": True,
                    "token": token,
                    "device_name": self.config.get("device_name")
                })
            else:
                self._send_json({"success": False, "error": "Invalid or expired PIN code."}, 401)
            return

        if path == "/api/pair/unpair":
            body = self._read_json_body()
            device_id = body.get("device_id")
            paired = self.config.get("paired_devices", {})
            if device_id in paired:
                del paired[device_id]
                save_config(self.config)
            self._send_json({"success": True})
            return

        # 2. File Receiving Endpoint (High Speed Chunked Stream)
        if path == "/api/transfer/send":
            self._handle_incoming_file_stream()
            return

        # 3. Transfer Controls
        if path == "/api/transfer/pause":
            res = self.transfer.pause_transfer()
            self._send_json({"success": res})
            return

        if path == "/api/transfer/resume":
            res = self.transfer.resume_transfer()
            self._send_json({"success": res})
            return

        if path == "/api/transfer/cancel":
            res = self.transfer.cancel_transfer()
            self._send_json({"success": res})
            return

        # 4. History Controls
        if path == "/api/history/clear":
            self.history.clear()
            self._send_json({"success": True})
            return

        # 5. Settings
        if path == "/api/settings/folder":
            body = self._read_json_body()
            new_folder = body.get("path")
            if new_folder and os.path.exists(new_folder):
                self.config["download_dir"] = str(Path(new_folder).resolve())
                save_config(self.config)
                self._send_json({"success": True, "download_dir": self.config["download_dir"]})
            else:
                self._send_json({"success": False, "error": "Folder path does not exist."}, 400)
            return

        if path == "/api/settings/clipboard":
            body = self._read_json_body()
            enabled = body.get("enabled", True)
            self.config["clipboard_sync_enabled"] = bool(enabled)
            save_config(self.config)
            self._send_json({"success": True, "enabled": self.config["clipboard_sync_enabled"]})
            return

        if path == "/api/settings/open_folder":
            download_dir = self.config.get("download_dir", str(Path.home() / "Downloads" / "Seamless"))
            try:
                os.makedirs(download_dir, exist_ok=True)
                os.startfile(download_dir)
                self._send_json({"success": True, "download_dir": download_dir})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)
            return

        # 6. Clipboard Sync Endpoint
        if path == "/api/clipboard":
            body = self._read_json_body()
            text = body.get("text", "")
            if text and self.config.get("clipboard_sync_enabled", True):
                self._apply_windows_clipboard(text)
                self._send_json({"success": True})
            else:
                self._send_json({"success": False}, 400)
            return

        self._send_json({"error": "Route not found"}, 404)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length).decode("utf-8")
            try:
                return json.loads(raw)
            except Exception:
                pass
        return {}

    def _handle_incoming_file_stream(self):
        """
        Receives binary file stream chunk-by-chunk with SHA-256 computation and progress tracking.
        """
        raw_filename = self.headers.get("X-Seamless-Filename", "")
        # Decode URL-encoded filename if present
        filename = urllib.parse.unquote(raw_filename) if "%" in raw_filename else raw_filename
        filesize = int(self.headers.get("X-Seamless-Filesize", 0))
        sender_id = self.headers.get("X-Seamless-Sender-Id", "unknown")
        sender_name = self.headers.get("X-Seamless-Sender-Name", "Android Device")
        expected_sha = self.headers.get("X-Seamless-SHA256", "").lower()

        if not filename:
            filename = f"seamless_file_{int(time.time())}.bin"

        download_dir = self.config.get("download_dir", str(Path.home() / "Downloads" / "Seamless"))
        target_path = SecurityManager.get_safe_destination_path(download_dir, filename)

        transfer_id = f"tx_{int(time.time() * 1000)}"
        self.transfer.start_transfer(
            transfer_id=transfer_id,
            filename=target_path.name,
            filesize=filesize,
            direction="incoming",
            peer_id=sender_id,
            peer_name=sender_name
        )

        hasher = hashlib.sha256()
        received_bytes = 0
        chunk_size = 65536  # 64 KB streaming buffer

        try:
            with open(target_path, "wb") as f:
                while received_bytes < filesize or (filesize == 0 and True):
                    # Check pause signal
                    while self.transfer.is_paused():
                        time.sleep(0.1)

                    # Check cancel signal
                    if self.transfer.is_cancelled():
                        f.close()
                        if target_path.exists():
                            target_path.unlink()  # Clean up partial file
                        self._send_json({"success": False, "cancelled": True}, 200)
                        return

                    to_read = min(chunk_size, filesize - received_bytes) if filesize > 0 else chunk_size
                    chunk = self.rfile.read(to_read)
                    if not chunk:
                        break

                    f.write(chunk)
                    hasher.update(chunk)
                    received_bytes += len(chunk)
                    self.transfer.update_progress(received_bytes)

            actual_sha = hasher.hexdigest().lower()

            # Verify integrity if checksum provided
            if expected_sha and actual_sha != expected_sha:
                self.transfer.fail_transfer("SHA-256 integrity mismatch")
                if target_path.exists():
                    target_path.unlink()
                self._send_json({"success": False, "error": "Checksum validation failed."}, 400)
                return

            self.transfer.complete_transfer(saved_path=str(target_path), sha256=actual_sha)
            self._send_json({
                "success": True,
                "saved_path": str(target_path),
                "sha256": actual_sha,
                "bytes_received": received_bytes
            })

        except Exception as e:
            self.transfer.fail_transfer(str(e))
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass
            self._send_json({"success": False, "error": str(e)}, 500)

    def _serve_static(self, path: str):
        # Route to mobile app if requested
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys._MEIPASS)
            android_dir = base_dir / "android-app" / "src"
        else:
            android_dir = Path(__file__).resolve().parent.parent.parent.parent / "android-app" / "src"

        if path in ("/mobile", "/mobile/", "/android"):
            file_path = android_dir / "index.html"
        elif path in ("/mobile-app.js", "/mobile/mobile-app.js"):
            file_path = android_dir / "mobile-app.js"
        elif path == "/manifest.json":
            file_path = android_dir / "manifest.json"
        else:
            if path in ("", "/"):
                path = "/index.html"
            safe_subpath = path.lstrip("/")
            file_path = (self.renderer_dir / safe_subpath).resolve()

        # Strict sandbox check
        valid_roots = [str(self.renderer_dir), str(android_dir)]
        is_safe = any(str(file_path).startswith(root) for root in valid_roots)
        if not is_safe or not file_path.exists() or file_path.is_dir():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def _apply_windows_clipboard(self, text: str):
        try:
            import subprocess
            cmd = f'Set-Clipboard -Value "{text.replace('"', '`"')}"'
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False, timeout=2)
        except Exception as e:
            print(f"[Clipboard] Sync error: {e}")


def run_server(port: int = 5173, renderer_dir: Path = None):
    config = load_config()
    config["http_port"] = port
    security = SecurityManager()
    history = HistoryManager()
    transfer = TransferEngine(history)
    discovery = DiscoveryService(config)

    # Start discovery
    discovery.start()

    # Configure handler
    SeamlessHandler.security = security
    SeamlessHandler.history = history
    SeamlessHandler.transfer = transfer
    SeamlessHandler.discovery = discovery
    SeamlessHandler.config = config
    SeamlessHandler.renderer_dir = renderer_dir

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", port), SeamlessHandler)
    server.security = security
    server.config = config
    local_ip = get_local_ip()
    print(f"\n=======================================================")
    print(f" Seamless Windows Core running on port {port}")
    print(f" Local Web UI:    http://localhost:{port}")
    print(f" Network Address: http://{local_ip}:{port}")
    print(f" UDP Discovery:   Listening on port 52400")
    print(f" Downloads Path:  {config.get('download_dir')}")
    print(f"=======================================================\n")
    return server
