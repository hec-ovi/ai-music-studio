"""Album export service: MP4 renders and YouTube package artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.core.config import settings
from src.core.exceptions import ExportError
from src.core.storage import (
    album_dir,
    album_file_public_url,
    album_folder,
    cover_path,
    load_plan,
)
from src.models.album import ExportArtifact


def _safe_name(text: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in text).strip()
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned or "Track"


def _file_name_from_url(url_or_name: str) -> str:
    if "/" not in url_or_name:
        return url_or_name
    parsed = urlparse(url_or_name)
    return unquote(Path(parsed.path).name)


class ExportService:
    """Render static-cover MP4 files and generate a YouTube upload package."""

    def __init__(self, ffmpeg_bin: str = settings.ffmpeg_bin) -> None:
        self._ffmpeg_bin = ffmpeg_bin

    def export_track_mp4(self, album_id: str) -> list[ExportArtifact]:
        """Create one MP4 per generated song using cover + audio."""
        data = load_plan(album_id)
        songs = data.get("songs", [])
        if not songs:
            raise ExportError("No generated songs found for this album")

        album_name = str(data.get("plan", {}).get("album_name", "Album"))
        root = album_dir(album_id)
        cover = cover_path(album_id)
        outputs: list[ExportArtifact] = []

        for raw_song in songs:
            if not isinstance(raw_song, dict):
                continue
            index = int(raw_song.get("index", 0))
            song_name = str(raw_song.get("name", f"Track {index + 1}"))
            audio_url = str(raw_song.get("audio_url", ""))
            if not audio_url:
                continue

            audio_file_name = _file_name_from_url(audio_url)
            audio_path = root / audio_file_name
            if not audio_path.exists():
                alt = sorted(root.glob(f"{index + 1:02d}_*.mp3"))
                if alt:
                    audio_path = alt[0]
                else:
                    raise ExportError(f"Audio file not found for song {index + 1}: {audio_file_name}")

            mp4_name = f"{index + 1:02d}_{_safe_name(song_name)}.mp4"
            mp4_path = root / mp4_name

            self._render_mp4(
                cover_path=cover if cover.exists() else None,
                audio_path=audio_path,
                output_path=mp4_path,
            )

            outputs.append(
                ExportArtifact(
                    kind="track_mp4",
                    song_index=index,
                    file_name=mp4_name,
                    url=album_file_public_url(album_id, mp4_name),
                    status="ready",
                )
            )

        if not outputs:
            raise ExportError("No MP4 files were exported")

        # Also write a compact index for external tooling.
        index_payload = {
            "album_id": album_id,
            "album_name": album_name,
            "tracks": [item.model_dump() for item in outputs],
        }
        index_path = root / "mp4_index.json"
        index_path.write_text(json.dumps(index_payload, indent=2))
        outputs.insert(
            0,
            ExportArtifact(
                kind="track_mp4_index",
                song_index=None,
                file_name=index_path.name,
                url=album_file_public_url(album_id, index_path.name),
                status="ready",
            ),
        )
        return outputs

    def generate_youtube_package(self, album_id: str) -> list[ExportArtifact]:
        """Create YouTube-ready manifest + upload template files."""
        data = load_plan(album_id)
        plan = data.get("plan", {}) if isinstance(data, dict) else {}
        songs = data.get("songs", []) if isinstance(data, dict) else []

        if not isinstance(songs, list) or not songs:
            raise ExportError("Cannot create YouTube package without generated songs")

        album_name = str(plan.get("album_name", "Untitled Album")).strip() or "Untitled Album"
        album_description = str(plan.get("album_description", "")).strip()
        folder = album_folder(album_id)
        root = album_dir(album_id)

        mp4_by_index: dict[int, str] = {}
        for mp4 in sorted(root.glob("*.mp4")):
            prefix = mp4.stem.split("_", 1)[0]
            try:
                idx = int(prefix) - 1
            except ValueError:
                continue
            mp4_by_index[idx] = mp4.name

        videos: list[dict] = []
        for raw_song in songs:
            if not isinstance(raw_song, dict):
                continue
            index = int(raw_song.get("index", 0))
            name = str(raw_song.get("name", f"Track {index + 1}"))
            description = str(raw_song.get("description", "")).strip()
            audio_url = str(raw_song.get("audio_url", ""))
            audio_name = _file_name_from_url(audio_url) if audio_url else ""
            mp4_name = mp4_by_index.get(index, "")
            videos.append(
                {
                    "track_number": index + 1,
                    "title": f"{index + 1:02d}. {name}",
                    "description": description,
                    "mp4_file": mp4_name,
                    "audio_file": audio_name,
                    "thumbnail_file": "cover.png" if cover_path(album_id).exists() else None,
                    "contains_synthetic_media": True,
                }
            )

        manifest = {
            "album_id": album_id,
            "album_folder": folder,
            "album_name": album_name,
            "playlist": {
                "title": album_name,
                "description": album_description,
                "privacy_status": "unlisted",
            },
            "videos": videos,
            "notes": [
                "Ensure OAuth credentials are configured before upload.",
                "Set status.containsSyntheticMedia=true for each upload.",
                "Upload order should follow track_number ascending.",
            ],
        }

        manifest_path = root / "youtube_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        script_path = root / "youtube_upload_template.py"
        script_path.write_text(_youtube_script_template())

        readme_path = root / "YOUTUBE_UPLOAD.md"
        readme_path.write_text(_youtube_readme_template())

        return [
            ExportArtifact(
                kind="youtube_package",
                song_index=None,
                file_name=manifest_path.name,
                url=album_file_public_url(album_id, manifest_path.name),
                status="ready",
            ),
            ExportArtifact(
                kind="youtube_package",
                song_index=None,
                file_name=script_path.name,
                url=album_file_public_url(album_id, script_path.name),
                status="ready",
            ),
            ExportArtifact(
                kind="youtube_package",
                song_index=None,
                file_name=readme_path.name,
                url=album_file_public_url(album_id, readme_path.name),
                status="ready",
            ),
        ]

    def _render_mp4(self, cover_path: Path | None, audio_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if cover_path and cover_path.exists():
            cmd = [
                self._ffmpeg_bin,
                "-y",
                "-loop",
                "1",
                "-framerate",
                "2",
                "-i",
                str(cover_path),
                "-i",
                str(audio_path),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-tune",
                "stillimage",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        else:
            cmd = [
                self._ffmpeg_bin,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=1024x1024:r=2",
                "-i",
                str(audio_path),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise ExportError(f"ffmpeg not found ({self._ffmpeg_bin})") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            msg = stderr[-500:] if stderr else str(exc)
            raise ExportError(f"ffmpeg failed for {audio_path.name}: {msg}") from exc


def _youtube_script_template() -> str:
    return """#!/usr/bin/env python3
