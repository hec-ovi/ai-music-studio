from __future__ import annotations

import unittest

from src.tools.acestep import AceStepTool


class AceStepPromptLimitTests(unittest.TestCase):
    def test_fit_prompt_limits_words_and_chars(self) -> None:
        long_prompt = " ".join(f"token{i}" for i in range(300))
        clipped = AceStepTool._fit_prompt(long_prompt)  # noqa: SLF001
        self.assertLessEqual(len(clipped.split()), 96)
        self.assertLessEqual(len(clipped), 720)

    def test_fit_lyrics_limits_words_and_chars(self) -> None:
        long_lyrics = "\n".join(f"line {i} " + ("la " * 20) for i in range(200))
        clipped = AceStepTool._fit_lyrics(long_lyrics)  # noqa: SLF001
        self.assertLessEqual(len(clipped.split()), 320)
        self.assertLessEqual(len(clipped), 1800)


if __name__ == "__main__":
    unittest.main()
