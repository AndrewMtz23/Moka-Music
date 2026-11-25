from __future__ import annotations

import io
import math
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import mutagen
from PIL import Image


class AudioWaveformError(RuntimeError):
    pass


class AudioWaveformCancelled(AudioWaveformError):
    pass


MAX_WAVEFORM_WIDTH = 4096
MAX_WAVEFORM_HEIGHT = 512


@dataclass(frozen=True)
class AudioWaveform:
    duration: float
    peaks: tuple[float, ...]


def build_waveform_command(filepath: str | Path, *, width: int, height: int) -> list[str]:
    path = Path(filepath)
    _validate_dimensions(width, height)
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-filter_complex",
        f"[0:a:0]showwavespic=s={width}x{height}:colors=0x40c4ff:scale=lin[v]",
        "-map",
        "[v]",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]


def extract_waveform(
    filepath: str | Path,
    *,
    width: int = 1200,
    height: int = 128,
    cancel_event: threading.Event | None = None,
) -> AudioWaveform:
    path = Path(filepath)
    _validate_dimensions(width, height)
    if not path.is_file():
        raise AudioWaveformError(f"Audio file does not exist: {path}")
    if cancel_event is not None and cancel_event.is_set():
        raise AudioWaveformCancelled("Waveform extraction cancelled")
    if shutil.which("ffmpeg") is None:
        raise AudioWaveformError("FFmpeg was not found on PATH")

    try:
        audio = mutagen.File(str(path))
        duration = float(audio.info.length) if audio is not None and audio.info is not None else 0.0
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        raise AudioWaveformError(f"Could not read audio duration: {exc}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise AudioWaveformError("Audio duration is unavailable")

    command = build_waveform_command(path, width=width, height=height)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise AudioWaveformError(f"Could not start FFmpeg: {exc}") from exc
    while True:
        if cancel_event is not None and cancel_event.is_set():
            process.terminate()
            process.communicate()
            raise AudioWaveformCancelled("Waveform extraction cancelled")
        try:
            stdout, stderr = process.communicate(timeout=0.05)
            break
        except subprocess.TimeoutExpired:
            continue
    if cancel_event is not None and cancel_event.is_set():
        raise AudioWaveformCancelled("Waveform extraction cancelled")
    if process.returncode != 0:
        detail = stderr.decode(errors="replace").strip()
        raise AudioWaveformError(detail or f"FFmpeg exited with {process.returncode}")

    try:
        with Image.open(io.BytesIO(stdout)) as image:
            rgb_image = image.convert("RGB")
            if rgb_image.size != (width, height):
                raise AudioWaveformError(
                    f"FFmpeg returned waveform size {rgb_image.width}x{rgb_image.height}, expected {width}x{height}"
                )
            peaks = _peaks_from_rgb(rgb_image)
    except AudioWaveformError:
        raise
    except (OSError, ValueError) as exc:
        raise AudioWaveformError(f"Could not decode waveform image: {exc}") from exc

    return AudioWaveform(duration=duration, peaks=peaks)


def _validate_dimensions(width: int, height: int) -> None:
    if not 1 <= width <= MAX_WAVEFORM_WIDTH or not 1 <= height <= MAX_WAVEFORM_HEIGHT:
        raise ValueError(f"Waveform dimensions must be between 1x1 and {MAX_WAVEFORM_WIDTH}x{MAX_WAVEFORM_HEIGHT}")


def _peaks_from_rgb(image: Image.Image) -> tuple[float, ...]:
    width, height = image.size
    pixels = image.load()
    peaks: list[float] = []
    center = (height - 1) / 2
    for x in range(width):
        painted_rows = [
            y
            for y in range(height)
            if max(pixels[x, y]) > 24  # type: ignore[arg-type]
        ]
        if not painted_rows:
            peaks.append(0.0)
            continue
        extent = max(abs(y - center) for y in painted_rows)
        peaks.append(min(1.0, extent / max(center, 1.0)))
    return tuple(peaks)
