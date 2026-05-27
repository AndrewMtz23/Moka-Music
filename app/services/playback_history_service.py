from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any


def record_playback(
    history: list[dict[str, object]],
    *,
    filepath: str,
    filename: str,
    metadata: dict[str, str] | None = None,
    played_at: str | None = None,
    limit: int = 500,
) -> list[dict[str, object]]:
    metadata = metadata or {}
    normalized = normalize_history_path(filepath)
    now = played_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = [dict(item) for item in history if isinstance(item, dict)]
    existing = next((item for item in records if normalize_history_path(str(item.get("filepath", ""))) == normalized), None)

    if existing is None:
        existing = {"filepath": filepath, "play_count": 0}
        records.append(existing)

    existing.update(
        {
            "filepath": filepath,
            "filename": filename,
            "title": str(metadata.get("title", "") or Path(filename).stem),
            "artist": str(metadata.get("artist", "") or ""),
            "album": str(metadata.get("album", "") or ""),
            "last_played": now,
            "play_count": _safe_int(existing.get("play_count", 0)) + 1,
        }
    )

    records.sort(key=lambda item: str(item.get("last_played", "")), reverse=True)
    return records[:limit]


def played_paths(history: list[dict[str, object]]) -> set[str]:
    return {
        normalize_history_path(str(item.get("filepath", "") or ""))
        for item in history
        if isinstance(item, dict) and item.get("filepath")
    }


def last_played_map(history: list[dict[str, object]]) -> dict[str, str]:
    return {
        normalize_history_path(str(item.get("filepath", "") or "")): str(item.get("last_played", "") or "")
        for item in history
        if isinstance(item, dict) and item.get("filepath")
    }


def playback_history_summary(history: list[dict[str, object]]) -> dict[str, object]:
    records = [dict(item) for item in history if isinstance(item, dict)]
    total_plays = sum(_safe_int(item.get("play_count", 0)) for item in records)
    top_tracks = sorted(records, key=lambda item: _safe_int(item.get("play_count", 0)), reverse=True)[:10]
    return {
        "unique_tracks": len(records),
        "total_plays": total_plays,
        "last_played": records[0].get("last_played", "") if records else "",
        "top_tracks": top_tracks,
        "rows": records,
    }


def normalize_history_path(filepath: str) -> str:
    if not filepath:
        return ""
    return os.path.normcase(os.path.abspath(filepath))


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
