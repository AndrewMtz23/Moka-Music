from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..constants import FileFormats
from ..services.file_service import add_song_to_library


@dataclass
class DropPayload:
    folders: list[str] = field(default_factory=list)
    audio_files: list[str] = field(default_factory=list)
    image_files: list[str] = field(default_factory=list)


@dataclass
class DropAddResult:
    added: int
    errors: list[str] = field(default_factory=list)


class DropController:
    def parse_paths(self, raw_data: str, *, splitlist: Callable[[str], list[str] | tuple[str, ...]]) -> list[str]:
        try:
            entries = splitlist(raw_data)
        except Exception:
            entries = raw_data.split() if isinstance(raw_data, str) else []
        return [str(entry).strip("{}") for entry in entries if str(entry).strip("{}")]

    def classify_paths(self, paths: list[str]) -> DropPayload:
        payload = DropPayload()
        for file_path in paths:
            path = Path(file_path)
            if path.is_dir():
                payload.folders.append(str(path))
            elif path.suffix.lower() in FileFormats.AUDIO:
                payload.audio_files.append(str(path))
            elif path.suffix.lower() in FileFormats.IMAGES:
                payload.image_files.append(str(path))
        return payload

    def payload_from_raw(
        self,
        raw_data: str,
        *,
        splitlist: Callable[[str], list[str] | tuple[str, ...]],
    ) -> DropPayload:
        return self.classify_paths(self.parse_paths(raw_data, splitlist=splitlist))

    def add_audio_files(
        self,
        audio_files: list[str],
        *,
        controller,
        song_info,
        translator,
    ) -> DropAddResult:
        added = 0
        errors: list[str] = []
        for filepath in audio_files:
            result = add_song_to_library(
                filepath,
                controller,
                song_info=song_info,
                translator=translator,
            )
            if result.success:
                added += 1
            else:
                errors.extend(result.errors or [result.message])
        return DropAddResult(added=added, errors=errors)
