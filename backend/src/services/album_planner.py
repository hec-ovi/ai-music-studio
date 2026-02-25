"""Album planning service — calls Ollama LLM, parses the plan, then unloads model."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from src.core.exceptions import PlanningError
from src.models.album import AlbumPlan, SongPlan
from src.tools.ollama import OllamaTool

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "album_planner.md"
_LOGGER = logging.getLogger(__name__)

_MAX_ALBUM_NAME_CHARS = 32
_MAX_SONG_NAME_CHARS = 30
_MAX_ALBUM_DESC_CHARS = 220
_MAX_SONG_DESC_CHARS = 120
_MAX_MUSIC_PROMPT_CHARS = 560
_MAX_MUSIC_PROMPT_WORDS = 85
_MAX_COVER_PROMPT_CHARS = 420
_MAX_COVER_PROMPT_WORDS = 90
_MAX_LYRICS_CHARS = 1400
_MAX_LYRICS_WORDS = 260

_TITLE_STOP_WORDS = {
    "the", "and", "for", "with", "from", "into", "that", "this", "your", "album", "music",
    "sound", "song", "songs", "track", "tracks", "style", "genre", "theme",
}

_GENERIC_TITLE_RE = re.compile(r"^(track|song|piece|movement)\s*\d*$", re.IGNORECASE)
_GENERIC_DESC_MARKERS = (
    "movement inspired by",
    "introductory and sparse",
    "steady and meditative",
    "textural and evolving",
    "expansive and cinematic",
    "reflective and minimal",
)
_GENERIC_PROMPT_MARKERS = (
    "cinematic ambient instrumental inspired by",
    "blend organic acoustic textures",
    "keep dynamics smooth",
)

_ADJECTIVES = [
    "Dawn", "Quiet", "Neon", "Silver", "Cedar", "Velvet", "Ocean", "Signal", "Lunar", "Tidal",
    "Amber", "Glass", "Moss", "Pulse", "Mist", "Afterlight", "Static", "Hollow",
]
_NOUNS = [
    "Thread", "Drift", "Vector", "Current", "Resonance", "Horizon", "Circuit", "Bloom", "Echo",
    "Fringe", "Canopy", "Arc", "Memory", "Fold", "Halo", "Frame", "Passage", "Field",
]

_ROLE_LIBRARY = [
    {
        "desc": "Sparse opener with restrained rhythm and clear spatial air.",
        "prompt": (
            "Instrumental opener inspired by {concept}. Start with low-density layers, delicate "
            "motif fragments, soft transients, and wide headroom. Emphasize restraint, clarity, "
            "and a graceful first-entry tone."
        ),
    },
    {
        "desc": "Gentle pulse section with stronger groove and controlled low-end.",
        "prompt": (
            "Instrumental groove chapter inspired by {concept}. Build a steady pulse with "
            "subtle percussion focus, warm bass support, and evolving harmonic bed. Keep timing "
            "precise and mix balance polished, never aggressive."
        ),
    },
    {
        "desc": "Signature motif track where the lead identity is clearly defined.",
        "prompt": (
            "Instrumental motif-focused piece inspired by {concept}. Present a distinctive lead "
            "voice over supportive texture, with call-and-response phrasing and clear emotional "
            "shape. Prioritize memorable melodic contour over density."
        ),
    },
    {
        "desc": "Experimental edge using unusual texture motion and modern sound design.",
        "prompt": (
            "Instrumental experimental chapter inspired by {concept}. Use modular texture motion, "
            "micro-detail transitions, and creative spatial automation while retaining musical "
            "cohesion. Keep the result refined, high-fidelity, and listenable."
        ),
    },
    {
        "desc": "Warm center track with lush harmony and intimate sonic perspective.",
        "prompt": (
            "Instrumental warm-core composition inspired by {concept}. Use richer harmonic "
            "voicing, rounded transients, and intimate stereo perspective. Keep rhythm soft and "
            "supportive, with tonal comfort as the primary emotional effect."
        ),
    },
    {
        "desc": "Late-night descent with lower activity and longer tail spaces.",
        "prompt": (
            "Instrumental downshift section inspired by {concept}. Reduce rhythmic density, extend "
            "decays, and use sparse melodic statements with deep ambience. Preserve continuity "
            "while clearly signaling late-phase release."
        ),
    },
    {
        "desc": "Afterglow bridge that reconnects previous motifs with subtle variation.",
        "prompt": (
            "Instrumental afterglow passage inspired by {concept}. Reintroduce selected motifs in "
            "altered timbre, add gentle modulation, and keep tonal flow smooth. The focus is "
            "cohesion and emotional continuity."
        ),
    },
    {
        "desc": "Closing track with minimal gestures and a calm, resolved finish.",
        "prompt": (
            "Instrumental closer inspired by {concept}. Use minimal gestures, stable harmony, and "
            "careful final phrasing that lands softly. End with breathable tail space and no "
            "abrupt cutoff."
        ),
    },
]


class AlbumPlannerService:
    """Generates an album plan via the Ollama LLM and unloads the model when done."""

    def __init__(self, ollama: OllamaTool) -> None:
        self._ollama = ollama

    async def plan(self, album_concept: str, num_songs: int) -> AlbumPlan:
        """Ask the LLM to produce a structured album plan."""
        prompt = self._build_prompt(album_concept, num_songs)
        raw = ""
        repaired_raw = ""

        try:
            raw = await self._ollama.generate(prompt, timeout=180.0, temperature=0.2)
            plan_dict = self._parse_json(raw)
            return self._validate(plan_dict, num_songs, album_concept)
        except Exception as first_exc:
            if not raw:
                raise PlanningError(
                    f"Failed to parse LLM plan: {first_exc}\n\nRaw output:\n{raw}"
                ) from first_exc

            try:
                repair_prompt = self._build_repair_prompt(album_concept, num_songs, raw)
                repaired_raw = await self._ollama.generate(
                    repair_prompt,
                    timeout=120.0,
                    temperature=0.0,
                )
                repaired_dict = self._parse_json(repaired_raw)
                return self._validate(repaired_dict, num_songs, album_concept)
            except Exception as second_exc:
                _LOGGER.warning(
                    "Planner output was not valid JSON after repair. "
                    "Using deterministic fallback. first=%s second=%s raw=%r repaired=%r",
                    first_exc,
                    second_exc,
                    raw[:800],
                    repaired_raw[:800],
                )
                return self._fallback_plan(album_concept, num_songs)
        finally:
            await self._ollama.unload()

    def _build_prompt(self, concept: str, num_songs: int) -> str:
        template = _PROMPT_FILE.read_text()
        payload = {"album_concept": concept, "num_songs": num_songs}
        return template.replace("{{ album_concept }}", json.dumps(payload, ensure_ascii=False))

    def _build_repair_prompt(self, concept: str, num_songs: int, raw: str) -> str:
        return f"""
