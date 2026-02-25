"""File-based storage helpers for generated album assets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from src.core.config import settings

ALBUMS_ROOT = Path(settings.output_dir) / "albums"
INDEX_ROOT = Path(settings.output_dir) / ".album-index"
INVALID_FOLDER_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
WHITESPACE_RE = re.compile(r"\s+")


def _ensure_roots() -> None:
    ALBUMS_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_ROOT.mkdir(parents=True, exist_ok=True)


def _meta_path(album_id: str) -> Path:
    return INDEX_ROOT / f"{album_id}.json"


def _default_meta(album_id: str) -> dict[str, str]:
    return {"album_id": album_id, "folder": album_id}


def _read_meta(album_id: str) -> dict[str, str]:
    _ensure_roots()
    meta_file = _meta_path(album_id)
    if meta_file.exists():
        return json.loads(meta_file.read_text())

    fallback = ALBUMS_ROOT / album_id
    if fallback.exists():
        data = _default_meta(album_id)
        _write_meta(album_id, data)
        return data

    raise FileNotFoundError(f"Album {album_id} does not exist")


def _write_meta(album_id: str, data: dict[str, str]) -> None:
    _ensure_roots()
    _meta_path(album_id).write_text(json.dumps(data, indent=2))


def _sanitize_folder_name(album_name: str) -> str:
    cleaned = INVALID_FOLDER_CHARS.sub("_", album_name).strip().strip(".")
    cleaned = WHITESPACE_RE.sub(" ", cleaned)
    if not cleaned:
        return "Untitled Album"
    return cleaned[:120]


def _unique_album_folder(base_name: str) -> str:
    candidate = base_name
    suffix = 2
    while (ALBUMS_ROOT / candidate).exists():
        candidate = f"{base_name} ({suffix})"
        suffix += 1
    return candidate


def init_album(album_id: str) -> Path:
    """Initialize storage for a new album request using the temporary ID folder."""
    _ensure_roots()
    path = ALBUMS_ROOT / album_id
    path.mkdir(parents=True, exist_ok=True)
    _write_meta(album_id, _default_meta(album_id))
    return path


def set_album_folder(album_id: str, album_name: str) -> str:
    """Rename temporary ID folder to a human-readable album folder."""
    meta = _read_meta(album_id)
    current_folder = meta["folder"]
    target_base = _sanitize_folder_name(album_name)

    if current_folder == target_base:
        return current_folder

    current_path = ALBUMS_ROOT / current_folder
    target_folder = _unique_album_folder(target_base)
    target_path = ALBUMS_ROOT / target_folder

    if current_path.exists() and current_path != target_path:
        current_path.rename(target_path)
    else:
        target_path.mkdir(parents=True, exist_ok=True)

    meta["folder"] = target_folder
    _write_meta(album_id, meta)
    return target_folder


def album_folder(album_id: str) -> str:
    """Return the resolved folder name for an album ID."""
    return _read_meta(album_id)["folder"]


def album_dir(album_id: str) -> Path:
    """Return (and create) the directory for an album's assets."""
    folder = album_folder(album_id)
    path = ALBUMS_ROOT / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_plan(album_id: str, plan: dict) -> None:
    """Persist album generation state as JSON."""
    path = album_dir(album_id) / "plan.json"
    path.write_text(json.dumps(plan, indent=2))


def load_plan(album_id: str) -> dict:
    """Load a previously saved album state."""
    path = album_dir(album_id) / "plan.json"
    return json.loads(path.read_text())


def song_path(album_id: str, index: int, name: str) -> Path:
    """Return the path where a song audio file should be saved."""
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
    safe_name = WHITESPACE_RE.sub(" ", safe_name)
    if not safe_name:
        safe_name = f"Track {index + 1}"
    return album_dir(album_id) / f"{index + 1:02d}_{safe_name}.mp3"


def cover_path(album_id: str) -> Path:
    """Return the path for the album cover image."""
    return album_dir(album_id) / "cover.png"


def song_public_url(album_id: str, file_name: str) -> str:
    """Return the backend static URL for a song file."""
    return album_file_public_url(album_id, file_name)


def album_file_public_url(album_id: str, file_name: str) -> str:
    """Return the backend static URL for any file in an album folder."""
    folder = quote(album_folder(album_id), safe="")
    return f"/output/albums/{folder}/{quote(file_name, safe='')}"


def cover_public_url(album_id: str) -> str:
    """Return the backend static URL for an album cover image."""
    folder = quote(album_folder(album_id), safe="")
    return f"/output/albums/{folder}/cover.png"


def clear_generated_assets(album_id: str) -> None:
    """Remove previously generated audio and cover files, preserving plan metadata."""
    path = album_dir(album_id)
    for audio_file in path.glob("*.mp3"):
        audio_file.unlink(missing_ok=True)
    for video_file in path.glob("*.mp4"):
        video_file.unlink(missing_ok=True)
    cover_file = path / "cover.png"
    cover_file.unlink(missing_ok=True)
    for extra_name in ("mp4_index.json", "youtube_manifest.json", "youtube_upload_template.py", "YOUTUBE_UPLOAD.md"):
        (path / extra_name).unlink(missing_ok=True)
