"""Cover generation service — calls FLUX.2-klein, GPU is cleared on return."""

from src.core.exceptions import CoverGenerationError
from src.core.storage import album_folder, cover_path, cover_public_url
from src.tools.flux import FluxTool


class CoverService:
    """Generates album cover art via the FLUX.2-klein inference service."""

    def __init__(self, flux: FluxTool) -> None:
        self._flux = flux

    async def generate(self, cover_prompt: str, album_id: str, size: int = 1024) -> str:
        """Generate and save album cover, return public URL path.

        Args:
            cover_prompt: FLUX image generation prompt.
            album_id: Album identifier for file placement.
            size: Square image size (512 or 1024).

        Returns:
            Relative URL path to the generated cover image.

        Raises:
            CoverGenerationError: If FLUX generation fails.
        """
        await self._flux.generate_cover(
            prompt=cover_prompt,
            album_id=album_folder(album_id),
            width=size,
            height=size,
        )
        if not cover_path(album_id).exists():
            raise CoverGenerationError("FLUX returned success but no cover file was produced")
        return cover_public_url(album_id)
