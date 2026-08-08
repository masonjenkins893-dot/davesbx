"""DAVESBX — Main FastAPI application."""
import os
import sys
import json
import time
import psutil
import shutil
import secrets
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Depends, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from config import (
    load_config, save_config, WORKSPACE_DIR, APP_DIR,
    get_workspace_path, get_workspace_size
)
from auth import verify_api_key
from logs import activity_log
from terminal import terminal_manager
from workspace import workspace_manager
from executor import execution_engine
from video import video_processor
from scheduler import scheduler_manager, script_manager

app = FastAPI(
    title="DAVESBX — Sandbox Console",
    description="Persistent sandbox console for a single AI agent. Terminal, files, code execution, and more.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure config is saved on first run
cfg = load_config()
if cfg.get("public_url", "") == "":
    cfg["public_url"] = f"http://localhost:{cfg['port']}"
    save_config(cfg)


# --- Pydantic models ---

class FileSave(BaseModel):
    path: str
    content: str = ""
    binary: Optional[str] = None  # base64 for binary

class FileEdit(BaseModel):
    content: str

class RenameRequest(BaseModel):
    new_name: str

class MoveRequest(BaseModel):
    src: str
    dest: str

class MoveBatchRequest(BaseModel):
    items: list

class DeleteBatchRequest(BaseModel):
    paths: list

class ZipRequest(BaseModel):
    paths: list
    output: str

class UnzipRequest(BaseModel):
    dest: Optional[str] = None

class FolderRequest(BaseModel):
    path: str

class CommandRequest(BaseModel):
    command: str

class InputRequest(BaseModel):
    data: str

class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"

class DebugRequest(BaseModel):
    code: str
    breakpoints: Optional[list] = None

class PackageRequest(BaseModel):
    manager: str = "pip"  # pip | npm
    packages: list

class EnvRequest(BaseModel):
    key: str
    value: str

class ReminderRequest(BaseModel):
    message: str
    target_time: str

class ScheduleRequest(BaseModel):
    command: str
    run_at: Optional[str] = None
    interval: Optional[float] = None

class ScriptRegisterRequest(BaseModel):
    file_path: str
    name: Optional[str] = None

class ConfigUpdate(BaseModel):
    storage_limit_gb: Optional[float] = None
    timezone: Optional[str] = None
    url_mode: Optional[str] = None
    cloudflare: Optional[dict] = None
    supabase: Optional[dict] = None


# --- Health & Status ---

@app.get("/ping")
async def ping():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}


@app.get("/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    storage = workspace_manager.get_storage_status()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram": {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "percent": vm.percent
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent
        },
        "workspace_storage": storage,
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/whoami", dependencies=[Depends(verify_api_key)])
async def whoami():
    cfg = load_config()
    return {
        "workspace_dir": str(WORKSPACE_DIR.resolve()),
        "api_base_url": cfg.get("public_url", f"http://localhost:{cfg['port']}"),
        "files": workspace_manager.list_files_tree()
    }


@app.get("/time", dependencies=[Depends(verify_api_key)])
async def get_time():
    cfg = load_config()
    tz = cfg.get("timezone", "UTC")
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz))
    except:
        now = datetime.now(timezone.utc)
    return {
        "time": now.isoformat(),
        "timezone": tz,
        "epoch": int(now.timestamp())
    }


@app.get("/processes", dependencies=[Depends(verify_api_key)])
async def get_processes():
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "cmdline"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info["cpu_percent"],
                "memory_percent": round(info["memory_percent"] or 0, 2),
                "cmdline": " ".join(info["cmdline"] or [])[:200]
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"processes": procs, "count": len(procs)}


# --- Terminal ---

@app.post("/terminal/new", dependencies=[Depends(verify_api_key)])
async def new_terminal():
    tid = terminal_manager.create_terminal()
    activity_log.add("terminal", f"Created terminal {tid}")
    return {"id": tid}

@app.get("/terminals", dependencies=[Depends(verify_api_key)])
async def list_terminals():
    return {"terminals": terminal_manager.list_terminals()}

@app.delete("/terminal/{tid}", dependencies=[Depends(verify_api_key)])
async def delete_terminal(tid: str):
    result = terminal_manager.delete_terminal(tid)
    if not result:
        raise HTTPException(404, "Terminal not found")
    activity_log.add("terminal", f"Deleted terminal {tid}")
    return {"deleted": True, "id": tid}

