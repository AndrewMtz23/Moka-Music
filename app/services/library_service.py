from pathlib import Path
from difflib import SequenceMatcher
import re
from typing import Callable

from app.models import FilterMode, SortMode, TrackInfo


MetadataCache = dict[str, TrackInfo]

BITRATE_128_MAX_KBPS = 160
BITRATE_256_MIN_KBPS = 161
BITRATE_256_MAX_KBPS = 287
BITRATE_320_MIN_KBPS = 288


def sort_files(
    files: list[str],
    metadata_cache: MetadataCache,
    mode: SortMode,
    mtime_getter: Callable[[str], float],
    last_played_getter: Callable[[str], str] | None = None,
) -> list[str]:
    sorted_files = list(files)
    if mode == SortMode.MANUAL:
        return sorted_files
    if mode == SortMode.FILENAME:
        sorted_files.sort(key=natural_filename_key)
    elif mode == SortMode.ARTIST:
        sorted_files.sort(key=lambda value: metadata_sort_value(value, metadata_cache, "artist"))
    elif mode == SortMode.ALBUM:
        sorted_files.sort(key=lambda value: metadata_sort_value(value, metadata_cache, "album"))
    elif mode == SortMode.TRACK_NUMBER:
        sorted_files.sort(key=lambda value: track_number(value, metadata_cache))
    elif mode == SortMode.DURATION:
        sorted_files.sort(key=lambda value: duration(value, metadata_cache))
    elif mode == SortMode.BITRATE:
        sorted_files.sort(key=lambda value: bitrate_sort_value(value, metadata_cache))
    elif mode == SortMode.DATE_ADDED:
        sorted_files.sort(key=mtime_getter)
    elif mode == SortMode.LAST_PLAYED:
        sorted_files.sort(key=lambda value: (last_played_getter(value) if last_played_getter else "", value.lower()), reverse=True)
    return sorted_files


def metadata_sort_value(filename: str, metadata_cache: MetadataCache, field: str) -> tuple[str, str]:
    metadata = metadata_for(filename, metadata_cache)
    return (str(metadata.get(field, "") or "").lower(), filename.lower())


def natural_filename_key(filename: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", filename.lower())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def duration(filename: str, metadata_cache: MetadataCache) -> float:
    cached = metadata_cache.get(filename)
    return float(cached.duration or 0.0) if cached else 0.0


def bitrate(filename: str, metadata_cache: MetadataCache) -> int:
    try:
        return int(audio_quality_for(filename, metadata_cache).get("bitrate_kbps", 0) or 0)
    except (TypeError, ValueError):
        return 0


def bitrate_sort_value(filename: str, metadata_cache: MetadataCache) -> tuple[bool, int, str]:
    value = bitrate(filename, metadata_cache)
    return (value <= 0, value, filename.lower())


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
    played_paths: set[str] | None = None,
) -> list[str]:
    normalized_query = query.strip().lower()
    duplicate_set = duplicate_filenames(files, metadata_cache) if mode == FilterMode.DUPLICATES else set()
    results: list[str] = []
    for filename in files:
        metadata = metadata_for(filename, metadata_cache)
        if normalized_query and normalized_query not in search_blob(filename, metadata):
            continue
        if not matches_filter(
            filename,
            metadata,
            metadata_cache,
            mode,
            duplicate_set=duplicate_set,
            has_cover_art=has_cover_art,
            played_paths=played_paths,
        ):
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
    metadata_cache: MetadataCache,
    mode: FilterMode,
    *,
    duplicate_set: set[str] | None = None,
    has_cover_art: Callable[[str], bool] | None = None,
    played_paths: set[str] | None = None,
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
    if mode == FilterMode.LOW_BITRATE:
        return bool(audio_quality_for(filename, metadata_cache).get("low_bitrate"))
    if mode == FilterMode.BITRATE_128:
        return bitrate_in_range(filename, metadata_cache, maximum=BITRATE_128_MAX_KBPS)
    if mode == FilterMode.BITRATE_256:
        return bitrate_in_range(
            filename,
            metadata_cache,
            minimum=BITRATE_256_MIN_KBPS,
            maximum=BITRATE_256_MAX_KBPS,
        )
    if mode == FilterMode.BITRATE_320:
        return bitrate_in_range(filename, metadata_cache, minimum=BITRATE_320_MIN_KBPS)
    if mode == FilterMode.POSSIBLY_CORRUPT:
        return bool(audio_quality_for(filename, metadata_cache).get("possibly_corrupt"))
    if mode == FilterMode.UNPLAYED:
        return normalized_filepath_for(filename, metadata_cache) not in (played_paths or set())
    return True


