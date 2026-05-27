from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Callable


SUPPORTED_OUTPUT_FORMATS = (".mp3", ".wav", ".flac", ".ogg")


@dataclass(frozen=True)
class AudioConversionItem:
    source: Path
    destination: Path


@dataclass
class AudioConversionResult:
    converted: int
    errors: list[str]
    items: list[AudioConversionItem]


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def build_conversion_items(
    sources: list[str | Path],
    output_folder: str | Path,
    output_extension: str,
) -> list[AudioConversionItem]:
    extension = normalize_output_extension(output_extension)
    destination_folder = Path(output_folder)
    used_names: set[str] = set()
    items: list[AudioConversionItem] = []
    for source_value in sources:
        source = Path(source_value)
        destination = unique_destination(destination_folder / f"{source.stem}{extension}", used_names)
        items.append(AudioConversionItem(source=source, destination=destination))
    return items


def convert_audio_files(
    items: list[AudioConversionItem],
    *,
    overwrite: bool = False,
    progress_callback: Callable[[int, str], bool] | None = None,
) -> AudioConversionResult:
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg is not available")

    converted = 0
    errors: list[str] = []
    total = len(items)
    for index, item in enumerate(items, start=1):
        if progress_callback and not progress_callback(index - 1, total, item.source.name):
            break
        try:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            command = build_ffmpeg_command(item.source, item.destination, overwrite=overwrite)
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode == 0:
                converted += 1
            else:
                detail = completed.stderr.strip() or completed.stdout.strip() or f"ffmpeg exited with {completed.returncode}"
                errors.append(f"{item.source.name}: {detail}")
        except Exception as exc:
            errors.append(f"{item.source.name}: {exc}")
        if progress_callback:
            progress_callback(index, total, f"{index}/{total}")

    return AudioConversionResult(converted=converted, errors=errors, items=items)


def build_ffmpeg_command(source: Path, destination: Path, *, overwrite: bool = False) -> list[str]:
    command = ["ffmpeg", "-y" if overwrite else "-n", "-i", str(source)]
    suffix = destination.suffix.lower()
    if suffix == ".mp3":
        command.extend(["-codec:a", "libmp3lame", "-b:a", "192k"])
    elif suffix == ".ogg":
        command.extend(["-codec:a", "libvorbis", "-q:a", "5"])
    elif suffix == ".flac":
        command.extend(["-codec:a", "flac"])
    elif suffix == ".wav":
        command.extend(["-codec:a", "pcm_s16le"])
    command.append(str(destination))
    return command


def normalize_output_extension(value: str) -> str:
    extension = value.strip().lower()
    if not extension.startswith("."):
        extension = f".{extension}"
    if extension not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {value}")
    return extension


def unique_destination(path: Path, used_names: set[str]) -> Path:
    candidate = path
    index = 2
    while candidate.name.lower() in used_names or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    used_names.add(candidate.name.lower())
    return candidate
