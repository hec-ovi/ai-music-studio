from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest import mock

from src.core import storage
from src.core.config import settings
from src.core.db import backfill_from_storage, get_album_session, init_db, list_albums
from src.services.export import ExportService


class DbAndExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.output = Path(self._tmp.name) / "output"
        self.output.mkdir(parents=True, exist_ok=True)

        self._old_output_dir = settings.output_dir
        self._old_db_path = settings.db_path
        self._old_albums_root = storage.ALBUMS_ROOT
        self._old_index_root = storage.INDEX_ROOT

        settings.output_dir = str(self.output)
        settings.db_path = str(self.output / "studio.db")
        storage.ALBUMS_ROOT = self.output / "albums"
        storage.INDEX_ROOT = self.output / ".album-index"

    def tearDown(self) -> None:
        settings.output_dir = self._old_output_dir
        settings.db_path = self._old_db_path
        storage.ALBUMS_ROOT = self._old_albums_root
        storage.INDEX_ROOT = self._old_index_root
        self._tmp.cleanup()

    def test_db_backfill_discovers_existing_album(self) -> None:
        album_id = "album-backfill-1"
        folder = "Tideleaf Reverie"
        (self.output / "albums" / folder).mkdir(parents=True, exist_ok=True)
        (self.output / ".album-index").mkdir(parents=True, exist_ok=True)

        (self.output / ".album-index" / f"{album_id}.json").write_text(
            json.dumps({"album_id": album_id, "folder": folder})
        )

        plan_payload = {
            "album_id": album_id,
            "status": "complete",
            "cover_url": f"/output/albums/{quote(folder)}/cover.png",
            "plan": {
                "album_name": folder,
                "album_description": "Calm instrumental suite.",
                "cover_prompt": "cinematic wallpaper no text",
                "songs": [
                    {
                        "index": 0,
                        "name": "Ocean Mist",
                        "description": "Soft opener",
                        "music_prompt": "instrumental ambient with flute and ocean texture",
                        "lyrics": "",
                        "instrumental": True,
                        "duration_seconds": 60,
                        "bpm": 72,
                    }
                ],
            },
            "songs": [
                {
                    "index": 0,
                    "name": "Ocean Mist",
                    "description": "Soft opener",
                    "duration_seconds": 60,
                    "audio_url": f"/output/albums/{quote(folder)}/01_Ocean Mist.mp3",
                }
            ],
        }
        (self.output / "albums" / folder / "plan.json").write_text(json.dumps(plan_payload, indent=2))

        init_db()
        backfill_from_storage(str(self.output))

        rows = list_albums()
        self.assertTrue(rows, "Expected backfilled albums list to be non-empty")
        row = rows[0]
        self.assertEqual(row["album_id"], album_id)
        self.assertEqual(row["songs_planned"], 1)
        self.assertEqual(row["songs_ready"], 1)

        detail = get_album_session(album_id)
        self.assertIsNotNone(detail)
        self.assertEqual(len(detail["songs"]), 1)
        self.assertEqual(detail["songs"][0]["status"], "complete")

    def test_export_service_generates_mp4_and_youtube_files(self) -> None:
        album_id = "album-export-1"
        storage.init_album(album_id)
        storage.set_album_folder(album_id, "Export Test")

        album_path = storage.album_dir(album_id)
        audio = album_path / "01_Ocean Mist.mp3"
        cover = album_path / "cover.png"
        audio.write_bytes(b"fake mp3")
        cover.write_bytes(b"fake png")

        storage.save_plan(
            album_id,
            {
                "album_id": album_id,
                "status": "complete",
                "cover_url": storage.cover_public_url(album_id),
                "plan": {
                    "album_name": "Export Test",
                    "album_description": "Album for export tests",
                    "cover_prompt": "test prompt",
                    "songs": [
                        {
                            "index": 0,
                            "name": "Ocean Mist",
                            "description": "desc",
                            "music_prompt": "prompt",
                            "lyrics": "",
                            "instrumental": True,
                            "duration_seconds": 60,
                            "bpm": 72,
                        }
                    ],
                },
                "songs": [
                    {
                        "index": 0,
                        "name": "Ocean Mist",
                        "description": "desc",
                        "duration_seconds": 60,
                        "audio_url": storage.song_public_url(album_id, audio.name),
                    }
                ],
            },
        )

        def _fake_run(cmd: list[str], check: bool, stdout: int, stderr: int, text: bool):  # noqa: ARG001
            Path(cmd[-1]).write_bytes(b"fake mp4")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        with mock.patch("subprocess.run", side_effect=_fake_run):
            svc = ExportService(ffmpeg_bin="ffmpeg")
            mp4_files = svc.export_track_mp4(album_id)
            self.assertTrue(any(item.file_name.endswith(".mp4") for item in mp4_files))
            self.assertTrue((album_path / "01_Ocean Mist.mp4").exists())

            yt_files = svc.generate_youtube_package(album_id)
            self.assertTrue(any(item.file_name == "youtube_manifest.json" for item in yt_files))
            self.assertTrue((album_path / "youtube_manifest.json").exists())
            self.assertTrue((album_path / "youtube_upload_template.py").exists())


if __name__ == "__main__":
    unittest.main()
