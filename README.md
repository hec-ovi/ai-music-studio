# AI Music Studio

Production-style local AI album generation on AMD ROCm (Strix Halo / gfx1151):
- concept planning (LLM)
- multi-track music generation
- optional album cover generation
- live progress streaming to frontend
- per-track playback and download
- editable plan review before rendering
- persistent album/session library (SQLite)
- one-click MP4 export (cover + track audio)
- YouTube upload package export (manifest + template script)

Everything runs locally in Docker containers.

## What This System Delivers

- End-to-end album creation from one prompt.
- Two generation modes:
  - `Auto`: concept -> plan -> songs -> cover -> complete.
  - `Review`: concept -> plan pause -> manual plan edits -> approve -> songs -> cover -> complete.
- Song-by-song progress events (SSE) and incremental track availability.
- Configurable approximate song length at creation time.
- Optional cover generation (`include_cover=true|false`).
- Selectable cover size (`cover_size=512|1024`).
- ROCm-compatible music/image inference on AMD iGPU.
- Deterministic fallback planning when LLM JSON output is malformed.
- Persistent album/session history in a tiny local SQLite DB.
- Album library navigation after restarts (no lost sessions).
- Export pipeline:
  - per-track MP4 rendering from cover + MP3
  - YouTube package artifacts (`youtube_manifest.json`, uploader template, instructions)

## Stack (Full, Pro-Level)

- Orchestration:
  - Docker Compose (5 services)
  - FastAPI backend (SSE, orchestration, persistence)
- Planning / language:
  - Ollama
  - `gpt-oss:20b`
- Music inference:
  - ACE-Step 1.5 (turbo path)
  - PyTorch ROCm / HIP
  - Per-song prompt + optional CoT enhancement flags
- Image inference:
  - FLUX.2-klein-4B
  - diffusers + transformers + accelerate
  - Runtime load/generate/unload behavior
- Frontend:
  - React 19
  - Vite 7
  - Zustand state
  - Framer Motion
  - Tailwind v4
- Data / API:
  - OpenAPI (`/openapi.json`)
  - Swagger (`/docs`)
  - ReDoc (`/redoc`)
  - Server-Sent Events for generation stream
  - SQLite session DB (`output/studio.db`)

## High-Impact Capabilities

- Plan review + approval:
  - pause after planning
  - edit album metadata + cover prompt + per-song prompts/lyrics/meta
  - approve and resume generation from saved plan
- Output organization:
  - one album folder per generated album name
  - `cover.png` and `NN_<TrackName>.mp3` in the same folder
- Session persistence:
  - all albums indexed in SQLite
  - list/detail APIs for historical navigation
- Export pipeline:
  - MP4 per track (`NN_<TrackName>.mp4`)
  - YouTube package artifacts inside album folder
- Frontend generation UX:
  - animated progress state
  - real-time status
  - play/download controls as tracks complete

## Prerequisites

- Ubuntu 25.10+ (kernel/driver stack compatible with ROCm for your hardware)
- AMD Strix Halo class device (gfx1151 target in this repo)
- Docker + Compose plugin
- Sufficient unified memory/VRAM headroom (64GB+ recommended, 128GB ideal)

## Quick Start

```bash
git clone https://github.com/your-org/ai-music-studio.git
cd ai-music-studio

cp .env.template .env
# edit .env and set host directories

docker compose up -d --build
```

Open:
- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/redoc`

## Configuration (`.env`)

Required host-path variables:

- `OLLAMA_MODELS_DIR`: Ollama model storage
- `HF_CACHE_DIR`: Hugging Face cache for FLUX/ACE-Step assets
- `ACESTEP_CHECKPOINTS_DIR`: ACE-Step checkpoints path
- `OUTPUT_DIR`: generated output root

Port/config variables:

- `ACESTEP_PORT` (default `8001`)
- `FLUX_PORT` (default `8002`)
- `BACKEND_PORT` (default `8000`)
- `FRONTEND_PORT` (default `5173`)
- `VITE_API_URL` (default `http://localhost:8000`)

## API (Core)

### Album lifecycle

- `POST /api/albums`
  - create a new album request
  - returns `{ album_id, status }`

- `GET /api/albums/{album_id}/stream`
  - SSE stream for generation
  - query params:
    - `concept` (required unless `use_saved_plan=true`)
    - `num_songs` (1..12)
    - `song_length_seconds` (30..420, optional)
    - `include_cover` (`true|false`)
    - `cover_size` (`512|1024`)
    - `stop_after_plan` (`true|false`)
    - `use_saved_plan` (`true|false`)

- `GET /api/albums/{album_id}/result`
  - fetch final result object

- `GET /api/albums`
  - list persisted album sessions (library)

- `GET /api/albums/{album_id}/session`
  - full persisted session detail (songs + exports)

### Plan review/edit

