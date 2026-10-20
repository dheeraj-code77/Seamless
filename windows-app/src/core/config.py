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

# Folder name used for received files.
TRANSFER_FOLDER_NAME = "Seamless Transfer"


def get_desktop_dir() -> Path:
    """
    Resolves the real Windows Desktop folder.

    The Desktop can be moved or redirected, for example to OneDrive, so the
    shell folder registry value is preferred over the plain home folder path.
    """
    if os.name == "nt":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Desktop")
            expanded = os.path.expandvars(str(value))
            if expanded:
                return Path(expanded)
        except Exception:
            pass
    return Path.home() / "Desktop"


DEFAULT_DOWNLOAD_DIR = get_desktop_dir() / TRANSFER_FOLDER_NAME

# The earlier default. Kept so an existing install that never changed the
# location can be moved to the new default without overwriting a real choice.
LEGACY_DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "Seamless"

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
                original_download_dir = str(data.get("download_dir", ""))
                data = _migrate_default_download_dir(data)
                # The migration changes the stored location, so it is written
                # back now. Otherwise the old path would be offered again on
                # the next start.
                if str(data.get("download_dir", "")) != original_download_dir:
                    save_config(data)
                return data
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def _migrate_default_download_dir(config: dict) -> dict:
    """
    Moves an untouched default location to the current default.

    Only the previous built-in default is migrated. A location the user picked
    themselves is always preserved, and no files are moved or deleted.
    """
    current = str(config.get("download_dir", ""))
    legacy = str(LEGACY_DEFAULT_DOWNLOAD_DIR)
    if current and current != legacy:
        return config
    new_dir = str(DEFAULT_DOWNLOAD_DIR)
    if current != new_dir:
        print(f"[Config] Transfer folder moved from '{current or legacy}' to '{new_dir}'.")
        print("[Config] Files already received stay in the previous folder.")
    config["download_dir"] = new_dir
    return config


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
