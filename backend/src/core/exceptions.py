"""Domain exceptions for AI Music Studio backend."""


class AlbumNotFoundError(Exception):
    """Raised when an album_id does not correspond to any active generation."""


class PlanningError(Exception):
    """Raised when Ollama LLM fails to produce a valid album plan."""


class CoverGenerationError(Exception):
    """Raised when the FLUX service fails to generate the album cover."""


class MusicGenerationError(Exception):
    """Raised when ACE-Step fails to generate a song."""


class ServiceUnavailableError(Exception):
    """Raised when a downstream service (Ollama, FLUX, ACE-Step) is unreachable."""


class ExportError(Exception):
    """Raised when local media export (MP4/package) fails."""