@app.get("/terminal/{tid}/output", dependencies=[Depends(verify_api_key)])
async def terminal_output(tid: str):
    return {"id": tid, "output": terminal_manager.get_terminal_output(tid)}

@app.post("/terminal/{tid}/run", dependencies=[Depends(verify_api_key)])
async def run_command(tid: str, req: CommandRequest):
    result = terminal_manager.run_command(tid, req.command)
    activity_log.add("command", f"Terminal {tid}: {req.command}", {"result": result})
    return result


# --- Commands ---

@app.post("/command/{cmd_id}/stop", dependencies=[Depends(verify_api_key)])
async def stop_command(cmd_id: str):
    result = terminal_manager.stop_command(cmd_id)
    return {"stopped": result, "command_id": cmd_id}

@app.get("/command/{cmd_id}/status", dependencies=[Depends(verify_api_key)])
async def command_status(cmd_id: str):
    return terminal_manager.get_command_status(cmd_id)

@app.get("/command/{cmd_id}/output", dependencies=[Depends(verify_api_key)])
async def command_output(cmd_id: str):
    return {"id": cmd_id, "output": terminal_manager.get_command_output(cmd_id)}

@app.post("/command/{cmd_id}/input", dependencies=[Depends(verify_api_key)])
async def command_input(cmd_id: str, req: InputRequest):
    result = terminal_manager.send_input(cmd_id, req.data)
    return {"sent": result, "command_id": cmd_id}

@app.get("/commands/running", dependencies=[Depends(verify_api_key)])
async def running_commands():
    return {"running": terminal_manager.get_running_commands()}


# --- Debugging ---

@app.post("/debug", dependencies=[Depends(verify_api_key)])
async def debug_code(req: DebugRequest):
    result = execution_engine.debug(req.code, req.breakpoints)
    activity_log.add("debug", "Debug execution", {"result": result.get("steps", [])})
    return result


# --- Workspace Files ---

@app.post("/file/save", dependencies=[Depends(verify_api_key)])
async def save_file(req: FileSave):
    import base64
    content = req.content
    if req.binary:
        content = base64.b64decode(req.binary)
    result = workspace_manager.save_file(req.path, content)
    activity_log.add("file", f"Saved: {req.path}")
    return result

@app.put("/file/{path:path}", dependencies=[Depends(verify_api_key)])
async def edit_file(path: str, req: FileEdit):
    result = workspace_manager.save_file(path, req.content)
    activity_log.add("file", f"Edited: {path}")
    return result

@app.get("/file/{path:path}", dependencies=[Depends(verify_api_key)])
async def read_file(path: str, as_text: bool = Query(False)):
    result = workspace_manager.read_file(path, as_text)
    if result.get("raw"):
        return FileResponse(result["file_path"])
    return result

@app.get("/files", dependencies=[Depends(verify_api_key)])
async def list_files():
    return {"files": workspace_manager.list_files_flat()}

@app.get("/files/tree", dependencies=[Depends(verify_api_key)])
async def list_files_tree():
    return workspace_manager.list_files_tree()

@app.post("/file/upload", dependencies=[Depends(verify_api_key)])
async def upload_file(file: UploadFile = File(...), dest: str = Query("")):
    target = get_workspace_path(f"{dest}/{file.filename}" if dest else file.filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        shutil.copyfileobj(file.file, f)
    activity_log.add("file", f"Uploaded: {file.filename}")
    return {"uploaded": True, "path": str(target.relative_to(WORKSPACE_DIR.resolve()))}

@app.get("/file/{path:path}/download", dependencies=[Depends(verify_api_key)])
async def download_file(path: str):
    target = get_workspace_path(path)
    if not target.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(target), filename=target.name)

@app.delete("/file/{path:path}", dependencies=[Depends(verify_api_key)])
async def delete_file(path: str):
    result = workspace_manager.delete_file(path)
    activity_log.add("file", f"Deleted: {path}")
    return result

@app.post("/file/delete_batch", dependencies=[Depends(verify_api_key)])
async def delete_batch(req: DeleteBatchRequest):
    return workspace_manager.delete_batch(req.paths)

@app.post("/file/{path:path}/rename", dependencies=[Depends(verify_api_key)])
async def rename_file(path: str, req: RenameRequest):
    return workspace_manager.rename_file(path, req.new_name)

