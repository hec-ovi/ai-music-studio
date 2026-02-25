"""Album domain models — request, plan, and result DTOs."""

from typing import Annotated
from pydantic import BaseModel, Field


class AlbumRequest(BaseModel):
    """User request to generate a complete album."""

    concept: Annotated[str, Field(description="Album concept, name, or theme description")]
    num_songs: Annotated[int, Field(default=7, ge=1, le=12, description="Number of songs to generate")]


class SongPlan(BaseModel):
    """AI-planned metadata for a single song."""

    index: Annotated[int, Field(description="Song position (0-based)")]
    name: Annotated[str, Field(description="Song title")]
    music_prompt: Annotated[str, Field(description="ACE-Step music generation prompt")]
    lyrics: Annotated[str, Field(default="", description="Song lyrics (empty = instrumental)")]
    instrumental: Annotated[bool, Field(default=False, description="True if no vocals")]
    duration_seconds: Annotated[float, Field(ge=30, le=420, description="Target duration in seconds")]
    bpm: Annotated[int | None, Field(default=None, ge=40, le=240, description="Beats per minute")]
    description: Annotated[str, Field(description="Short song description for display")]


class AlbumPlan(BaseModel):
    """Complete album plan produced by the LLM."""

    album_name: Annotated[str, Field(description="Generated album title")]
    album_description: Annotated[str, Field(description="Album concept summary")]
    cover_prompt: Annotated[str, Field(description="FLUX image generation prompt for album cover")]
    songs: Annotated[list[SongPlan], Field(description="Ordered list of songs to generate")]


class SongResult(BaseModel):
    """Result for a single generated song."""

    index: Annotated[int, Field(description="Song position (0-based)")]
    name: Annotated[str, Field(description="Song title")]
    description: Annotated[str, Field(description="Short song description")]
    duration_seconds: Annotated[float, Field(description="Actual duration in seconds")]
    audio_url: Annotated[str, Field(description="URL to download the audio file")]


class SessionSong(BaseModel):
    """Persisted song row for album sessions (planned + generated fields)."""

    index: Annotated[int, Field(description="Song position (0-based)")]
    name: Annotated[str, Field(description="Song title")]
    music_prompt: Annotated[str, Field(description="ACE-Step prompt used/planned")]
    lyrics: Annotated[str, Field(description="Lyrics text (empty for instrumental)")]
    instrumental: Annotated[bool, Field(description="Instrumental flag")]
    duration_seconds: Annotated[float, Field(description="Target/actual duration in seconds")]
    bpm: Annotated[int | None, Field(default=None, description="Optional BPM hint")]
    description: Annotated[str, Field(description="Short song description")]
    audio_url: Annotated[str | None, Field(default=None, description="Generated audio URL")]
    status: Annotated[str, Field(default="planned", description="planned/generating/complete")]


class AlbumResult(BaseModel):
    """Complete generated album with cover and all songs."""

    album_id: Annotated[str, Field(description="Unique album identifier")]
    album_name: Annotated[str, Field(description="Album title")]
    album_description: Annotated[str, Field(description="Album description")]
    cover_url: Annotated[
        str | None,
        Field(description="URL to the album cover image, if generated"),
    ]
    songs: Annotated[list[SongResult], Field(description="All generated songs")]


class CreateAlbumResponse(BaseModel):
    """Immediate response after submitting an album generation request."""

    album_id: Annotated[str, Field(description="Unique album ID — use to stream progress")]
    status: Annotated[str, Field(default="queued", description="Initial status")]


class AlbumSummary(BaseModel):
    """Compact album session summary for library/history listing."""

    album_id: Annotated[str, Field(description="Unique album identifier")]
    folder: Annotated[str, Field(description="Filesystem folder used for this album")]
    album_name: Annotated[str | None, Field(default=None, description="Album title, if available")]
    concept: Annotated[str | None, Field(default=None, description="Original creation concept")]
    status: Annotated[str, Field(description="Current generation status")]
    cover_url: Annotated[str | None, Field(default=None, description="Cover URL when available")]
    songs_planned: Annotated[int, Field(description="Number of planned tracks")]
    songs_ready: Annotated[int, Field(description="Number of generated tracks")]
    include_cover: Annotated[bool, Field(description="Whether cover generation is enabled")]
    cover_size: Annotated[int, Field(description="Cover size in pixels")]
    song_length_seconds: Annotated[int | None, Field(default=None, description="Approx target track length")]
    created_at: Annotated[str, Field(description="Creation timestamp (UTC ISO)")]
    updated_at: Annotated[str, Field(description="Last update timestamp (UTC ISO)")]
    error: Annotated[str | None, Field(default=None, description="Last error, if any")]


class ExportArtifact(BaseModel):
    """Single exported artifact record."""

    id: Annotated[int | None, Field(default=None, description="Database export row id")]
    kind: Annotated[str, Field(description="Export kind (track_mp4, youtube_package, etc.)")]
    song_index: Annotated[int | None, Field(default=None, description="Song index for per-track artifacts")]
    file_name: Annotated[str, Field(description="File name in album folder")]
    url: Annotated[str, Field(description="Public URL to download/open artifact")]
    status: Annotated[str, Field(default="ready", description="Export status")]
    created_at: Annotated[str | None, Field(default=None, description="Created timestamp (UTC ISO)")]


class AlbumSession(BaseModel):
    """Full persisted album session detail."""

    album_id: Annotated[str, Field(description="Unique album identifier")]
    folder: Annotated[str, Field(description="Filesystem folder for this album")]
    concept: Annotated[str, Field(description="Original user concept")]
    requested_num_songs: Annotated[int, Field(description="Requested number of songs")]
    include_cover: Annotated[bool, Field(description="Whether cover generation was enabled")]
    cover_size: Annotated[int, Field(description="Cover size in pixels")]
    song_length_seconds: Annotated[int | None, Field(default=None, description="Approx target song length")]
    status: Annotated[str, Field(description="Album status")]
    album_name: Annotated[str | None, Field(default=None, description="Album title")]
    album_description: Annotated[str | None, Field(default=None, description="Album description")]
    cover_url: Annotated[str | None, Field(default=None, description="Cover URL")]
    error: Annotated[str | None, Field(default=None, description="Error details, if any")]
    created_at: Annotated[str, Field(description="Created timestamp")]
    updated_at: Annotated[str, Field(description="Updated timestamp")]
    completed_at: Annotated[str | None, Field(default=None, description="Completion timestamp")]
    songs: Annotated[list[SessionSong], Field(description="All planned/generated song rows")]
    exports: Annotated[list[ExportArtifact], Field(default_factory=list, description="Exported artifacts")]


class ExportTracksResponse(BaseModel):
    """Response for MP4 track export operation."""

    album_id: Annotated[str, Field(description="Album id")]
    album_name: Annotated[str, Field(description="Album display name")]
    exported_tracks: Annotated[int, Field(description="How many MP4 files were exported")]
    files: Annotated[list[ExportArtifact], Field(description="Per-track export records")]


class YouTubePackageResponse(BaseModel):
    """Response for YouTube metadata/package export."""

    album_id: Annotated[str, Field(description="Album id")]
    album_name: Annotated[str, Field(description="Album display name")]
    playlist_title: Annotated[str, Field(description="Suggested playlist title")]
    files: Annotated[list[ExportArtifact], Field(description="Generated package files")]
