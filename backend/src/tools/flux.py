"""FLUX.2-klein image generation tool.

Calls the FLUX FastAPI service, which loads the model, generates,
and unloads before returning. GPU memory is clear after this call.
"""

import httpx

from src.core.config import settings
from src.core.exceptions import CoverGenerationError, ServiceUnavailableError


class FluxTool:
    """Client for the FLUX.2-klein inference service."""

    def __init__(self, base_url: str = settings.flux_url) -> None:
        self._base_url = base_url.rstrip("/")

    async def generate_cover(
        self,
        prompt: str,
        album_id: str,
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
        timeout: float = 1200.0,
    ) -> str:
        """Request cover image generation and return the server-side file path.

        Args:
            prompt: FLUX image generation prompt.
            album_id: Album identifier for file naming.
            width: Image width in pixels.
            height: Image height in pixels.
            seed: Optional random seed for reproducibility.
            timeout: HTTP timeout in seconds (generation can be slow).

        Returns:
            URL path to the generated cover image.

        Raises:
            ServiceUnavailableError: If the FLUX service is unreachable.
            CoverGenerationError: If generation fails.
        """
        payload = {
            "prompt": prompt,
            "album_id": album_id,
            "width": width,
            "height": height,
            "num_inference_steps": 4,
            "guidance_scale": 1.0,
        }
        if seed is not None:
            payload["seed"] = seed

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self._base_url}/generate", json=payload)
                resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ServiceUnavailableError(f"Cannot reach FLUX service at {self._base_url}") from exc
        except httpx.HTTPStatusError as exc:
            raise CoverGenerationError(
                f"FLUX service returned {exc.response.status_code}: {exc.response.text}"
            ) from exc

        data = resp.json()
        return data["url_path"]
