"""Tiny SQLite persistence layer for album sessions, songs, and exports."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.config import settings


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _db_path() -> Path:
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create database schema if missing."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS albums (
                album_id TEXT PRIMARY KEY,
                folder TEXT NOT NULL,
                concept TEXT NOT NULL DEFAULT '',
                requested_num_songs INTEGER NOT NULL DEFAULT 0,
                include_cover INTEGER NOT NULL DEFAULT 1,
                cover_size INTEGER NOT NULL DEFAULT 1024,
                song_length_seconds INTEGER,
                status TEXT NOT NULL DEFAULT 'queued',
                album_name TEXT,
                album_description TEXT,
                cover_url TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS songs (
                album_id TEXT NOT NULL,
                song_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                music_prompt TEXT NOT NULL DEFAULT '',
                lyrics TEXT NOT NULL DEFAULT '',
                instrumental INTEGER NOT NULL DEFAULT 1,
                duration_seconds REAL NOT NULL DEFAULT 60,
                bpm INTEGER,
                audio_url TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (album_id, song_index),
                FOREIGN KEY (album_id) REFERENCES albums(album_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                album_id TEXT NOT NULL,
                song_index INTEGER,
                kind TEXT NOT NULL,
                file_name TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                created_at TEXT NOT NULL,
                FOREIGN KEY (album_id) REFERENCES albums(album_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_albums_updated_at ON albums(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_songs_album_status ON songs(album_id, status);
            CREATE INDEX IF NOT EXISTS idx_exports_album_kind ON exports(album_id, kind);
            """
        )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def create_album_session(
    album_id: str,
    folder: str,
    concept: str = "",
    requested_num_songs: int = 0,
    include_cover: bool = True,
    cover_size: int = 1024,
    song_length_seconds: int | None = None,
    status: str = "queued",
) -> None:
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO albums (
                album_id, folder, concept, requested_num_songs, include_cover, cover_size,
                song_length_seconds, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(album_id) DO UPDATE SET
                folder=excluded.folder,
                concept=excluded.concept,
                requested_num_songs=excluded.requested_num_songs,
                include_cover=excluded.include_cover,
                cover_size=excluded.cover_size,
                song_length_seconds=excluded.song_length_seconds,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                album_id,
                folder,
                concept.strip(),
                requested_num_songs,
                int(include_cover),
                cover_size,
                song_length_seconds,
                status,
                now,
                now,
            ),
        )


def update_album(album_id: str, **fields: Any) -> None:
    """Update a subset of album fields."""
    if not fields:
        return

    allowed = {
        "folder",
        "concept",
        "requested_num_songs",
        "include_cover",
        "cover_size",
        "song_length_seconds",
        "status",
        "album_name",
        "album_description",
        "cover_url",
        "error",
        "completed_at",
    }
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return

    if "include_cover" in data:
        data["include_cover"] = int(bool(data["include_cover"]))
    if "concept" in data and isinstance(data["concept"], str):
        data["concept"] = data["concept"].strip()

    data["updated_at"] = _utc_now()
    columns = ", ".join(f"{k}=?" for k in data)
    values = list(data.values()) + [album_id]

    with _connect() as conn:
        conn.execute(f"UPDATE albums SET {columns} WHERE album_id=?", values)


def replace_album_plan(album_id: str, plan: dict[str, Any]) -> None:
    """Persist current plan and replace planned song rows."""
    songs = plan.get("songs", [])
    now = _utc_now()

    with _connect() as conn:
        conn.execute("DELETE FROM songs WHERE album_id=?", (album_id,))
        for idx, raw in enumerate(songs):
            if not isinstance(raw, dict):
                continue
            conn.execute(
                """
                INSERT INTO songs (
                    album_id, song_index, name, description, music_prompt, lyrics,
                    instrumental, duration_seconds, bpm, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
                ON CONFLICT(album_id, song_index) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    music_prompt=excluded.music_prompt,
                    lyrics=excluded.lyrics,
                    instrumental=excluded.instrumental,
                    duration_seconds=excluded.duration_seconds,
                    bpm=excluded.bpm,
                    status='planned',
                    updated_at=excluded.updated_at
                """,
                (
                    album_id,
                    idx,
                    str(raw.get("name", f"Track {idx + 1}")),
                    str(raw.get("description", "")),
                    str(raw.get("music_prompt", "")),
                    str(raw.get("lyrics", "")),
                    int(bool(raw.get("instrumental", True))),
                    float(raw.get("duration_seconds", 60.0)),
                    _to_int_or_none(raw.get("bpm")),
                    now,
                    now,
                ),
            )

    update_album(
        album_id,
        album_name=str(plan.get("album_name", "")),
        album_description=str(plan.get("album_description", "")),
    )


