"""Music generation service — generates songs one-by-one via ACE-Step 1.5."""

from src.core.storage import song_path, song_public_url
from src.models.album import SongPlan, SongResult
from src.tools.acestep import AceStepTool


class MusicService:
    """Generates songs sequentially using the ACE-Step 1.5 REST API."""

    def __init__(self, acestep: AceStepTool) -> None:
        self._acestep = acestep

    async def generate_song(
        self,
        album_id: str,
        song: SongPlan,
    ) -> SongResult:
        """Generate one song and return its result.

        Args:
            album_id: Album identifier used for file paths.
            song: Song plan to render.

        Returns:
            SongResult for the completed song.

        Raises:
            MusicGenerationError: If song generation fails.
        """
        output = song_path(album_id, song.index, song.name)
        await self._acestep.generate_song(
            music_prompt=song.music_prompt,
            lyrics=song.lyrics,
            instrumental=song.instrumental,
            duration_seconds=song.duration_seconds,
            bpm=song.bpm,
            output_path=output,
            thinking=True,
            use_cot_caption=True,
            use_cot_language=True,
            use_cot_metas=True,
        )

        audio_url = song_public_url(album_id, output.name)
        return SongResult(
            index=song.index,
            name=song.name,
            description=song.description,
            duration_seconds=song.duration_seconds,
            audio_url=audio_url,
        )
