from __future__ import annotations

import os
from pathlib import Path
from tkinter import messagebox, simpledialog

from ..controllers.backup_controller import BackupController
from ..controllers.cleanup_controller import CleanupController
from ..controllers.cleanup_preset_controller import CleanupPresetController
from ..models import SortMode
from ..services.audio_conversion_service import build_conversion_items, convert_audio_files
from ..utils.ui_formatting import metadata_label_key
from ..services.metadata_import_service import filter_import_items_for_library, load_metadata_import_items
from ..services.metadata_tools_service import (
    build_normalize_plan,
    build_search_replace_plan,
    tool_plan_groups,
    tool_plan_preview,
)
from ..services.playlist_export_service import export_library_report, export_library_view_json, export_playlist
from ..views.modals.backup_history_modal import show_backup_history_modal
from ..views.modals.change_preview_modal import confirm_change_preview
from ..views.modals.cleanup_preset_modal import show_cleanup_preset_modal
from ..views.modals.clear_metadata_modal import KEEP_FIELDS_KEY
from ..views.modals.audio_conversion_modal import request_audio_conversion_options
from ..views.modals.online_metadata_modal import request_online_metadata_selection
from ..views.modals.metadata_import_preview_modal import confirm_metadata_import
from ..views.modals.playlist_insert_preview_modal import request_playlist_insert_preview
from ..views.modals.rename_metadata_modal import confirm_rename_metadata
from ..views.modals.search_replace_metadata_modal import request_search_replace_metadata


