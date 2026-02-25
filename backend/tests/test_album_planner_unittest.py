from __future__ import annotations

import unittest

from src.services.album_planner import AlbumPlannerService


class _DummyOllama:
    async def generate(self, prompt: str, timeout: float, temperature: float = 0.2) -> str:  # noqa: ARG002
        raise RuntimeError("not used in unit tests")

    async def unload(self) -> None:
        return None


class AlbumPlannerTests(unittest.TestCase):
    def test_parse_json_extracts_from_noisy_llm_output(self) -> None:
        service = AlbumPlannerService(_DummyOllama())
        raw = """
<think>internal reasoning</think>
Here is the JSON:
```json
{"album_name":"Tideleaf Reverie","album_description":"Desc","cover_prompt":"Prompt","songs":[]}
```
"""
        parsed = service._parse_json(raw)  # noqa: SLF001
        self.assertEqual(parsed["album_name"], "Tideleaf Reverie")

    def test_validate_compacts_names_and_replaces_generic_tracks(self) -> None:
        service = AlbumPlannerService(_DummyOllama())
        raw = {
            "album_name": "The Ultimate Incredible Meditation Suite With Way Too Many Words",
            "album_description": "A very long description " * 40,
            "cover_prompt": "simple cover prompt",
            "songs": [
                {
                    "index": 0,
                    "name": "Track 1",
                    "description": "A introductory and sparse movement inspired by ambient music.",
                    "music_prompt": "short",
                    "lyrics": "",
                    "instrumental": True,
                    "duration_seconds": 700,
                    "bpm": 500,
                },
                {
                    "index": 1,
                    "name": "Song 2",
                    "description": "A steady and meditative movement inspired by ambient music.",
                    "music_prompt": "cinematic ambient instrumental inspired by concept",
                    "lyrics": "",
                    "instrumental": True,
                    "duration_seconds": 20,
                    "bpm": 20,
                },
            ],
        }

        plan = service._validate(raw, num_songs=2, album_concept="chillout nature meditation flute ocean")  # noqa: SLF001
        self.assertEqual(len(plan.songs), 2)
        self.assertLessEqual(len(plan.album_name), 32)
        self.assertTrue(all(len(song.name) <= 30 for song in plan.songs))
        self.assertTrue(all(not song.name.lower().startswith(("track", "song")) for song in plan.songs))
        self.assertTrue(all(30 <= song.duration_seconds <= 420 for song in plan.songs))
        self.assertTrue(all(song.bpm is None or 40 <= song.bpm <= 240 for song in plan.songs))
        self.assertTrue(all(len(song.music_prompt.split()) >= 18 for song in plan.songs))


if __name__ == "__main__":
    unittest.main()
