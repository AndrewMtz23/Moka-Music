import os
import re

from .file_service import sanitize_filename


def _metadata_value(metadata: dict[str, object], key: str) -> str:
    return str(metadata.get(key, "") or "").strip()


def _track_number(metadata: dict[str, object], fallback: int = 0) -> int:
    value = _metadata_value(metadata, "track_number")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback or 0)
    return max(0, parsed)


def _filename_parts(filename: str) -> tuple[str, str]:
    stem, _extension = os.path.splitext(filename)
    stem = _strip_leading_track_prefix(stem)
    parts = [part.strip() for part in stem.split(" - ") if part.strip()]
    if len(parts) >= 3 and parts[0].isdigit():
        return parts[1], " - ".join(parts[2:])
    if len(parts) >= 2:
        return parts[0], " - ".join(parts[1:])
    return "", stem.strip()


def _strip_leading_track_prefix(value: str) -> str:
    return re.sub(r"^\s*\d{1,4}\s*(?:[-._)]\s*|\s+)", "", value).strip()


def playlist_base_name(
    filename: str,
    metadata: dict[str, object],
    *,
    track_number: int | None = None,
) -> str:
    fallback_artist, fallback_title = _filename_parts(filename)
    number = int(track_number) if track_number is not None else _track_number(metadata)
    title = _metadata_value(metadata, "title") or fallback_title
    artist = _metadata_value(metadata, "artist") or fallback_artist

    parts = [f"{number:03d}"]
    if artist:
        parts.append(artist)
    parts.append(title)
    return sanitize_filename(" - ".join(parts))


def playlist_filename_from_metadata(
    filename: str,
    metadata: dict[str, object],
    used_names: set[str],
    *,
    track_number: int | None = None,
) -> str:
    _stem, extension = os.path.splitext(filename)
    base_name = playlist_base_name(filename, metadata, track_number=track_number)
    candidate = f"{base_name}{extension}"
    suffix = 2
    while candidate in used_names and candidate != filename:
        candidate = f"{base_name} ({suffix}){extension}"
        suffix += 1
    return candidate
