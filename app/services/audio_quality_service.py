from __future__ import annotations

from pathlib import Path
from typing import Any

import mutagen


LOW_BITRATE_THRESHOLD_KBPS = 128


def inspect_audio_quality(filepath: str | Path) -> dict[str, object]:
    path = Path(filepath)
    try:
        audio = mutagen.File(str(path))
    except Exception:
        return default_audio_quality(path, possibly_corrupt=True)
    return inspect_audio_quality_from_audio(audio, path)


def inspect_audio_quality_from_audio(audio, filepath: str | Path) -> dict[str, object]:
    path = Path(filepath)
    quality: dict[str, object] = {
        "bitrate_kbps": 0,
        "sample_rate": 0,
        "channels": "",
        "format": path.suffix.lower().lstrip(".").upper(),
        "file_size_mb": _file_size_mb(path),
        "low_bitrate": False,
        "possibly_corrupt": False,
    }
    try:
        if audio is None or getattr(audio, "info", None) is None:
            quality["possibly_corrupt"] = True
            return quality
        info = audio.info
        bitrate = int(getattr(info, "bitrate", 0) or 0)
        sample_rate = int(getattr(info, "sample_rate", 0) or 0)
        channels = _channels_label(getattr(info, "channels", 0))
        quality.update(
            {
                "bitrate_kbps": int(round(bitrate / 1000)) if bitrate else 0,
                "sample_rate": sample_rate,
                "channels": channels,
                "format": _format_label(audio, path),
            }
        )
        quality["low_bitrate"] = bool(quality["bitrate_kbps"] and quality["bitrate_kbps"] < LOW_BITRATE_THRESHOLD_KBPS)
    except Exception:
        quality["possibly_corrupt"] = True
    return quality


def default_audio_quality(filepath: str | Path, *, possibly_corrupt: bool = False) -> dict[str, object]:
    path = Path(filepath)
    return {
        "bitrate_kbps": 0,
        "sample_rate": 0,
        "channels": "",
        "format": path.suffix.lower().lstrip(".").upper(),
        "file_size_mb": _file_size_mb(path),
        "low_bitrate": False,
        "possibly_corrupt": possibly_corrupt,
    }


def format_audio_quality(quality: dict[str, object]) -> str:
    if not quality:
        return "-"
    if quality.get("possibly_corrupt"):
        return "Problema al leer audio"
    parts: list[str] = []
    bitrate = int(quality.get("bitrate_kbps", 0) or 0)
    sample_rate = int(quality.get("sample_rate", 0) or 0)
    channels = str(quality.get("channels", "") or "")
    format_name = str(quality.get("format", "") or "")
    file_size = float(quality.get("file_size_mb", 0.0) or 0.0)
    if bitrate:
        parts.append(f"{bitrate} kbps")
    if sample_rate:
        parts.append(f"{sample_rate} Hz")
    if channels:
        parts.append(channels)
    if format_name:
        parts.append(format_name)
    if file_size:
        parts.append(f"{file_size:.1f} MB")
    return " / ".join(parts) if parts else "-"


def _channels_label(value: Any) -> str:
    try:
        channels = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if channels == 1:
        return "mono"
    if channels == 2:
        return "stereo"
    if channels > 2:
        return f"{channels}ch"
    return ""


def _file_size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def _format_label(audio, path: Path) -> str:
    mime = getattr(audio, "mime", None)
    if isinstance(mime, list) and mime:
        return str(mime[0]).replace("audio/", "").upper()
    return path.suffix.lower().lstrip(".").upper()