def mark_song_running(album_id: str, song_index: int) -> None:
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE songs
            SET status='generating', updated_at=?
            WHERE album_id=? AND song_index=?
            """,
            (now, album_id, song_index),
        )


def upsert_song_result(
    album_id: str,
    song_index: int,
    name: str,
    description: str,
    duration_seconds: float,
    audio_url: str,
) -> None:
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO songs (
                album_id, song_index, name, description, duration_seconds,
                audio_url, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'complete', ?, ?)
            ON CONFLICT(album_id, song_index) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                duration_seconds=excluded.duration_seconds,
                audio_url=excluded.audio_url,
                status='complete',
                updated_at=excluded.updated_at
            """,
            (
                album_id,
                song_index,
                name,
                description,
                duration_seconds,
                audio_url,
                now,
                now,
            ),
        )


def list_albums(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                a.album_id,
                a.folder,
                a.concept,
                a.status,
                a.album_name,
                a.album_description,
                a.cover_url,
                a.include_cover,
                a.cover_size,
                a.requested_num_songs,
                a.song_length_seconds,
                a.error,
                a.created_at,
                a.updated_at,
                COUNT(s.song_index) AS songs_planned,
                SUM(CASE WHEN s.status='complete' THEN 1 ELSE 0 END) AS songs_ready
            FROM albums a
            LEFT JOIN songs s ON s.album_id = a.album_id
            GROUP BY a.album_id
            ORDER BY a.updated_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(row)
        item["include_cover"] = bool(item["include_cover"])
        item["songs_planned"] = int(item.get("songs_planned") or 0)
        item["songs_ready"] = int(item.get("songs_ready") or 0)
        result.append(item)
    return result


def get_album_session(album_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        album_row = conn.execute(
            "SELECT * FROM albums WHERE album_id=?",
            (album_id,),
        ).fetchone()
        if not album_row:
            return None

        song_rows = conn.execute(
            """
            SELECT * FROM songs
            WHERE album_id=?
            ORDER BY song_index ASC
            """,
            (album_id,),
        ).fetchall()

        export_rows = conn.execute(
            """
            SELECT id, kind, song_index, file_name, url, status, created_at
            FROM exports
            WHERE album_id=?
            ORDER BY id DESC
            """,
            (album_id,),
        ).fetchall()

    album = _row_to_dict(album_row)
    album["include_cover"] = bool(album["include_cover"])
    songs = [_row_to_dict(row) for row in song_rows]
    exports = [_row_to_dict(row) for row in export_rows]
    return {"album": album, "songs": songs, "exports": exports}


def clear_exports(album_id: str, kind: str | None = None) -> None:
    with _connect() as conn:
        if kind:
            conn.execute("DELETE FROM exports WHERE album_id=? AND kind=?", (album_id, kind))
        else:
            conn.execute("DELETE FROM exports WHERE album_id=?", (album_id,))


def record_export(
    album_id: str,
    kind: str,
    file_name: str,
    url: str,
    song_index: int | None = None,
    status: str = "ready",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO exports (
                album_id, kind, song_index, file_name, url, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                album_id,
                kind,
                song_index,
                file_name,
                url,
                status,
                _utc_now(),
            ),
        )


def backfill_from_storage(output_dir: str) -> None:
    """Backfill DB rows from persisted plan files if DB is empty/missing records."""
    output_root = Path(output_dir)
    albums_root = output_root / "albums"
    index_root = output_root / ".album-index"

    if not albums_root.exists():
        return

    # Build album_id -> folder mapping from index metadata first.
    album_folder_by_id: dict[str, str] = {}
    if index_root.exists():
        for meta_file in index_root.glob("*.json"):
            try:
                data = json.loads(meta_file.read_text())
            except Exception:  # noqa: BLE001
                continue
            album_id = str(data.get("album_id") or meta_file.stem).strip()
            folder = str(data.get("folder") or album_id).strip()
            if album_id and folder:
                album_folder_by_id[album_id] = folder

    # Also infer from plan payloads.
    for plan_file in albums_root.glob("*/plan.json"):
        try:
            payload = json.loads(plan_file.read_text())
        except Exception:  # noqa: BLE001
            continue
        album_id = str(payload.get("album_id") or "").strip()
        if album_id:
            album_folder_by_id.setdefault(album_id, plan_file.parent.name)

    for album_id, folder in album_folder_by_id.items():
        plan_file = albums_root / folder / "plan.json"
        payload: dict[str, Any] = {}
        if plan_file.exists():
            try:
                payload = json.loads(plan_file.read_text())
            except Exception:  # noqa: BLE001
                payload = {}

        plan = payload.get("plan", {}) if isinstance(payload, dict) else {}
        songs_planned = plan.get("songs", []) if isinstance(plan, dict) else []
        songs_done = payload.get("songs", []) if isinstance(payload, dict) else []
        status = str(payload.get("status", "queued")) if isinstance(payload, dict) else "queued"
        cover_url = payload.get("cover_url") if isinstance(payload, dict) else None

        # Creation timestamp is best effort from plan file mtime.
        created_at = _utc_now()
        if plan_file.exists():
            created_at = datetime.fromtimestamp(
                plan_file.stat().st_mtime,
                tz=UTC,
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        with _connect() as conn:
            existing = conn.execute(
                "SELECT album_id FROM albums WHERE album_id=?",
                (album_id,),
            ).fetchone()

            now = _utc_now()
            if existing:
                conn.execute(
                    """
                    UPDATE albums
                    SET folder=?, status=?, album_name=?, album_description=?, cover_url=?, updated_at=?
                    WHERE album_id=?
                    """,
                    (
                        folder,
                        status,
                        str(plan.get("album_name", folder)),
                        str(plan.get("album_description", "")),
                        str(cover_url) if cover_url else None,
                        now,
                        album_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO albums (
                        album_id, folder, status, album_name, album_description,
                        cover_url, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        album_id,
                        folder,
                        status,
                        str(plan.get("album_name", folder)),
                        str(plan.get("album_description", "")),
                        str(cover_url) if cover_url else None,
                        created_at,
                        now,
                    ),
                )

            conn.execute("DELETE FROM songs WHERE album_id=?", (album_id,))
            for idx, raw in enumerate(songs_planned):
                if not isinstance(raw, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO songs (
                        album_id, song_index, name, description, music_prompt, lyrics,
                        instrumental, duration_seconds, bpm, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
                    """,
                    (
                        album_id,
                        idx,
                        str(raw.get("name", f"Track {idx + 1}")),
                        str(raw.get("description", "")),
                        str(raw.get("music_prompt", "")),
                        str(raw.get("lyrics", "")),
                        int(bool(raw.get("instrumental", True))),
                        float(raw.get("duration_seconds", 60.0)),
                        _to_int_or_none(raw.get("bpm")),
                        now,
                        now,
                    ),
                )

            for raw in songs_done:
                if not isinstance(raw, dict):
                    continue
                song_index = _to_int_or_none(raw.get("index"))
                if song_index is None:
                    continue
                conn.execute(
                    """
                    INSERT INTO songs (
                        album_id, song_index, name, description, duration_seconds, audio_url,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'complete', ?, ?)
                    ON CONFLICT(album_id, song_index) DO UPDATE SET
                        name=excluded.name,
                        description=excluded.description,
                        duration_seconds=excluded.duration_seconds,
                        audio_url=excluded.audio_url,
                        status='complete',
                        updated_at=excluded.updated_at
                    """,
                    (
                        album_id,
                        song_index,
                        str(raw.get("name", f"Track {song_index + 1}")),
                        str(raw.get("description", "")),
                        float(raw.get("duration_seconds", 60.0)),
                        str(raw.get("audio_url", "")),
                        now,
                        now,
                    ),
                )


def _to_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
