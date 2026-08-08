"""Authentication middleware for DAVESBX."""
from fastapi import Request, HTTPException
from config import load_config


async def verify_api_key(request: Request):
    """Verify the API key on every request except /ping."""
    cfg = load_config()
    if not cfg.get("auth_enabled", True):
        return True

    # Skip auth for /ping and /docs
    path = request.url.path
    if path in ("/ping", "/docs", "/openapi.json", "/redoc"):
        return True

    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not api_key or api_key != cfg.get("api_key"):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True
