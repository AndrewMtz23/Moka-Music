import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ..models import ActionResult
from ..services.backup_service import iter_backup_payloads, read_backup_payload
from ..utils.ui_formatting import backup_action_label


BackupGroup = tuple[object, object, list[str]]
ControllerTreePair = tuple[object, object]


@dataclass
class BackupRestoreResult:
    restored: bool
    errors: list[str]
    refreshed_pairs: set[tuple[int, int]]


class BackupController:
    def __init__(self, translator: Callable[..., str], song_info=None) -> None:
        self.t = translator
        self.song_info = song_info
        self.logger = logging.getLogger(__name__)
        self.last_backup_path: Optional[Path] = None
        self.last_backup_paths: list[Path] = []

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def set_song_info(self, song_info) -> None:
        self.song_info = song_info

    def create_metadata_backups(
        self,
        groups: list[BackupGroup],
        metadata: dict[str, str],
    ) -> Optional[Path]:
        backup_paths: list[Path] = []
        for controller, _tree, filenames in groups:
            backup_paths.append(controller.crear_respaldo_metadatos(metadata, filenames))
        if backup_paths:
            self.last_backup_paths = backup_paths
            self.last_backup_path = backup_paths[-1]
        return self.last_backup_path

    def has_recent_backup(self) -> bool:
        return bool(self.last_backup_paths)

    def recent_backup_label(self) -> str:
        return ", ".join(str(path) for path in self.last_backup_paths)

    def metadata_changes(
        self,
        groups: list[BackupGroup],
        metadata: dict[str, str],
        label_for_field: Callable[[str], str],
    ) -> list[tuple[str, str, str, str]]:
        changes: list[tuple[str, str, str, str]] = []
        for controller, _tree, filenames in groups:
            for filename in filenames:
                cached = controller.get_track_info(filename)
                current_metadata = cached.metadata if cached else {}
                for field, new_value in metadata.items():
                    current_value = str(current_metadata.get(field, "") or "").strip()
                    normalized_new = str(new_value or "").strip()
                    if current_value != normalized_new:
                        changes.append(
                            (
                                filename,
                                label_for_field(field),
                                current_value or "-",
                                normalized_new or "-",
                            )
                        )
        return changes

    def list_metadata_backups(self) -> list[dict[str, object]]:
        backups: list[dict[str, object]] = []
        for path, payload in iter_backup_payloads():
            backups.append(
                {
                    "path": path,
                    "created_at": str(payload.get("created_at", "")),
                    "folder": str(payload.get("library_folder", "")),
                    "track_count": int(payload.get("track_count", 0) or 0),
                    "action": backup_action_label(payload.get("applied_metadata", {}), self.t),
                }
            )
        return backups

    def restore_paths(
        self,
        backup_paths: list[Path],
        controller_tree_pairs: list[ControllerTreePair],
    ) -> BackupRestoreResult:
        restored = False
        errors: list[str] = []
        refreshed_pairs: set[tuple[int, int]] = set()
        folder_mismatch = self.t("backup.folder_mismatch")

        for backup_path in backup_paths:
            for controller, tree in controller_tree_pairs:
                if not controller.carpeta:
                    continue
                result: ActionResult = controller.restaurar_respaldo_metadatos(backup_path)
                if result.success:
                    restored = True
                    self._invalidate_controller(controller)
                    refreshed_pairs.add((id(controller), id(tree)))
                    break
                if result.message != folder_mismatch:
                    errors.extend(result.errors or [result.message])

        return BackupRestoreResult(
            restored=restored,
            errors=errors,
            refreshed_pairs=refreshed_pairs,
        )

    def create_current_snapshots_for_paths(
        self,
        backup_paths: list[Path],
        controller_tree_pairs: list[ControllerTreePair],
        metadata: dict[str, str],
    ) -> list[Path]:
        snapshots: list[Path] = []
        for backup_path in backup_paths:
            backup_folder = self._backup_folder(backup_path)
            if not backup_folder:
                continue
            for controller, _tree in controller_tree_pairs:
                if not controller.carpeta:
                    continue
                if os.path.normcase(backup_folder) != os.path.normcase(controller.carpeta):
                    continue
                try:
                    snapshots.append(controller.crear_respaldo_metadatos(metadata, controller.archivos.copy()))
                except Exception as exc:
                    self.logger.warning("Could not create undo snapshot: %s", exc)
                break
        return snapshots

    def _backup_folder(self, backup_path: Path) -> str:
        try:
            payload = read_backup_payload(backup_path)
            return str(payload.get("library_folder", "") or "")
        except Exception as exc:
            self.logger.warning("Could not inspect backup folder: %s", exc)
            return ""

    def _invalidate_controller(self, controller) -> None:
        if not self.song_info:
            return
        for filename in controller.archivos:
            self.song_info.invalidate(os.path.join(controller.carpeta, filename))
