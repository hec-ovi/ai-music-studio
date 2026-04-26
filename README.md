<h1 align="center">ai-music-studio</h1>

<p align="center">
  <strong>Local AI album generation on AMD ROCm: LLM album plan + ACE-Step 1.5 tracks + FLUX cover art, with SSE-streamed progress and YouTube-ready exports.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Working-brightgreen" alt="Status" />
  <img src="https://img.shields.io/badge/AMD-ROCm-ED1C24?logo=amd&logoColor=white" alt="ROCm" />
  <img src="https://img.shields.io/badge/ACE--Step-1.5-9B59B6" alt="ACE-Step" />
  <img src="https://img.shields.io/badge/FLUX-2_klein_4B-FF6B6B" alt="FLUX" />
  <img src="https://img.shields.io/badge/Ollama-111111?logo=ollama&logoColor=white" alt="Ollama" />
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License" />
</p>

---

## What this is

`ai-music-studio` turns one concept into a complete album pipeline:
- LLM album planning
- song-by-song music generation
- optional cover generation
- real-time streaming progress
- persistent session library
- MP3 + MP4 + YouTube-ready export artifacts

Everything runs locally in Docker.

## Why This Repo

- **End-to-end album generation** from a single prompt
- **Two workflows**:
  - `Auto`: plan -> songs -> cover -> done
  - `Review`: plan -> edit/approve -> songs -> cover -> done
- **Live UX** with SSE status + per-track playback/download as tracks finish
- **Resume-safe** with SQLite-backed session history
- **Export-ready** output for publishing workflows

## Tech Stack

### Core Platform
- Docker Compose (multi-service orchestration)
- FastAPI backend (orchestration + SSE + persistence)
- SQLite session DB (`output/studio.db`)

### AI/Inference
- Ollama (`gpt-oss:20b`) for planning
- ACE-Step 1.5 for music generation
- FLUX.2-klein-4B for album cover generation
- PyTorch ROCm/HIP (AMD GPU path)
- diffusers + transformers + accelerate

### Frontend
- React 19
- Vite 7
- Zustand
- Framer Motion
- Tailwind v4

### API/Docs
- OpenAPI: `/openapi.json`
- Swagger: `/docs`
- ReDoc: `/redoc`

## Architecture

```text
Frontend (React)
  -> FastAPI backend (SSE orchestration)
    -> Ollama (album plan JSON)
    -> ACE-Step (track generation, sequential)
    -> FLUX (optional cover)
  -> output/albums/<Album Name>/
  -> output/studio.db
```

## Features

- Plan generation with strict JSON guardrails + repair fallback
- Plan review/edit before rendering (album fields + per-song prompts)
- Song length control (`30..420s`)
- Optional cover mode (`include_cover=true|false`)
- Cover size options (`512` / `1024`)
- Session library (`GET /api/albums`) for history + resume
- Per-track MP4 export (static cover + AAC audio)
- YouTube package export:
  - `youtube_manifest.json`
  - `youtube_upload_template.py`
  - `YOUTUBE_UPLOAD.md`

## Quick Start

```bash
git clone https://github.com/your-org/ai-music-studio.git
cd ai-music-studio
cp .env.template .env
# edit .env host paths
docker compose up -d --build
```

Open:
- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/redoc`

## Configuration

Set these in `.env`:

### Required host paths
- `OLLAMA_MODELS_DIR`
- `HF_CACHE_DIR`
- `ACESTEP_CHECKPOINTS_DIR`
- `OUTPUT_DIR`

### Ports/models
- `OLLAMA_MODEL` (default: `gpt-oss:20b`)
- `ACESTEP_MODEL` (default: `acestep-v15-turbo`)
- `ACESTEP_PORT` (default: `8001`)
- `FLUX_PORT` (default: `8002`)
- `BACKEND_PORT` (default: `8000`)
- `FRONTEND_PORT` (default: `5173`)
- `VITE_API_URL` (default: `http://localhost:8000`)

## API Overview

### Album lifecycle

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/albums` | Create album request (`album_id`) |
| `GET` | `/api/albums/{album_id}/stream` | SSE generation stream |
| `GET` | `/api/albums/{album_id}/result` | Final album payload |

### Plan review/edit

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/albums/{album_id}/plan` | Fetch editable plan |
| `PUT` | `/api/albums/{album_id}/plan` | Save edited plan |

### Session library

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/albums` | List persisted sessions |
| `GET` | `/api/albums/{album_id}/session` | Full session detail |

### Export

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/albums/{album_id}/exports/mp4` | Export one MP4 per song |
| `POST` | `/api/albums/{album_id}/exports/youtube-package` | Export YouTube package files |

## SSE Events

Main event types:
- `planning`
- `plan_ready`
- `plan_review_required`
- `song_start`
- `song_progress`
- `song_ready`
- `cover_generating`
- `cover_ready`
- `complete`
- `error`

## Output Layout

```text
output/
  studio.db
  albums/
    Tideleaf Reverie/
      plan.json
      cover.png
      01_Bamboo Dawn Mist.mp3
      01_Bamboo Dawn Mist.mp4
      ...
      mp4_index.json
      youtube_manifest.json
      youtube_upload_template.py
      YOUTUBE_UPLOAD.md
```

Notes:
- Folder names are sanitized.
- Name collisions auto-suffix (e.g. `Album (2)`).

## Frontend UX

- Minimal creator page with generation settings
- Live generation monitor with per-track controls
- Plan review editor before render
- Session library panel (open/resume/export)
- Result page with playback + export actions

## YouTube Pipeline Status

Implemented now:
- MP4 render per track
- structured metadata manifest export
- upload template script + operator notes

Still pending for full automation:
- OAuth credentials + actual `videos.insert` / playlist API calls

Useful docs:
- `https://developers.google.com/youtube/v3/docs/videos/insert`
- `https://developers.google.com/youtube/v3/docs/thumbnails/set`
- `https://developers.google.com/youtube/v3/docs/playlistItems/insert`

## Development

### Backend (local dev)

```bash
cd backend
uv run uvicorn src.main:app --reload --reload-dir src
```

### Frontend (local dev)

```bash
cd frontend
npm run dev
```

### Checks

```bash
python -m compileall -q backend/src backend/tests flux/src
cd backend && python -m unittest discover -s tests -v
cd frontend && npm run build
```

## Troubleshooting

- `ERR_INCOMPLETE_CHUNKED_ENCODING`:
  - stream ended unexpectedly; inspect backend + inference logs together.
- `ImportError: libgomp.so.1`:
  - missing runtime libs in container image.
- `MIOpen ... workspace required ... provided ...`:
  - not a crash; ROCm skipped a high-workspace solver and used a fallback kernel.
  - typically performance impact only.

## License

[MIT](LICENSE) for original code in this repository (FastAPI orchestration backend, React frontend, Compose configs, scripts).

Third-party model weights and runtimes downloaded or invoked at runtime retain their own upstream licenses, including:
- ACE-Step 1.5 (check upstream terms before commercial release)
- FLUX.2-klein-4B (check upstream terms before commercial release)
- Ollama runtime (MIT) and any models pulled through it (per-model license)
- diffusers, transformers, accelerate (Apache 2.0)
- PyTorch ROCm (BSD-3-Clause)

This repository does not redistribute model weights. Anything you generate with this stack is subject to the terms of the specific model that produced it; verify those terms before publishing or monetizing the output.
