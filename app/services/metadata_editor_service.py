import logging
import os
from pathlib import Path
from typing import Optional

import eyed3
import eyed3.id3
import mutagen
from mutagen.mp4 import MP4, MP4Cover

from ..constants import DEFAULT_METADATA, FileFormats
from .cover_service import process_cover_image


class MetadataEditor:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        eyed3.log.setLevel("ERROR")
        self.id3_version = eyed3.id3.ID3_V2_3

    def aplicar_metadatos_en_lote(
        self,
        lista_rutas: list[str],
        datos: dict[str, str],
        portada_path: Optional[str] = None,
    ) -> tuple[int, list[str]]:
        success_count = 0
        errors: list[str] = []
        portada_data = self._procesar_portada(portada_path) if portada_path else None

        if portada_path and not portada_data:
            errors.append("No se pudo procesar la portada seleccionada.")

        for ruta in lista_rutas:
            try:
                if not self._validar_archivo(ruta):
                    errors.append(f"Archivo invalido: {os.path.basename(ruta)}")
                    continue

                audio = self._cargar_audio(ruta)
                if audio is None:
                    errors.append(f"No se pudo abrir: {os.path.basename(ruta)}")
                    continue

                self._aplicar_metadatos_basicos(audio, datos)
                if portada_data:
                    self._aplicar_portada(audio, portada_data)
                self._guardar_audio(audio)
                success_count += 1
            except Exception as exc:
                filename = os.path.basename(ruta)
                errors.append(f"{filename}: {exc}")
                self.logger.error("Error applying metadata to %s: %s", ruta, exc)

        return success_count, errors

    def _procesar_portada(self, ruta: Optional[str]) -> Optional[bytes]:
        if not ruta:
            return None
        image_data = process_cover_image(ruta)
        if image_data is None:
            self.logger.error("Error processing cover art %s", ruta)
            return None
        return image_data

    def _cargar_audio(self, ruta: str):
        try:
            if ruta.lower().endswith(".mp3"):
                audio = eyed3.load(ruta)
                if audio is None:
                    return None
                if audio.tag is None:
                    audio.initTag(version=self.id3_version)
                return audio
            audio = mutagen.File(ruta, easy=True)
            return audio
        except Exception as exc:
            self.logger.error("Error loading audio %s: %s", ruta, exc)
            return None

    def _guardar_audio(self, audio) -> None:
        if isinstance(audio, eyed3.core.AudioFile):
            if audio.tag is None:
                audio.initTag(version=self.id3_version)
            audio.tag.save(version=self.id3_version)
            return
        audio.save()

    def _aplicar_metadatos_basicos(self, audio, datos: dict[str, str]) -> None:
        if isinstance(audio, eyed3.core.AudioFile):
            if audio.tag is None:
                audio.initTag(version=self.id3_version)
            if "artist" in datos:
                audio.tag.artist = datos["artist"] or None
            if "album_artist" in datos:
                audio.tag.album_artist = datos["album_artist"] or None
            if "album" in datos:
                audio.tag.album = datos["album"] or None
            if "title" in datos:
                audio.tag.title = datos["title"] or None
            if "genre" in datos:
                audio.tag.genre = datos["genre"] or None
            if "year" in datos:
                if datos["year"]:
                    try:
                        audio.tag.recording_date = eyed3.core.Date(int(datos["year"]))
                    except (TypeError, ValueError):
                        self.logger.warning("Invalid year ignored: %s", datos["year"])
                else:
                    audio.tag.recording_date = None
            if "track_number" in datos:
                if datos["track_number"]:
                    try:
                        audio.tag.track_num = (int(datos["track_number"]), 0)
                    except (TypeError, ValueError):
                        self.logger.warning("Invalid track number ignored: %s", datos["track_number"])
                else:
                    audio.tag.track_num = None
            if "comment" in datos:
                self._set_mp3_comment(audio, datos["comment"])
            return

        if isinstance(audio, mutagen.FileType):
            field_map = {
                "artist": "artist",
                "album_artist": "albumartist",
                "album": "album",
                "title": "title",
                "genre": "genre",
                "year": "date",
                "track_number": "tracknumber",
                "comment": "comment",
            }
            for source_key, target_key in field_map.items():
                if source_key in datos:
                    if datos[source_key] != "":
                        audio[target_key] = [str(datos[source_key])]
                    elif target_key in audio:
                        del audio[target_key]

    def _set_mp3_comment(self, audio, value: str) -> None:
        try:
            if value:
                audio.tag.comments.set(value)
                return
            for comment in list(audio.tag.comments):
                audio.tag.comments.remove(comment.description, comment.lang)
        except Exception as exc:
            self.logger.warning("Could not update comment: %s", exc)

    def _aplicar_portada(self, audio, image_data: bytes) -> None:
        if isinstance(audio, eyed3.core.AudioFile):
            if audio.tag is None:
                audio.initTag(version=self.id3_version)
            if audio.tag.images:
                for image in list(audio.tag.images):
                    audio.tag.images.remove(image.description)
            audio.tag.images.set(
                3,
                image_data,
                "image/jpeg",
                "Cover",
            )
            return

        if isinstance(audio, MP4):
            audio["covr"] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
            return

        if isinstance(audio, mutagen.FileType):
            if audio.tags is None:
                audio.add_tags()
            if hasattr(audio.tags, "add"):
                audio.tags.add(
                    mutagen.id3.APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=image_data,
                    )
                )

    def aplicar_portada_desde_bytes(self, ruta: str, image_data: Optional[bytes]) -> tuple[bool, list[str]]:
        try:
            if not self._validar_archivo(ruta):
                return False, [f"Archivo invalido: {os.path.basename(ruta)}"]
            audio = self._cargar_audio(ruta)
            if audio is None:
                return False, [f"No se pudo abrir: {os.path.basename(ruta)}"]
            if image_data:
                self._aplicar_portada(audio, image_data)
            else:
                self._limpiar_portada(audio)
            self._guardar_audio(audio)
            return True, []
        except Exception as exc:
            filename = os.path.basename(ruta)
            self.logger.error("Error restoring cover art for %s: %s", ruta, exc)
            return False, [f"{filename}: {exc}"]

    def obtener_portada(self, ruta: str) -> Optional[bytes]:
        try:
            if not self._validar_archivo(ruta):
                return None
            if ruta.lower().endswith(".mp3"):
                audio = eyed3.load(ruta)
                if audio and audio.tag:
                    for image in audio.tag.images:
                        if image.picture_type == 3:
                            return image.image_data
                    for image in audio.tag.images:
                        return image.image_data
                return None

            audio = mutagen.File(ruta)
            if audio and getattr(audio, "tags", None):
                for key, value in audio.tags.items():
                    if key == "covr" and isinstance(value, list):
                        for cover in value:
                            if isinstance(cover, (bytes, MP4Cover)):
                                return bytes(cover)
                    if key.startswith("APIC") and hasattr(value, "data"):
                        return value.data
            return None
        except Exception as exc:
            self.logger.warning("Could not read cover art from %s: %s", ruta, exc)
            return None

    def _limpiar_portada(self, audio) -> None:
        if isinstance(audio, eyed3.core.AudioFile):
            if audio.tag is None:
                audio.initTag(version=self.id3_version)
            for image in list(audio.tag.images):
                audio.tag.images.remove(image.description)
            return

        if isinstance(audio, MP4):
            if "covr" in audio:
                del audio["covr"]
            return

        if isinstance(audio, mutagen.FileType) and getattr(audio, "tags", None):
            for key in list(audio.tags.keys()):
                if str(key).startswith("APIC") or str(key) == "covr":
                    del audio.tags[key]

    def _validar_archivo(self, ruta: str) -> bool:
        path = Path(ruta)
        return path.exists() and path.is_file() and path.suffix.lower() in FileFormats.AUDIO

    def obtener_metadatos(self, ruta: str) -> Optional[dict[str, str]]:
        try:
            if not self._validar_archivo(ruta):
                return None
            audio = self._cargar_audio(ruta)
            if not audio:
                return None

            metadata = DEFAULT_METADATA.copy()
            metadata["title"] = Path(ruta).stem

            if isinstance(audio, eyed3.core.AudioFile) and audio.tag:
                metadata.update(
                    {
                        "artist": audio.tag.artist or "",
                        "album_artist": audio.tag.album_artist or "",
                        "album": audio.tag.album or "",
                        "title": audio.tag.title or Path(ruta).stem,
                        "year": str(audio.tag.recording_date.year) if audio.tag.recording_date else "",
                        "track_number": str(audio.tag.track_num[0]) if audio.tag.track_num else "0",
                        "genre": audio.tag.genre.name if audio.tag.genre else "",
                        "comment": self._get_mp3_comment(audio),
                    }
                )
            elif isinstance(audio, mutagen.FileType):
                metadata.update(
                    {
                        "artist": self._get_first_value(audio, "artist"),
                        "album_artist": self._get_first_value(audio, "albumartist"),
                        "album": self._get_first_value(audio, "album"),
                        "title": self._get_first_value(audio, "title") or Path(ruta).stem,
                        "year": self._get_first_value(audio, "date"),
                        "track_number": self._get_first_value(audio, "tracknumber") or "0",
                        "genre": self._get_first_value(audio, "genre"),
                        "comment": self._get_first_value(audio, "comment"),
                    }
                )

            return metadata
        except Exception as exc:
            self.logger.error("Error reading metadata from %s: %s", ruta, exc)
            return None

    def _get_first_value(self, audio, key: str) -> str:
        value = audio.get(key, [""])
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value)

    def _get_mp3_comment(self, audio) -> str:
        try:
            for comment in audio.tag.comments:
                if comment.text:
                    return str(comment.text)
        except Exception:
            return ""
        return ""
