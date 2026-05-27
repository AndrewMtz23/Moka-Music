from __future__ import annotations

from collections import Counter

from ..models import TrackInfo


def build_library_stats(files: list[str], metadata_cache: dict[str, TrackInfo]) -> dict[str, object]:
    total = len(files)
    total_duration = sum(float((metadata_cache.get(filename).duration if metadata_cache.get(filename) else 0) or 0) for filename in files)
    complete_count = 0
    genre_counter: Counter[str] = Counter()
    year_counter: Counter[str] = Counter()
    artist_counter: Counter[str] = Counter()
    album_counter: Counter[str] = Counter()

    for filename in files:
        cached = metadata_cache.get(filename)
        metadata = cached.metadata if cached else {}
        if _is_complete(metadata):
            complete_count += 1
        _add_counter(genre_counter, metadata.get("genre"))
        _add_counter(year_counter, _year_bucket(metadata.get("year")))
        _add_counter(artist_counter, metadata.get("artist"))
        _add_counter(album_counter, metadata.get("album"))

    completion_percent = round((complete_count / total) * 100, 1) if total else 0.0
    return {
        "total_tracks": total,
        "total_duration": total_duration,
        "complete_metadata": complete_count,
        "completion_percent": completion_percent,
        "genres": genre_counter.most_common(10),
        "years": sorted(year_counter.items()),
        "top_artists": artist_counter.most_common(10),
        "top_albums": album_counter.most_common(10),
    }


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds or 0)))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _is_complete(metadata: dict[str, str]) -> bool:
    required = ("title", "artist", "album", "year", "track_number")
    return all(str(metadata.get(field, "") or "").strip() and str(metadata.get(field, "")).strip() != "0" for field in required)


def _add_counter(counter: Counter[str], value) -> None:
    normalized = str(value or "").strip()
    if normalized:
        counter[normalized] += 1


def _year_bucket(value) -> str:
    year = str(value or "").strip()
    return year[:4] if len(year) >= 4 and year[:4].isdigit() else ""
