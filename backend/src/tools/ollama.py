"""Ollama LLM tool — sends a prompt and returns the text response.

Stateless, framework-agnostic, no knowledge of FastAPI or business logic.
"""

import httpx

from src.core.config import settings
from src.core.exceptions import PlanningError, ServiceUnavailableError


class OllamaTool:
    """Thin wrapper around the Ollama /api/generate endpoint."""

    def __init__(
        self,
        base_url: str = settings.ollama_url,
        model: str = settings.ollama_model,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def generate(
        self,
        prompt: str,
        timeout: float = 120.0,
        temperature: float = 0.8,
    ) -> str:
        """Send a prompt to Ollama and return the full text response.

        Args:
            prompt: The complete prompt string.
            timeout: HTTP timeout in seconds.

        Returns:
            The model's text output.

        Raises:
            ServiceUnavailableError: If Ollama is unreachable.
            PlanningError: If the request fails or returns an error.
        """
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ServiceUnavailableError(f"Cannot reach Ollama at {self._base_url}") from exc
        except httpx.HTTPStatusError as exc:
            raise PlanningError(f"Ollama returned {exc.response.status_code}") from exc

        body = resp.json()
        return body.get("response", "")

    async def unload(self) -> None:
        """Force Ollama to unload the model and free GPU memory."""
        payload = {"model": self._model, "keep_alive": 0}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{self._base_url}/api/generate", json=payload)
        except Exception:
            # Best-effort — ignore errors during unload
            pass
