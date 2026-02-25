"""Health check route."""

from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Service liveness probe."""
    return {"status": "ok", "service": "ai-music-studio-backend"}
