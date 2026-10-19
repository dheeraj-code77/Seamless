"""
Seamless Real-Time Transfer Engine
Tracks active transfers, streaming progress, throughput, and status.
"""
import time
import threading
from typing import Dict, Any, Optional
from .history import HistoryManager


class TransferEngine:
    def __init__(self, history_mgr: HistoryManager):
        self.history_mgr = history_mgr
        self.lock = threading.Lock()
        self.current_transfer: Optional[Dict[str, Any]] = None
        self._last_time = 0.0
        self._last_bytes = 0
        self._speed_samples = []

    def start_transfer(self, transfer_id: str, filename: str, filesize: int,
                       direction: str, peer_id: str, peer_name: str) -> Dict[str, Any]:
        with self.lock:
            now = time.time()
            self._last_time = now
            self._last_bytes = 0
            self._speed_samples = []

            self.current_transfer = {
                "transfer_id": transfer_id,
                "filename": filename,
                "filesize": filesize,
                "direction": direction,
                "peer_id": peer_id,
                "peer_name": peer_name,
                "bytes_transferred": 0,
                "progress_percent": 0.0,
                "speed_mbps": 0.0,
                "eta_seconds": 0,
                "status": "transferring",
                "is_paused": False,
                "is_cancelled": False,
                "start_time": now,
                "error": None
            }
            return self.current_transfer.copy()

    def update_progress(self, bytes_transferred: int) -> None:
        with self.lock:
            if not self.current_transfer or self.current_transfer["status"] != "transferring":
                return

            now = time.time()
            self.current_transfer["bytes_transferred"] = bytes_transferred

            # Calculate progress percentage
            filesize = self.current_transfer["filesize"]
            if filesize > 0:
                percent = min(100.0, (bytes_transferred / filesize) * 100.0)
                self.current_transfer["progress_percent"] = round(percent, 1)

            # Rolling speed calculation
            dt = now - self._last_time
            if dt >= 0.3:  # update speed every 300ms
                db = bytes_transferred - self._last_bytes
                if dt > 0:
                    speed = (db / dt) / (1024 * 1024)  # MB/s
                    self._speed_samples.append(speed)
                    if len(self._speed_samples) > 5:
                        self._speed_samples.pop(0)
                    avg_speed = sum(self._speed_samples) / len(self._speed_samples)
                    self.current_transfer["speed_mbps"] = round(avg_speed, 1)

                    # Calculate ETA
                    remaining_bytes = max(0, filesize - bytes_transferred)
                    if avg_speed > 0:
                        eta = int((remaining_bytes / (1024 * 1024)) / avg_speed)
                        self.current_transfer["eta_seconds"] = max(1, eta)
                    else:
                        self.current_transfer["eta_seconds"] = 0

                self._last_time = now
                self._last_bytes = bytes_transferred

    def is_cancelled(self) -> bool:
        with self.lock:
            if not self.current_transfer:
                return False
            return self.current_transfer.get("is_cancelled", False)

    def is_paused(self) -> bool:
        with self.lock:
            if not self.current_transfer:
                return False
            return self.current_transfer.get("is_paused", False)

    def pause_transfer(self) -> bool:
        with self.lock:
            if self.current_transfer and self.current_transfer["status"] == "transferring":
                self.current_transfer["is_paused"] = True
                self.current_transfer["status"] = "paused"
                return True
            return False

    def resume_transfer(self) -> bool:
        with self.lock:
            if self.current_transfer and self.current_transfer["status"] == "paused":
                self.current_transfer["is_paused"] = False
                self.current_transfer["status"] = "transferring"
                self._last_time = time.time()
                return True
            return False

    def cancel_transfer(self) -> bool:
        with self.lock:
            if self.current_transfer and self.current_transfer["status"] in ("transferring", "paused"):
                self.current_transfer["is_cancelled"] = True
                self.current_transfer["status"] = "cancelled"
                self._record_history("cancelled")
                return True
            return False

    def complete_transfer(self, saved_path: Optional[str] = None, sha256: Optional[str] = None) -> None:
        with self.lock:
            if self.current_transfer:
                self.current_transfer["status"] = "completed"
                self.current_transfer["progress_percent"] = 100.0
                self.current_transfer["speed_mbps"] = 0.0
                self.current_transfer["eta_seconds"] = 0
                self._record_history("completed", saved_path, sha256)

    def fail_transfer(self, error_msg: str) -> None:
        with self.lock:
            if self.current_transfer:
                self.current_transfer["status"] = "failed"
                self.current_transfer["error"] = error_msg
                self._record_history("failed", error_msg=error_msg)

    def _record_history(self, final_status: str, saved_path: Optional[str] = None,
                        sha256: Optional[str] = None, error_msg: Optional[str] = None) -> None:
        if not self.current_transfer:
            return
        entry = {
            "transfer_id": self.current_transfer["transfer_id"],
            "filename": self.current_transfer["filename"],
            "filesize": self.current_transfer["filesize"],
            "direction": self.current_transfer["direction"],
            "peer_id": self.current_transfer["peer_id"],
            "peer_name": self.current_transfer["peer_name"],
            "status": final_status,
            "saved_path": saved_path,
            "sha256": sha256,
            "error": error_msg,
            "timestamp": int(time.time())
        }
        self.history_mgr.add_entry(entry)

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            if not self.current_transfer:
                return {"status": "idle"}
            return self.current_transfer.copy()
