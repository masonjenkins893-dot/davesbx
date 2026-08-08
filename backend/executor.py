"""Code execution engine with persistent sessions."""
import sys
import io
import time
import traceback
import resource
from typing import Any


class ExecutionEngine:
    """Persistent Python execution session — variables stay alive between calls."""

    def __init__(self):
        self._global_ns: dict = {"__builtins__": __builtins__}
        self._local_ns: dict = {}

    def execute(self, code: str, language: str = "python") -> dict:
        if language != "python":
            return {"error": f"Language '{language}' not yet supported. Only Python is available."}

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        sys.stdout = stdout_buf
        sys.stderr = stderr_buf

        start_time = time.time()
        start_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        result = None
        error = None
        try:
            # Try eval first (for expressions), then exec (for statements)
            try:
                result = eval(code, self._global_ns, self._local_ns)
            except SyntaxError:
                exec(code, self._global_ns, self._local_ns)
        except Exception as e:
            error = traceback.format_exc()

        end_time = time.time()
        end_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        return {
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "result": str(result) if result is not None else None,
            "error": error,
            "execution_time_ms": round((end_time - start_time) * 1000, 2),
            "memory_used_mb": round((end_mem - start_mem) / 1024, 2) if end_mem > start_mem else 0
        }

    def debug(self, code: str, breakpoints: list = None) -> dict:
        """Run code with breakpoints, stepping through execution."""
        # Use Python's pdb programmatically
        import pdb
        old_stdout = sys.stdout
        stdout_buf = io.StringIO()
        sys.stdout = stdout_buf

        steps = []

        class StepCollector(pdb.Pdb):
            def user_line(self, frame):
                filename = frame.f_code.co_filename
                lineno = frame.f_lineno
                local_vars = {k: repr(v) for k, v in frame.f_locals.items() if not k.startswith("_")}
                steps.append({
                    "file": filename,
                    "line": lineno,
                    "variables": local_vars
                })
                if breakpoints and lineno not in breakpoints:
                    self.set_continue()
                else:
                    self.set_step()

        try:
            debugger = StepCollector(stdout=stdout_buf)
            debugger.run(code, self._global_ns, self._local_ns)
        except Exception as e:
            sys.stdout = old_stdout
            return {"error": traceback.format_exc(), "steps": steps}

        sys.stdout = old_stdout
        return {
            "stdout": stdout_buf.getvalue(),
            "steps": steps,
            "breakpoints": breakpoints or []
        }

    def reset(self):
        """Clear the execution session."""
        self._global_ns = {"__builtins__": __builtins__}
        self._local_ns = {}
        return {"reset": True}


execution_engine = ExecutionEngine()