class MetadataWorkflowMixin:
    """Metadata, cleanup, cover, backup, and rename UI workflows."""

    def _save_preview_metadata(self) -> None:
        controller = self._preview_controller
        filename = self._preview_filename
        current_song = self.preview.get_current_song()
        if controller is None or not filename or not current_song:
            messagebox.showwarning(self.t("dialog.selection"), self.t("preview.no_active_song"))
            return

        cover_path = current_song.get("cover_art")
        metadata = self.preview.get_edited_metadata()
        tree = self._tree_for_controller(controller)
        if not self._create_metadata_backup_for_groups([(controller, tree, [filename])], metadata):
            return
        apply_result = self._metadata_apply_controller().apply_single(
            controller=controller,
            tree=tree,
            filename=filename,
            metadata=metadata,
            cover_path=cover_path if isinstance(cover_path, str) and Path(cover_path).exists() else None,
            song_info=self.song_info,
        )
        if apply_result.success:
            self._record_undo_action("undo.metadata")
            self._load_song_preview(controller, filename)
            self._refresh_changed_library_pairs([(controller, tree, [filename])], apply_result.changed_pairs)
        self._handle_action_result(apply_result.result)

    def _select_preview_cover(self) -> None:
        if not self.preview.get_current_song():
            messagebox.showwarning(self.t("dialog.selection"), self.t("preview.no_active_song"))
            return
        cover_path = self.file_handler.seleccionar_imagen()
        if cover_path:
            self._apply_cover_to_targets(cover_path, targets=self._preview_cover_targets())

    def _handle_cover_drop(self, event) -> None:
        try:
            payload = self._drop_controller().payload_from_raw(event.data, splitlist=self.root.tk.splitlist)
            if not payload.image_files:
                messagebox.showwarning(self.t("dialog.cover_selected"), self.t("message.no_image_dropped"))
                return
            self._apply_cover_to_targets(payload.image_files[0], targets=self._preview_cover_targets())
        except Exception as exc:
            self.logger.error("Error handling cover drop: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.could_not_process_drop", error=exc))

    def _cover_targets(self) -> list[tuple[MetadataController, object, list[str]]]:
        return self._cover_controller().cover_targets(
            selections=self._selected_filenames_by_controller(),
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
            tree_for_controller=self._tree_for_controller,
        )

    def _preview_cover_targets(self) -> list[tuple[MetadataController, object, list[str]]]:
        controller = self._preview_controller
        filename = self._preview_filename
        if controller is None or not filename:
            return []
        tree = self._tree_for_controller(controller)
        if tree is None:
            return []
        return [(controller, tree, [filename])]

    def _apply_cover_to_targets(self, cover_path: str, targets=None, *, apply_entire_folder: bool = True) -> None:
        if not self.file_handler.validar_imagen(cover_path):
            return
        targets = targets if targets is not None else self._cover_targets()
        if not targets:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_cover_target"))
            return
        backup_targets = self._folder_cover_targets(targets) if apply_entire_folder else targets
        target_count = sum(len(filenames) for _controller, _tree, filenames in backup_targets)
        self.preview.update_cover_from_file(cover_path)
        backup_metadata = {"__cover__": os.path.basename(cover_path)}
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t("message.apply_cover_to_count", count=target_count, name=os.path.basename(cover_path)),
        ):
            return
        if not self._create_metadata_backup_for_groups(backup_targets, backup_metadata):
            return

        progress = self._begin_progress(
            title=self.t("progress.cover_title"),
            message=self.t("progress.cover_body"),
            total=target_count,
        )
        try:
            result = self._cover_controller().apply_manual_cover(
                targets=targets,
                cover_path=cover_path,
                song_info=self.song_info,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
                progress_callback=progress.update,
                apply_entire_folder=apply_entire_folder,
            )
        finally:
            progress.close()
        self._refresh_changed_library_pairs(targets, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            self._record_undo_action("undo.cover")
            message = self.t("message.cover_applied", count=result.success_count)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

    def _folder_cover_targets(self, targets):
        folder_targets = []
        seen_controllers: set[int] = set()
        for controller, tree, _filenames in targets:
            if id(controller) in seen_controllers:
                continue
            seen_controllers.add(id(controller))
            folder_targets.append((controller, tree, controller.archivos.copy()))
        return folder_targets

    def _apply_auto_cover_from_folder(self) -> None:
        targets = self._cover_targets()
        target_count = sum(len(filenames) for _controller, _tree, filenames in targets)
        if not targets:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_cover_target"))
            return
        self._apply_auto_cover_targets(targets)

    def _apply_auto_cover_targets(self, targets) -> None:
        cover_plan = self._cover_controller().build_auto_cover_plan(targets)
        if not cover_plan.groups:
            messagebox.showwarning(self.t("dialog.cover_selected"), self.t("auto_cover.not_found"))
            return

        message = self.t("auto_cover.confirm", count=cover_plan.planned_count, covers=len(cover_plan.groups))
        if cover_plan.missing:
            message += self.t("auto_cover.missing_count", count=len(cover_plan.missing))
        if not messagebox.askyesno(self.t("dialog.confirm"), message):
            return

        backup_groups = [
            (controller, tree, filenames)
            for controller, tree, filenames, _cover_path in cover_plan.groups
        ]
        if not self._create_metadata_backup_for_groups(backup_groups, {"__cover__": "auto"}):
            return

        progress = self._begin_progress(
            title=self.t("progress.cover_title"),
            message=self.t("progress.cover_body"),
            total=cover_plan.planned_count,
        )
        try:
            result = self._cover_controller().apply_cover_plan(
                cover_plan.groups,
                song_info=self.song_info,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
                progress_callback=progress.update,
            )
        finally:
            progress.close()
        if result.preview_cover_path:
            self.preview.update_cover_from_file(result.preview_cover_path)
        self._refresh_changed_library_pairs(backup_groups, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            self._record_undo_action("undo.cover")
            done = self.t("auto_cover.done", count=result.success_count)
            if result.errors:
                done += self.t("message.errors_count", count=len(result.errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), done)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

    def _refresh_changed_library_pairs(
        self,
        groups: list[tuple[MetadataController, object, list[str]]],
        changed_pairs: set[tuple[int, int]],
    ) -> None:
        refreshed: set[tuple[int, int]] = set()
        for controller, tree, _filenames in groups:
            key = (id(controller), id(tree))
            if key in changed_pairs and key not in refreshed:
                self._refresh_library_tree(controller, tree)
                refreshed.add(key)

    def _show_clear_metadata_modal(self) -> None:
        target = self._metadata_apply_controller().preview_target(
            controller=self._preview_controller,
            filename=self._preview_filename,
            current_song=self.preview.get_current_song(),
            tree_for_controller=self._tree_for_controller,
        )
        if not target:
            messagebox.showwarning(self.t("dialog.selection"), self.t("preview.no_active_song"))
            return

        clear_folder = messagebox.askyesnocancel(
            self.t("metadata_clear.scope_title"),
            self.t("metadata_clear.scope_prompt"),
        )
        if clear_folder is None:
            return

        metadata = self._metadata_dialog_controller().request_clear(self.root, target.current_song)
        if metadata is None:
            return
        keep_fields = self._extract_keep_fields(metadata)
        if clear_folder:
            self._apply_clear_metadata_to_folder(target, keep_fields)
            return
        self._apply_metadata_to_preview_target(target, metadata, done_key="metadata_clear.done")

    def _extract_keep_fields(self, metadata: dict[str, str]) -> set[str]:
        raw_value = str(metadata.pop(KEEP_FIELDS_KEY, "") or "")
        return {field for field in raw_value.split("|") if field}

    def _apply_clear_metadata_to_folder(self, target, keep_fields: set[str]) -> None:
        controller = target.controller
        tree = target.tree
        filenames = controller.archivos.copy()
        if not filenames:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return
        backup_metadata = {
            "metadata_clear": "folder",
            "keep_fields": ",".join(sorted(keep_fields)),
        }
        if not self._create_metadata_backup_for_groups([(controller, tree, filenames)], backup_metadata):
            return

        progress = self._begin_progress(
            title=self.t("progress.metadata_title"),
            message=self.t("progress.metadata_body"),
            total=len(filenames),
        )
        success_count = 0
        errors: list[str] = []
        try:
            for completed, filename in enumerate(filenames):
                if not progress.update(completed, len(filenames), filename):
                    errors.append("Operacion cancelada por el usuario.")
                    break
                cached = controller.get_track_info(filename)
                current_metadata = dict(cached.metadata) if cached else {}
                metadata = self._clear_metadata_payload(current_metadata, keep_fields)
                result = self._metadata_apply_controller().apply_single(
                    controller=controller,
                    tree=tree,
                    filename=filename,
                    metadata=metadata,
                    cover_path=None,
                    song_info=self.song_info,
                )
                if result.success:
                    success_count += 1
                else:
                    errors.extend(result.result.errors or [result.result.message])
                progress.update(completed + 1, len(filenames), filename)
        finally:
            progress.close()

        if success_count:
            self._record_undo_action("undo.metadata")
            self._refresh_library_tree(controller, tree)
            if self._preview_controller is controller and self._preview_filename:
                self._load_song_preview(controller, self._preview_filename)
            message = self.t("metadata_clear.done_count", count=success_count)
            if errors:
                message += self.t("message.errors_count", count=len(errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(errors) if errors else self.t("message.could_not_apply_metadata"),
        )

    def _clear_metadata_payload(self, current_metadata: dict[str, str], keep_fields: set[str]) -> dict[str, str]:
        fields = [field for field, _label_key in self._metadata_dialog_controller().fields]
        return {
            field: str(current_metadata.get(field, "") or "").strip() if field in keep_fields else ""
            for field in fields
        }

    def _show_edit_metadata_modal(self) -> None:
        target = self._metadata_apply_controller().preview_target(
            controller=self._preview_controller,
            filename=self._preview_filename,
            current_song=self.preview.get_current_song(),
            tree_for_controller=self._tree_for_controller,
        )
        if not target:
            messagebox.showwarning(self.t("dialog.selection"), self.t("preview.no_active_song"))
            return

        edit_folder = messagebox.askyesnocancel(
            self.t("metadata_edit.scope_title"),
            self.t("metadata_edit.scope_prompt"),
        )
        if edit_folder is None:
            return

        groups = (
            [(target.controller, target.tree, target.controller.archivos.copy())]
            if edit_folder
            else [(target.controller, target.tree, [target.filename])]
        )
        selected_count = self._metadata_apply_controller().selected_count(groups)
        if not selected_count:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return

        metadata = self._metadata_dialog_controller().request_edit(
            self.root,
            target.current_song,
            selected_count=selected_count,
            is_batch_edit=edit_folder,
        )
        if metadata is None:
            return

        if edit_folder:
            validation = target.controller.validar_datos(metadata)
            if not validation.success:
                messagebox.showwarning(self.t("dialog.metadata"), validation.message)
                return
            if not self._confirm_metadata_change_preview(groups, metadata):
                return

            if not self._create_metadata_backup_for_groups(groups, metadata):
                return

            progress = self._begin_progress(
                title=self.t("progress.metadata_title"),
                message=self.t("progress.metadata_body"),
                total=selected_count,
            )
            try:
                result = self._metadata_apply_controller().apply_groups(
                    groups=groups,
                    metadata=metadata,
                    song_info=self.song_info,
                    preview_controller=self._preview_controller,
                    preview_filename=self._preview_filename,
                    progress_callback=progress.update,
                )
            finally:
                progress.close()
            self._refresh_changed_library_pairs(groups, result.changed_pairs)

            if result.affected_preview and self._preview_controller and self._preview_filename:
                self._load_song_preview(self._preview_controller, self._preview_filename)

            if result.success_count:
                self._record_undo_action("undo.metadata")
                message = self.t("metadata_edit.done_count", count=result.success_count)
                if result.errors:
                    message += self.t("message.errors_count", count=len(result.errors))
                    self._show_toast(self.t("toast.partial"), kind="warning")
                else:
                    self._show_toast(self.t("toast.done"), kind="success")
                messagebox.showinfo(self.t("dialog.done"), message)
                return

            messagebox.showerror(
                self.t("dialog.error"),
                "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
            )
            return

        self._apply_metadata_to_preview_target(target, metadata, done_key="metadata_edit.done")

    def _apply_metadata_to_preview_target(self, target, metadata: dict[str, str], *, done_key: str) -> None:
        groups = [(target.controller, target.tree, [target.filename])]
        if not self._create_metadata_backup_for_groups(groups, metadata):
            return
        apply_result = self._metadata_apply_controller().apply_single(
            controller=target.controller,
            tree=target.tree,
            filename=target.filename,
            metadata=metadata,
            cover_path=None,
            song_info=self.song_info,
        )
        if apply_result.success:
            self._record_undo_action("undo.metadata")
            self._load_song_preview(target.controller, target.filename)
            self._refresh_changed_library_pairs(groups, apply_result.changed_pairs)
            messagebox.showinfo(self.t("dialog.done"), self.t(done_key))
        else:
            detail = "\n".join(apply_result.result.errors) if apply_result.result.errors else apply_result.result.message
            messagebox.showerror(self.t("dialog.error"), detail)

    def _selected_filenames_by_controller(self) -> list[tuple[MetadataController, object, list[str]]]:
        return self._selection_controller().selected_filenames_by_controller(
            [
                (self.controller_principal, self.tree_principal),
                (self.controller_nueva, self.tree_nueva),
            ]
        )

    def _convert_selected_audio(self) -> None:
        selections = self._selected_filenames_by_controller()
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("audio_conversion.no_selection"))
            return
        sources: list[str] = []
        for controller, _tree, filenames in selections:
            sources.extend(str(Path(controller.carpeta) / filename) for filename in filenames)
        options = request_audio_conversion_options(self.root, self.t, len(sources))
        if not options:
            return
        try:
            items = build_conversion_items(
                sources,
                str(options["destination"]),
                str(options["format"]),
            )
        except Exception as exc:
            messagebox.showerror(self.t("dialog.error"), self.t("audio_conversion.failed", error=exc))
            return

        progress = self._begin_progress(
            title=self.t("audio_conversion.title"),
            message=self.t("audio_conversion.progress"),
            total=len(items),
        )
        try:
            result = convert_audio_files(
                items,
                overwrite=bool(options.get("overwrite")),
                progress_callback=progress.update,
            )
        except RuntimeError:
            messagebox.showerror(self.t("dialog.error"), self.t("audio_conversion.ffmpeg_missing"))
            return
        except Exception as exc:
            messagebox.showerror(self.t("dialog.error"), self.t("audio_conversion.failed", error=exc))
            return
        finally:
            progress.close()

        self._refresh_libraries_after_conversion(str(options["destination"]))
        if result.errors:
            self._show_toast(self.t("toast.partial"), kind="warning")
            detail = self.t("audio_conversion.done_with_errors", count=result.converted, errors=len(result.errors))
            detail += "\n\n" + "\n".join(result.errors[:5])
            if len(result.errors) > 5:
                detail += self.t("message.more_errors", count=len(result.errors) - 5)
            messagebox.showwarning(self.t("audio_conversion.title"), detail)
            return
        self._show_toast(self.t("audio_conversion.done", count=result.converted), kind="success")
        messagebox.showinfo(self.t("dialog.done"), self.t("audio_conversion.done", count=result.converted))

    def _refresh_libraries_after_conversion(self, destination: str) -> None:
        destination_path = Path(destination).resolve()
        for controller, tree in (
            (self.controller_principal, self.tree_principal),
            (self.controller_nueva, self.tree_nueva),
        ):
            if controller.carpeta and Path(controller.carpeta).resolve() == destination_path:
                controller.refresh_library()
                self._refresh_library_tree(controller, tree)

    def _create_metadata_backup_for_groups(
        self,
        groups: list[tuple[MetadataController, object, list[str]]],
        metadata: dict[str, str],
    ) -> Optional[Path]:
        try:
            return self._backup_controller().create_metadata_backups(groups, metadata)
        except Exception as exc:
            self.logger.error("Could not create metadata backup: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.backup_failed", error=exc))
            return None

    def _record_undo_action(self, label_key: str) -> None:
        backup_controller = self._backup_controller()
        if backup_controller.has_recent_backup():
            self.undo_controller.record(self.t(label_key), backup_controller.last_backup_paths)

    def _record_undo_paths(self, label_key: str, backup_paths: list[Path]) -> None:
        self.undo_controller.record(self.t(label_key), backup_paths)

    def _backup_controller(self) -> BackupController:
        if not hasattr(self, "backup_controller"):
            self.backup_controller = BackupController(self.t, getattr(self, "song_info", None))
        return self.backup_controller

    def _confirm_metadata_change_preview(
        self,
        groups: list[tuple[MetadataController, object, list[str]]],
        metadata: dict[str, str],
        *,
        parent=None,
    ) -> bool:
        changes = self._backup_controller().metadata_changes(
            groups,
            metadata,
            lambda field: self.t(self._metadata_label_key(field)).rstrip(":"),
        )

        if not changes:
            messagebox.showinfo(self.t("dialog.done"), self.t("change_preview.no_changes"), parent=parent)
            return False

        return confirm_change_preview(parent or self.root, self.t, changes)

    def _list_metadata_backups(self) -> list[dict[str, object]]:
        return self._backup_controller().list_metadata_backups()

    def _metadata_label_key(self, key: str) -> str:
        return metadata_label_key(key)

    def _show_backup_history(self) -> None:
        backups = self._list_metadata_backups()
        if not backups:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("backup.history_empty"))
            return

        show_backup_history_modal(
            self.root,
            self.t,
            backups,
            lambda path, parent: self._restore_backup_paths([path], parent=parent),
        )

    def _restore_backup_paths(self, backup_paths: list[Path], parent=None) -> bool:
        pairs = self._controller_tree_pairs()
        result = self._backup_controller().restore_paths(backup_paths, pairs)

        for controller, tree in pairs:
            if (id(controller), id(tree)) in result.refreshed_pairs:
                self._refresh_library_tree(controller, tree)

        if self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.restored:
            messagebox.showinfo(self.t("dialog.done"), self.t("backup.restored_from_last"), parent=parent)
            return True

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("backup.restore_failed"),
            parent=parent,
        )
        return False

    def _controller_tree_pairs(self):
        return [
            (self.controller_principal, self.tree_principal),
            (self.controller_nueva, self.tree_nueva),
        ]

    def _undo_last_metadata_change(self) -> None:
        self._undo_last_action()

    def _undo_last_action(self) -> None:
        action = self.undo_controller.pop_undo()
        if action is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("undo.empty"))
            return
        if not messagebox.askyesno(self.t("dialog.confirm"), self.t("undo.confirm", action=action.label)):
            self.undo_controller.push_undo(action)
            return
        snapshots = self._backup_controller().create_current_snapshots_for_paths(
            list(action.backup_paths),
            self._controller_tree_pairs(),
            {"undo_snapshot": action.label},
        )
        if self._restore_backup_paths(list(action.backup_paths)):
            if snapshots:
                self.undo_controller.push_redo(type(action)(label=action.label, backup_paths=tuple(snapshots)))
            self._show_toast(self.t("undo.done", action=action.label), kind="info")
        else:
            self.undo_controller.push_undo(action)

    def _redo_last_action(self) -> None:
        action = self.undo_controller.pop_redo()
        if action is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("redo.empty"))
            return
        if not messagebox.askyesno(self.t("dialog.confirm"), self.t("redo.confirm", action=action.label)):
            self.undo_controller.push_redo(action)
            return
        snapshots = self._backup_controller().create_current_snapshots_for_paths(
            list(action.backup_paths),
            self._controller_tree_pairs(),
            {"redo_snapshot": action.label},
        )
        if self._restore_backup_paths(list(action.backup_paths)):
            if snapshots:
                self.undo_controller.push_undo(type(action)(label=action.label, backup_paths=tuple(snapshots)))
            self._show_toast(self.t("redo.done", action=action.label), kind="info")
        else:
            self.undo_controller.push_redo(action)


    def _cleanup_action_options(self) -> list[tuple[str, str]]:
        return self._cleanup_controller().action_options()

    def _cleanup_controller(self) -> CleanupController:
        if not hasattr(self, "cleanup_controller"):
            self.cleanup_controller = CleanupController(getattr(self, "song_info", None))
        return self.cleanup_controller

    def _cleanup_preset_controller(self) -> CleanupPresetController:
        if not hasattr(self, "cleanup_preset_controller"):
            self.cleanup_preset_controller = CleanupPresetController()
        return self.cleanup_preset_controller

    def _normalize_cleanup_presets(self, raw_presets) -> list[dict[str, object]]:
        return self._cleanup_controller().normalize_presets(raw_presets)

    def _refresh_cleanup_preset_menu(self) -> None:
        if not hasattr(self, "cleanup_preset_menu"):
            return
        self._cleanup_preset_controller().refresh_menu(
            self.cleanup_presets,
            self.cleanup_preset_menu,
            self.cleanup_preset_var,
        )

    def _selected_cleanup_preset(self) -> Optional[dict[str, object]]:
        selected_name = self.cleanup_preset_var.get().strip() if hasattr(self, "cleanup_preset_var") else ""
        return self._cleanup_preset_controller().selected_preset(self.cleanup_presets, selected_name)

    def _show_create_cleanup_preset_modal(self) -> None:
        result = show_cleanup_preset_modal(self.root, self.t, self._cleanup_action_options())
        if not result:
            return
        name = str(result.get("name", "")).strip()
        actions = [str(action) for action in result.get("actions", [])]
        if not name or not actions:
            return
        existing = self._cleanup_preset_controller().preset_index_by_name(self.cleanup_presets, name)
        replace_existing = False
        if existing is not None:
            replace_existing = messagebox.askyesno(
                self.t("dialog.confirm"),
                self.t("presets.replace_confirm", name=name),
            )
        if existing is not None and not replace_existing:
            return
        upsert = self._cleanup_preset_controller().upsert_preset(
            self.cleanup_presets,
            name=name,
            actions=actions,
            replace_existing=replace_existing,
        )
        self.cleanup_presets = upsert.presets
        self.cleanup_preset_var.set(name)
        self._refresh_cleanup_preset_menu()
        self._save_config()

    def _delete_selected_cleanup_preset(self) -> None:
        preset = self._selected_cleanup_preset()
        if not preset:
            messagebox.showwarning(self.t("dialog.selection"), self.t("presets.none_selected"))
            return
        name = str(preset.get("name", ""))
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t("presets.delete_confirm", name=name),
        ):
            return
        self.cleanup_presets = self._cleanup_preset_controller().delete_preset(self.cleanup_presets, name)
        self._refresh_cleanup_preset_menu()
        self._save_config()

    def _apply_selected_cleanup_preset(self) -> None:
        preset = self._selected_cleanup_preset()
        if not preset:
            messagebox.showwarning(self.t("dialog.selection"), self.t("presets.none_selected"))
            return
        actions = [str(action) for action in preset.get("actions", [])]
        self._apply_quick_cleanup_actions(actions, preset_name=str(preset.get("name", "")))

    def _show_batch_edit_modal(self) -> None:
        selections = self._selected_filenames_by_controller()
        selected_count = self._metadata_apply_controller().selected_count(selections)
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return

        metadata = self._metadata_dialog_controller().request_batch(self.root, selected_count=selected_count)
        if not metadata:
            return

        validation = selections[0][0].validar_datos(metadata)
        if not validation.success:
            messagebox.showwarning(self.t("dialog.metadata"), validation.message)
            return

        if not self._confirm_metadata_change_preview(selections, metadata):
            return

        if not self._create_metadata_backup_for_groups(selections, metadata):
            return

        progress = self._begin_progress(
            title=self.t("progress.metadata_title"),
            message=self.t("progress.metadata_body"),
            total=selected_count,
        )
        try:
            result = self._metadata_apply_controller().apply_groups(
                groups=selections,
                metadata=metadata,
                song_info=self.song_info,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
                progress_callback=progress.update,
            )
        finally:
            progress.close()
        self._refresh_changed_library_pairs(selections, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            self._record_undo_action("undo.metadata")
            message = self.t("batch_edit.done", count=result.success_count)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

    def _search_online_metadata(self) -> None:
        target = self._metadata_apply_controller().preview_target(
            controller=self._preview_controller,
            filename=self._preview_filename,
            current_song=self.preview.get_current_song(),
            tree_for_controller=self._tree_for_controller,
        )
        if not target:
            messagebox.showwarning(self.t("dialog.selection"), self.t("preview.no_active_song"))
            return

        search_metadata = dict(target.current_song)
        try:
            self.root.configure(cursor="watch")
            self.root.update_idletasks()
            results = self.online_metadata.search(search_metadata)
        except Exception as exc:
            self.logger.error("Online metadata search failed: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("online_metadata.search_failed", error=exc))
            return
        finally:
            self.root.configure(cursor="")

        if not results:
            messagebox.showinfo(self.t("online_metadata.title"), self.t("online_metadata.no_results"))
            return

        metadata = request_online_metadata_selection(self.root, self.t, results)
        if not metadata:
            return
        if not self._confirm_metadata_change_preview([(target.controller, target.tree, [target.filename])], metadata):
            return
        self._apply_metadata_to_preview_target(target, metadata, done_key="metadata_edit.done")

    def _metadata_tool_targets(self) -> list[tuple[MetadataController, object, list[str]]]:
        selections = self._selected_filenames_by_controller()
        if selections:
            return selections
        target = self._active_playlist_target()
        if target is None:
            return []
        controller, tree = target
        return [(controller, tree, controller.archivos.copy())] if controller.archivos else []

    def _complete_metadata_online(self) -> None:
        targets = self._metadata_tool_targets()
        if not targets:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return
        plan: list[tuple[MetadataController, object, str, dict[str, str]]] = []
        total = sum(len(filenames) for _controller, _tree, filenames in targets)
        progress = self._begin_progress(
            title=self.t("metadata_tools.online_title"),
            message=self.t("metadata_tools.online_body"),
            total=total,
        )
        try:
            completed = 0
            for controller, tree, filenames in targets:
                for filename in filenames:
                    if not progress.update(completed, total, filename):
                        break
                    cached = controller.get_track_info(filename)
                    current = dict(cached.metadata) if cached else {}
                    try:
                        results = self.online_metadata.search(current, limit=1)
                    except Exception as exc:
                        self.logger.warning("Online metadata failed for %s: %s", filename, exc)
                        results = []
                    completed += 1
                    progress.update(completed, total, filename)
                    if not results:
                        continue
                    updates = {
                        key: value
                        for key, value in results[0].metadata().items()
                        if value and str(current.get(key, "") or "").strip() != str(value).strip()
                    }
                    if updates:
                        plan.append((controller, tree, filename, updates))
        finally:
            progress.close()

        self._apply_metadata_tool_plan(
            plan,
            backup_metadata={"metadata_tool": "online"},
            done_message_key="metadata_tools.online_done",
            undo_key="undo.metadata",
        )

    def _find_missing_covers(self) -> None:
        targets = self._metadata_tool_targets()
        missing_targets: list[tuple[MetadataController, object, list[str]]] = []
        for controller, tree, filenames in targets:
            duplicate_set = controller.duplicate_filenames()
            missing = [
                filename
                for filename in filenames
                if "missing_cover" in controller.issue_keys_for_file(filename, duplicate_set)
            ]
            if missing:
                missing_targets.append((controller, tree, missing))
        if not missing_targets:
            messagebox.showinfo(self.t("dialog.done"), self.t("metadata_tools.no_missing_covers"))
            return
        self._apply_auto_cover_targets(missing_targets)

    def _normalize_metadata_tool(self) -> None:
        targets = self._metadata_tool_targets()
        if not targets:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return
        plan_items = build_normalize_plan(targets)
        plan = [(item.controller, item.tree, item.filename, item.updates) for item in plan_items]
        self._apply_metadata_tool_plan(
            plan,
            backup_metadata={"metadata_tool": "normalize"},
            done_message_key="metadata_tools.normalize_done",
            undo_key="undo.cleanup",
            preview_changes=tool_plan_preview(
                plan_items,
                lambda field: self.t(self._metadata_label_key(field)).rstrip(":"),
            ),
            groups=tool_plan_groups(plan_items),
        )

    def _search_replace_metadata_tool(self) -> None:
        targets = self._metadata_tool_targets()
        if not targets:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return
        options = request_search_replace_metadata(self.root, self.t)
        if not options:
            return
        plan_items = build_search_replace_plan(
            targets,
            field=str(options["field"]),
            search_text=str(options["search_text"]),
            replacement=str(options["replacement"]),
            case_sensitive=bool(options["case_sensitive"]),
        )
        plan = [(item.controller, item.tree, item.filename, item.updates) for item in plan_items]
        self._apply_metadata_tool_plan(
            plan,
            backup_metadata={
                "metadata_tool": "search_replace",
                "field": str(options["field"]),
                "search": str(options["search_text"]),
            },
            done_message_key="metadata_tools.search_replace_done",
            undo_key="undo.cleanup",
            preview_changes=tool_plan_preview(
                plan_items,
                lambda field: self.t(self._metadata_label_key(field)).rstrip(":"),
            ),
            groups=tool_plan_groups(plan_items),
        )

    def _apply_metadata_tool_plan(
        self,
        plan: list[tuple[MetadataController, object, str, dict[str, str]]],
        *,
        backup_metadata: dict[str, str],
        done_message_key: str,
        undo_key: str,
        preview_changes: list[tuple[str, str, str, str]] | None = None,
        groups: list[tuple[MetadataController, object, list[str]]] | None = None,
    ) -> None:
        if not plan:
            messagebox.showinfo(self.t("dialog.done"), self.t("change_preview.no_changes"))
            return
        if preview_changes is None:
            preview_changes = []
            for controller, _tree, filename, updates in plan:
                cached = controller.get_track_info(filename)
                current = dict(cached.metadata) if cached else {}
                for field, value in updates.items():
                    preview_changes.append(
                        (
                            filename,
                            self.t(self._metadata_label_key(field)).rstrip(":"),
                            str(current.get(field, "") or "").strip() or "-",
                            str(value or "").strip() or "-",
                        )
                    )
        if not confirm_change_preview(self.root, self.t, preview_changes):
            return
        groups = groups or self._groups_from_metadata_tool_plan(plan)
        if not self._create_metadata_backup_for_groups(groups, backup_metadata):
            return
        success_count = 0
        errors: list[str] = []
        changed_pairs: set[tuple[int, int]] = set()
        progress = self._begin_progress(
            title=self.t("progress.metadata_title"),
            message=self.t("progress.metadata_body"),
            total=len(plan),
        )
        try:
            for completed, (controller, tree, filename, updates) in enumerate(plan):
                if not progress.update(completed, len(plan), filename):
                    errors.append(self.t("message.operation_cancelled"))
                    break
                result = controller.aplicar_cambios_a_archivo(filename, updates)
                if result.success:
                    success_count += 1
                    changed_pairs.add((id(controller), id(tree)))
                    if controller.carpeta:
                        self.song_info.invalidate(os.path.join(controller.carpeta, filename))
                else:
                    errors.extend(result.errors or [result.message])
                progress.update(completed + 1, len(plan), filename)
        finally:
            progress.close()
        self._refresh_changed_library_pairs(groups, changed_pairs)
        if self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)
        if success_count:
            self._record_undo_action(undo_key)
            message = self.t(done_message_key, count=success_count)
            if errors:
                message += self.t("message.errors_count", count=len(errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return
        messagebox.showerror(self.t("dialog.error"), "\n".join(errors) if errors else self.t("message.could_not_apply_metadata"))

    def _groups_from_metadata_tool_plan(
        self,
        plan: list[tuple[MetadataController, object, str, dict[str, str]]],
    ) -> list[tuple[MetadataController, object, list[str]]]:
        grouped: dict[tuple[int, int], tuple[MetadataController, object, list[str]]] = {}
        for controller, tree, filename, _updates in plan:
            key = (id(controller), id(tree))
            if key not in grouped:
                grouped[key] = (controller, tree, [])
            grouped[key][2].append(filename)
        return list(grouped.values())

    def _apply_quick_cleanup(self, action: str) -> None:
        self._apply_quick_cleanup_actions([action])

    def _apply_quick_cleanup_actions(self, actions: list[str], preset_name: str = "") -> None:
        selections = self._selected_filenames_by_controller()
        selected_count = self._cleanup_controller().selected_count(selections)
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return

        action_label = self._cleanup_controller().action_label(actions, preset_name, self.t)
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t(
                "quick_actions.confirm",
                action=action_label,
                count=selected_count,
            ),
        ):
            return

        plan = self._cleanup_controller().build_plan(selections, actions)
        if not plan:
            messagebox.showinfo(self.t("dialog.done"), self.t("change_preview.no_changes"))
            return
        if not self._confirm_cleanup_plan_preview(plan):
            return
        if not self._create_metadata_backup_for_groups(
            selections,
            self._cleanup_controller().backup_metadata(actions, action_label, preset_name),
        ):
            return

        progress = self._begin_progress(
            title=self.t("progress.cleanup_title"),
            message=self.t("progress.cleanup_body"),
            total=len(plan),
        )
        try:
            result = self._cleanup_controller().execute_plan(
                plan,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
                progress_callback=progress.update,
            )
        finally:
            progress.close()
        self._refresh_changed_library_pairs(result.changed_groups, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            self._record_undo_action("undo.cleanup")
            message = self.t("quick_actions.done", count=result.success_count)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

    def _confirm_cleanup_plan_preview(
        self,
        plan: list[tuple[MetadataController, object, str, dict[str, str]]],
    ) -> bool:
        changes = self._cleanup_controller().preview_changes(
            plan,
            lambda field: self.t(self._metadata_label_key(field)).rstrip(":"),
        )
        return confirm_change_preview(self.root, self.t, changes)

    def _number_tracks_for_active_library(self) -> None:
        controller = self._preview_controller or (
            self.controller_principal if self.controller_principal.archivos else self.controller_nueva
        )
        tree = self._tree_for_controller(controller)
        if tree is None or not controller.archivos:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return
        if not self._can_reorder_current_view(controller, tree):
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.reorder_needs_full_view"))
            return
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t("quick_actions.confirm_number_tracks", count=len(controller.archivos)),
        ):
            return
        if not self._create_metadata_backup_for_groups(
            [(controller, tree, controller.archivos.copy())],
            {"track_number": "order"},
        ):
            return
        result = controller.apply_track_numbers_from_order()
        if result.success:
            for filename in controller.archivos:
                self.song_info.invalidate(os.path.join(controller.carpeta, filename))
            self._refresh_library_tree(controller, tree)
            if self._preview_controller is controller and self._preview_filename:
                self._load_song_preview(controller, self._preview_filename)
        self._handle_action_result(result)

    def _insert_selected_at_position(self) -> None:
        selections = self._selected_filenames_by_controller()
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return
        if len(selections) > 1:
            messagebox.showwarning(self.t("dialog.selection"), self.t("playlist_insert.one_library"))
            return

        controller, tree, filenames = selections[0]
        if not controller.archivos:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return
        if not self._can_reorder_current_view(controller, tree):
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.reorder_needs_full_view"))
            return

        position = simpledialog.askinteger(
            self.t("playlist_insert.title"),
            self.t("playlist_insert.prompt", count=len(filenames), total=len(controller.archivos)),
            parent=self.root,
            minvalue=1,
            maxvalue=len(controller.archivos),
        )
        if position is None:
            return

        plan = self._playlist_workflow_controller().build_insert_plan(
            controller=controller,
            tree=tree,
            filenames=filenames,
            position=position,
        )
        if not plan.items:
            messagebox.showinfo(self.t("dialog.done"), self.t("change_preview.no_changes"))
            return
        confirmed_plan = request_playlist_insert_preview(
            self.root,
            self.t,
            plan,
            lambda final_order: self._playlist_workflow_controller().build_plan_from_order(
                controller=controller,
                tree=tree,
                final_order=final_order,
            ),
        )
        if confirmed_plan is None:
            return
        plan = confirmed_plan

        progress = self._begin_progress(
            title=self.t("progress.playlist_title"),
            message=self.t("progress.playlist_body"),
            total=len(plan.items) * 2,
        )
        try:
            result = self._playlist_workflow_controller().execute_plan(
                plan,
                song_info=self.song_info,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
                progress_callback=progress.update,
            )
        finally:
            progress.close()
        self._preview_filename = result.preview_filename
        self._refresh_changed_library_pairs([(controller, tree, plan.final_order)], result.changed_pairs)
        self._set_sort_widget_for_controller(controller, SortMode.MANUAL)

        if self._preview_controller is controller and self._preview_filename:
            self._select_filename_in_tree(tree, self._preview_filename)
            self._load_song_preview(controller, self._preview_filename)

        if result.success:
            if result.backup_path:
                self._record_undo_paths("undo.playlist", [result.backup_path])
            message = self.t(
                "playlist_insert.done",
                tracks=result.track_numbers_updated,
                renamed=result.renamed,
            )
            if result.backup_path:
                message += f"\n{self.t('message.backup_created', path=result.backup_path)}"
            self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

    def _prepare_active_playlist(self) -> None:
        target = self._active_playlist_target()
        if target is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return

        controller, tree = target
        if not self._can_reorder_current_view(controller, tree):
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.reorder_needs_full_view"))
            return

        plan = self._playlist_workflow_controller().build_plan_from_order(
            controller=controller,
            tree=tree,
            final_order=controller.archivos.copy(),
        )
        if not plan.items:
            messagebox.showinfo(self.t("dialog.done"), self.t("change_preview.no_changes"))
            return
        confirmed_plan = request_playlist_insert_preview(
            self.root,
            self.t,
            plan,
            lambda final_order: self._playlist_workflow_controller().build_plan_from_order(
                controller=controller,
                tree=tree,
                final_order=final_order,
            ),
        )
        if confirmed_plan is None:
            return
        plan = confirmed_plan

        progress = self._begin_progress(
            title=self.t("progress.playlist_title"),
            message=self.t("progress.playlist_body"),
            total=len(plan.items) * 2,
        )
        try:
            result = self._playlist_workflow_controller().execute_plan(
                plan,
                song_info=self.song_info,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
                progress_callback=progress.update,
            )
        finally:
            progress.close()
        self._preview_filename = result.preview_filename
        self._refresh_changed_library_pairs([(controller, tree, plan.final_order)], result.changed_pairs)
        self._set_sort_widget_for_controller(controller, SortMode.MANUAL)

        if self._preview_controller is controller and self._preview_filename:
            self._select_filename_in_tree(tree, self._preview_filename)
            self._load_song_preview(controller, self._preview_filename)

        if result.success:
            if result.backup_path:
                self._record_undo_paths("undo.playlist", [result.backup_path])
            message = self.t(
                "playlist_prepare.done",
                tracks=result.track_numbers_updated,
                renamed=result.renamed,
            )
            if result.backup_path:
                message += f"\n{self.t('message.backup_created', path=result.backup_path)}"
            self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

    def _active_playlist_target(self):
        selections = self._selected_filenames_by_controller()
        if len(selections) > 1:
            messagebox.showwarning(self.t("dialog.selection"), self.t("playlist_insert.one_library"))
            return None
        if selections:
            controller, tree, _filenames = selections[0]
            return controller, tree
        if self._preview_controller is not None and self._preview_controller.archivos:
            tree = self._tree_for_controller(self._preview_controller)
            if tree is not None:
                return self._preview_controller, tree
        if self.controller_nueva.archivos:
            return self.controller_nueva, self.tree_nueva
        if self.controller_principal.archivos:
            return self.controller_principal, self.tree_principal
        return None

    def _active_library_view_target(self):
        selections = self._selected_filenames_by_controller()
        if len(selections) > 1:
            messagebox.showwarning(self.t("dialog.selection"), self.t("playlist_insert.one_library"))
            return None
        if selections:
            controller, tree, _filenames = selections[0]
            return controller, tree

        filtered_panels = []
        for panel in getattr(self, "_library_panels", []):
            controller = panel.get("controller")
            tree = panel.get("tree")
            if not controller or not getattr(controller, "archivos", None):
                continue
            query = self._panel_search_query(panel)
            filter_mode = panel.get("filter_mode")
            if query or getattr(filter_mode, "name", "ALL") != "ALL":
                if self._visible_filenames(tree):
                    filtered_panels.append((controller, tree))
        if len(filtered_panels) == 1:
            return filtered_panels[0]

        if self._preview_controller is not None and self._preview_controller.archivos:
            tree = self._tree_for_controller(self._preview_controller)
            if tree is not None:
                return self._preview_controller, tree
        if self.controller_nueva.archivos:
            return self.controller_nueva, self.tree_nueva
        if self.controller_principal.archivos:
            return self.controller_principal, self.tree_principal
        return None

    def _export_active_playlist(self) -> None:
        target = self._active_playlist_target()
        if target is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("playlist_export.no_library"))
            return
        controller, _tree = target
        filenames = controller.archivos.copy()
        if not controller.carpeta or not filenames:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("playlist_export.no_files"))
            return
        initial_name = f"{Path(controller.carpeta).name or 'playlist'}.m3u8"
        output_path = self.file_handler.seleccionar_destino_playlist(initial_name=initial_name)
        if not output_path:
            return
        metadata_by_filename = {}
        for filename in filenames:
            cached = controller.get_track_info(filename)
            metadata = dict(cached.metadata) if cached else {}
            if cached:
                metadata["duration"] = str(cached.duration or 0)
            metadata_by_filename[filename] = metadata
        try:
            if Path(output_path).suffix.lower() == ".json":
                path = export_library_view_json(
                    folder=controller.carpeta,
                    output_path=output_path,
                    filenames=filenames,
                    metadata_by_filename=metadata_by_filename,
                    audio_quality_by_filename=_quality_by_filename,
                    duration_by_filename=duration_by_filename,
                    library_position_by_filename={
                        filename: index
                        for index, filename in enumerate(controller.archivos, start=1)
                    },
                    filter_info={"label": self.t("dialog.selection"), "mode": "SELECTION", "search": ""},
                )
            else:
                path = export_playlist(
                    folder=controller.carpeta,
                    filenames=filenames,
                    output_path=output_path,
                    metadata_by_filename=metadata_by_filename,
                )
        except Exception as exc:
            self.logger.error("Could not export playlist: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("playlist_export.failed", error=exc))
            return
        self._show_toast(self.t("playlist_export.done", path=path), kind="success")
        messagebox.showinfo(self.t("dialog.done"), self.t("playlist_export.done", path=path))

    def _export_current_library_view_json(self) -> None:
        target = self._active_library_view_target()
        if target is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("library_view_export.no_library"))
            return
        controller, tree = target
        filenames = self._visible_filenames(tree)
        if not controller.carpeta or not filenames:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("library_view_export.no_files"))
            return

        folder_name = Path(controller.carpeta).name or "library"
        output_path = self.file_handler.seleccionar_destino_library_view_json(
            initial_name=f"{folder_name}_vista_actual.json",
        )
        if not output_path:
            return

        metadata_by_filename: dict[str, dict[str, str]] = {}
        audio_quality_by_filename: dict[str, dict[str, object]] = {}
        duration_by_filename: dict[str, float] = {}
        for filename in filenames:
            cached = controller.get_track_info(filename)
            metadata_by_filename[filename] = dict(cached.metadata) if cached else {}
            audio_quality_by_filename[filename] = dict(cached.audio_quality) if cached else {}
            duration_by_filename[filename] = float(cached.duration or 0.0) if cached else 0.0

        panel = self._get_library_panel(controller, tree)
        filter_info = {
            "label": str(panel["filter_var"].get()) if panel else self.t("filter.all"),
            "mode": getattr(panel.get("filter_mode"), "name", "ALL") if panel else "ALL",
            "search": self._panel_search_query(panel) if panel else "",
        }
        library_position_by_filename = {
            filename: index
            for index, filename in enumerate(controller.archivos, start=1)
        }

        try:
            path = export_library_view_json(
                folder=controller.carpeta,
                output_path=output_path,
                filenames=filenames,
                metadata_by_filename=metadata_by_filename,
                audio_quality_by_filename=audio_quality_by_filename,
                duration_by_filename=duration_by_filename,
                library_position_by_filename=library_position_by_filename,
                filter_info=filter_info,
            )
        except Exception as exc:
            self.logger.error("Could not export current library view: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("library_view_export.failed", error=exc))
            return
        self._show_toast(self.t("library_view_export.done", path=path), kind="success")
        messagebox.showinfo(self.t("dialog.done"), self.t("library_view_export.done", path=path))

    def _export_selected_tracks(self) -> None:
        selections = self._selected_filenames_by_controller()
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("selected_export.no_selection"))
            return
        if len(selections) > 1:
            messagebox.showwarning(self.t("dialog.selection"), self.t("playlist_insert.one_library"))
            return
        controller, _tree, filenames = selections[0]
        if not controller.carpeta or not filenames:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("selected_export.no_selection"))
            return

        folder_name = Path(controller.carpeta).name or "library"
        output_path = self.file_handler.seleccionar_destino_playlist(
            initial_name=f"{folder_name}_seleccion.m3u8",
        )
        if not output_path:
            return

        metadata_by_filename, _quality_by_filename, duration_by_filename = self._export_metadata_maps(controller, filenames)
        for filename, duration in duration_by_filename.items():
            metadata_by_filename.setdefault(filename, {})["duration"] = str(duration)

        try:
            path = export_playlist(
                folder=controller.carpeta,
                filenames=filenames,
                output_path=output_path,
                metadata_by_filename=metadata_by_filename,
            )
        except Exception as exc:
            self.logger.error("Could not export selected tracks: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("selected_export.failed", error=exc))
            return
        self._show_toast(self.t("selected_export.done", path=path), kind="success")
        messagebox.showinfo(self.t("dialog.done"), self.t("selected_export.done", path=path))

    def _export_library_report(self) -> None:
        target = self._active_playlist_target()
        if target is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("library_report_export.no_library"))
            return
        controller, _tree = target
        filenames = controller.archivos.copy()
        if not controller.carpeta or not filenames:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("library_report_export.no_files"))
            return

        folder_name = Path(controller.carpeta).name or "library"
        output_path = self.file_handler.seleccionar_destino_library_report(
            initial_name=f"{folder_name}_reporte.json",
        )
        if not output_path:
            return

        metadata_by_filename, audio_quality_by_filename, duration_by_filename = self._export_metadata_maps(controller, filenames)
        library_position_by_filename = {filename: index for index, filename in enumerate(controller.archivos, start=1)}
        duplicate_set = controller.duplicate_filenames()
        issues_by_filename = {
            filename: controller.issue_keys_for_file(filename, duplicate_set)
            for filename in filenames
        }

        try:
            path = export_library_report(
                folder=controller.carpeta,
                output_path=output_path,
                filenames=filenames,
                metadata_by_filename=metadata_by_filename,
                audio_quality_by_filename=audio_quality_by_filename,
                duration_by_filename=duration_by_filename,
                library_position_by_filename=library_position_by_filename,
                issues_by_filename=issues_by_filename,
                summary=controller.get_quality_report(),
            )
        except Exception as exc:
            self.logger.error("Could not export library report: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("library_report_export.failed", error=exc))
            return
        self._show_toast(self.t("library_report_export.done", path=path), kind="success")
        messagebox.showinfo(self.t("dialog.done"), self.t("library_report_export.done", path=path))

    def _import_metadata_from_json(self) -> None:
        target = self._active_playlist_target()
        if target is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("metadata_import.no_library"))
            return
        controller, tree = target
        if not controller.carpeta or not controller.archivos:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("metadata_import.no_library"))
            return

        filepath = self.file_handler.seleccionar_metadata_json()
        if not filepath:
            return

        try:
            import_items = filter_import_items_for_library(
                load_metadata_import_items(filepath),
                controller.archivos,
            )
        except Exception as exc:
            self.logger.error("Could not read metadata import file: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("metadata_import.failed", error=exc))
            return

        if not import_items:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("metadata_import.no_matches"))
            return

        current_metadata = {
            filename: dict(controller.get_track_info(filename).metadata)
            for filename in controller.archivos
            if controller.get_track_info(filename)
        }
        selected_fields = confirm_metadata_import(self.root, self.t, import_items, current_metadata)
        if not selected_fields:
            return

        changed_filenames = [item.filename for item in import_items]
        try:
            backup_path = controller.crear_respaldo_metadatos(
                {"metadata_import_fields": ", ".join(selected_fields)},
                filenames=changed_filenames,
            )
        except Exception as exc:
            self.logger.error("Could not create metadata import backup: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.backup_failed", error=exc))
            return

        success_count = 0
        errors: list[str] = []
        for item in import_items:
            metadata = {
                field: value
                for field, value in item.metadata.items()
                if field in selected_fields
            }
            if not metadata:
                continue
            result = controller.aplicar_cambios_a_archivo(item.filename, metadata)
            if result.success:
                success_count += 1
            else:
                errors.extend(result.errors or [result.message])

        self._refresh_library_tree(controller, tree)
        self._record_undo_paths("undo.metadata", [backup_path])
        if errors:
            messagebox.showwarning(
                self.t("dialog.error"),
                self.t("metadata_import.partial", count=success_count, errors=len(errors)) + "\n\n" + "\n".join(errors[:5]),
            )
            self._show_toast(self.t("toast.partial"), kind="warning")
            return
        self._show_toast(self.t("metadata_import.done", count=success_count), kind="success")
        messagebox.showinfo(
            self.t("dialog.done"),
            self.t("metadata_import.done_with_backup", count=success_count, path=backup_path),
        )

    def _export_metadata_maps(self, controller, filenames: list[str]):
        metadata_by_filename: dict[str, dict[str, str]] = {}
        audio_quality_by_filename: dict[str, dict[str, object]] = {}
        duration_by_filename: dict[str, float] = {}
        for filename in filenames:
            cached = controller.get_track_info(filename)
            metadata_by_filename[filename] = dict(cached.metadata) if cached else {}
            audio_quality_by_filename[filename] = dict(cached.audio_quality) if cached else {}
            duration_by_filename[filename] = float(cached.duration or 0.0) if cached else 0.0
        return metadata_by_filename, audio_quality_by_filename, duration_by_filename

    def _select_filename_in_tree(self, tree, filename: str) -> None:
        for item_id in tree.get_children():
            if self._filename_from_tree_item(tree.item(item_id)) == filename:
                tree.selection_set(item_id)
                tree.focus(item_id)
                tree.see(item_id)
                return

    def _show_rename_from_metadata_preview(self) -> None:
        selections = self._selected_filenames_by_controller()
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return

        plan = self._rename_controller().build_plan(selections)
        if not plan:
            messagebox.showinfo(self.t("dialog.done"), self.t("rename_metadata.no_changes"))
            return

        if not confirm_rename_metadata(self.root, self.t, plan):
            return

        result = self._rename_controller().execute_plan(
            plan,
            song_info=self.song_info,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        self._preview_filename = result.preview_filename
        self._refresh_rename_pairs(plan, result.changed_pairs)

        if self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.renamed:
            message = self.t("rename_metadata.done", count=result.renamed)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(self.t("dialog.error"), "\n".join(result.errors))

    def _filename_from_metadata(self, controller: MetadataController, filename: str, used_names: set[str]) -> str:
        return self._rename_controller().filename_from_metadata(controller, filename, used_names)

    def _refresh_rename_pairs(
        self,
        plan: list[RenamePlanItem],
        changed_pairs: set[tuple[int, int]],
    ) -> None:
        refreshed: set[tuple[int, int]] = set()
        for item in plan:
            key = (id(item.controller), id(item.tree))
            if key in changed_pairs and key not in refreshed:
                self._refresh_library_tree(item.controller, item.tree)
                refreshed.add(key)

