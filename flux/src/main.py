"""FLUX.2-klein-4B inference service.

Loads the model on demand, generates one image, then explicitly frees
GPU memory before returning — ensuring the iGPU is clear for ACE-Step.
"""

import asyncio
import gc
import os
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="FLUX.2-klein Image Service",
    description="Album cover generation via FLUX.2-klein-4B on ROCm",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/output"))
FLUX_MODEL = os.getenv("FLUX_MODEL", "black-forest-labs/FLUX.2-klein-4B")


class GenerateRequest(BaseModel):
    """Request body for cover image generation."""

    prompt: Annotated[str, Field(description="Image generation prompt")]
    album_id: Annotated[str, Field(description="Album folder name for file placement")]
    width: Annotated[int, Field(default=1024, ge=512, le=2048, description="Image width in pixels")]
    height: Annotated[int, Field(default=1024, ge=512, le=2048, description="Image height in pixels")]
    num_inference_steps: Annotated[int, Field(default=4, ge=1, le=20, description="Diffusion steps (4 recommended for klein)")]
    guidance_scale: Annotated[float, Field(default=1.0, ge=0.0, le=10.0, description="Classifier-free guidance scale")]
    seed: Annotated[int | None, Field(default=None, description="Random seed for reproducibility")]


class GenerateResponse(BaseModel):
    """Response after successful image generation."""

    album_id: Annotated[str, Field(description="Album identifier")]
    file_path: Annotated[str, Field(description="Absolute path to generated image")]
    url_path: Annotated[str, Field(description="Relative URL path to download image")]


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "model": FLUX_MODEL}


@app.post("/generate", tags=["Generation"])
async def generate_cover(req: GenerateRequest) -> GenerateResponse:
    """Generate an album cover image.

    Loads FLUX.2-klein-4B, generates the image, then immediately unloads
    the model and clears GPU memory before returning.

    Args:
        req: Generation parameters including prompt and album_id.

    Returns:
        GenerateResponse with file path and download URL.

    Raises:
        HTTPException 500: If image generation fails.
    """
    album_dir = OUTPUT_DIR / "albums" / req.album_id
    album_dir.mkdir(parents=True, exist_ok=True)
    output_path = album_dir / "cover.png"

    try:
        # Offload heavy blocking work so /health remains responsive.
        await asyncio.to_thread(_generate_image, req, output_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}") from exc

    return GenerateResponse(
        album_id=req.album_id,
        file_path=str(output_path),
        url_path=f"/output/albums/{quote(req.album_id, safe='')}/cover.png",
    )


@app.get("/albums/{album_id}/cover.png", tags=["Files"])
async def get_cover(album_id: str) -> FileResponse:
    """Download a generated album cover.

    Args:
        album_id: Album identifier.

    Returns:
        The PNG image file.

    Raises:
        HTTPException 404: If the cover has not been generated yet.
    """
    path = OUTPUT_DIR / "albums" / album_id / "cover.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover not found")
    return FileResponse(str(path), media_type="image/png")


# ─── Pipeline lifecycle ───────────────────────────────────────────────────────

def _generate_image(req: GenerateRequest, output_path: Path) -> None:
    """Run one full image generation transaction and always release GPU memory."""
    pipeline = None
    try:
        pipeline = _load_pipeline()

        generator = None
        if req.seed is not None:
            generator = torch.Generator(device="cuda").manual_seed(req.seed)

        image = pipeline(
            prompt=req.prompt,
            height=req.height,
            width=req.width,
            guidance_scale=req.guidance_scale,
            num_inference_steps=req.num_inference_steps,
            generator=generator,
        ).images[0]
        image.save(str(output_path))
    finally:
        _unload_pipeline(pipeline)


def _load_pipeline():
    """Load FLUX.2-klein pipeline onto GPU."""
    import diffusers  # type: ignore[import]

    # Newer diffusers versions expose Flux2Pipeline for FLUX.2 models.
    # Avoid AutoPipeline fallback because its lazy import path may pull
    # incompatible optional pipelines in mixed dependency sets.
    candidates = ["Flux2KleinPipeline", "Flux2Pipeline", "FluxPipeline"]
    errors: list[str] = []

    for name in candidates:
        try:
            cls = getattr(diffusers, name, None)
        except Exception as exc:  # pragma: no cover - exercised in container runtime
            errors.append(f"{name} getattr: {exc}")
            continue

        if cls is None:
            continue

        try:
            pipe = cls.from_pretrained(
                FLUX_MODEL,
                torch_dtype=torch.bfloat16,
                low_cpu_mem_usage=False,
            )
            return pipe.to("cuda")
        except Exception as exc:  # pragma: no cover - exercised in container runtime
            errors.append(f"{name}: {exc}")

    raise RuntimeError(
        "Could not load a compatible FLUX pipeline for model "
        f"{FLUX_MODEL}. Tried {candidates}. Errors: {' | '.join(errors)}"
    )


def _unload_pipeline(pipeline) -> None:
    """Delete pipeline and release all GPU memory."""
    if pipeline is not None:
        del pipeline
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
