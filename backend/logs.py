"""Logging system for DAVESBX."""
import json
from datetime import datetime
from pathlib import Path
from config import LOGS_DIR


class ActivityLog:
    """Timestamped activity log — not streamed, checked after the fact."""

    def __init__(self):
        self.log_file = LOGS_DIR / "activity.jsonl"
        self.error_file = LOGS_DIR / "errors.jsonl"

    def add(self, entry_type: str, message: str, details: dict = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            "message": message,
            "details": details or {}
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        if entry_type == "error":
            with open(self.error_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return entry

    def get_all(self, limit: int = 500, offset: int = 0) -> list:
        if not self.log_file.exists():
            return []
        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        entries.reverse()
        return entries[offset:offset + limit]

    def get_errors(self, limit: int = 500, offset: int = 0) -> list:
        if not self.error_file.exists():
            return []
        entries = []
        with open(self.error_file, "r") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        entries.reverse()
        return entries[offset:offset + limit]

    def search(self, query: str, limit: int = 100) -> list:
        if not self.log_file.exists():
            return []
        entries = []
        query_lower = query.lower()
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if query_lower in entry.get("message", "").lower() or query_lower in json.dumps(entry.get("details", {})).lower():
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
        entries.reverse()
        return entries[:limit]


activity_log = ActivityLog()
