from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SUPPORTED_OUTPUT_FORMATS = (".mp3", ".wav", ".flac", ".ogg")


@dataclass(frozen=True)
class AudioConversionPreset:
    id: str
    extension: str
    bitrate: str | None = None


AUDIO_CONVERSION_PRESETS: tuple[AudioConversionPreset, ...] = (
    AudioConversionPreset("mp3_320", ".mp3", "320k"),
    AudioConversionPreset("mp3_256", ".mp3", "256k"),
    AudioConversionPreset("mp3_128", ".mp3", "128k"),
    AudioConversionPreset("wav", ".wav"),
    AudioConversionPreset("flac", ".flac"),
)


@dataclass(frozen=True)
class AudioConversionItem:
    source: Path
    destination: Path
    bitrate: str | None = None


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
    *,
    bitrate: str | None = None,
    preserve_structure: bool = False,
    source_root: str | Path | None = None,
) -> list[AudioConversionItem]:
    extension = normalize_output_extension(output_extension)
    destination_folder = Path(output_folder)
    used_names: set[str] = set()
    items: list[AudioConversionItem] = []
    root_path = Path(source_root).resolve() if source_root else None
    for source_value in sources:
        source = Path(source_value)
        destination = destination_folder / f"{source.stem}{extension}"
        if preserve_structure and root_path is not None:
            try:
                relative_parent = source.resolve().parent.relative_to(root_path)
                destination = destination_folder / relative_parent / f"{source.stem}{extension}"
            except ValueError:
                destination = destination_folder / f"{source.stem}{extension}"
        destination = unique_destination(destination, used_names)
        items.append(AudioConversionItem(source=source, destination=destination, bitrate=bitrate))
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
            command = build_ffmpeg_command(item.source, item.destination, overwrite=overwrite, bitrate=item.bitrate)
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode == 0:
                converted += 1
            else:
                detail = (
                    completed.stderr.strip() or completed.stdout.strip() or f"ffmpeg exited with {completed.returncode}"
                )
                errors.append(f"{item.source.name}: {detail}")
        except Exception as exc:
            errors.append(f"{item.source.name}: {exc}")
        if progress_callback:
            progress_callback(index, total, f"{index}/{total}")

    return AudioConversionResult(converted=converted, errors=errors, items=items)


def build_ffmpeg_command(
    source: Path, destination: Path, *, overwrite: bool = False, bitrate: str | None = None
) -> list[str]:
    command = ["ffmpeg", "-y" if overwrite else "-n", "-i", str(source)]
    suffix = destination.suffix.lower()
    if suffix == ".mp3":
        command.extend(["-codec:a", "libmp3lame", "-b:a", bitrate or "192k"])
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


def preset_by_id(preset_id: str) -> AudioConversionPreset:
    for preset in AUDIO_CONVERSION_PRESETS:
        if preset.id == preset_id:
            return preset
    raise ValueError(f"Unsupported audio preset: {preset_id}")


def unique_destination(path: Path, used_names: set[str]) -> Path:
    candidate = path
    index = 2
    while str(candidate).lower() in used_names or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    used_names.add(str(candidate).lower())
    return candidate