\"\"\"Template uploader for generated YouTube package.

Requirements:
  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
  export YOUTUBE_CLIENT_SECRETS=./client_secret.json
\"\"\"

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    manifest = json.loads(Path("youtube_manifest.json").read_text())
    print("Loaded manifest for:", manifest["album_name"])
    print("Tracks:", len(manifest["videos"]))
    print("")
    print("Next steps:")
    print("1) Implement OAuth flow + YouTube Data API client.")
    print("2) Create playlist with manifest['playlist'].")
    print("3) Upload each mp4_file in order and set containsSyntheticMedia=true.")
    print("4) Set cover.png as thumbnail (if available).")


if __name__ == "__main__":
    main()
"""


def _youtube_readme_template() -> str:
    return """# YouTube Export Package

This folder contains generated metadata and helper files for YouTube upload.

- `youtube_manifest.json`: playlist + per-track metadata
- `youtube_upload_template.py`: starter uploader script
- `cover.png`: album cover used as video thumbnail (if generated)
- `NN_<TrackName>.mp4`: one static-cover video per track

Recommended upload flow:
1. Authenticate with YouTube Data API v3.
2. Create playlist from `playlist` fields in the manifest.
3. Upload each track MP4 in `track_number` order.
4. Set `containsSyntheticMedia=true` during upload.
5. Apply `cover.png` as thumbnail for each video.
"""
