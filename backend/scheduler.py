"""Scheduling, reminders, and background scripts."""
import threading
import time
import uuid
import subprocess
import os
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from config import WORKSPACE_DIR, get_workspace_path


@dataclass
class Reminder:
    id: str
    message: str
    target_time: datetime
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ScheduledJob:
    id: str
    command: str
    interval: Optional[float] = None  # None = one-time
    run_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    running: bool = False
    last_output: str = ""
    cancel: bool = False


@dataclass
class BackgroundScript:
    id: str
    name: str
    file_path: str
    process: Optional[subprocess.Popen] = None
    status: str = "stopped"  # running | stopped | crashed
    output: str = ""
    started_at: Optional[datetime] = None
    uptime: float = 0
    auto_restart: bool = True


class SchedulerManager:
    def __init__(self):
        self.reminders: dict[str, Reminder] = {}
        self.scheduled_jobs: dict[str, ScheduledJob] = {}
        self._scheduler_thread = None
        self._lock = threading.Lock()

    def add_reminder(self, message: str, target_time: str) -> dict:
        rid = f"rem_{uuid.uuid4().hex[:8]}"
        dt = datetime.fromisoformat(target_time)
        self.reminders[rid] = Reminder(id=rid, message=message, target_time=dt)
        return {"id": rid, "message": message, "target_time": target_time}

    def list_reminders(self) -> list:
        return [
            {
                "id": r.id,
                "message": r.message,
                "target_time": r.target_time.isoformat(),
                "created_at": r.created_at.isoformat()
            }
            for r in self.reminders.values()
        ]

    def get_due_reminders(self) -> list:
        now = datetime.now()
        due = []
        for rid, r in list(self.reminders.items()):
            if r.target_time <= now:
                due.append({
                    "id": r.id,
                    "message": r.message,
                    "target_time": r.target_time.isoformat()
                })
                del self.reminders[rid]
        return due

    def delete_reminder(self, rid: str) -> bool:
        if rid in self.reminders:
            del self.reminders[rid]
            return True
        return False

    def schedule_job(self, command: str, run_at: str = None, interval: float = None) -> dict:
        job_id = f"sched_{uuid.uuid4().hex[:8]}"
        job = ScheduledJob(
            id=job_id,
            command=command,
            interval=interval,
            run_at=datetime.fromisoformat(run_at) if run_at else None
        )
        self.scheduled_jobs[job_id] = job

        # Start a thread for this job
        def run_job():
            while not job.cancel:
                if job.run_at and datetime.now() < job.run_at:
                    time.sleep(1)
                    continue

                job.running = True
                job.last_run = datetime.now()
                try:
                    result = subprocess.run(
                        job.command, shell=True,
                        capture_output=True, text=True, timeout=3600
                    )
                    job.last_output = result.stdout + result.stderr
                except Exception as e:
                    job.last_output = str(e)
                job.running = False

                if job.interval:
                    time.sleep(job.interval)
                else:
                    break

        t = threading.Thread(target=run_job, daemon=True)
        t.start()
        return {"id": job_id, "command": command, "run_at": run_at, "interval": interval}

    def list_jobs(self) -> list:
        return [
            {
                "id": j.id,
                "command": j.command,
                "interval": j.interval,
                "run_at": j.run_at.isoformat() if j.run_at else None,
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "running": j.running,
                "last_output": j.last_output[:500]
            }
            for j in self.scheduled_jobs.values()
        ]

    def cancel_job(self, job_id: str) -> bool:
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id].cancel = True
            del self.scheduled_jobs[job_id]
            return True
        return False


class ScriptManager:
    """Manages persistent background scripts."""

    def __init__(self):
        self.scripts: dict[str, BackgroundScript] = {}
        self._lock = threading.Lock()

    def register(self, file_path: str, name: str = None) -> dict:
        target = get_workspace_path(file_path)
        if not target.exists():
            return {"error": f"Script file not found: {file_path}"}

        script_id = f"script_{uuid.uuid4().hex[:8]}"
        script_name = name or target.stem
        script = BackgroundScript(id=script_id, name=script_name, file_path=file_path)
        self.scripts[script_id] = script
        self._start(script_id)
        return {"id": script_id, "name": script_name, "status": script.status}

    def _start(self, script_id: str):
        script = self.scripts[script_id]
        target = get_workspace_path(script.file_path)

        # Determine how to run the script
        ext = target.suffix.lower()
        if ext == ".py":
            cmd = ["python", str(target)]
        elif ext == ".js":
            cmd = ["node", str(target)]
        elif ext == ".sh":
            cmd = ["bash", str(target)]
        else:
            cmd = [str(target)]

        try:
            script.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(WORKSPACE_DIR.resolve()),
                env={**os.environ}
            )
            script.status = "running"
            script.started_at = datetime.now()

            # Monitor thread
            def monitor():
                output = ""
                for line in script.process.stdout:
                    output += line
                    script.output = output[-10000:]  # Keep last 10k chars

                script.process.wait()
                if script.process.returncode != 0 and script.auto_restart:
                    script.status = "crashed"
                    time.sleep(2)
                    self._start(script_id)
                else:
                    script.status = "stopped"

            threading.Thread(target=monitor, daemon=True).start()
        except Exception as e:
            script.status = "crashed"
            script.output = str(e)

    def start_script(self, script_id: str) -> dict:
        if script_id not in self.scripts:
            return {"error": "Script not found"}
        self._start(script_id)
        return {"id": script_id, "status": self.scripts[script_id].status}

    def stop_script(self, script_id: str) -> dict:
        if script_id not in self.scripts:
            return {"error": "Script not found"}
        script = self.scripts[script_id]
        if script.process:
            try:
                script.process.kill()
            except:
                pass
        script.status = "stopped"
        return {"id": script_id, "status": "stopped"}

    def list_scripts(self) -> list:
        result = []
        for s in self.scripts.values():
            uptime = 0
            if s.started_at and s.status == "running":
                uptime = (datetime.now() - s.started_at).total_seconds()
            result.append({
                "id": s.id,
                "name": s.name,
                "file": s.file_path,
                "status": s.status,
                "uptime_seconds": round(uptime, 1),
                "output_tail": s.output[-500:]
            })
        return result

    def get_logs(self, script_id: str) -> dict:
        if script_id not in self.scripts:
            return {"error": "Script not found"}
        return {"id": script_id, "output": self.scripts[script_id].output}

    def auto_start_all(self):
        """Start all registered scripts on app boot."""
        for script_id in list(self.scripts.keys()):
            if self.scripts[script_id].status in ("stopped", "crashed"):
                self._start(script_id)


scheduler_manager = SchedulerManager()
script_manager = ScriptManager()
