from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..constants import LIBRARY_CACHE_FILE_NAME
from .track_scan_service import TrackScanResult

SCANNER_VERSION = 2
logger = logging.getLogger(__name__)


@dataclass
class LibraryCacheSnapshot:
    tracks: dict[str, TrackScanResult] = field(default_factory=dict)
    manual_paths: set[str] = field(default_factory=set)
    locked_paths: set[str] = field(default_factory=set)


class LibraryCache:
    def __init__(self, db_path: str | Path = LIBRARY_CACHE_FILE_NAME) -> None:
        self.db_path = Path(db_path)
        self._initialized = False

    def get_valid_track(self, filepath: str | Path) -> TrackScanResult | None:
        path = Path(filepath)
        stats = self._file_stats(path)
        if stats is None:
            return None
        try:
            self._ensure_schema()
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT filename, metadata_json, duration, audio_quality_json, has_cover_art, error
                    FROM track_cache
                    WHERE filepath = ?
                      AND size = ?
                      AND mtime = ?
                      AND scanner_version = ?
                    """,
                    (self._normalize_path(path), stats["size"], stats["mtime"], SCANNER_VERSION),
                ).fetchone()
            if row is None:
                return None
            return TrackScanResult(
                filename=str(row[0]),
                filepath=self._normalize_path(path),
                metadata=self._loads_dict(row[1]),
                duration=float(row[2] or 0.0),
                audio_quality=self._loads_dict(row[3]),
                has_cover_art=self._decode_bool(row[4]),
                error=str(row[5] or ""),
            )
        except Exception as exc:
            logger.debug("Ignoring library cache read failure for %s: %s", path, exc)
            return None

    def save_track(self, result: TrackScanResult) -> None:
        self.save_tracks([result])

    def save_tracks(
        self,
        results: list[TrackScanResult],
        *,
        expected_stats: dict[str, tuple[int, float]] | None = None,
    ) -> None:
        if not results:
            return
        try:
            self._ensure_schema()
            rows = []
            for result in results:
                path = Path(result.filepath)
                stats = self._file_stats(path)
                if stats is None:
                    continue
                if expected_stats is not None and expected_stats.get(result.filepath) != (
                    stats["size"],
                    stats["mtime"],
                ):
                    continue
                rows.append(
                    (
                        self._normalize_path(path),
                        self._normalize_path(path.parent),
                        result.filename,
                        stats["size"],
                        stats["mtime"],
                        json.dumps(result.metadata, ensure_ascii=True, sort_keys=True),
                        float(result.duration or 0.0),
                        json.dumps(result.audio_quality, ensure_ascii=True, sort_keys=True),
                        self._encode_bool(result.has_cover_art),
                        result.error,
                        time.time(),
                        SCANNER_VERSION,
                    )
                )
            with self._connection() as connection:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO track_cache (
                        filepath, folder, filename, size, mtime, metadata_json,
                        duration, audio_quality_json, has_cover_art, error,
                        scanned_at, scanner_version
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        except Exception as exc:
            logger.debug("Ignoring library cache batch write failure: %s", exc)

    def get_folder_snapshot(self, folder: str | Path) -> LibraryCacheSnapshot:
        """Read once, then validate files without holding a database connection."""
        snapshot = LibraryCacheSnapshot()
        normalized_folder = self._normalize_path(Path(folder))
        # Lock state is authoritative: a database error must not silently unlock tracks.
        self._ensure_schema()
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT filepath, filename, size, mtime, metadata_json, duration,
                          audio_quality_json, has_cover_art, error
                   FROM track_cache WHERE folder = ? AND scanner_version = ?""",
                (normalized_folder, SCANNER_VERSION),
            ).fetchall()
            snapshot.manual_paths = {
                row[0]
                for row in connection.execute("SELECT filepath FROM manual_track_numbers")
                if str(Path(row[0]).parent) == normalized_folder
            }
            snapshot.locked_paths = {
                row[0]
                for row in connection.execute("SELECT filepath FROM explicit_track_locks")
                if str(Path(row[0]).parent) == normalized_folder
            }
        for row in rows:
            try:
                stats = self._file_stats(Path(row[0]))
                if stats is None or stats["size"] != row[2] or stats["mtime"] != row[3]:
                    continue
                snapshot.tracks[row[1]] = TrackScanResult(
                    filename=row[1],
                    filepath=row[0],
                    metadata=self._loads_dict(row[4]),
                    duration=float(row[5] or 0.0),
                    audio_quality=self._loads_dict(row[6]),
                    has_cover_art=self._decode_bool(row[7]),
                    error=str(row[8] or ""),
                )
            except (TypeError, ValueError) as exc:
                logger.debug("Ignoring invalid cached metadata for %s: %s", row[0], exc)
        return snapshot

    def invalidate_path(self, filepath: str | Path) -> None:
        try:
            self._ensure_schema()
            with self._connection() as connection:
                connection.execute(
                    "DELETE FROM track_cache WHERE filepath = ?",
                    (self._normalize_path(Path(filepath)),),
                )
        except Exception as exc:
            logger.debug("Ignoring library cache path invalidation failure for %s: %s", filepath, exc)

    def is_track_number_manual(self, filepath: str | Path) -> bool:
        self._ensure_schema()
        with self._connection() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM manual_track_numbers WHERE filepath = ?",
                    (self._normalize_path(Path(filepath)),),
                ).fetchone()
                is not None
            )

    def set_track_number_manual(self, filepath: str | Path, manual: bool) -> None:
        # User intent is independent of disposable scan-cache entries.
        self._ensure_schema()
        with self._connection() as connection:
            if manual:
                connection.execute(
                    "INSERT OR IGNORE INTO manual_track_numbers (filepath) VALUES (?)",
                    (self._normalize_path(Path(filepath)),),
                )
            else:
                connection.execute(
                    "DELETE FROM manual_track_numbers WHERE filepath = ?",
                    (self._normalize_path(Path(filepath)),),
                )

    def invalidate_folder(self, folder: str | Path) -> None:
        try:
            self._ensure_schema()
            with self._connection() as connection:
                connection.execute(
                    "DELETE FROM track_cache WHERE folder = ?",
                    (self._normalize_path(Path(folder)),),
                )
        except Exception as exc:
            logger.debug("Ignoring library cache folder invalidation failure for %s: %s", folder, exc)

    def is_track_number_locked(self, filepath: str | Path) -> bool:
        self._ensure_schema()
        with self._connection() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM explicit_track_locks WHERE filepath = ?",
                    (self._normalize_path(Path(filepath)),),
                ).fetchone()
                is not None
            )

    def set_track_number_locked(self, filepath: str | Path, locked: bool) -> None:
        self._ensure_schema()
        with self._connection() as connection:
            query = (
                "INSERT OR IGNORE INTO explicit_track_locks (filepath) VALUES (?)"
                if locked
                else "DELETE FROM explicit_track_locks WHERE filepath = ?"
            )
            connection.execute(query, (self._normalize_path(Path(filepath)),))

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS track_cache (
                    filepath TEXT PRIMARY KEY,
                    folder TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    metadata_json TEXT NOT NULL,
                    duration REAL NOT NULL,
                    audio_quality_json TEXT NOT NULL,
                    has_cover_art INTEGER,
                    error TEXT NOT NULL DEFAULT '',
                    scanned_at REAL NOT NULL,
                    scanner_version INTEGER NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_track_cache_folder ON track_cache(folder)")
            connection.execute("CREATE TABLE IF NOT EXISTS manual_track_numbers (filepath TEXT PRIMARY KEY)")
            # Older automatic/manual assignments are not explicit user locks.
            connection.execute("CREATE TABLE IF NOT EXISTS explicit_track_locks (filepath TEXT PRIMARY KEY)")
        self._initialized = True

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _file_stats(self, path: Path) -> dict[str, float | int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return {"size": stat.st_size, "mtime": stat.st_mtime}

    def _normalize_path(self, path: Path) -> str:
        try:
            return str(path.resolve())
        except OSError:
            return str(path)

    def _loads_dict(self, value: str) -> dict:
        decoded = json.loads(value or "{}")
        return decoded if isinstance(decoded, dict) else {}

    def _encode_bool(self, value: bool | None) -> int | None:
        if value is None:
            return None
        return 1 if value else 0

    def _decode_bool(self, value) -> bool | None:
        if value is None:
            return None
        return bool(value)
