"""
Seamless Configuration & State Manager
"""
import os
import sys
import json
import uuid
import socket
from pathlib import Path

# Base Paths
APP_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "Seamless"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "Seamless"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "device_id": str(uuid.uuid4())[:8],
    "device_name": socket.gethostname() or "Windows-PC",
    "device_type": "windows",
    "http_port": 5173,
    "udp_port": 52400,
    "download_dir": str(DEFAULT_DOWNLOAD_DIR),
    "paired_devices": {},  # {device_id: {"name": str, "token": str, "ip": str, "paired_at": int}}
    "clipboard_sync_enabled": True
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults for any missing keys
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Config] Error saving config: {e}", file=sys.stderr)


def get_local_ip() -> str:
    """Finds the active local Wi-Fi / LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually connect externally, but selects the default outbound interface
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip
