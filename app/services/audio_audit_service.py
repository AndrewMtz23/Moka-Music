from __future__ import annotations

import re
from pathlib import Path

from ..constants import FileFormats


def build_audio_quality_rows(groups: list[tuple[object, object, list[str]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for controller, _tree, filenames in groups:
        for filename in filenames:
            cached = controller.get_track_info(filename)
            quality = dict(cached.audio_quality) if cached else {}
            rows.append(
                {
                    "filename": filename,
                    "title": (cached.metadata.get("title", "") if cached else ""),
                    "artist": (cached.metadata.get("artist", "") if cached else ""),
                    "duration": float(cached.duration or 0.0) if cached else 0.0,
                    "bitrate_kbps": quality.get("bitrate_kbps", 0),
                    "sample_rate": quality.get("sample_rate", 0),
                    "channels": quality.get("channels", ""),
                    "format": quality.get("format", ""),
                    "low_bitrate": bool(quality.get("low_bitrate", False)),
                    "possibly_corrupt": bool(quality.get("possibly_corrupt", False)),
                }
            )
    return rows


def detect_advanced_duplicates(
    groups: list[tuple[object, object, list[str]]], *, duration_tolerance: float = 2.0
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for controller, _tree, filenames in groups:
        for filename in filenames:
            cached = controller.get_track_info(filename)
            metadata = dict(cached.metadata) if cached else {}
            title = str(metadata.get("title", "") or Path(filename).stem)
            artist = str(metadata.get("artist", "") or "")
            candidates.append(
                {
                    "filename": filename,
                    "title": title,
                    "artist": artist,
                    "duration": float(cached.duration or 0.0) if cached else 0.0,
                    "key": (_normalize_text(artist), _normalize_text(title)),
                }
            )

    duplicates: list[dict[str, object]] = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            if left["key"] != right["key"]:
                continue
            duration_delta = abs(float(left["duration"]) - float(right["duration"]))
            if duration_delta <= duration_tolerance:
                duplicates.append(
                    {
                        "filename": f"{left['filename']} / {right['filename']}",
                        "title": left["title"],
                        "artist": left["artist"],
                        "duration": f"{left['duration']:.1f}s / {right['duration']:.1f}s",
                        "issue": f"duplicate_duration_delta_{duration_delta:.1f}s",
                    }
                )
    return duplicates


def validate_audio_files(groups: list[tuple[object, object, list[str]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    supported = {suffix.lower() for suffix in FileFormats.AUDIO}
    for controller, _tree, filenames in groups:
        for filename in filenames:
            path = Path(controller.carpeta) / filename
            cached = controller.get_track_info(filename)
            quality = dict(cached.audio_quality) if cached else {}
            issues: list[str] = []
            if not path.exists():
                issues.append("missing_file")
            if path.suffix.lower() not in supported:
                issues.append("unsupported_extension")
            if quality.get("possibly_corrupt"):
                issues.append("possibly_corrupt")
            if quality.get("bitrate_kbps", 0) == 0:
                issues.append("missing_bitrate")
            if issues:
                rows.append(
                    {
                        "filename": filename,
                        "path": str(path),
                        "format": quality.get("format", path.suffix.lower().lstrip(".").upper()),
                        "issues": ", ".join(issues),
                    }
                )
    return rows


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
