"""Album generation routes — create + SSE stream progress."""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.core.db import (
    clear_exports,
    create_album_session,
    get_album_session,
    list_albums,
    mark_song_running,
    record_export,
    replace_album_plan,
    update_album,
    upsert_song_result,
)
from src.core.exceptions import (
    CoverGenerationError,
    ExportError,
    MusicGenerationError,
    PlanningError,
    ServiceUnavailableError,
)
from src.core.storage import (
    clear_generated_assets,
    cover_path,
    cover_public_url,
    init_album,
    load_plan,
    save_plan,
    set_album_folder,
)
from src.models.album import (
    AlbumPlan,
    AlbumRequest,
    AlbumResult,
    AlbumSession,
    AlbumSummary,
    CreateAlbumResponse,
    ExportArtifact,
    ExportTracksResponse,
    SessionSong,
    SongResult,
    YouTubePackageResponse,
)
from src.models.progress import ProgressEvent
from src.services.album_planner import AlbumPlannerService
from src.services.cover import CoverService
from src.services.export import ExportService
from src.services.music import MusicService
from src.tools.acestep import AceStepTool
from src.tools.flux import FluxTool
from src.tools.ollama import OllamaTool

router = APIRouter()
logger = logging.getLogger(__name__)


def _sse(event: ProgressEvent) -> str:
    """Format one SSE event payload."""
    return f"data: {event.model_dump_json()}\n\n"


def _to_song_plan(song_row: dict) -> SessionSong:
    return SessionSong(
        index=int(song_row.get("song_index", 0)),
        name=str(song_row.get("name", "Track")),
        music_prompt=str(song_row.get("music_prompt", "")),
        lyrics=str(song_row.get("lyrics", "")),
        instrumental=bool(song_row.get("instrumental", True)),
        duration_seconds=float(song_row.get("duration_seconds", 60.0)),
        bpm=song_row.get("bpm"),
        description=str(song_row.get("description", "")),
        audio_url=song_row.get("audio_url"),
        status=str(song_row.get("status", "planned")),
    )


def _to_export_artifact(row: dict) -> ExportArtifact:
    return ExportArtifact(
        id=row.get("id"),
        kind=str(row.get("kind", "unknown")),
        song_index=row.get("song_index"),
        file_name=str(row.get("file_name", "")),
        url=str(row.get("url", "")),
        status=str(row.get("status", "ready")),
        created_at=row.get("created_at"),
    )


@router.post("/albums", tags=["Albums"])
async def create_album(request: AlbumRequest) -> CreateAlbumResponse:
    """Submit an album generation request.

    Returns immediately with an album_id. Use GET /api/albums/{album_id}/stream
    to receive real-time SSE progress events.

    Args:
        request: Album concept and song count.

    Returns:
        CreateAlbumResponse with the album_id to track progress.
    """
    album_id = str(uuid.uuid4())
    init_album(album_id)
    create_album_session(
        album_id=album_id,
        folder=album_id,
        concept=request.concept,
        requested_num_songs=request.num_songs,
        status="queued",
    )
    return CreateAlbumResponse(album_id=album_id, status="queued")


@router.get("/albums", tags=["Albums"])
async def list_album_sessions(
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AlbumSummary]:
    """List persisted album sessions for history/navigation."""
    rows = list_albums(limit=limit)
    return [
        AlbumSummary(
            album_id=str(row["album_id"]),
            folder=str(row["folder"]),
            album_name=row.get("album_name"),
            concept=row.get("concept"),
            status=str(row.get("status", "queued")),
            cover_url=row.get("cover_url"),
            songs_planned=int(row.get("songs_planned", 0)),
            songs_ready=int(row.get("songs_ready", 0)),
            include_cover=bool(row.get("include_cover", True)),
            cover_size=int(row.get("cover_size", 1024)),
            song_length_seconds=row.get("song_length_seconds"),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            error=row.get("error"),
        )
        for row in rows
    ]


