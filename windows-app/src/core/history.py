"""
Seamless Transfer History Store
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from .config import CONFIG_DIR

HISTORY_FILE = CONFIG_DIR / "history.json"


class HistoryManager:
    def __init__(self):
        self.file_path = HISTORY_FILE
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            self._save([])

    def _load(self) -> List[Dict[str, Any]]:
        try:
            if self.file_path.exists():
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
        except Exception as e:
            print(f"[History] Save error: {e}")

    def add_entry(self, entry: Dict[str, Any]) -> None:
        items = self._load()
        if "timestamp" not in entry:
            entry["timestamp"] = int(time.time())
        # Prepend new entry
        items.insert(0, entry)
        # Keep maximum 100 historical items
        items = items[:100]
        self._save(items)

    def get_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        items = self._load()
        return items[:limit]

    def clear(self) -> None:
        self._save([])
