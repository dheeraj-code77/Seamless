"""
Seamless UDP Discovery Service
Zero-configuration Wi-Fi broadcast discovery.
"""
import json
import time
import socket
import threading
from typing import Dict, Any, List
from .config import get_local_ip

UDP_PORT = 52400
BEACON_INTERVAL = 2.5
PEER_TIMEOUT = 10.0


class DiscoveryService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self._running = False
        self._broadcast_thread = None
        self._listener_thread = None

    def start(self) -> None:
        self._running = True

        # Broadcast thread
        self._broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._broadcast_thread.start()

        # Listener thread
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        print(f"[Discovery] UDP Discovery active on port {UDP_PORT}")

    def stop(self) -> None:
        self._running = False

    def _broadcast_loop(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.5)

        while self._running:
            try:
                local_ip = get_local_ip()
                beacon = {
                    "type": "SEAMLESS_DISCOVERY",
                    "device_id": self.config.get("device_id", "win-dev"),
                    "device_name": self.config.get("device_name", "Windows PC"),
                    "device_type": "windows",
                    "ip": local_ip,
                    "port": self.config.get("http_port", 5173),
                    "version": "1.0.0",
                    "timestamp": time.time()
                }
                payload = json.dumps(beacon).encode("utf-8")
                # Broadcast on standard local subnet broadcast addresses
                s.sendto(payload, ("<broadcast>", UDP_PORT))
                s.sendto(payload, ("255.255.255.255", UDP_PORT))
            except Exception as e:
                # Silently catch transient socket errors
                pass

            # Prune stale peers
            self._prune_peers()
            time.sleep(BEACON_INTERVAL)

        s.close()

    def _listen_loop(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # Bind to all interfaces on UDP_PORT
            s.bind(("", UDP_PORT))
        except Exception as e:
            print(f"[Discovery] Warning: Could not bind to UDP port {UDP_PORT}: {e}")
            s.close()
            return

        s.settimeout(1.0)
        my_id = self.config.get("device_id")

        while self._running:
            try:
                data, addr = s.recvfrom(4096)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "SEAMLESS_DISCOVERY":
                    sender_id = msg.get("device_id")
                    if sender_id and sender_id != my_id:
                        with self.lock:
                            # Update or add peer
                            self.peers[sender_id] = {
                                "device_id": sender_id,
                                "device_name": msg.get("device_name", "Unknown Device"),
                                "device_type": msg.get("device_type", "unknown"),
                                "ip": addr[0] if msg.get("ip") in ("127.0.0.1", "") else msg.get("ip", addr[0]),
                                "port": msg.get("port", 5173),
                                "last_seen": time.time()
                            }
            except (socket.timeout, json.JSONDecodeError):
                continue
            except Exception:
                continue

        s.close()

    def _prune_peers(self) -> None:
        now = time.time()
        with self.lock:
            stale_keys = [k for k, v in self.peers.items() if now - v["last_seen"] > PEER_TIMEOUT]
            for k in stale_keys:
                del self.peers[k]

    def get_discovered_devices(self) -> List[Dict[str, Any]]:
        self._prune_peers()
        with self.lock:
            return list(self.peers.values())
