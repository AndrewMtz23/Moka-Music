from __future__ import annotations

import os
from pathlib import Path
from tkinter import messagebox, simpledialog

from ..controllers.backup_controller import BackupController
from ..controllers.cleanup_controller import CleanupController
from ..controllers.cleanup_preset_controller import CleanupPresetController
from ..models import SortMode
from ..utils.ui_formatting import metadata_label_key
from ..views.modals.backup_history_modal import show_backup_history_modal
from ..views.modals.change_preview_modal import confirm_change_preview
from ..views.modals.cleanup_preset_modal import show_cleanup_preset_modal
from ..views.modals.playlist_insert_preview_modal import confirm_playlist_insert_preview
from ..views.modals.rename_metadata_modal import confirm_rename_metadata


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

    def _apply_cover_to_targets(self, cover_path: str, targets=None) -> None:
        if not self.file_handler.validar_imagen(cover_path):
            return
        targets = targets if targets is not None else self._cover_targets()
        if not targets:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_cover_target"))
            return
        folder_targets = self._folder_cover_targets(targets)
        target_count = sum(len(filenames) for _controller, _tree, filenames in folder_targets)
        self.preview.update_cover_from_file(cover_path)
        backup_metadata = {"__cover__": os.path.basename(cover_path)}
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t("message.apply_cover_to_count", count=target_count, name=os.path.basename(cover_path)),
        ):
            return
        if not self._create_metadata_backup_for_groups(folder_targets, backup_metadata):
            return

        result = self._cover_controller().apply_manual_cover(
            targets=targets,
            cover_path=cover_path,
            song_info=self.song_info,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        self._refresh_changed_library_pairs(targets, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            message = self.t("message.cover_applied", count=result.success_count)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
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

        result = self._cover_controller().apply_cover_plan(
            cover_plan.groups,
            song_info=self.song_info,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        if result.preview_cover_path:
            self.preview.update_cover_from_file(result.preview_cover_path)
        self._refresh_changed_library_pairs(backup_groups, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            done = self.t("auto_cover.done", count=result.success_count)
            if result.errors:
                done += self.t("message.errors_count", count=len(result.errors))
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

        metadata = self._metadata_dialog_controller().request_clear(self.root, target.current_song)
        if metadata is None:
            return
        self._apply_metadata_to_preview_target(target, metadata, done_key="metadata_clear.done")

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
        selections = self._selected_filenames_by_controller()
        selected_count = self._metadata_apply_controller().selected_count(selections)
        is_batch_edit = selected_count > 1

        metadata = self._metadata_dialog_controller().request_edit(
            self.root,
            target.current_song,
            selected_count=selected_count,
            is_batch_edit=is_batch_edit,
        )
        if metadata is None:
            return

        if is_batch_edit:
            validation = target.controller.validar_datos(metadata)
            if not validation.success:
                messagebox.showwarning(self.t("dialog.metadata"), validation.message)
                return
            if not self._confirm_metadata_change_preview(selections, metadata):
                return

            if not self._create_metadata_backup_for_groups(selections, metadata):
                return

            result = self._metadata_apply_controller().apply_groups(
                groups=selections,
                metadata=metadata,
                song_info=self.song_info,
                preview_controller=self._preview_controller,
                preview_filename=self._preview_filename,
            )
            self._refresh_changed_library_pairs(selections, result.changed_pairs)

            if result.affected_preview and self._preview_controller and self._preview_filename:
                self._load_song_preview(self._preview_controller, self._preview_filename)

            if result.success_count:
                message = self.t("batch_edit.done", count=result.success_count)
                if result.errors:
                    message += self.t("message.errors_count", count=len(result.errors))
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
        pairs = [
            (self.controller_principal, self.tree_principal),
            (self.controller_nueva, self.tree_nueva),
        ]
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

    def _undo_last_metadata_change(self) -> None:
        backup_controller = self._backup_controller()
        if not backup_controller.has_recent_backup():
            messagebox.showwarning(self.t("dialog.no_files"), self.t("backup.no_recent_backup"))
            return
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t("backup.confirm_restore", path=backup_controller.recent_backup_label()),
        ):
            return
        self._restore_backup_paths(backup_controller.last_backup_paths)

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

        result = self._metadata_apply_controller().apply_groups(
            groups=selections,
            metadata=metadata,
            song_info=self.song_info,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        self._refresh_changed_library_pairs(selections, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            message = self.t("batch_edit.done", count=result.success_count)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
            messagebox.showinfo(self.t("dialog.done"), message)
            return

        messagebox.showerror(
            self.t("dialog.error"),
            "\n".join(result.errors) if result.errors else self.t("message.could_not_apply_metadata"),
        )

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

        result = self._cleanup_controller().execute_plan(
            plan,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        self._refresh_changed_library_pairs(result.changed_groups, result.changed_pairs)

        if result.affected_preview and self._preview_controller and self._preview_filename:
            self._load_song_preview(self._preview_controller, self._preview_filename)

        if result.success_count:
            message = self.t("quick_actions.done", count=result.success_count)
            if result.errors:
                message += self.t("message.errors_count", count=len(result.errors))
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
        if not confirm_playlist_insert_preview(self.root, self.t, plan):
            return

        result = self._playlist_workflow_controller().execute_plan(
            plan,
            song_info=self.song_info,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        self._preview_filename = result.preview_filename
        self._refresh_changed_library_pairs([(controller, tree, plan.final_order)], result.changed_pairs)
        self._set_sort_widget_for_controller(controller, SortMode.MANUAL)

        if self._preview_controller is controller and self._preview_filename:
            self._select_filename_in_tree(tree, self._preview_filename)
            self._load_song_preview(controller, self._preview_filename)

        if result.success:
            message = self.t(
                "playlist_insert.done",
                tracks=result.track_numbers_updated,
                renamed=result.renamed,
            )
            if result.backup_path:
                message += f"\n{self.t('message.backup_created', path=result.backup_path)}"
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
        if not confirm_playlist_insert_preview(self.root, self.t, plan):
            return

        result = self._playlist_workflow_controller().execute_plan(
            plan,
            song_info=self.song_info,
            preview_controller=self._preview_controller,
            preview_filename=self._preview_filename,
        )
        self._preview_filename = result.preview_filename
        self._refresh_changed_library_pairs([(controller, tree, plan.final_order)], result.changed_pairs)
        self._set_sort_widget_for_controller(controller, SortMode.MANUAL)

        if self._preview_controller is controller and self._preview_filename:
            self._select_filename_in_tree(tree, self._preview_filename)
            self._load_song_preview(controller, self._preview_filename)

        if result.success:
            message = self.t(
                "playlist_prepare.done",
                tracks=result.track_numbers_updated,
                renamed=result.renamed,
            )
            if result.backup_path:
                message += f"\n{self.t('message.backup_created', path=result.backup_path)}"
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

