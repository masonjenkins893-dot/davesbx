"""Workspace file system management."""
import os
import shutil
import json
import zipfile
import time
from pathlib import Path
from datetime import datetime
from config import (
    WORKSPACE_DIR, BACKUPS_DIR, get_workspace_path,
    get_workspace_size, load_config
)

TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".csv", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".mq5", ".mqh", ".html", ".css", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1", ".sql", ".r",
    ".go", ".rs", ".c", ".cpp", ".h", ".java", ".rb", ".php", ".vue",
    ".svelte", ".env", ".gitignore", ".log", ".conf"
}


class WorkspaceManager:

    def save_file(self, path: str, content: str | bytes) -> dict:
        target = get_workspace_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Backup if exists
        if target.exists():
            self._backup_file(path)
        if isinstance(content, bytes):
            with open(target, "wb") as f:
                f.write(content)
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
        return {"path": path, "size": target.stat().st_size, "saved": True}

    def read_file(self, path: str, as_text: bool = False) -> dict:
        target = get_workspace_path(path)
        if not target.exists():
            return {"error": "File not found"}
        ext = target.suffix.lower()
        if as_text or ext in TEXT_EXTENSIONS:
            if ext == ".pdf":
                # Extract text from PDF
                try:
                    import subprocess
                    result = subprocess.run(
                        ["pdftotext", str(target), "-"],
                        capture_output=True, text=True
                    )
                    return {"path": path, "content": result.stdout, "type": "text"}
                except:
                    return {"path": path, "content": "[PDF text extraction failed]", "type": "text"}
            with open(target, "r", encoding="utf-8") as f:
                return {"path": path, "content": f.read(), "type": "text"}
        else:
            return {"path": path, "raw": True, "file_path": str(target), "type": "binary"}

    def delete_file(self, path: str) -> dict:
        target = get_workspace_path(path)
        if not target.exists():
            return {"error": "File not found"}
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"deleted": True, "path": path}

    def delete_batch(self, paths: list) -> dict:
        results = []
        for p in paths:
            result = self.delete_file(p)
            results.append({"path": p, "result": result})
        return {"deleted": results}

    def rename_file(self, path: str, new_name: str) -> dict:
        target = get_workspace_path(path)
        if not target.exists():
            return {"error": "File not found"}
        new_path = target.parent / new_name
        target.rename(new_path)
        return {"renamed": True, "old_path": path, "new_path": str(new_path.relative_to(WORKSPACE_DIR.resolve()))}

    def move_file(self, src: str, dest: str) -> dict:
        src_path = get_workspace_path(src)
        dest_path = get_workspace_path(dest)
        if not src_path.exists():
            return {"error": "Source not found"}
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest_path))
        return {"moved": True, "from": src, "to": dest}

    def move_batch(self, items: list) -> dict:
        results = []
        for item in items:
            result = self.move_file(item["from"], item["to"])
            results.append({"from": item["from"], "result": result})
        return {"moved": results}

    def search_files(self, path: str, query: str) -> list:
        target = get_workspace_path(path)
        results = []
        if target.is_dir():
            for f in target.rglob("*"):
                if f.is_file() and query.lower() in f.name.lower():
                    results.append(str(f.relative_to(WORKSPACE_DIR.resolve())))
                    # Also search content for text files
                if f.is_file() and f.suffix.lower() in TEXT_EXTENSIONS:
                    try:
                        content = f.read_text(encoding="utf-8")
                        if query.lower() in content.lower():
                            results.append(str(f.relative_to(WORKSPACE_DIR.resolve())))
                    except:
                        pass
        else:
            if target.is_file() and target.suffix.lower() in TEXT_EXTENSIONS:
                try:
                    content = target.read_text(encoding="utf-8")
                    matches = [line for line in content.split("\n") if query.lower() in line.lower()]
                    if matches:
                        results.append({"path": path, "matches": matches})
                except:
                    pass
        return list(set(results))

    def list_files_flat(self) -> list:
        workspace = WORKSPACE_DIR.resolve()
        files = []
        for f in workspace.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(workspace))
                files.append({
                    "path": rel,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
        return files

    def list_files_tree(self) -> dict:
        workspace = WORKSPACE_DIR.resolve()

        def build_tree(path: Path) -> dict:
            node = {
                "name": path.name,
                "path": str(path.relative_to(workspace)) if path != workspace else "",
                "type": "directory" if path.is_dir() else "file",
                "size": path.stat().st_size if path.is_file() else 0
            }
            if path.is_dir():
                children = []
                for child in sorted(path.iterdir()):
                    if child.name.startswith("."):
                        continue
                    children.append(build_tree(child))
                node["children"] = children
            return node

        return build_tree(workspace)

    def create_folder(self, path: str) -> dict:
        target = get_workspace_path(path)
        target.mkdir(parents=True, exist_ok=True)
        return {"created": True, "path": path}

    def zip_files(self, paths: list, output_path: str) -> dict:
        output = get_workspace_path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in paths:
                target = get_workspace_path(p)
                if target.is_file():
                    zf.write(target, p)
                elif target.is_dir():
                    for f in target.rglob("*"):
                        if f.is_file():
                            zf.write(f, str(f.relative_to(WORKSPACE_DIR.resolve())))
        return {"zipped": True, "output": output_path, "size": output.stat().st_size}

    def unzip_file(self, path: str, dest: str = "") -> dict:
        target = get_workspace_path(path)
        if not target.exists():
            return {"error": "Archive not found"}
        dest_dir = get_workspace_path(dest) if dest else target.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "r") as zf:
            zf.extractall(dest_dir)
        return {"unzipped": True, "path": path, "destination": dest or str(target.parent)}

    def export_workspace(self) -> str:
        """Returns path to a zip of the entire workspace."""
        export_path = BACKUPS_DIR / f"workspace_export_{int(time.time())}.zip"
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
            workspace = WORKSPACE_DIR.resolve()
            for f in workspace.rglob("*"):
                if f.is_file():
                    zf.write(f, str(f.relative_to(workspace)))
        return str(export_path)

    def reset_workspace(self) -> dict:
        workspace = WORKSPACE_DIR.resolve()
        for item in workspace.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        return {"reset": True}

    def _backup_file(self, path: str):
        target = get_workspace_path(path)
        if not target.exists():
            return
        backup_dir = BACKUPS_DIR / path.replace("/", "_")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        backup_path = backup_dir / f"v_{timestamp}"
        shutil.copy2(target, backup_path)
        return backup_path

    def get_versions(self, path: str) -> list:
        backup_dir = BACKUPS_DIR / path.replace("/", "_")
        if not backup_dir.exists():
            return []
        versions = []
        for v in sorted(backup_dir.iterdir(), reverse=True):
            versions.append({
                "version_id": v.name,
                "timestamp": v.stat().st_mtime,
                "size": v.stat().st_size
            })
        return versions

    def get_version(self, path: str, version_id: str) -> dict:
        backup_dir = BACKUPS_DIR / path.replace("/", "_")
        version_path = backup_dir / version_id
        if not version_path.exists():
            return {"error": "Version not found"}
        with open(version_path, "r", encoding="utf-8") as f:
            return {"path": path, "version_id": version_id, "content": f.read()}

    def get_storage_status(self) -> dict:
        cfg = load_config()
        size_bytes = get_workspace_size()
        limit_bytes = cfg.get("storage_limit_gb", 10) * 1024 * 1024 * 1024
        return {
            "used_bytes": size_bytes,
            "limit_bytes": limit_bytes,
            "used_gb": round(size_bytes / (1024**3), 3),
            "limit_gb": cfg.get("storage_limit_gb", 10),
            "percentage": round((size_bytes / limit_bytes) * 100, 2) if limit_bytes > 0 else 0,
            "warning": size_bytes > limit_bytes * 0.9
        }


workspace_manager = WorkspaceManager()
