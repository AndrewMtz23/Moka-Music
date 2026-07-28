import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from ..constants import DEFAULT_METADATA, FileFormats
from ..i18n import I18n
from ..models import ActionResult, FilterMode, SortMode, TrackInfo
from ..services.backup_service import (
    build_track_backup,
    decode_cover_art,
    read_backup_payload,
    write_metadata_backup,
)
from ..services.library_cache_service import LibraryCache
from ..services.library_service import duplicate_filenames, quality_report, sort_files
from ..services.library_service import filter_files as filter_library_files
from ..services.library_stats_service import build_library_stats
from ..services.metadata_editor_service import MetadataEditor
from ..services.playback_history_service import normalize_history_path
from ..services.track_scan_service import scan_track


class MetadataController:
    def __init__(
        self,
        translator: Optional[Callable[..., str]] = None,
        library_cache: Optional[LibraryCache] = None,
    ) -> None:
        self.t = translator or I18n().t
        self.archivos: list[str] = []
        self.carpeta = ""
        self.portada_path: Optional[str] = None
        self._metadata_cache: dict[str, TrackInfo] = {}
        self._cover_cache: dict[str, bool] = {}
        self._issue_cache: dict[str, list[str]] = {}
        self._duplicate_cache: set[str] | None = None
        self._duplicate_cache_signature: tuple[tuple[str, str, str, str], ...] | None = None
        self._sort_mode = SortMode.TRACK_NUMBER
        self._played_paths: set[str] = set()
        self._last_played_by_path: dict[str, str] = {}
        self._last_load_metrics: dict[str, object] = {}
        self.logger = logging.getLogger(__name__)
        self.metadata_editor = MetadataEditor()
        self.library_cache = library_cache or LibraryCache()

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def cargar_archivos_mp3(self, carpeta: str) -> list[str]:
        total_start = time.perf_counter()
        path = Path(carpeta)
        if not path.exists():
            raise FileNotFoundError(self.t("file.not_found", path=carpeta))

        self.carpeta = str(path.resolve())
        self.archivos = []
        self._metadata_cache.clear()
        self._cover_cache.clear()
        self._invalidate_derived_caches()
        self._last_load_metrics = {}

        list_start = time.perf_counter()
        audio_items = [
            item for item in sorted(path.iterdir()) if item.is_file() and item.suffix.lower() in FileFormats.AUDIO
        ]
        list_elapsed = time.perf_counter() - list_start

        scan_start = time.perf_counter()
        slowest_scans: list[dict[str, object]] = []
        cache_hits = 0
        cache_misses = 0
        for item in audio_items:
            self.archivos.append(item.name)
            item_start = time.perf_counter()
            cache_hit = self._precache_metadata(item.name)
            if cache_hit:
                cache_hits += 1
            else:
                cache_misses += 1
            scan_elapsed = time.perf_counter() - item_start
            slowest_scans.append({"filename": item.name, "seconds": round(scan_elapsed, 4)})
        scan_elapsed = time.perf_counter() - scan_start

        sort_start = time.perf_counter()
        self._apply_sorting()
        sort_elapsed = time.perf_counter() - sort_start

        total_elapsed = time.perf_counter() - total_start
        slowest_scans = sorted(slowest_scans, key=lambda item: item["seconds"], reverse=True)[:5]
        self._last_load_metrics = {
            "folder": self.carpeta,
            "file_count": len(self.archivos),
            "list_seconds": round(list_elapsed, 4),
            "scan_seconds": round(scan_elapsed, 4),
            "sort_seconds": round(sort_elapsed, 4),
            "total_seconds": round(total_elapsed, 4),
            "avg_scan_seconds": round(scan_elapsed / len(audio_items), 4) if audio_items else 0.0,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "slowest_scans": slowest_scans,
        }
        self.logger.info(
            "Library load metrics: folder=%s files=%s list=%.4fs scan=%.4fs sort=%.4fs total=%.4fs avg_scan=%.4fs cache_hits=%s cache_misses=%s slowest=%s",
            self.carpeta,
            len(self.archivos),
            list_elapsed,
            scan_elapsed,
            sort_elapsed,
            total_elapsed,
            self._last_load_metrics["avg_scan_seconds"],
            cache_hits,
            cache_misses,
            slowest_scans,
        )
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
        self._invalidate_derived_caches()
        self._sort_mode = SortMode.TRACK_NUMBER

    def adopt_loaded_state_from(self, other: "MetadataController") -> None:
        self.carpeta = other.carpeta
        self.archivos = other.archivos.copy()
        self.portada_path = other.portada_path
        self._metadata_cache = dict(other._metadata_cache)
        self._cover_cache = dict(other._cover_cache)
        self._issue_cache = dict(other._issue_cache)
        self._duplicate_cache = set(other._duplicate_cache) if other._duplicate_cache is not None else None
        self._duplicate_cache_signature = other._duplicate_cache_signature
        self._sort_mode = other._sort_mode
        self._last_load_metrics = dict(other._last_load_metrics)

    def register_file(self, filename: str) -> None:
        if filename not in self.archivos:
            self.archivos.append(filename)
        self._precache_metadata(filename)
        self._invalidate_derived_caches()
        self._apply_sorting()

    def remove_file(self, filename: str) -> None:
        self._invalidate_file_cache(filename)
        if filename in self.archivos:
            self.archivos.remove(filename)
        self._metadata_cache.pop(filename, None)
        self._cover_cache.pop(filename, None)
        self._invalidate_file_derived_cache(filename)
        self._invalidate_duplicate_cache()

    def rename_file(self, old_name: str, new_name: str) -> None:
        self._invalidate_file_cache(old_name)
        self._invalidate_file_cache(new_name)
        if old_name in self.archivos:
            index = self.archivos.index(old_name)
            self.archivos[index] = new_name
        self._metadata_cache.pop(old_name, None)
        self._cover_cache.pop(old_name, None)
        self._precache_metadata(new_name, force_rescan=True)
        self._invalidate_file_derived_cache(old_name)
        self._invalidate_file_derived_cache(new_name)
        self._invalidate_duplicate_cache()
        self._apply_sorting()

    def _precache_metadata(self, filename: str, *, force_rescan: bool = False) -> bool:
        filepath = os.path.join(self.carpeta, filename)
        scan = None if force_rescan else self.library_cache.get_valid_track(filepath)
        cache_hit = scan is not None
        if scan is None:
            scan = scan_track(filepath)
            self.library_cache.save_track(scan)
        self._metadata_cache[filename] = TrackInfo(
            filename=filename,
            filepath=filepath,
            metadata=scan.metadata,
            duration=scan.duration,
            cover_art=None,
            audio_quality=scan.audio_quality,
        )
        if scan.has_cover_art is not None:
            self._cover_cache[filename] = bool(scan.has_cover_art)
        self._invalidate_file_derived_cache(filename)
        return cache_hit

    def _invalidate_file_cache(self, filename: str) -> None:
        if not self.carpeta or not filename:
            return
        self.library_cache.invalidate_path(os.path.join(self.carpeta, filename))

    def _invalidate_file_derived_cache(self, filename: str) -> None:
        self._issue_cache.pop(filename, None)
        self._invalidate_duplicate_cache()

    def _invalidate_duplicate_cache(self) -> None:
        self._duplicate_cache = None
        self._duplicate_cache_signature = None

    def _invalidate_derived_caches(self) -> None:
        self._issue_cache.clear()
        self._invalidate_duplicate_cache()

    def _get_file_metadata(self, filepath: str) -> dict[str, str]:
        metadata = self.metadata_editor.obtener_metadatos(filepath)
        if metadata:
            return metadata
        return DEFAULT_METADATA.copy()

    def set_sort_mode(self, mode: SortMode) -> None:
        self._sort_mode = mode
        self._apply_sorting()

    def set_playback_history(self, played_paths: set[str], last_played_by_path: dict[str, str]) -> None:
        self._played_paths = set(played_paths)
        self._last_played_by_path = dict(last_played_by_path)
        if self._sort_mode == SortMode.LAST_PLAYED:
            self._apply_sorting()

    def _apply_sorting(self) -> None:
        self.archivos = sort_files(
            self.archivos,
            self._metadata_cache,
            self._sort_mode,
            self._get_file_mtime,
            self._last_played_for_file,
        )

    def _get_file_mtime(self, filename: str) -> float:
        try:
            return os.path.getmtime(os.path.join(self.carpeta, filename))
        except OSError:
            return 0.0

    def _last_played_for_file(self, filename: str) -> str:
        return self._last_played_by_path.get(normalize_history_path(os.path.join(self.carpeta, filename)), "")

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
                self._invalidate_file_cache(filename)
                self._precache_metadata(filename, force_rescan=True)
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
                    self._invalidate_file_cache(filename)
                    self._precache_metadata(filename, force_rescan=True)
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

        shifted_filenames: list[str] = []
        if "track_number" in metadatos:
            shift_result = self._shift_track_numbers_for_edit(filename, metadatos.get("track_number", ""))
            if not shift_result.success:
                return shift_result
            shifted_filenames = list((shift_result.data or {}).get("shifted_filenames", []))

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

        self._invalidate_file_cache(filename)
        self._precache_metadata(filename, force_rescan=True)
        self._apply_sorting()
        return ActionResult.ok(
            self.t("message.song_metadata_saved"),
            data={"shifted_filenames": shifted_filenames},
        )

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

        if "track_number" in metadatos and len(selected) == 1:
            result = self.aplicar_cambios_a_archivo(selected[0], metadatos, portada_path)
            if result.success:
                return 1, []
            return 0, result.errors or [result.message]

        rutas = [os.path.join(self.carpeta, filename) for filename in selected]
        success_count, errors = self.metadata_editor.aplicar_metadatos_en_lote(
            rutas,
            metadatos,
            portada_path,
        )
        if success_count:
            for filename in selected:
                self._invalidate_file_cache(filename)
                self._precache_metadata(filename, force_rescan=True)
            self._apply_sorting()
        return success_count, errors

    def _shift_track_numbers_for_edit(self, edited_filename: str, target_value: str) -> ActionResult:
        try:
            target_number = int(str(target_value).strip())
        except (TypeError, ValueError):
            return ActionResult.ok("", data={"shifted_filenames": []})
        if target_number < 0:
            return ActionResult.ok("", data={"shifted_filenames": []})

        current_number = self._track_number_for_file(edited_filename)
        if current_number == target_number:
            return ActionResult.ok("", data={"shifted_filenames": []})

        affected: list[tuple[int, str]] = []
        for filename in self.archivos:
            if filename == edited_filename:
                continue
            number = self._track_number_for_file(filename)
            if number is None:
                continue
            if current_number is not None and current_number > target_number:
                should_shift = target_number <= number < current_number
            else:
                should_shift = number >= target_number
            if should_shift:
                affected.append((number, filename))

        shifted: list[str] = []
        errors: list[str] = []
        for number, filename in sorted(affected, reverse=True):
            filepath = os.path.join(self.carpeta, filename)
            new_number = number + 1
            success, file_errors = self.metadata_editor.aplicar_metadatos_en_lote(
                [filepath],
                {"track_number": str(new_number)},
            )
            if success:
                shifted.append(filename)
                self._set_cached_track_number(filename, new_number)
            else:
                errors.extend(file_errors or [filename])

        if errors:
            return ActionResult.fail(
                self.t("message.could_not_apply_metadata"),
                errors=errors,
                data={"shifted_filenames": shifted},
            )
        return ActionResult.ok("", data={"shifted_filenames": shifted})

    def _track_number_for_file(self, filename: str) -> Optional[int]:
        cached = self._metadata_cache.get(filename)
        metadata = cached.metadata if cached else {}
        value = str(metadata.get("track_number", "") or "").strip()
        if not value:
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    def _set_cached_track_number(self, filename: str, track_number: int) -> None:
        cached = self._metadata_cache.get(filename)
        if cached is None:
            return
        cached.metadata["track_number"] = str(track_number)

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
        for index, filename in enumerate(self.archivos, start=0):
            filepath = os.path.join(self.carpeta, filename)
            success, file_errors = self.metadata_editor.aplicar_metadatos_en_lote(
                [filepath],
                {"track_number": str(index)},
            )
            if success:
                success_count += 1
                self._invalidate_file_cache(filename)
                self._precache_metadata(filename, force_rescan=True)
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
            played_paths=self._played_paths,
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

    def get_library_stats(self) -> dict[str, object]:
        return build_library_stats(self.archivos, self._metadata_cache)

    def metadata_cache_snapshot(self) -> dict[str, TrackInfo]:
        return dict(self._metadata_cache)

    def load_metrics_snapshot(self) -> dict[str, object]:
        return dict(self._last_load_metrics)

    def duplicate_filenames(self) -> set[str]:
        signature = self._duplicate_signature()
        if self._duplicate_cache is not None and self._duplicate_cache_signature == signature:
            return set(self._duplicate_cache)
        duplicates = duplicate_filenames(self.archivos, self._metadata_cache)
        self._duplicate_cache = set(duplicates)
        self._duplicate_cache_signature = signature
        return set(duplicates)

    def _duplicate_signature(self) -> tuple[tuple[str, str, str, str], ...]:
        signature: list[tuple[str, str, str, str]] = []
        for filename in self.archivos:
            cached = self._metadata_cache.get(filename)
            metadata = cached.metadata if cached else {}
            signature.append(
                (
                    filename,
                    str(metadata.get("artist", "") or ""),
                    str(metadata.get("title", "") or ""),
                    str(metadata.get("track_number", "") or ""),
                )
            )
        return tuple(signature)

    def issue_keys_for_file(self, filename: str, duplicate_set: Optional[set[str]] = None) -> list[str]:
        base_issues = list(self._base_issue_keys_for_file(filename))
        if filename in (duplicate_set or set()):
            base_issues.append("duplicate")
        return base_issues

    def _base_issue_keys_for_file(self, filename: str) -> list[str]:
        cached_issues = self._issue_cache.get(filename)
        if cached_issues is not None:
            return list(cached_issues)
        cached = self.get_track_info(filename)
        metadata = cached.metadata if cached else {}
        issues: list[str] = []
        if not str(metadata.get("artist", "") or "").strip():
            issues.append("missing_artist")
        if not str(metadata.get("album", "") or "").strip():
            issues.append("missing_album")
        if not str(metadata.get("year", "") or "").strip():
            issues.append("missing_year")
        track_value = str(metadata.get("track_number", "") or "").strip()
        try:
            missing_track = not track_value or int(track_value) < 0
        except ValueError:
            missing_track = True
        if missing_track:
            issues.append("missing_track")
        if not self._has_cover_art(filename):
            issues.append("missing_cover")
        quality = cached.audio_quality if cached else {}
        if quality.get("low_bitrate"):
            issues.append("low_bitrate")
        if quality.get("possibly_corrupt"):
            issues.append("possibly_corrupt")
        self._issue_cache[filename] = list(issues)
        return list(issues)