Return ONLY one valid JSON object for an album plan.
No markdown, no prose, no backticks, no extra keys.

Hard constraints:
- songs length must be exactly {num_songs}
- song indexes must be 0..{max(num_songs - 1, 0)}
- album_name: 2-4 words, max 32 chars
- song name: 2-4 words, max 30 chars, never Track/Song placeholders
- album_description: max 220 chars
- song description: max 120 chars
- music_prompt: 35-75 words, actionable and specific
- cover_prompt: 50-90 words, no text/logos/watermarks
- duration_seconds: 30..420
- bpm: null or 40..240
- keep tracks varied in role and texture

Use this concept:
{concept}

Noisy output to repair:
{raw}
""".strip()

    def _parse_json(self, raw: str) -> dict:
        """Extract and parse JSON from possibly-noisy LLM output."""
        clean = self._clean_output(raw)
        candidates = [clean]

        extracted = self._extract_first_json_object(clean)
        if extracted and extracted != clean:
            candidates.append(extracted)

        parse_error: Exception | None = None
        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = self._decode_json(candidate)
                if isinstance(parsed, dict):
                    return parsed
                parse_error = ValueError(f"Expected JSON object, got {type(parsed).__name__}")
            except Exception as exc:
                parse_error = exc

        raise ValueError("No valid JSON object found in LLM response") from parse_error

    def _clean_output(self, raw: str) -> str:
        clean = raw.strip()
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"```(?:json)?", "", clean, flags=re.IGNORECASE)
        clean = clean.replace("```", "")
        return clean.strip()

    def _decode_json(self, text: str) -> Any:
        parsed = json.loads(text)
        if isinstance(parsed, str):
            nested = parsed.strip()
            if nested.startswith("{") and nested.endswith("}"):
                return json.loads(nested)
        return parsed

    def _extract_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for idx, char in enumerate(text[start:], start=start):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]

        return None

    def _validate(self, data: dict, num_songs: int, album_concept: str) -> AlbumPlan:
        """Validate and normalize planner output into a compact, generation-safe plan."""
        songs_data = data.get("songs")
        if not isinstance(songs_data, list):
            songs_data = []

        album_name = self._normalize_title(
            str(data.get("album_name") or ""),
            fallback=self._fallback_album_name(album_concept),
            max_chars=_MAX_ALBUM_NAME_CHARS,
        )
        album_description = self._normalize_sentence(
            str(data.get("album_description") or ""),
            fallback=(
                f"Instrumental album inspired by {self._short_concept(album_concept)}. "
                "Each track has a distinct role while keeping a cohesive flow."
            ),
            max_chars=_MAX_ALBUM_DESC_CHARS,
            max_words=42,
        )
        cover_prompt = self._normalize_cover_prompt(
            str(data.get("cover_prompt") or ""),
            album_concept=album_concept,
            album_name=album_name,
        )

        songs: list[SongPlan] = []
        for i in range(num_songs):
            source = songs_data[i] if i < len(songs_data) and isinstance(songs_data[i], dict) else {}
            role = self._role_for_index(i)

            raw_name = str(source.get("name") or "")
            fallback_name = self._fallback_song_name(i, album_concept)
            name = self._normalize_title(raw_name, fallback=fallback_name, max_chars=_MAX_SONG_NAME_CHARS)
            if self._looks_generic_title(name):
                name = self._normalize_title(
                    fallback_name,
                    fallback=f"Track {i + 1}",
                    max_chars=_MAX_SONG_NAME_CHARS,
                )

            lyrics = self._normalize_multiline(
                str(source.get("lyrics", "")),
                max_chars=_MAX_LYRICS_CHARS,
                max_words=_MAX_LYRICS_WORDS,
            )

            instrumental = bool(source.get("instrumental", not lyrics.strip()))
            if instrumental:
                lyrics = ""

            description = self._normalize_sentence(
                str(source.get("description") or ""),
                fallback=role["desc"],
                max_chars=_MAX_SONG_DESC_CHARS,
                max_words=20,
            )
            if self._looks_generic_description(description):
                description = self._normalize_sentence(
                    role["desc"],
                    fallback="Distinct chapter in the album arc.",
                    max_chars=_MAX_SONG_DESC_CHARS,
                    max_words=20,
                )

            raw_music_prompt = str(source.get("music_prompt") or description or "")
            music_prompt = self._normalize_prompt(
                raw_music_prompt,
                max_chars=_MAX_MUSIC_PROMPT_CHARS,
                max_words=_MAX_MUSIC_PROMPT_WORDS,
            )
            if self._looks_generic_prompt(music_prompt):
                music_prompt = self._normalize_prompt(
                    self._role_prompt(role["prompt"], album_concept),
                    max_chars=_MAX_MUSIC_PROMPT_CHARS,
                    max_words=_MAX_MUSIC_PROMPT_WORDS,
                )

            duration = self._as_float(source.get("duration_seconds"), self._default_duration(i))
            duration = max(30.0, min(420.0, duration))

            songs.append(
                SongPlan(
                    index=i,
                    name=name,
                    music_prompt=music_prompt,
                    lyrics=lyrics,
                    instrumental=instrumental,
                    duration_seconds=duration,
                    bpm=self._as_int_or_none(source.get("bpm")),
                    description=description,
                )
            )

        songs = self._dedupe_song_names(songs, album_concept)

        return AlbumPlan(
            album_name=album_name,
            album_description=album_description,
            cover_prompt=cover_prompt,
            songs=songs,
        )

    def _as_int_or_none(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if 40 <= parsed <= 240 else None

    def _as_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_space(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _clip_words(self, text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]).strip()

    def _clip_chars(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        clipped = text[:max_chars].rstrip(" ,.;:-")
        if not clipped:
            clipped = text[:max_chars].strip()
        return clipped

    def _normalize_title(self, raw: str, fallback: str, max_chars: int) -> str:
        title = self._normalize_space(raw)
        title = re.sub(r"[\"'`“”‘’]", "", title)
        title = re.sub(r"[:;|/\\]+", " ", title)
        title = re.sub(r"[^A-Za-z0-9&+\- ]", "", title)
        title = self._normalize_space(title)

        words = title.split()
        if len(words) > 4:
            words = words[:4]
        title = " ".join(words)
        title = self._clip_chars(title, max_chars)

        if not title:
            title = self._clip_chars(self._normalize_space(fallback), max_chars)

        title = title.strip(" -_")
        if not title:
            return "Untitled"
        return title.title()

    def _normalize_sentence(self, raw: str, fallback: str, max_chars: int, max_words: int) -> str:
        text = self._normalize_space(raw)
        text = self._clip_words(text, max_words)
        text = self._clip_chars(text, max_chars)
        if not text:
            text = self._clip_chars(self._clip_words(self._normalize_space(fallback), max_words), max_chars)
        return text

    def _normalize_prompt(self, raw: str, max_chars: int, max_words: int) -> str:
        text = self._normalize_space(raw)
        text = re.sub(r"[\"`]+", "", text)
        text = self._clip_words(text, max_words)
        text = self._clip_chars(text, max_chars)
        return text

    def _normalize_multiline(self, raw: str, max_chars: int, max_words: int) -> str:
        text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
        text = re.sub(r"[ \t]+", " ", text)
        text = self._clip_words(text, max_words)
        return self._clip_chars(text, max_chars)

    def _normalize_cover_prompt(self, raw: str, album_concept: str, album_name: str) -> str:
        prompt = self._normalize_prompt(
            raw,
            max_chars=_MAX_COVER_PROMPT_CHARS,
            max_words=_MAX_COVER_PROMPT_WORDS,
        )
        if not prompt or self._looks_generic_cover_prompt(prompt):
            prompt = self._fallback_cover_prompt(album_concept, album_name)

        lower = prompt.lower()
        if "no text" not in lower:
            prompt = f"{prompt}, no text, no logos"
            prompt = self._clip_chars(prompt, _MAX_COVER_PROMPT_CHARS)
        return prompt

    def _looks_generic_title(self, title: str) -> bool:
        return bool(_GENERIC_TITLE_RE.match(title.strip()))

    def _looks_generic_description(self, description: str) -> bool:
        lower = description.lower()
        return any(marker in lower for marker in _GENERIC_DESC_MARKERS)

    def _looks_generic_prompt(self, prompt: str) -> bool:
        lower = prompt.lower()
        if any(marker in lower for marker in _GENERIC_PROMPT_MARKERS):
            return True
        words = lower.split()
        return len(words) < 18

    def _looks_generic_cover_prompt(self, prompt: str) -> bool:
        lower = prompt.lower()
        return (
            lower.startswith("atmospheric album artwork inspired by")
            or "inspired by untitled" in lower
            or len(lower.split()) < 30
        )

    def _short_concept(self, concept: str) -> str:
        text = self._normalize_space(concept)
        text = self._clip_words(text, 10)
        return self._clip_chars(text, 90)

    def _concept_focus_token(self, concept: str) -> str:
        tokens = re.findall(r"[A-Za-z0-9]+", concept.lower())
        filtered = [t for t in tokens if len(t) >= 4 and t not in _TITLE_STOP_WORDS]
        if not filtered:
            return ""
        return filtered[0].title()

    def _seed(self, concept: str) -> int:
        digest = hashlib.sha1(concept.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def _fallback_album_name(self, concept: str) -> str:
        seed = self._seed(concept)
        focus = self._concept_focus_token(concept)
        noun = _NOUNS[seed % len(_NOUNS)]
        if focus:
            return self._normalize_title(
                f"{focus} {noun}",
                fallback=f"{_ADJECTIVES[seed % len(_ADJECTIVES)]} {noun}",
                max_chars=_MAX_ALBUM_NAME_CHARS,
            )
        return self._normalize_title(
            f"{_ADJECTIVES[seed % len(_ADJECTIVES)]} {noun}",
            fallback="Signal Reverie",
            max_chars=_MAX_ALBUM_NAME_CHARS,
        )

    def _fallback_song_name(self, index: int, concept: str) -> str:
        seed = self._seed(concept)
        focus = self._concept_focus_token(concept)
        adj = _ADJECTIVES[(seed + index * 3) % len(_ADJECTIVES)]
        noun = _NOUNS[(seed + index * 5) % len(_NOUNS)]
        if focus and index % 2 == 0:
            candidate = f"{focus} {noun}"
            return self._normalize_title(candidate, fallback=f"{adj} {noun}", max_chars=_MAX_SONG_NAME_CHARS)
        return self._normalize_title(f"{adj} {noun}", fallback=f"Piece {index + 1}", max_chars=30)

    def _role_for_index(self, index: int) -> dict[str, str]:
        return _ROLE_LIBRARY[index % len(_ROLE_LIBRARY)]

    def _role_prompt(self, template: str, concept: str) -> str:
        return template.format(concept=self._short_concept(concept))

    def _default_duration(self, index: int) -> float:
        defaults = [62.0, 60.0, 64.0, 61.0, 63.0, 60.0, 58.0, 57.0]
        return defaults[index % len(defaults)]

    def _fallback_cover_prompt(self, concept: str, album_name: str) -> str:
        concept_hint = self._short_concept(concept)
        return (
            f"Ultra-detailed cinematic wallpaper inspired by {album_name} and {concept_hint}, "
            "balanced wide composition, layered depth, natural and synthetic texture contrast, "
            "soft volumetric lighting, restrained color palette, atmospheric clarity, high-fidelity "
            "materials, modern album-art direction, no text, no logos"
        )

    def _dedupe_song_names(self, songs: list[SongPlan], concept: str) -> list[SongPlan]:
        deduped: list[SongPlan] = []
        seen: dict[str, int] = {}

        for i, song in enumerate(songs):
            base = song.name
            key = base.lower()
            count = seen.get(key, 0) + 1
            seen[key] = count

            if count == 1:
                deduped.append(song)
                continue

            candidate = self._normalize_title(
                f"{base} {count}",
                fallback=self._fallback_song_name(i, concept),
                max_chars=_MAX_SONG_NAME_CHARS,
            )
            deduped.append(song.model_copy(update={"name": candidate}))

        return deduped

    def _fallback_plan(self, concept: str, num_songs: int) -> AlbumPlan:
        album_name = self._fallback_album_name(concept)
        album_description = self._normalize_sentence(
            (
                f"{album_name} is an instrumental concept album inspired by "
                f"{self._short_concept(concept)}. Tracks progress through distinct sonic roles "
                "with polished continuity."
            ),
            fallback="Instrumental concept album with varied roles and cohesive flow.",
            max_chars=_MAX_ALBUM_DESC_CHARS,
            max_words=42,
        )
        cover_prompt = self._fallback_cover_prompt(concept, album_name)

        songs: list[SongPlan] = []
        for i in range(num_songs):
            role = self._role_for_index(i)
            name = self._fallback_song_name(i, concept)
            songs.append(
                SongPlan(
                    index=i,
                    name=name,
                    description=self._normalize_sentence(
                        role["desc"],
                        fallback="Distinct chapter in the album arc.",
                        max_chars=_MAX_SONG_DESC_CHARS,
                        max_words=20,
                    ),
                    music_prompt=self._normalize_prompt(
                        self._role_prompt(role["prompt"], concept),
                        max_chars=_MAX_MUSIC_PROMPT_CHARS,
                        max_words=_MAX_MUSIC_PROMPT_WORDS,
                    ),
                    lyrics="",
                    instrumental=True,
                    duration_seconds=self._default_duration(i),
                    bpm=72 + (i % 4) * 4,
                )
            )

        songs = self._dedupe_song_names(songs, concept)
        return AlbumPlan(
            album_name=album_name,
            album_description=album_description,
            cover_prompt=cover_prompt,
            songs=songs,
        )
