from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mutagen
from mutagen.mp4 import MP4Cover

from ..constants import DEFAULT_METADATA, FileFormats
from .audio_quality_service import default_audio_quality, inspect_audio_quality_from_audio


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackScanResult:
    filename: str
    filepath: str
    metadata: dict[str, str]
    duration: float
    audio_quality: dict[str, object]
    has_cover_art: bool | None = None
    error: str = ""


def scan_track(filepath: str | Path) -> TrackScanResult:
    path = Path(filepath)
    metadata = DEFAULT_METADATA.copy()
    metadata["title"] = path.stem

    if not _is_valid_audio_path(path):
        return TrackScanResult(
            filename=path.name,
            filepath=str(path),
            metadata=metadata,
            duration=0.0,
            audio_quality=default_audio_quality(path, possibly_corrupt=True),
            has_cover_art=False,
            error="Unsupported or missing audio file",
        )

    easy_audio = None
    full_audio = None
    errors: list[str] = []

    try:
        easy_audio = mutagen.File(str(path), easy=True)
    except Exception as exc:
        errors.append(str(exc))
        logger.debug("Could not read easy metadata for %s: %s", path, exc)

    if easy_audio is not None:
        metadata.update(_metadata_from_easy_audio(easy_audio, path))

    try:
        full_audio = mutagen.File(str(path))
    except Exception as exc:
        errors.append(str(exc))
        logger.debug("Could not read full audio info for %s: %s", path, exc)

    duration = _duration_from_audio(full_audio)
    quality = inspect_audio_quality_from_audio(full_audio, path)
    has_cover_art = _has_cover_art(full_audio)
    error = "; ".join(error for error in errors if error)

    return TrackScanResult(
        filename=path.name,
        filepath=str(path),
        metadata=metadata,
        duration=duration,
        audio_quality=quality,
        has_cover_art=has_cover_art,
        error=error,
    )


def _is_valid_audio_path(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() in FileFormats.AUDIO


def _metadata_from_easy_audio(audio, path: Path) -> dict[str, str]:
    return {
        "artist": _first_value(audio, "artist"),
        "album_artist": _first_value(audio, "albumartist"),
        "album": _first_value(audio, "album"),
        "title": _first_value(audio, "title") or path.stem,
        "year": _first_value(audio, "date"),
        "track_number": _first_value(audio, "tracknumber") or "0",
        "genre": _first_value(audio, "genre"),
        "comment": _first_value(audio, "comment"),
    }


def _first_value(audio, key: str) -> str:
    value = audio.get(key, [""])
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _duration_from_audio(audio) -> float:
    try:
        return float(getattr(getattr(audio, "info", None), "length", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _has_cover_art(audio) -> bool:
    try:
        tags = getattr(audio, "tags", None)
        if not tags:
            return False
        for key, value in tags.items():
            if str(key).startswith("APIC") and hasattr(value, "data"):
                return True
            if key == "covr" and isinstance(value, list):
                return any(isinstance(cover, (bytes, MP4Cover)) for cover in value)
            if _looks_like_cover_key(key, value):
                return True
    except Exception as exc:
        logger.warning("Could not inspect embedded cover art: %s", exc)
    return False


def _looks_like_cover_key(key: Any, value: Any) -> bool:
    key_text = str(key).lower()
    return "cover" in key_text and bool(value)
