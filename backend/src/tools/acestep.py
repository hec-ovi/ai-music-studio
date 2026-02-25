"""ACE-Step 1.5 music generation tool.

Submits a generation task, polls until complete, and downloads the audio.
Each song is generated sequentially to honour the single-model-at-a-time policy.
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from src.core.config import settings
from src.core.exceptions import MusicGenerationError, ServiceUnavailableError

_POLL_INTERVAL = 5.0   # seconds between status polls
_MAX_WAIT = 1800.0      # maximum wait per song (30 min)
# First task can block while ACE-Step lazily loads large checkpoints on cold start.
_SUBMIT_TIMEOUT = 900.0
_SUBMIT_RETRIES = 4
_POLL_TIMEOUT = 30.0
_DOWNLOAD_TIMEOUT = 120.0
_MAX_PROMPT_WORDS = 96
_MAX_PROMPT_CHARS = 720
_MAX_LYRICS_WORDS = 320
_MAX_LYRICS_CHARS = 1800


class AceStepTool:
    """Client for the ACE-Step 1.5 REST API."""

    def __init__(self, base_url: str = settings.acestep_url) -> None:
        self._base_url = base_url.rstrip("/")

    async def generate_song(
        self,
        music_prompt: str,
        lyrics: str,
        instrumental: bool,
        duration_seconds: float,
        bpm: int | None,
        output_path: Path,
        thinking: bool = True,
        use_cot_caption: bool = True,
        use_cot_language: bool = True,
        use_cot_metas: bool = True,
        timeout: float = _MAX_WAIT,
    ) -> Path:
        """Generate a single song and save it to output_path.

        Uses thinking=True so ACE-Step's 5Hz LM fills in musical details
        (audio codes, key, time signature) beyond the high-level prompt.

        Args:
            music_prompt: Descriptive prompt for the music.
            lyrics: Song lyrics (empty string → instrumental).
            instrumental: Flag to suppress vocal generation.
            duration_seconds: Target duration in seconds.
            bpm: Optional BPM hint (None lets the LM decide).
            output_path: Destination file path for the generated audio.
            thinking: Enable ACE-Step's internal LM for musical detail.
            use_cot_caption: Enable CoT caption enhancement.
            use_cot_language: Enable CoT language enhancement.
            use_cot_metas: Enable CoT metadata enhancement (BPM/key/signature).
            timeout: Maximum seconds to wait for this song.

        Returns:
            Path to the saved audio file.

        Raises:
            ServiceUnavailableError: If ACE-Step is unreachable.
            MusicGenerationError: If generation fails or times out.
        """
        task_id = await self._submit_task(
            prompt=music_prompt,
            lyrics=lyrics,
            instrumental=instrumental,
            duration=duration_seconds,
            bpm=bpm,
            thinking=thinking,
            use_cot_caption=use_cot_caption,
            use_cot_language=use_cot_language,
            use_cot_metas=use_cot_metas,
        )

        audio_url = await self._wait_for_result(task_id, timeout)
        await self._download_audio(audio_url, output_path)
        return output_path

    async def _submit_task(
        self,
        prompt: str,
        lyrics: str,
        instrumental: bool,
        duration: float,
        bpm: int | None,
        thinking: bool,
        use_cot_caption: bool,
        use_cot_language: bool,
        use_cot_metas: bool,
    ) -> str:
        """Submit a generation task and return the task_id."""
        safe_prompt = self._fit_prompt(prompt)
        safe_lyrics = "[instrumental]" if instrumental else self._fit_lyrics(lyrics)

        payload: dict = {
            "prompt": safe_prompt,
            "lyrics": safe_lyrics,
            "thinking": thinking,
            "use_cot_caption": use_cot_caption,
            "use_cot_language": use_cot_language,
            "use_cot_metas": use_cot_metas,
            "audio_duration": duration,
            # Slightly lower steps to reduce long-tail generation timeouts.
            "inference_steps": 6,
            "batch_size": 1,
        }
        if bpm is not None:
            payload["bpm"] = bpm

        retryable_status = {502, 503, 504}
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=_SUBMIT_TIMEOUT) as client:
            for attempt in range(1, _SUBMIT_RETRIES + 1):
                try:
                    resp = await client.post(f"{self._base_url}/release_task", json=payload)
                    resp.raise_for_status()
                except httpx.ConnectError as exc:
                    last_error = exc
                    if attempt >= _SUBMIT_RETRIES:
                        raise ServiceUnavailableError(
                            f"Cannot reach ACE-Step at {self._base_url}"
                        ) from exc
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))
                    continue
                except httpx.TimeoutException as exc:
                    last_error = exc
                    if attempt >= _SUBMIT_RETRIES:
                        raise MusicGenerationError(
                            f"ACE-Step task submission timed out after {_SUBMIT_TIMEOUT:.0f}s"
                        ) from exc
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))
                    continue
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    status = exc.response.status_code
                    detail = self._extract_response_detail(exc.response)
                    if status in retryable_status and attempt < _SUBMIT_RETRIES:
                        await asyncio.sleep(min(2 ** (attempt - 1), 8))
                        continue
                    message = f"ACE-Step returned {status}"
                    if detail:
                        message += f": {detail}"
                    raise MusicGenerationError(message) from exc
                except httpx.RequestError as exc:
                    last_error = exc
                    if attempt >= _SUBMIT_RETRIES:
                        raise ServiceUnavailableError(
                            f"ACE-Step request failed: {exc}"
                        ) from exc
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))
                    continue

                try:
                    body = resp.json()
                except ValueError as exc:
                    last_error = exc
                    if attempt < _SUBMIT_RETRIES:
                        await asyncio.sleep(min(2 ** (attempt - 1), 8))
                        continue
                    snippet = (resp.text or "").strip().replace("\n", " ")[:300]
                    raise MusicGenerationError(
                        "ACE-Step submission response was not valid JSON"
                        + (f": {snippet}" if snippet else "")
                    ) from exc

                task_id = ""
                if isinstance(body, dict):
                    data = body.get("data")
                    if isinstance(data, dict):
                        raw_task_id = data.get("task_id")
                        if isinstance(raw_task_id, str):
                            task_id = raw_task_id

                if task_id:
                    return task_id

                detail = ""
                if isinstance(body, dict):
                    raw_detail = body.get("detail") or body.get("message")
                    if raw_detail is not None:
                        detail = str(raw_detail)
                if attempt < _SUBMIT_RETRIES:
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))
                    continue
                raise MusicGenerationError(
                    "ACE-Step submission succeeded but did not return task_id"
                    + (f": {detail}" if detail else "")
                )

        raise MusicGenerationError(
            f"ACE-Step task submission failed after {_SUBMIT_RETRIES} attempts"
        ) from last_error

    async def _wait_for_result(self, task_id: str, timeout: float) -> str:
        """Poll until the task succeeds, then return the audio download URL."""
        elapsed = 0.0
        async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as client:
            while elapsed < timeout:
                await asyncio.sleep(_POLL_INTERVAL)
                elapsed += _POLL_INTERVAL

                try:
                    resp = await client.post(
                        f"{self._base_url}/query_result",
                        json={"task_id_list": [task_id]},
                    )
                    resp.raise_for_status()
                except Exception:
                    continue  # transient error — keep polling

                task = self._extract_task(resp.json().get("data"), task_id)
                if not task:
                    continue
                status = task.get("status", 0)

                if status == 1:
                    # Success — extract audio URL
                    audio_path = task.get("audio_path") or task.get("output_path", "")
                    if not audio_path:
                        audio_path = self._extract_audio_path_from_result(task.get("result"))
                    if not audio_path:
                        raise MusicGenerationError(
                            f"ACE-Step task {task_id} succeeded but returned no audio path: {task}"
                        )
                    return f"{self._base_url}/v1/audio?path={audio_path}"
                if status == 2:
                    raise MusicGenerationError(f"ACE-Step task {task_id} failed: {task}")

        raise MusicGenerationError(f"ACE-Step task {task_id} timed out after {timeout}s")

    async def _download_audio(self, url: str, dest: Path) -> None:
        """Download audio from the ACE-Step service to dest."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(dest, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
        except httpx.TimeoutException as exc:
            raise MusicGenerationError(
                f"ACE-Step audio download timed out after {_DOWNLOAD_TIMEOUT:.0f}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise MusicGenerationError(
                f"ACE-Step audio download failed: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(f"ACE-Step audio download request failed: {exc}") from exc

    @staticmethod
    def _extract_task(data: object, task_id: str) -> dict | None:
        """Support both ACE-Step response shapes: dict keyed by task_id or list of task objects."""
        if isinstance(data, dict):
            task = data.get(task_id)
            return task if isinstance(task, dict) else None

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("task_id") == task_id:
                    return item
        return None

    @staticmethod
    def _extract_audio_path_from_result(result: object) -> str:
        """Extract audio path from ACE-Step `result` when direct fields are missing."""
        if not result:
            return ""

        parsed: object
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                return ""
        else:
            parsed = result

        if not isinstance(parsed, list) or not parsed:
            return ""
        first = parsed[0]
        if not isinstance(first, dict):
            return ""

        file_val = first.get("file")
        if not isinstance(file_val, str):
            return ""

        # Common shape: "/v1/audio?path=%2Fapp%2F...mp3"
        parsed_url = urlparse(file_val)
        qs = parse_qs(parsed_url.query)
        path_vals = qs.get("path")
        if path_vals:
            return unquote(path_vals[0])

        # Fallbacks for direct path style values.
        if file_val.startswith("/"):
            return file_val
        return ""

    @staticmethod
    def _extract_response_detail(response: httpx.Response) -> str:
        """Extract human-readable detail from an HTTP error response."""
        try:
            payload: Any = response.json()
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("message")
                if detail is not None:
                    return str(detail)
                return json.dumps(payload)[:300]
            return str(payload)[:300]
        except Exception:
            return (response.text or "").strip().replace("\n", " ")[:300]

    @staticmethod
    def _fit_prompt(text: str) -> str:
        return AceStepTool._clip_text(
            text=text,
            max_words=_MAX_PROMPT_WORDS,
            max_chars=_MAX_PROMPT_CHARS,
            keep_tail=True,
        )

    @staticmethod
    def _fit_lyrics(text: str) -> str:
        return AceStepTool._clip_text(
            text=text,
            max_words=_MAX_LYRICS_WORDS,
            max_chars=_MAX_LYRICS_CHARS,
            keep_tail=False,
        )

    @staticmethod
    def _clip_text(text: str, max_words: int, max_chars: int, keep_tail: bool) -> str:
        normalized = " ".join(text.split()).strip()
        if not normalized:
            return ""

        words = normalized.split()
        if len(words) > max_words:
            if keep_tail and max_words >= 16:
                head = max_words - 10
                normalized = " ".join(words[:head] + words[-10:])
            else:
                normalized = " ".join(words[:max_words])

        if len(normalized) <= max_chars:
            return normalized

        if keep_tail and max_chars >= 120:
            head_len = max_chars - 36
            tail_len = 30
            return f"{normalized[:head_len].rstrip()} ... {normalized[-tail_len:].lstrip()}"

        return normalized[:max_chars].rstrip(" ,.;:-")
