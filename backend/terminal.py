"""Terminal engine using subprocess (node-pty on Windows build)."""
import subprocess
import threading
import time
import uuid
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# OSC 633 escape sequences (VS Code shell integration)
OSC_CMD_START = "\x1b]633;A"
OSC_CMD_END = "\x1b]633;B"
OSC_CMD_EXIT = "\x1b]633;C="


@dataclass
class Command:
    id: str
    terminal_id: str
    command: str
    status: str = "running"  # running | done | failed
    output: str = ""
    exit_code: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    process: Optional[subprocess.Popen] = None


@dataclass
class Terminal:
    id: str
    output_history: str = ""
    commands: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class TerminalManager:
    def __init__(self):
        self.terminals: dict[str, Terminal] = {}
        self.commands: dict[str, Command] = {}
        self._lock = threading.Lock()

    def create_terminal(self) -> str:
        term_id = f"term_{len(self.terminals) + 1}"
        self.terminals[term_id] = Terminal(id=term_id)
        return term_id

    def list_terminals(self) -> list:
        return [
            {
                "id": t.id,
                "created_at": t.created_at,
                "command_count": len(t.commands),
                "active_commands": sum(1 for c in t.commands if c.status == "running")
            }
            for t in self.terminals.values()
        ]

    def delete_terminal(self, term_id: str) -> bool:
        if term_id not in self.terminals:
            return False
        # Kill any running commands
        for cmd in self.terminals[term_id].commands:
            if cmd.status == "running" and cmd.process:
                try:
                    cmd.process.kill()
                except:
                    pass
                cmd.status = "failed"
                cmd.exit_code = -1
                cmd.finished_at = time.time()
        del self.terminals[term_id]
        return True

    def get_terminal_output(self, term_id: str) -> str:
        if term_id not in self.terminals:
            return ""
        return self.terminals[term_id].output_history

    def run_command(self, term_id: str, command: str) -> dict:
        with self._lock:
            if term_id not in self.terminals:
                return {"error": f"Terminal {term_id} not found"}

            terminal = self.terminals[term_id]

            # Check concurrency — is another command already running?
            running = [c for c in terminal.commands if c.status == "running"]
            if running:
                return {
                    "error": "A command is already running in this terminal",
                    "running_command": running[0].id,
                    "running_command_text": running[0].command,
                    "options": ["stop", "new_terminal", "queue"]
                }

            cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
            cmd = Command(id=cmd_id, terminal_id=term_id, command=command)

            try:
                # Emit OSC start sequence
                terminal.output_history += f"{OSC_CMD_START}\r\n"
                terminal.output_history += f"$ {command}\r\n"

                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    cwd=os.getcwd(),
                    env={**os.environ, "PS1": "$ "}
                )
                cmd.process = process
                self.commands[cmd_id] = cmd
                terminal.commands.append(cmd)

                # Read output in a thread
                def read_output():
                    output = ""
                    for line in process.stdout:
                        output += line
                        terminal.output_history += line
                        cmd.output += line

                    process.wait()
                    cmd.exit_code = process.returncode
                    cmd.finished_at = time.time()
                    cmd.status = "done" if process.returncode == 0 else "failed"
                    terminal.output_history += f"{OSC_CMD_END}\r\n{OSC_CMD_EXIT}{cmd.exit_code}\r\n"

                t = threading.Thread(target=read_output, daemon=True)
                t.start()
                cmd.process_thread = t

                return {
                    "command_id": cmd_id,
                    "terminal_id": term_id,
                    "status": "running",
                    "message": f"Command started: {command}"
                }

            except Exception as e:
                cmd.status = "failed"
                cmd.finished_at = time.time()
                cmd.exit_code = -1
                self.commands[cmd_id] = cmd
                terminal.commands.append(cmd)
                return {"error": str(e), "command_id": cmd_id, "status": "failed"}

    def stop_command(self, cmd_id: str) -> bool:
        if cmd_id not in self.commands:
            return False
        cmd = self.commands[cmd_id]
        if cmd.status != "running":
            return False
        if cmd.process:
            try:
                cmd.process.kill()
            except:
                pass
        cmd.status = "failed"
        cmd.exit_code = -1
        cmd.finished_at = time.time()
        return True

    def get_command_status(self, cmd_id: str) -> dict:
        if cmd_id not in self.commands:
            return {"error": "Command not found"}
        cmd = self.commands[cmd_id]
        return {
            "id": cmd.id,
            "command": cmd.command,
            "status": cmd.status,
            "exit_code": cmd.exit_code,
            "started_at": cmd.started_at,
            "finished_at": cmd.finished_at
        }

    def get_command_output(self, cmd_id: str) -> str:
        if cmd_id not in self.commands:
            return ""
        return self.commands[cmd_id].output

    def send_input(self, cmd_id: str, data: str) -> bool:
        if cmd_id not in self.commands:
            return False
        cmd = self.commands[cmd_id]
        if cmd.status != "running" or not cmd.process:
            return False
        try:
            cmd.process.stdin.write(data + "\n")
            cmd.process.stdin.flush()
            return True
        except:
            return False

    def get_running_commands(self) -> list:
        return [
            {
                "id": cmd.id,
                "terminal_id": cmd.terminal_id,
                "command": cmd.command,
                "started_at": cmd.started_at
            }
            for cmd in self.commands.values()
            if cmd.status == "running"
        ]


terminal_manager = TerminalManager()