def duplicate_filenames(files: list[str], metadata_cache: MetadataCache) -> set[str]:
    groups: dict[str, list[str]] = {}
    for filename in files:
        duplicate_key = exact_duplicate_key_for(filename, metadata_for(filename, metadata_cache))
        if duplicate_key:
            groups.setdefault(duplicate_key, []).append(filename)
    duplicates = {
        filename
        for filenames in groups.values()
        if len(filenames) > 1
        for filename in filenames
    }
    duplicates.update(fuzzy_duplicate_filenames(files, metadata_cache))
    return duplicates


def fuzzy_duplicate_filenames(files: list[str], metadata_cache: MetadataCache, threshold: float = 0.92) -> set[str]:
    duplicates: set[str] = set()
    keys = {
        filename: fuzzy_duplicate_key_for(filename, metadata_for(filename, metadata_cache))
        for filename in files
    }
    for index, filename in enumerate(files):
        key = keys.get(filename, "")
        if not key:
            continue
        for other in files[index + 1 :]:
            other_key = keys.get(other, "")
            if not other_key:
                continue
            if SequenceMatcher(None, key, other_key).ratio() >= threshold:
                duplicates.update({filename, other})
    return duplicates


def quality_report(files: list[str], metadata_cache: MetadataCache) -> dict[str, int]:
    duplicate_tracks = duplicate_filenames(files, metadata_cache)
    report = {
        "total": len(files),
        "missing_artist": 0,
        "missing_album": 0,
        "missing_year": 0,
        "missing_track": 0,
        "duplicate_groups": 0,
        "duplicate_tracks": 0,
        "low_bitrate": 0,
        "possibly_corrupt": 0,
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

        quality = audio_quality_for(filename, metadata_cache)
        if quality.get("low_bitrate"):
            report["low_bitrate"] += 1
        if quality.get("possibly_corrupt"):
            report["possibly_corrupt"] += 1

    report["duplicate_tracks"] = len(duplicate_tracks)
    report["duplicate_groups"] = estimate_duplicate_groups(files, metadata_cache, duplicate_tracks)
    return report


def metadata_for(filename: str, metadata_cache: MetadataCache) -> dict[str, str]:
    cached = metadata_cache.get(filename)
    return cached.metadata if cached else {}


def audio_quality_for(filename: str, metadata_cache: MetadataCache) -> dict[str, object]:
    cached = metadata_cache.get(filename)
    return cached.audio_quality if cached else {}


def bitrate_in_range(
    filename: str,
    metadata_cache: MetadataCache,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool:
    try:
        bitrate = int(audio_quality_for(filename, metadata_cache).get("bitrate_kbps", 0) or 0)
    except (TypeError, ValueError):
        return False
    if bitrate <= 0:
        return False
    if minimum is not None and bitrate < minimum:
        return False
    if maximum is not None and bitrate > maximum:
        return False
    return True


def normalized_filepath_for(filename: str, metadata_cache: MetadataCache) -> str:
    from app.services.playback_history_service import normalize_history_path

    cached = metadata_cache.get(filename)
    return normalize_history_path(cached.filepath if cached else filename)


def exact_duplicate_key_for(filename: str, metadata: dict[str, str]) -> str:
    title = str(metadata.get("title", "")).strip().lower() or Path(filename).stem.lower()
    artist = str(metadata.get("artist", "")).strip().lower()
    if not title:
        return ""
    return f"{artist}|{title}"


def fuzzy_duplicate_key_for(filename: str, metadata: dict[str, str]) -> str:
    title = str(metadata.get("title", "") or Path(filename).stem).lower()
    artist = str(metadata.get("artist", "") or "").lower()
    return normalize_duplicate_text(f"{artist} {title}")


def normalize_duplicate_text(value: str) -> str:
    value = re.sub(r"\b(remaster(?:ed)?|radio edit|explicit|clean|version|mix|mono|stereo)\b", " ", value)
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def estimate_duplicate_groups(files: list[str], metadata_cache: MetadataCache, duplicate_tracks: set[str]) -> int:
    seen: set[str] = set()
    groups = 0
    for filename in files:
        if filename not in duplicate_tracks:
            continue
        key = fuzzy_duplicate_key_for(filename, metadata_for(filename, metadata_cache))
        if key and key not in seen:
            seen.add(key)
            groups += 1
    return groups
