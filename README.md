# DAVESBX — Sandbox Console

A persistent sandbox console for a single AI agent, packaged as a standalone Windows `.exe`. Think e2b-style code sandbox, but running locally on a Windows VPS with a FastAPI layer in front of it.

## Quick Start

1. Download the latest `.exe` installer from [Releases](../../releases)
2. Run the installer — no setup wizard, no configuration needed
3. On first launch, DAVESBX:
   - Auto-generates a public URL (FastAPI on `0.0.0.0:8420`)
   - Auto-generates an API key
   - Opens to the dashboard
4. Copy the URL and API key from the top bar — give them to your AI agent

## Architecture

```
┌─────────────────────────────────┐
│  Tauri Desktop App (UI)         │  ← Glassmorphism React frontend
│  ├─ Dashboard (files + terminal)│
│  ├─ Logs                        │
│  └─ Settings                    │
├─────────────────────────────────┤
│  FastAPI Backend (sidecar)      │  ← PyInstaller-bundled .exe
│  ├─ Terminal engine             │
│  ├─ Workspace filesystem        │
│  ├─ Code execution engine       │
│  ├─ Video processing            │
│  ├─ Scheduling & reminders       │
│  ├─ Background scripts           │
│  └─ Activity logging            │
└─────────────────────────────────┘
```

## API Endpoints

Full interactive docs available at `http://localhost:8420/docs` when the app is running.

### Terminal
- `POST /terminal/new` — open a new terminal
- `POST /terminal/{id}/run` — run a command
- `GET /terminal/{id}/output` — get output
- `GET /terminals` — list all terminals
- `DELETE /terminal/{id}` — close a terminal
- `POST /command/{id}/stop` — stop a running command
- `GET /command/{id}/status` — check command status
- `POST /command/{id}/input` — send stdin input
- `GET /commands/running` — list all active commands

### Workspace Files
- `POST /file/save` — create/write any file type
- `PUT /file/{path}` — edit a file
- `GET /file/{path}` — read/download a file (raw or text)
- `GET /files` — flat file list
- `GET /files/tree` — nested folder tree
- `POST /file/upload` — upload a file
- `DELETE /file/{path}` — delete a file
- `POST /file/delete_batch` — batch delete
- `POST /file/{path}/rename` — rename
- `POST /file/move` / `POST /file/move_batch` — move files
- `GET /file/{path}/search` — search by name/content
- `GET /file/{path}/versions` — list backup versions
- `POST /folder` — create a folder
- `POST /archive/zip` / `POST /archive/unzip` — zip/unzip
- `GET /workspace/export` — export workspace as zip
- `POST /reset` — wipe workspace

### Video
- `POST /video/process/{path}` — scene-aware keyframe extraction + transcript
- `GET /video/{path}/frames` — list extracted keyframes
- `GET /video/{path}/transcript` — get timestamped transcript

### Code Execution
- `POST /execute` — run code (Python first, persistent session)
- `POST /debug` — debug with breakpoints

### Environment
- `POST /packages/install` — install pip/npm packages
- `GET/POST /env` — get/set environment variables
- `GET /status` — CPU, RAM, disk, workspace size
- `GET /whoami` — workspace path, API URL, full file listing
- `GET /processes` — list running processes
- `GET /ping` — health check (no auth)

### Time
- `GET /time` — current time (timezone-aware)

### Reminders
- `POST /reminder` — set a reminder
- `GET /reminder` — list active reminders
- `GET /reminder/due` — check what's due
- `DELETE /reminder/{id}` — cancel

### Scheduling
- `POST /schedule` — schedule a command (one-time or repeating)
- `GET /schedule` — list scheduled jobs
- `DELETE /schedule/{id}` — cancel

### Background Scripts
- `POST /script/register` — register & start a persistent script
- `GET /scripts` — list all scripts with status
- `POST /script/{id}/start` — start/restart
- `POST /script/{id}/stop` — stop
- `GET /script/{id}/logs` — view output

### Logs
- `GET /logs` — full activity history
- `GET /logs/errors` — errors only

### Config
- `GET /config` — current settings
- `POST /config` — update settings
- `POST /config/regenerate-key` — new API key
- `POST /config/toggle-auth` — enable/disable auth
- `POST /app/restart` — restart DAVESBX

## Public URL Modes

| Mode | Setup | URL Format |
|------|-------|------------|
| FastAPI (default) | None | `http://your-vps-ip:8420` |
| Cloudflare Tunnel | CF API token + domain | `https://sandbox.yourdomain.com` or `*.trycloudflare.com` |
| Supabase Edge | Supabase token + project ref | `https://[ref].supabase.co/functions/v1/davesbx-sandbox` |

## Build from Source

```bash
# Frontend
cd frontend && npm install && npm run build

# Backend (on Windows)
pip install -r backend/requirements.txt
pip install pyinstaller
pyinstaller davesbx-backend.spec

# Full app (on Windows with Rust + Tauri)
npx tauri build
```

Or just push to the repo — GitHub Actions builds automatically and publishes the `.exe` to Releases.

## License

MIT