@router.get(
    "/albums/{album_id}/session",
    tags=["Albums"],
    responses={404: {"description": "Album session not found"}},
)
async def get_album_session_detail(album_id: str) -> AlbumSession:
    """Return one persisted album session with songs and exports."""
    payload = get_album_session(album_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Album session not found")

    album = payload["album"]
    songs = payload["songs"]
    exports = payload["exports"]

    return AlbumSession(
        album_id=str(album["album_id"]),
        folder=str(album["folder"]),
        concept=str(album.get("concept", "")),
        requested_num_songs=int(album.get("requested_num_songs", 0)),
        include_cover=bool(album.get("include_cover", 1)),
        cover_size=int(album.get("cover_size", 1024)),
        song_length_seconds=album.get("song_length_seconds"),
        status=str(album.get("status", "queued")),
        album_name=album.get("album_name"),
        album_description=album.get("album_description"),
        cover_url=album.get("cover_url"),
        error=album.get("error"),
        created_at=str(album.get("created_at", "")),
        updated_at=str(album.get("updated_at", "")),
        completed_at=album.get("completed_at"),
        songs=[_to_song_plan(row) for row in songs],
        exports=[_to_export_artifact(row) for row in exports],
    )


@router.post(
    "/albums/{album_id}/exports/mp4",
    tags=["Exports"],
    responses={404: {"description": "Album not found"}},
)
async def export_album_mp4(album_id: str) -> ExportTracksResponse:
    """Export one static-cover MP4 per generated track."""
    try:
        data = load_plan(album_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Album not found") from exc

    service = ExportService()
    try:
        files = service.export_track_mp4(album_id)
    except ExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clear_exports(album_id, kind="track_mp4")
    clear_exports(album_id, kind="track_mp4_index")
    for item in files:
        record_export(
            album_id=album_id,
            kind=item.kind,
            file_name=item.file_name,
            url=item.url,
            song_index=item.song_index,
            status=item.status,
        )

    album_name = str(data.get("plan", {}).get("album_name", "Untitled"))
    return ExportTracksResponse(
        album_id=album_id,
        album_name=album_name,
        exported_tracks=sum(1 for f in files if f.kind == "track_mp4"),
        files=files,
    )


@router.post(
    "/albums/{album_id}/exports/youtube-package",
    tags=["Exports"],
    responses={404: {"description": "Album not found"}},
)
async def export_youtube_package(album_id: str) -> YouTubePackageResponse:
    """Export YouTube playlist/video metadata package for an album."""
    try:
        data = load_plan(album_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Album not found") from exc

    service = ExportService()
    try:
        # Ensure MP4s exist before packaging.
        mp4_files = service.export_track_mp4(album_id)
        files = service.generate_youtube_package(album_id)
    except ExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clear_exports(album_id, kind="track_mp4")
    clear_exports(album_id, kind="track_mp4_index")
    for item in mp4_files:
        record_export(
            album_id=album_id,
            kind=item.kind,
            file_name=item.file_name,
            url=item.url,
            song_index=item.song_index,
            status=item.status,
        )

    clear_exports(album_id, kind="youtube_package")
    for item in files:
        record_export(
            album_id=album_id,
            kind=item.kind,
            file_name=item.file_name,
            url=item.url,
            song_index=item.song_index,
            status=item.status,
        )

    album_name = str(data.get("plan", {}).get("album_name", "Untitled"))
    return YouTubePackageResponse(
        album_id=album_id,
        album_name=album_name,
        playlist_title=album_name,
        files=files,
    )


@router.get("/albums/{album_id}/stream", tags=["Albums"])
async def stream_album_generation(
    album_id: str,
    concept: str | None = Query(
        default=None,
        description="Album concept for planning (not required when use_saved_plan=true).",
    ),
    num_songs: int = Query(
        default=7,
        ge=1,
        le=12,
        description="Number of songs to generate (1..12).",
    ),
    include_cover: bool = Query(
        default=True,
        description="If false, skip FLUX cover generation and generate music only.",
    ),
    cover_size: int = Query(
        default=1024,
        ge=512,
        le=1024,
        description="Cover size in pixels (square).",
    ),
    stop_after_plan: bool = Query(
        default=False,
        description="If true, stop after plan_ready so the plan can be reviewed/edited.",
    ),
    use_saved_plan: bool = Query(
        default=False,
        description="If true, skip planning and continue from the saved plan.",
    ),
    song_length_seconds: int | None = Query(
        default=None,
        ge=30,
        le=420,
        description=(
            "Approximate target song duration in seconds (30..420) "
            "for newly planned songs."
        ),
    ),
) -> StreamingResponse:
    """Stream album generation progress as Server-Sent Events.

    Connect after POST /api/albums. The stream emits typed events:
    - planning: LLM is generating the album plan
    - plan_ready: Plan is complete (includes song list)
    - plan_review_required: Stream paused after planning for manual review/approval
    - song_start: ACE-Step starting a song
    - song_ready: Song is complete (includes audio URL)
    - cover_generating: FLUX is rendering the album cover
    - cover_ready: Cover is complete (includes cover URL)
    - complete: Full album ready (includes all data)
    - error: A stage failed (includes error message)

    Args:
        album_id: Album ID from POST /api/albums.
        concept: Album concept (passed through for generation).
        num_songs: Number of songs to generate.
        include_cover: Whether to generate album cover art.
        cover_size: Cover size in pixels (512 or 1024).
        stop_after_plan: Pause stream after planning.
        use_saved_plan: Reuse previously saved plan.
        song_length_seconds: Optional per-song target duration hint.

    Returns:
        SSE stream of ProgressEvent JSON objects.
    """
    if cover_size not in {512, 1024}:
        raise HTTPException(status_code=422, detail="cover_size must be 512 or 1024")

    return StreamingResponse(
        _safe_generation_stream(
            album_id=album_id,
            concept=concept,
            num_songs=num_songs,
            include_cover=include_cover,
            cover_size=cover_size,
            stop_after_plan=stop_after_plan,
            use_saved_plan=use_saved_plan,
            song_length_seconds=song_length_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/albums/{album_id}/result",
    tags=["Albums"],
    responses={404: {"description": "Album not found or not yet complete"}},
)
async def get_album_result(album_id: str) -> AlbumResult:
    """Retrieve the completed album result.

    Args:
        album_id: Album identifier.

    Returns:
        Full AlbumResult with cover URL and song list.

    Raises:
        HTTPException 404: If the album_id is unknown or generation not complete.
    """
    try:
        data = load_plan(album_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Album not found or not yet complete") from exc

    if data.get("status") != "complete":
        raise HTTPException(status_code=404, detail="Album not found or not yet complete")

    plan = data.get("plan", {})
    songs = data.get("songs", [])
    cover_url = data.get("cover_url")
    if cover_url is None and cover_path(album_id).exists():
        cover_url = cover_public_url(album_id)

    return AlbumResult(
        album_id=album_id,
        album_name=plan.get("album_name", "Untitled"),
        album_description=plan.get("album_description", ""),
        cover_url=cover_url,
        songs=[SongResult(**s) for s in songs],
    )


@router.get(
    "/albums/{album_id}/plan",
    tags=["Albums"],
    responses={404: {"description": "Album plan not found"}},
)
async def get_album_plan(album_id: str) -> AlbumPlan:
    """Return the currently saved editable album plan."""
    try:
        data = load_plan(album_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Album plan not found") from exc

    try:
        return _normalize_plan(AlbumPlan.model_validate(data.get("plan", {})))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Saved plan is invalid: {exc}") from exc


@router.put(
    "/albums/{album_id}/plan",
    tags=["Albums"],
    responses={
        404: {"description": "Album plan not found"},
        409: {"description": "Cannot edit plan after song generation has started"},
    },
)
async def update_album_plan(album_id: str, plan: AlbumPlan) -> AlbumPlan:
    """Update an album plan before generation starts."""
    normalized_plan = _normalize_plan(plan)

    try:
        existing = load_plan(album_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Album plan not found") from exc

    existing_songs = existing.get("songs", [])
    if existing_songs:
        raise HTTPException(status_code=409, detail="Cannot edit plan after song generation has started")

    folder = set_album_folder(album_id, normalized_plan.album_name)
    save_plan(album_id, _state_payload(
        album_id=album_id,
        plan=normalized_plan,
        songs=[],
        cover_url=existing.get("cover_url"),
        status=existing.get("status", "plan_ready"),
    ))
    replace_album_plan(album_id, normalized_plan.model_dump())
    update_album(
        album_id,
        folder=folder,
        album_name=normalized_plan.album_name,
        album_description=normalized_plan.album_description,
        status=existing.get("status", "plan_ready"),
        error=None,
    )
    return normalized_plan


# ─── SSE generation stream ────────────────────────────────────────────────────

def _normalize_plan(plan: AlbumPlan) -> AlbumPlan:
    if not plan.songs:
        raise HTTPException(status_code=400, detail="Plan must include at least one song")
    if len(plan.songs) > 12:
        raise HTTPException(status_code=400, detail="Plan cannot exceed 12 songs")

    normalized_songs = [
        song.model_copy(update={"index": idx})
        for idx, song in enumerate(plan.songs)
    ]
    return plan.model_copy(update={"songs": normalized_songs})


def _state_payload(
    album_id: str,
    plan: AlbumPlan,
    songs: list[SongResult],
    cover_url: str | None,
    status: str,
) -> dict:
    return {
        "album_id": album_id,
        "plan": plan.model_dump(),
        "songs": [song.model_dump() for song in songs],
        "cover_url": cover_url,
        "status": status,
    }


def _plan_payload(plan: AlbumPlan) -> dict:
    return {
        "album_name": plan.album_name,
        "album_description": plan.album_description,
        "songs": [
            {"index": s.index, "name": s.name, "description": s.description}
            for s in plan.songs
        ],
    }


def _load_saved_song_results(data: dict) -> list[SongResult]:
    songs = data.get("songs", [])
    if not isinstance(songs, list):
        return []

    loaded: dict[int, SongResult] = {}
    for raw in songs:
        try:
            item = SongResult.model_validate(raw)
            loaded[item.index] = item
        except Exception:  # noqa: BLE001
            continue

    return [loaded[idx] for idx in sorted(loaded)]


async def _generation_stream(
    album_id: str,
    concept: str | None,
    num_songs: int,
    include_cover: bool,
    cover_size: int,
    stop_after_plan: bool,
    use_saved_plan: bool,
    song_length_seconds: int | None,
) -> AsyncGenerator[str, None]:
    """Full end-to-end generation pipeline emitting SSE events."""

    ollama = OllamaTool()
    flux = FluxTool()
    acestep = AceStepTool()
    planner = AlbumPlannerService(ollama)
    cover_svc = CoverService(flux)
    music_svc = MusicService(acestep)

    songs_collected: list[SongResult] = []
    plan: AlbumPlan | None = None
    cover_url: str | None = None

    create_album_session(
        album_id=album_id,
        folder=album_id,
        concept=concept or "",
        requested_num_songs=num_songs,
        include_cover=include_cover,
        cover_size=cover_size,
        song_length_seconds=song_length_seconds,
        status="planning" if not use_saved_plan else "resuming",
    )
    update_album(
        album_id,
        concept=concept or "",
        requested_num_songs=num_songs,
        include_cover=include_cover,
        cover_size=cover_size,
        song_length_seconds=song_length_seconds,
        error=None,
    )

    # ── Stage 1: Plan load / creation ───────────────────────────────────────
    if use_saved_plan:
        yield _sse(ProgressEvent(
            event="planning",
            message="Loading saved album plan…",
            progress=0.05,
        ))
        try:
            saved = load_plan(album_id)
            plan = _normalize_plan(AlbumPlan.model_validate(saved.get("plan", {})))
            folder = set_album_folder(album_id, plan.album_name)
            replace_album_plan(album_id, plan.model_dump())
            valid_indexes = {s.index for s in plan.songs}
            songs_collected = [
                song
                for song in _load_saved_song_results(saved)
                if song.index in valid_indexes
            ]
            cover_url = saved.get("cover_url")
            if cover_url is None and cover_path(album_id).exists():
                cover_url = cover_public_url(album_id)
            update_album(
                album_id,
                folder=folder,
                album_name=plan.album_name,
                album_description=plan.album_description,
                cover_url=cover_url,
                status=saved.get("status", "plan_ready"),
                error=None,
            )
            for song in songs_collected:
                upsert_song_result(
                    album_id=album_id,
                    song_index=song.index,
                    name=song.name,
                    description=song.description,
                    duration_seconds=song.duration_seconds,
                    audio_url=song.audio_url,
                )
        except FileNotFoundError:
            update_album(album_id, status="error", error="No saved plan found")
            yield _sse(ProgressEvent(
                event="error",
                message="No saved plan found for this album. Generate a plan first.",
                progress=0.0,
            ))
            return
        except Exception as exc:  # noqa: BLE001
            update_album(album_id, status="error", error=f"Saved plan invalid: {exc}")
            yield _sse(ProgressEvent(
                event="error",
                message=f"Saved plan is invalid: {exc}",
                progress=0.0,
            ))
            return

        resume_note = ""
        if songs_collected:
            resume_note = f" — resuming from song {len(songs_collected) + 1}"

        yield _sse(ProgressEvent(
            event="plan_ready",
            message=f"Loaded saved plan: {plan.album_name} — {len(plan.songs)} songs{resume_note}",
            data=_plan_payload(plan),
            progress=0.15,
        ))
    else:
        if not concept:
            update_album(album_id, status="error", error="concept is required when use_saved_plan=false")
            yield _sse(ProgressEvent(
                event="error",
                message="concept is required when use_saved_plan=false",
                progress=0.0,
            ))
            return

        yield _sse(ProgressEvent(
            event="planning",
            message=f"Generating album plan for: {concept}",
            progress=0.05,
        ))

        try:
            plan = _normalize_plan(await planner.plan(concept, num_songs))
            if song_length_seconds is not None:
                plan = _apply_song_length_hint(plan, song_length_seconds)
        except (PlanningError, ServiceUnavailableError) as exc:
            update_album(album_id, status="error", error=str(exc))
            yield _sse(ProgressEvent(event="error", message=str(exc), progress=0.0))
            return

        folder = set_album_folder(album_id, plan.album_name)
        save_plan(album_id, _state_payload(
            album_id=album_id,
            plan=plan,
            songs=[],
            cover_url=None,
            status="plan_ready",
        ))
        replace_album_plan(album_id, plan.model_dump())
        update_album(
            album_id,
            folder=folder,
            album_name=plan.album_name,
            album_description=plan.album_description,
            status="plan_ready",
            error=None,
        )

        yield _sse(ProgressEvent(
            event="plan_ready",
            message=f"Album planned: {plan.album_name} — {len(plan.songs)} songs",
            data=_plan_payload(plan),
            progress=0.15,
        ))

    if stop_after_plan:
        save_plan(album_id, _state_payload(
            album_id=album_id,
            plan=plan,
            songs=songs_collected,
            cover_url=cover_url,
            status="plan_review_required",
        ))
        update_album(album_id, status="plan_review_required", cover_url=cover_url, error=None)
        yield _sse(ProgressEvent(
            event="plan_review_required",
            message="Plan ready for review. Edit prompts, then approve to continue.",
            data={"album_id": album_id},
            progress=0.17,
        ))
        return

    # Start clean only when this is a fresh run. Resume keeps existing files/results.
    if not songs_collected and cover_url is None:
        clear_generated_assets(album_id)
        clear_exports(album_id)

    save_plan(album_id, _state_payload(
        album_id=album_id,
        plan=plan,
        songs=songs_collected,
        cover_url=cover_url,
        status="generating",
    ))
    update_album(album_id, status="generating", cover_url=cover_url, error=None)

    # ── Stage 2: Song Generation (ACE-Step) ─────────────────────────────────
    completed_indexes = {song.index for song in songs_collected}
    total_songs = len(plan.songs)
    base_progress = 0.20
    song_budget = 0.70 if include_cover else 0.75
    per_song = song_budget / max(total_songs, 1)

    for song in plan.songs:
        if song.index in completed_indexes:
            continue

        song_idx = song.index
        progress_start = base_progress + song_idx * per_song
        mark_song_running(album_id, song_idx)

        yield _sse(ProgressEvent(
            event="song_start",
            message=f"Generating song {song_idx + 1}/{total_songs}: {song.name}",
            data={"index": song_idx, "name": song.name},
            progress=progress_start,
        ))

        song_task = asyncio.create_task(music_svc.generate_song(album_id, song))
        try:
            heartbeat_seconds = 0
            while not song_task.done():
                done, _ = await asyncio.wait({song_task}, timeout=15.0)
                if song_task in done:
                    break
                heartbeat_seconds += 15
                heartbeat_progress = min(
                    progress_start + (heartbeat_seconds / 6000.0),
                    progress_start + per_song * 0.85,
                )
                yield _sse(ProgressEvent(
                    event="song_progress",
                    message=f"Still generating: {song.name} ({heartbeat_seconds}s)",
                    data={
                        "index": song_idx,
                        "name": song.name,
                        "elapsed_seconds": heartbeat_seconds,
                    },
                    progress=min(heartbeat_progress, 0.96),
                ))

            song_result = song_task.result()
        except (MusicGenerationError, ServiceUnavailableError) as exc:
            progress_now = base_progress + len(songs_collected) * per_song
            save_plan(album_id, _state_payload(
                album_id=album_id,
                plan=plan,
                songs=songs_collected,
                cover_url=cover_url,
                status="error",
            ))
            update_album(album_id, status="error", error=f"Song generation failed: {exc}")
            yield _sse(ProgressEvent(
                event="error",
                message=f"Song generation failed: {exc}",
                progress=min(progress_now, 0.97),
            ))
            return
        except Exception as exc:  # noqa: BLE001
            progress_now = base_progress + len(songs_collected) * per_song
            save_plan(album_id, _state_payload(
                album_id=album_id,
                plan=plan,
                songs=songs_collected,
                cover_url=cover_url,
                status="error",
            ))
            update_album(album_id, status="error", error=f"Song generation failed unexpectedly: {exc}")
            yield _sse(ProgressEvent(
                event="error",
                message=f"Song generation failed unexpectedly: {exc}",
                progress=min(progress_now, 0.97),
            ))
            return
        finally:
            if not song_task.done():
                song_task.cancel()
                with suppress(asyncio.CancelledError):
                    await song_task

        songs_collected.append(song_result)
        completed_indexes.add(song_result.index)

        save_plan(album_id, _state_payload(
            album_id=album_id,
            plan=plan,
            songs=songs_collected,
            cover_url=cover_url,
            status="generating",
        ))
        upsert_song_result(
            album_id=album_id,
            song_index=song_result.index,
            name=song_result.name,
            description=song_result.description,
            duration_seconds=song_result.duration_seconds,
            audio_url=song_result.audio_url,
        )
        update_album(album_id, status="generating", error=None)

        progress_done = base_progress + (song_idx + 1) * per_song
        yield _sse(ProgressEvent(
            event="song_ready",
            message=f"Song ready: {song_result.name}",
            data=song_result.model_dump(),
            progress=min(progress_done, 0.95 if include_cover else 0.97),
        ))

    # ── Stage 3: Cover Generation (FLUX) ────────────────────────────────────
    if include_cover:
        if cover_url and cover_path(album_id).exists():
            update_album(album_id, status="cover_ready", cover_url=cover_url, error=None)
            yield _sse(ProgressEvent(
                event="cover_ready",
                message="Album cover already generated (resume)",
                data={"cover_url": cover_url},
                progress=0.98,
            ))
        else:
            yield _sse(ProgressEvent(
                event="cover_generating",
                message="Generating album cover with FLUX.2-klein…",
                progress=0.93,
            ))

            save_plan(album_id, _state_payload(
                album_id=album_id,
                plan=plan,
                songs=songs_collected,
                cover_url=cover_url,
                status="cover_generating",
            ))
            update_album(album_id, status="cover_generating", cover_url=cover_url, error=None)

            try:
                cover_url = await cover_svc.generate(plan.cover_prompt, album_id, size=cover_size)
            except (CoverGenerationError, ServiceUnavailableError) as exc:
                save_plan(album_id, _state_payload(
                    album_id=album_id,
                    plan=plan,
                    songs=songs_collected,
                    cover_url=cover_url,
                    status="error",
                ))
                update_album(album_id, status="error", error=f"Cover generation failed: {exc}")
                yield _sse(ProgressEvent(
                    event="error",
                    message=f"Cover generation failed: {exc}",
                    progress=0.93,
                ))
                return

            save_plan(album_id, _state_payload(
                album_id=album_id,
                plan=plan,
                songs=songs_collected,
                cover_url=cover_url,
                status="cover_ready",
            ))
            update_album(album_id, status="cover_ready", cover_url=cover_url, error=None)
        yield _sse(ProgressEvent(
            event="cover_ready",
            message="Album cover ready",
            data={"cover_url": cover_url},
            progress=0.98,
        ))
    else:
        cover_url = None
        save_plan(album_id, _state_payload(
            album_id=album_id,
            plan=plan,
            songs=songs_collected,
            cover_url=cover_url,
            status="cover_skipped",
        ))
        update_album(album_id, status="cover_skipped", cover_url=None, error=None)
        yield _sse(ProgressEvent(
            event="cover_ready",
            message="Cover skipped (music-only mode)",
            data={"cover_url": None},
            progress=0.98,
        ))

    # ── Stage 4: Complete ────────────────────────────────────────────────────
    result = AlbumResult(
        album_id=album_id,
        album_name=plan.album_name,
        album_description=plan.album_description,
        cover_url=cover_url,
        songs=songs_collected,
    )

    save_plan(album_id, _state_payload(
        album_id=album_id,
        plan=plan,
        songs=songs_collected,
        cover_url=cover_url,
        status="complete",
    ))
    update_album(
        album_id,
        status="complete",
        cover_url=cover_url,
        error=None,
        completed_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )

    yield _sse(ProgressEvent(
        event="complete",
        message=f"Album complete: {plan.album_name}",
        data=result.model_dump(),
        progress=1.0,
    ))


def _apply_song_length_hint(plan: AlbumPlan, song_length_seconds: int) -> AlbumPlan:
    """Apply one approximate duration target across all planned songs."""
    target = float(song_length_seconds)
    return plan.model_copy(update={
        "songs": [
            song.model_copy(update={"duration_seconds": target})
            for song in plan.songs
        ]
    })


async def _safe_generation_stream(
    album_id: str,
    concept: str | None,
    num_songs: int,
    include_cover: bool,
    cover_size: int,
    stop_after_plan: bool,
    use_saved_plan: bool,
    song_length_seconds: int | None,
) -> AsyncGenerator[str, None]:
    """Wrap generation stream to avoid abrupt chunk termination on uncaught errors."""
    try:
        async for chunk in _generation_stream(
            album_id=album_id,
            concept=concept,
            num_songs=num_songs,
            include_cover=include_cover,
            cover_size=cover_size,
            stop_after_plan=stop_after_plan,
            use_saved_plan=use_saved_plan,
            song_length_seconds=song_length_seconds,
        ):
            yield chunk
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled album stream failure for album_id=%s", album_id)
        update_album(album_id, status="error", error=f"Unhandled stream failure: {exc}")
        yield _sse(ProgressEvent(
            event="error",
            message=f"Generation failed unexpectedly: {exc}",
            progress=0.0,
        ))
