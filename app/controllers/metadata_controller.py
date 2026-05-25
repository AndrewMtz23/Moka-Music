import logging
import os
from pathlib import Path
from typing import Callable, Optional

from ..constants import DEFAULT_METADATA, FileFormats
from ..i18n import I18n
from ..services.metadata_editor_service import MetadataEditor
from ..models import ActionResult, FilterMode, SortMode, TrackInfo
from ..utils.audio_utils import AudioUtils
from ..services.backup_service import (
    build_track_backup,
    decode_cover_art,
    read_backup_payload,
    write_metadata_backup,
)
from ..services.library_service import filter_files as filter_library_files
from ..services.library_service import quality_report, sort_files


class MetadataController:
    def __init__(self, translator: Optional[Callable[..., str]] = None) -> None:
        self.t = translator or I18n().t
        self.archivos: list[str] = []
        self.carpeta = ""
        self.portada_path: Optional[str] = None
        self._metadata_cache: dict[str, TrackInfo] = {}
        self._cover_cache: dict[str, bool] = {}
        self._sort_mode = SortMode.FILENAME
        self.logger = logging.getLogger(__name__)
        self.metadata_editor = MetadataEditor()

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def cargar_archivos_mp3(self, carpeta: str) -> list[str]:
        path = Path(carpeta)
        if not path.exists():
            raise FileNotFoundError(self.t("file.not_found", path=carpeta))

        self.carpeta = str(path.resolve())
        self.archivos = []
        self._metadata_cache.clear()
        self._cover_cache.clear()

        for item in sorted(path.iterdir()):
            if item.is_file() and item.suffix.lower() in FileFormats.AUDIO:
                self.archivos.append(item.name)
                self._precache_metadata(item.name)

        self._apply_sorting()
        return self.archivos.copy()

    def refresh_library(self) -> list[str]:
        if not self.carpeta:
            self.archivos = []
            self._metadata_cache.clear()
            return []
        return self.cargar_archivos_mp3(self.carpeta)

    def clear_library(self) -> None:
        self.archivos = []
        self.carpeta = ""
        self.portada_path = None
        self._metadata_cache.clear()
        self._cover_cache.clear()
        self._sort_mode = SortMode.FILENAME

    def register_file(self, filename: str) -> None:
        if filename not in self.archivos:
            self.archivos.append(filename)
        self._precache_metadata(filename)
        self._apply_sorting()

    def remove_file(self, filename: str) -> None:
        if filename in self.archivos:
            self.archivos.remove(filename)
        self._metadata_cache.pop(filename, None)
        self._cover_cache.pop(filename, None)

    def rename_file(self, old_name: str, new_name: str) -> None:
        if old_name in self.archivos:
            index = self.archivos.index(old_name)
            self.archivos[index] = new_name
        self._metadata_cache.pop(old_name, None)
        self._cover_cache.pop(old_name, None)
        self._precache_metadata(new_name)
        self._apply_sorting()

    def _precache_metadata(self, filename: str) -> None:
        filepath = os.path.join(self.carpeta, filename)
        metadata = self._get_file_metadata(filepath)
        self._metadata_cache[filename] = TrackInfo(
            filename=filename,
            filepath=filepath,
            metadata=metadata,
            duration=AudioUtils.get_audio_duration(filepath),
            cover_art=None,
        )

    def _get_file_metadata(self, filepath: str) -> dict[str, str]:
        metadata = self.metadata_editor.obtener_metadatos(filepath)
        if metadata:
            return metadata
        return DEFAULT_METADATA.copy()

    def set_sort_mode(self, mode: SortMode) -> None:
        self._sort_mode = mode
        self._apply_sorting()

    def _apply_sorting(self) -> None:
        self.archivos = sort_files(
            self.archivos,
            self._metadata_cache,
            self._sort_mode,
            self._get_file_mtime,
        )

    def _get_file_mtime(self, filename: str) -> float:
        try:
            return os.path.getmtime(os.path.join(self.carpeta, filename))
        except OSError:
            return 0.0

    def aplicar_cambios(self, metadatos: dict[str, str]) -> tuple[int, list[str]]:
        if not self.archivos:
            return 0, ["No hay archivos para procesar."]
        rutas = [os.path.join(self.carpeta, filename) for filename in self.archivos]
        success_count, errors = self.metadata_editor.aplicar_metadatos_en_lote(
            rutas,
            metadatos,
            self.portada_path,
        )
        if success_count:
            for filename in self.archivos:
                self._precache_metadata(filename)
        return success_count, errors

    def crear_respaldo_metadatos(
        self,
        metadatos_a_aplicar: dict[str, str],
        filenames: Optional[list[str]] = None,
    ) -> Path:
        if not self.archivos:
            raise ValueError(self.t("message.no_loaded_files"))

        tracks = []
        target_filenames = [filename for filename in filenames or self.archivos if filename in self.archivos]
        for filename in target_filenames:
            cached = self._metadata_cache.get(filename)
            filepath = os.path.join(self.carpeta, filename)
            cover_art = self.metadata_editor.obtener_portada(filepath)
            tracks.append(
                build_track_backup(
                    filename=filename,
                    filepath=filepath,
                    metadata=dict(cached.metadata) if cached else self._get_file_metadata(filepath),
                    cover_art=cover_art,
                )
            )

        return write_metadata_backup(
            library_folder=self.carpeta,
            applied_metadata=metadatos_a_aplicar,
            tracks=tracks,
        )

    def restaurar_respaldo_metadatos(self, backup_path: str | Path) -> ActionResult:
        path = Path(backup_path)
        if not path.exists():
            return ActionResult.fail(self.t("backup.not_found"))

        try:
            payload = read_backup_payload(path)
        except Exception as exc:
            return ActionResult.fail(self.t("backup.could_not_read", error=exc))

        tracks = payload.get("tracks", [])
        if not isinstance(tracks, list) or not tracks:
            return ActionResult.fail(self.t("backup.empty"))
        backup_folder = str(payload.get("library_folder", "") or "")
        if backup_folder and self.carpeta and os.path.normcase(backup_folder) != os.path.normcase(self.carpeta):
            return ActionResult.fail(self.t("backup.folder_mismatch"))

        success_count = 0
        errors: list[str] = []
        for track in tracks:
            if not isinstance(track, dict):
                continue
            filename = str(track.get("filename", "") or "")
            filepath = str(track.get("filepath", "") or "")
            metadata = track.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            target_path = filepath if Path(filepath).exists() else os.path.join(self.carpeta, filename)
            success, file_errors = self.metadata_editor.aplicar_metadatos_en_lote([target_path], metadata)
            cover_success = True
            cover_errors: list[str] = []
            if "cover_art_b64" in track:
                cover_art = self._decode_cover_backup(track.get("cover_art_b64"))
                cover_success, cover_errors = self.metadata_editor.aplicar_portada_desde_bytes(target_path, cover_art)
            if success and cover_success:
                success_count += 1
                if filename in self.archivos:
                    self._precache_metadata(filename)
            else:
                errors.extend(file_errors or cover_errors or [filename])

        if success_count:
            if errors:
                return ActionResult.fail(
                    self.t("backup.restore_partial", count=success_count),
                    errors=errors,
                )
            return ActionResult.ok(self.t("backup.restored", count=success_count))
        return ActionResult.fail(self.t("backup.restore_failed"), errors=errors)

    def _decode_cover_backup(self, value) -> Optional[bytes]:
        if not value:
            return None
        try:
            return decode_cover_art(value)
        except Exception as exc:
            self.logger.warning("Could not decode cover backup: %s", exc)
            return None

    def aplicar_cambios_a_archivo(
        self,
        filename: str,
        metadatos: dict[str, str],
        portada_path: Optional[str] = None,
    ) -> ActionResult:
        if not filename or filename not in self.archivos:
            return ActionResult.fail(self.t("action.song_missing"))

        filepath = os.path.join(self.carpeta, filename)
        validation = self.validar_datos(metadatos)
        if not validation.success:
            return validation

        success_count, errors = self.metadata_editor.aplicar_metadatos_en_lote(
            [filepath],
            metadatos,
            portada_path,
        )
        if not success_count:
            return ActionResult.fail(
                self.t("message.could_not_apply_metadata"),
                errors=errors,
            )

        self._precache_metadata(filename)
        return ActionResult.ok(self.t("message.song_metadata_saved"))

    def aplicar_cambios_a_archivos(
        self,
        filenames: list[str],
        metadatos: dict[str, str],
        portada_path: Optional[str] = None,
    ) -> tuple[int, list[str]]:
        selected = [filename for filename in filenames if filename in self.archivos]
        if not selected:
            return 0, [self.t("message.no_song_selected")]

        validation = self.validar_datos(metadatos)
        if not validation.success:
            return 0, [validation.message]

        rutas = [os.path.join(self.carpeta, filename) for filename in selected]
        success_count, errors = self.metadata_editor.aplicar_metadatos_en_lote(
            rutas,
            metadatos,
            portada_path,
        )
        if success_count:
            for filename in selected:
                self._precache_metadata(filename)
        return success_count, errors

    def validar_datos(self, datos: dict[str, str]) -> ActionResult:
        year_value = datos.get("year", "")
        if year_value:
            try:
                year = int(year_value)
            except ValueError:
                return ActionResult.fail(self.t("validation.year_numeric"))
            if year < 1900 or year > 2100:
                return ActionResult.fail(self.t("validation.year_range"))

        track_value = datos.get("track_number", "")
        if track_value:
            try:
                track_number = int(track_value)
            except ValueError:
                return ActionResult.fail(self.t("message.track_number_numeric"))
            if track_number < 0:
                return ActionResult.fail(self.t("message.track_number_numeric"))

        return ActionResult.ok(self.t("validation.metadata_valid"))

    def get_track_info(self, filename: str) -> Optional[TrackInfo]:
        return self._metadata_cache.get(filename)

    def tiene_archivos(self) -> bool:
        return bool(self.archivos)

    def get_sorted_files(self) -> list[str]:
        return self.archivos.copy()

    def reorder_files(self, ordered_filenames: list[str]) -> None:
        known_files = [filename for filename in ordered_filenames if filename in self.archivos]
        remaining_files = [filename for filename in self.archivos if filename not in known_files]
        self.archivos = known_files + remaining_files
        self._sort_mode = SortMode.MANUAL

    def apply_track_numbers_from_order(self) -> ActionResult:
        if not self.carpeta or not self.archivos:
            return ActionResult.fail(self.t("message.no_loaded_files"))

        errors: list[str] = []
        success_count = 0
        for index, filename in enumerate(self.archivos, start=1):
            filepath = os.path.join(self.carpeta, filename)
            success, file_errors = self.metadata_editor.aplicar_metadatos_en_lote(
                [filepath],
                {"track_number": str(index)},
            )
            if success:
                success_count += 1
                self._precache_metadata(filename)
            else:
                errors.extend(file_errors or [filename])

        if errors:
            return ActionResult.fail(
                self.t("message.track_order_partial", count=success_count),
                errors=errors,
            )
        return ActionResult.ok(self.t("message.track_order_updated", count=success_count))

    def filter_files(self, query: str = "", mode: FilterMode = FilterMode.ALL) -> list[str]:
        return filter_library_files(
            self.archivos,
            self._metadata_cache,
            query,
            mode,
            has_cover_art=self._has_cover_art,
        )

    def _has_cover_art(self, filename: str) -> bool:
        if filename in self._cover_cache:
            return self._cover_cache[filename]
        filepath = os.path.join(self.carpeta, filename)
        try:
            has_cover = bool(self.metadata_editor.obtener_portada(filepath))
        except Exception as exc:
            self.logger.warning("Could not inspect cover art for %s: %s", filename, exc)
            has_cover = False
        self._cover_cache[filename] = has_cover
        return has_cover

    def get_quality_report(self) -> dict[str, int]:
        return quality_report(self.archivos, self._metadata_cache)