@app.post("/file/move", dependencies=[Depends(verify_api_key)])
async def move_file(req: MoveRequest):
    return workspace_manager.move_file(req.src, req.dest)

@app.post("/file/move_batch", dependencies=[Depends(verify_api_key)])
async def move_batch(req: MoveBatchRequest):
    return workspace_manager.move_batch(req.items)

@app.get("/file/{path:path}/search", dependencies=[Depends(verify_api_key)])
async def search_files(path: str, q: str = Query(...)):
    return {"results": workspace_manager.search_files(path, q)}

@app.get("/file/{path:path}/versions", dependencies=[Depends(verify_api_key)])
async def file_versions(path: str):
    return {"versions": workspace_manager.get_versions(path)}

@app.get("/file/{path:path}/versions/{version_id}", dependencies=[Depends(verify_api_key)])
async def get_version(path: str, version_id: str):
    return workspace_manager.get_version(path, version_id)

@app.post("/folder", dependencies=[Depends(verify_api_key)])
async def create_folder(req: FolderRequest):
    return workspace_manager.create_folder(req.path)

@app.post("/archive/zip", dependencies=[Depends(verify_api_key)])
async def archive_zip(req: ZipRequest):
    return workspace_manager.zip_files(req.paths, req.output)

@app.post("/archive/unzip", dependencies=[Depends(verify_api_key)])
async def archive_unzip(path: str, req: UnzipRequest):
    return workspace_manager.unzip_file(path, req.dest)

@app.get("/workspace/export", dependencies=[Depends(verify_api_key)])
async def export_workspace():
    zip_path = workspace_manager.export_workspace()
    return FileResponse(zip_path, filename="davesbx_workspace.zip")

@app.post("/reset", dependencies=[Depends(verify_api_key)])
async def reset_workspace():
    result = workspace_manager.reset_workspace()
    activity_log.add("workspace", "Workspace reset")
    return result


# --- Video ---

@app.post("/video/process/{path:path}", dependencies=[Depends(verify_api_key)])
async def process_video(path: str):
    result = video_processor.process_video(path)
    activity_log.add("video", f"Processed: {path}")
    return result

@app.get("/video/{path:path}/frames", dependencies=[Depends(verify_api_key)])
async def get_video_frames(path: str):
    return video_processor.get_frames(path)

@app.get("/video/{path:path}/transcript", dependencies=[Depends(verify_api_key)])
async def get_video_transcript(path: str):
    return video_processor.get_transcript(path)


# --- Code Execution ---

@app.post("/execute", dependencies=[Depends(verify_api_key)])
async def execute_code(req: ExecuteRequest):
    result = execution_engine.execute(req.code, req.language)
    activity_log.add("execute", f"Ran {req.language} code", {"result": result.get("result")})
    return result


# --- Packages ---

@app.post("/packages/install", dependencies=[Depends(verify_api_key)])
async def install_packages(req: PackageRequest):
    if not req.packages:
        return {"error": "No packages specified"}

    if req.manager == "pip":
        cmd = [sys.executable, "-m", "pip", "install"] + req.packages
    elif req.manager == "npm":
        cmd = ["npm", "install"] + req.packages
    else:
        return {"error": f"Unknown package manager: {req.manager}"}

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        activity_log.add("package", f"Installed {req.manager}: {', '.join(req.packages)}")
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {"error": "Package installation timed out"}


# --- Environment ---

@app.get("/env", dependencies=[Depends(verify_api_key)])
async def get_env():
    return {"env": dict(os.environ)}

@app.post("/env", dependencies=[Depends(verify_api_key)])
async def set_env(req: EnvRequest):
    os.environ[req.key] = req.value
    activity_log.add("env", f"Set {req.key}")
    return {"set": True, "key": req.key}


# --- Reminders ---

@app.post("/reminder", dependencies=[Depends(verify_api_key)])
async def add_reminder(req: ReminderRequest):
    return scheduler_manager.add_reminder(req.message, req.target_time)

@app.get("/reminder", dependencies=[Depends(verify_api_key)])
async def list_reminders():
    return {"reminders": scheduler_manager.list_reminders()}

@app.get("/reminder/due", dependencies=[Depends(verify_api_key)])
async def due_reminders():
    return {"due": scheduler_manager.get_due_reminders()}