- `GET /api/albums/{album_id}/plan`
  - fetch full editable plan

- `PUT /api/albums/{album_id}/plan`
  - update full editable plan before song generation starts

### Export APIs

- `POST /api/albums/{album_id}/exports/mp4`
  - render one MP4 per generated song (static cover + song audio)

- `POST /api/albums/{album_id}/exports/youtube-package`
  - generate YouTube metadata package artifacts

## SSE Events

Typical stream sequence (auto mode):

```jsonc
{ "event": "planning", "progress": 0.05, "data": null }
{ "event": "plan_ready", "progress": 0.15, "data": { "album_name": "...", "songs": [...] } }
{ "event": "song_start", "progress": 0.20, "data": { "index": 0, "name": "..." } }
{ "event": "song_ready", "progress": 0.70, "data": { "index": 0, "audio_url": "..." } }
{ "event": "cover_generating", "progress": 0.93, "data": null }
{ "event": "cover_ready", "progress": 0.98, "data": { "cover_url": "..." } }
{ "event": "complete", "progress": 1.0, "data": { "album_id": "...", "songs": [...] } }
```

Review mode adds:

```jsonc
{ "event": "plan_review_required", "progress": 0.17, "data": { "album_id": "..." } }
```

## Output Layout

Output is consolidated under one album folder (human-readable album name):

```text
output/
  albums/
    Zen Flute Temple/
      plan.json
      cover.png
      01_Morning Mist.mp3
      01_Morning Mist.mp4
      mp4_index.json
      youtube_manifest.json
      youtube_upload_template.py
      YOUTUBE_UPLOAD.md
      02_...
  studio.db
```

Notes:
- Folder names are sanitized for filesystem safety.
- Name collisions are handled with numeric suffixes (e.g. `Album Name (2)`).

## Frontend UX Summary

- Album creator:
  - concept input
  - song count
  - approximate song length control
  - cover toggle
  - cover size selector (`512`/`1024`)
  - plan review toggle
  - library panel with persisted sessions and quick actions
- Generation progress:
  - animated stage indicators
  - per-song readiness badges
  - inline audio playback
  - one-click download per track
- Plan review screen:
  - album name/description editing
  - cover prompt editing
  - per-song prompt/lyrics/tempo/duration editing

## YouTube Pipeline Feasibility (Planned)

Yes, this is feasible.

### What YouTube API supports

- Upload videos: `videos.insert`
- Set metadata (title, description, tags, privacy): `snippet` + `status` fields
- Set per-video thumbnail (your generated cover): `thumbnails.set`
- Create playlist: `playlists.insert`
- Add uploaded videos to playlist in order: `playlistItems.insert`

### Practical implementation pattern for this repo

1. For each generated `.mp3`, render a static-cover `.mp4` (FFmpeg).
2. Upload each `.mp4` with song title/description.
3. Apply the generated album cover as video thumbnail.
4. Create playlist named with album name.
5. Insert each uploaded video in album order.

### Compliance / policy considerations

- AI/synthetic content:
  - YouTube requires disclosure in certain cases (see “altered or synthetic content” policy).
  - API supports `status.containsSyntheticMedia` in video status metadata.
- Monetization:
  - Reused/low-transform content can fail YPP monetization review.
  - If monetization is a goal, add meaningful transformation and value.
- Quota:
  - Upload-related methods consume quota units; design retries and batching carefully.

### Official docs

- Videos upload: `videos.insert`  
  `https://developers.google.com/youtube/v3/docs/videos/insert`
- Set thumbnail: `thumbnails.set`  
  `https://developers.google.com/youtube/v3/docs/thumbnails/set`
- Playlist items: `playlistItems.insert`  
  `https://developers.google.com/youtube/v3/docs/playlistItems/insert`
- Quota costs:  
  `https://developers.google.com/youtube/v3/determine_quota_cost`
- Altered/synthetic content disclosure:  
  `https://support.google.com/youtube/answer/14328491`
- Monetization policy references:  
  `https://support.google.com/youtube/answer/1311392`

## Development

Backend:

```bash
cd backend
uv run uvicorn src.main:app --reload --reload-dir src
```

Frontend:

```bash
cd frontend
npm run dev
```

Type/build checks:

```bash
python -m compileall -q backend/src backend/tests flux/src
cd backend && python -m unittest discover -s tests -v
cd frontend && npm run build
```

## Troubleshooting Notes

- `ERR_INCOMPLETE_CHUNKED_ENCODING`:
  - usually indicates stream termination from backend exception or upstream disconnect.
  - check backend + inference container logs together.
- Missing shared libs in containers (`libgomp.so.1`, etc.):
  - ensure Dockerfile runtime deps include required system libraries.
- ROCm model/toolchain fallback warnings:
  - some ACE-Step paths may fall back from Triton/Inductor to PyTorch backend while still using GPU.
