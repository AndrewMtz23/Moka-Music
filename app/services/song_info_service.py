import io
import logging
import os
from pathlib import Path
from typing import Optional

import eyed3
import mutagen
from PIL import Image, UnidentifiedImageError

from ..constants import DEFAULT_COVER_ART, FileFormats
from ..utils.audio_utils import AudioUtils


class SongInfo:
    def __init__(self) -> None:
        self._metadata_cache: dict[str, dict] = {}
        self.logger = logging.getLogger(__name__)
        eyed3.log.setLevel("ERROR")

    def get_metadata(self, file_path: str, use_cache: bool = True) -> Optional[dict]:
        try:
            if use_cache and file_path in self._metadata_cache:
                return self._metadata_cache[file_path]
            if not self._is_valid_audio_file(file_path):
                return None

            suffix = Path(file_path).suffix.lower()
            metadata = self._get_mp3_metadata(file_path) if suffix == ".mp3" else self._get_generic_metadata(file_path)
            metadata["file_name"] = os.path.basename(file_path)
            metadata["file_path"] = file_path
            metadata["file_size"] = os.path.getsize(file_path)
            metadata["duration"] = AudioUtils.get_audio_duration(file_path)
            self._metadata_cache[file_path] = metadata
            return metadata
        except Exception as exc:
            self.logger.error("Error reading song metadata from %s: %s", file_path, exc)
            return None

    def _is_valid_audio_file(self, file_path: str) -> bool:
        path = Path(file_path)
        return path.exists() and path.is_file() and path.suffix.lower() in FileFormats.AUDIO

    def _get_mp3_metadata(self, file_path: str) -> dict:
        metadata = {
            "title": Path(file_path).stem,
            "artist": "",
            "album_artist": "",
            "album": "",
            "year": "",
            "genre": "",
            "track_number": 0,
            "comment": "",
            "cover_art": None,
        }
        try:
            audio = eyed3.load(file_path)
            if audio is None or audio.tag is None:
                return metadata
            tag = audio.tag
            metadata.update(
                {
                    "title": tag.title or Path(file_path).stem,
                    "artist": tag.artist or "",
                    "album_artist": tag.album_artist or "",
                    "album": tag.album or "",
                    "year": str(tag.recording_date.year) if tag.recording_date else "",
                    "genre": tag.genre.name if tag.genre else "",
                    "track_number": tag.track_num[0] if tag.track_num else 0,
                    "comment": self._mp3_comment(tag),
                    "cover_art": self._extract_mp3_cover(tag),
                }
            )
        except Exception as exc:
            self.logger.warning("Error processing mp3 metadata %s: %s", file_path, exc)
        return metadata

    def _extract_mp3_cover(self, tag) -> Optional[bytes]:
        try:
            for image in tag.images:
                if image.picture_type == 3:
                    return image.image_data
        except Exception as exc:
            self.logger.warning("Error extracting mp3 cover: %s", exc)
        return None

    def _get_generic_metadata(self, file_path: str) -> dict:
        metadata = {
            "title": Path(file_path).stem,
            "artist": "",
            "album_artist": "",
            "album": "",
            "year": "",
            "genre": "",
            "track_number": 0,
            "comment": "",
            "cover_art": None,
        }
        try:
            audio = mutagen.File(file_path, easy=True)
            if audio is None:
                return metadata
            metadata.update(
                {
                    "title": self._first_value(audio, "title") or Path(file_path).stem,
                    "artist": self._first_value(audio, "artist"),
                    "album_artist": self._first_value(audio, "albumartist"),
                    "album": self._first_value(audio, "album"),
                    "year": self._first_value(audio, "date"),
                    "genre": self._first_value(audio, "genre"),
                    "track_number": self._first_value(audio, "tracknumber") or 0,
                    "comment": self._first_value(audio, "comment"),
                }
            )

            full_audio = mutagen.File(file_path)
            metadata["cover_art"] = self._extract_generic_cover(full_audio)
        except Exception as exc:
            self.logger.warning("Error processing generic metadata %s: %s", file_path, exc)
        return metadata

    def _extract_generic_cover(self, audio) -> Optional[bytes]:
        try:
            if hasattr(audio, "tags") and audio.tags:
                for key, value in audio.tags.items():
                    if key.startswith("APIC") and hasattr(value, "data"):
                        return value.data
        except Exception as exc:
            self.logger.warning("Error extracting generic cover: %s", exc)
        return None

    def _first_value(self, audio, key: str):
        value = audio.get(key, [""])
        return value[0] if isinstance(value, list) and value else value

    def _mp3_comment(self, tag) -> str:
        try:
            for comment in tag.comments:
                if comment.text:
                    return str(comment.text)
        except Exception:
            return ""
        return ""

    def get_cover_image(self, file_path: str, size: tuple[int, int] = (300, 300)) -> Optional[Image.Image]:
        try:
            metadata = self.get_metadata(file_path)
            if not metadata or not metadata.get("cover_art"):
                return self._get_default_cover(size)
            with Image.open(io.BytesIO(metadata["cover_art"])) as image:
                image = image.convert("RGB")
                image.thumbnail(size, Image.LANCZOS)
                return image
        except UnidentifiedImageError:
            return self._get_default_cover(size)
        except Exception as exc:
            self.logger.error("Error building cover image for %s: %s", file_path, exc)
            return self._get_default_cover(size)

    def _get_default_cover(self, size: tuple[int, int]) -> Image.Image:
        try:
            if DEFAULT_COVER_ART and os.path.exists(DEFAULT_COVER_ART):
                with Image.open(DEFAULT_COVER_ART) as image:
                    image.thumbnail(size, Image.LANCZOS)
                    return image.copy()
        except Exception:
            pass
        return Image.new("RGB", size, "#333333")

    def clear_cache(self) -> None:
        self._metadata_cache.clear()

    def invalidate(self, file_path: str) -> None:
        self._metadata_cache.pop(file_path, None)