@app.delete("/reminder/{rid}", dependencies=[Depends(verify_api_key)])
async def delete_reminder(rid: str):
    result = scheduler_manager.delete_reminder(rid)
    if not result:
        raise HTTPException(404, "Reminder not found")
    return {"deleted": True}


# --- Scheduling ---

@app.post("/schedule", dependencies=[Depends(verify_api_key)])
async def schedule_job(req: ScheduleRequest):
    return scheduler_manager.schedule_job(req.command, req.run_at, req.interval)

@app.get("/schedule", dependencies=[Depends(verify_api_key)])
async def list_schedules():
    return {"jobs": scheduler_manager.list_jobs()}

@app.delete("/schedule/{job_id}", dependencies=[Depends(verify_api_key)])
async def cancel_schedule(job_id: str):
    result = scheduler_manager.cancel_job(job_id)
    if not result:
        raise HTTPException(404, "Scheduled job not found")
    return {"cancelled": True}


# --- Background Scripts ---

@app.post("/script/register", dependencies=[Depends(verify_api_key)])
async def register_script(req: ScriptRegisterRequest):
    return script_manager.register(req.file_path, req.name)

@app.get("/scripts", dependencies=[Depends(verify_api_key)])
async def list_scripts():
    return {"scripts": script_manager.list_scripts()}

@app.post("/script/{script_id}/start", dependencies=[Depends(verify_api_key)])
async def start_script(script_id: str):
    return script_manager.start_script(script_id)

@app.post("/script/{script_id}/stop", dependencies=[Depends(verify_api_key)])
async def stop_script(script_id: str):
    return script_manager.stop_script(script_id)

@app.get("/script/{script_id}/logs", dependencies=[Depends(verify_api_key)])
async def script_logs(script_id: str):
    return script_manager.get_logs(script_id)


# --- Logs ---

@app.get("/logs", dependencies=[Depends(verify_api_key)])
async def get_logs(limit: int = 500, offset: int = 0):
    return {"logs": activity_log.get_all(limit, offset)}

@app.get("/logs/errors", dependencies=[Depends(verify_api_key)])
async def get_error_logs(limit: int = 500, offset: int = 0):
    return {"errors": activity_log.get_errors(limit, offset)}


# --- Config / Settings ---

@app.get("/config", dependencies=[Depends(verify_api_key)])
async def get_config():
    cfg = load_config()
    # Don't expose full secrets
    safe = cfg.copy()
    if safe.get("cloudflare", {}).get("api_token"):
        safe["cloudflare"]["api_token"] = "***"
    if safe.get("supabase", {}).get("access_token"):
        safe["supabase"]["access_token"] = "***"
    return safe

@app.post("/config", dependencies=[Depends(verify_api_key)])
async def update_config(req: ConfigUpdate):
    cfg = load_config()
    if req.storage_limit_gb is not None:
        cfg["storage_limit_gb"] = req.storage_limit_gb
    if req.timezone is not None:
        cfg["timezone"] = req.timezone
    if req.url_mode is not None:
        cfg["url_mode"] = req.url_mode
    if req.cloudflare is not None:
        cfg["cloudflare"].update(req.cloudflare)
    if req.supabase is not None:
        cfg["supabase"].update(req.supabase)
    save_config(cfg)
    return {"updated": True, "config": cfg}

@app.post("/config/regenerate-key", dependencies=[Depends(verify_api_key)])
async def regenerate_api_key():
    cfg = load_config()
    cfg["api_key"] = secrets.token_urlsafe(32)
    save_config(cfg)
    return {"regenerated": True, "api_key": cfg["api_key"]}

@app.post("/config/toggle-auth", dependencies=[Depends(verify_api_key)])
async def toggle_auth():
    cfg = load_config()
    cfg["auth_enabled"] = not cfg.get("auth_enabled", True)
    save_config(cfg)
    return {"auth_enabled": cfg["auth_enabled"]}

@app.post("/app/restart", dependencies=[Depends(verify_api_key)])
async def restart_app():
    activity_log.add("system", "App restart requested")
    # On Windows, the Tauri shell will handle the actual restart
    return {"restart": True}


# --- Startup ---

@app.on_event("startup")
async def startup():
    activity_log.add("system", "DAVESBX started")
    # Auto-start any registered background scripts
    script_manager.auto_start_all()


if __name__ == "__main__":
    import uvicorn
    cfg = load_config()
    uvicorn.run(app, host=cfg["host"], port=cfg["port"])
