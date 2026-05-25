from pathlib import Path
from typing import Callable

from app.models import FilterMode, SortMode, TrackInfo


MetadataCache = dict[str, TrackInfo]


def sort_files(files: list[str], metadata_cache: MetadataCache, mode: SortMode, mtime_getter: Callable[[str], float]) -> list[str]:
    sorted_files = list(files)
    if mode == SortMode.MANUAL:
        return sorted_files
    if mode == SortMode.FILENAME:
        sorted_files.sort(key=lambda value: value.lower())
    elif mode == SortMode.ARTIST:
        sorted_files.sort(key=lambda value: metadata_sort_value(value, metadata_cache, "artist"))
    elif mode == SortMode.ALBUM:
        sorted_files.sort(key=lambda value: metadata_sort_value(value, metadata_cache, "album"))
    elif mode == SortMode.TRACK_NUMBER:
        sorted_files.sort(key=lambda value: track_number(value, metadata_cache))
    elif mode == SortMode.DURATION:
        sorted_files.sort(key=lambda value: duration(value, metadata_cache))
    elif mode == SortMode.DATE_ADDED:
        sorted_files.sort(key=mtime_getter)
    return sorted_files


def metadata_sort_value(filename: str, metadata_cache: MetadataCache, field: str) -> tuple[str, str]:
    metadata = metadata_for(filename, metadata_cache)
    return (str(metadata.get(field, "") or "").lower(), filename.lower())


def duration(filename: str, metadata_cache: MetadataCache) -> float:
    cached = metadata_cache.get(filename)
    return float(cached.duration or 0.0) if cached else 0.0


def track_number(filename: str, metadata_cache: MetadataCache) -> int:
    try:
        metadata = metadata_for(filename, metadata_cache)
        return int(metadata.get("track_number", 0))
    except (TypeError, ValueError):
        return 0


def filter_files(
    files: list[str],
    metadata_cache: MetadataCache,
    query: str = "",
    mode: FilterMode = FilterMode.ALL,
    *,
    has_cover_art: Callable[[str], bool] | None = None,
) -> list[str]:
    normalized_query = query.strip().lower()
    duplicate_set = duplicate_filenames(files, metadata_cache) if mode == FilterMode.DUPLICATES else set()
    results: list[str] = []
    for filename in files:
        metadata = metadata_for(filename, metadata_cache)
        if normalized_query and normalized_query not in search_blob(filename, metadata):
            continue
        if not matches_filter(filename, metadata, mode, duplicate_set=duplicate_set, has_cover_art=has_cover_art):
            continue
        results.append(filename)
    return results


def search_blob(filename: str, metadata: dict[str, str]) -> str:
    parts = [
        filename,
        metadata.get("title", ""),
        metadata.get("artist", ""),
        metadata.get("album", ""),
        metadata.get("genre", ""),
        metadata.get("year", ""),
        str(metadata.get("track_number", "")),
    ]
    return " ".join(str(part).lower() for part in parts)


def matches_filter(
    filename: str,
    metadata: dict[str, str],
    mode: FilterMode,
    *,
    duplicate_set: set[str] | None = None,
    has_cover_art: Callable[[str], bool] | None = None,
) -> bool:
    if mode == FilterMode.ALL:
        return True
    if mode == FilterMode.MISSING_ARTIST:
        return not str(metadata.get("artist", "")).strip()
    if mode == FilterMode.MISSING_ALBUM:
        return not str(metadata.get("album", "")).strip()
    if mode == FilterMode.MISSING_YEAR:
        return not str(metadata.get("year", "")).strip()
    if mode == FilterMode.MISSING_TRACK:
        value = str(metadata.get("track_number", "")).strip()
        return not value or value == "0"
    if mode == FilterMode.MISSING_COVER:
        return not bool(has_cover_art and has_cover_art(filename))
    if mode == FilterMode.DUPLICATES:
        return filename in (duplicate_set or set())
    return True


def duplicate_filenames(files: list[str], metadata_cache: MetadataCache) -> set[str]:
    groups: dict[str, list[str]] = {}
    for filename in files:
        duplicate_key = duplicate_key_for(filename, metadata_for(filename, metadata_cache))
        if duplicate_key:
            groups.setdefault(duplicate_key, []).append(filename)
    return {
        filename
        for filenames in groups.values()
        if len(filenames) > 1
        for filename in filenames
    }


def quality_report(files: list[str], metadata_cache: MetadataCache) -> dict[str, int]:
    duplicate_keys: dict[str, int] = {}
    report = {
        "total": len(files),
        "missing_artist": 0,
        "missing_album": 0,
        "missing_year": 0,
        "missing_track": 0,
        "duplicate_groups": 0,
        "duplicate_tracks": 0,
    }

    for filename in files:
        metadata = metadata_for(filename, metadata_cache)
        if not str(metadata.get("artist", "")).strip():
            report["missing_artist"] += 1
        if not str(metadata.get("album", "")).strip():
            report["missing_album"] += 1
        if not str(metadata.get("year", "")).strip():
            report["missing_year"] += 1

        value = str(metadata.get("track_number", "")).strip()
        if not value or value == "0":
            report["missing_track"] += 1

        duplicate_key = duplicate_key_for(filename, metadata)
        if duplicate_key:
            duplicate_keys[duplicate_key] = duplicate_keys.get(duplicate_key, 0) + 1

    duplicate_counts = [count for count in duplicate_keys.values() if count > 1]
    report["duplicate_groups"] = len(duplicate_counts)
    report["duplicate_tracks"] = sum(duplicate_counts)
    return report


def metadata_for(filename: str, metadata_cache: MetadataCache) -> dict[str, str]:
    cached = metadata_cache.get(filename)
    return cached.metadata if cached else {}


def duplicate_key_for(filename: str, metadata: dict[str, str]) -> str:
    title = str(metadata.get("title", "")).strip().lower() or Path(filename).stem.lower()
    artist = str(metadata.get("artist", "")).strip().lower()
    if not title:
        return ""
    return f"{artist}|{title}"
