"""Configuration and settings for DAVESBX."""
import os
import json
import secrets
from pathlib import Path

# Base directories
APP_DIR = Path(os.environ.get("DAVESBX_DIR", str(Path.home() / ".davesbx")))
APP_DIR.mkdir(parents=True, exist_ok=True)

WORKSPACE_DIR = APP_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = APP_DIR / "config.json"
LOGS_DIR = APP_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR = APP_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "api_key": secrets.token_urlsafe(32),
    "public_url": "",
    "url_mode": "fastapi",  # fastapi | cloudflare | supabase
    "host": "0.0.0.0",
    "port": 8420,
    "auth_enabled": True,
    "storage_limit_gb": 10,
    "timezone": "UTC",
    "cloudflare": {
        "api_token": "",
        "account_id": "",
        "domain": "",
        "tunnel_mode": "quick"  # quick | named
    },
    "supabase": {
        "access_token": "",
        "project_ref": "",
        "function_name": "davesbx-sandbox"
    }
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        # Merge with defaults for any new keys
        merged = {**DEFAULT_CONFIG, **cfg}
        return merged
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_workspace_path(relative: str) -> Path:
    """Resolve a relative path within the workspace, preventing path traversal."""
    workspace = WORKSPACE_DIR.resolve()
    target = (workspace / relative).resolve()
    if not str(target).startswith(str(workspace)):
        raise ValueError("Path traversal detected — access denied")
    return target


def get_workspace_size() -> int:
    """Get total size of workspace in bytes."""
    total = 0
    for path in WORKSPACE_DIR.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total
