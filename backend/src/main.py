"""AI Music Studio — FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core.config import settings
from src.core.db import backfill_from_storage, init_db
from src.routes.album import router as album_router
from src.routes.health import router as health_router

app = FastAPI(
    title="AI Music Studio API",
    description=(
        "End-to-end AI album generation: Ollama (LLM) → FLUX.2-klein (cover art) → "
        "ACE-Step 1.5 (music). All inference runs sequentially on AMD ROCm TheRock."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(album_router, prefix="/api")


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    backfill_from_storage(settings.output_dir)

output_dir = Path(settings.output_dir)
try:
    output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")
except (PermissionError, OSError):
    # /output doesn't exist locally (only inside Docker) — skip static mount
    pass
