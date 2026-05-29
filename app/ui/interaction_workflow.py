from __future__ import annotations

import os
from pathlib import Path
from tkinter import messagebox

from ..controllers.add_music_controller import abrir_selector_archivo, agregar_a_lista
from ..controllers.metadata_controller import MetadataController
from ..models import SortMode
from ..services.playback_history_service import record_playback
from ..utils.ui_formatting import format_action_error
from ..views.modals.incoming_folder_guide_modal import show_incoming_folder_guide
from ..views.modals.track_position_modal import request_track_position


class InteractionWorkflowMixin:
    """Playback, file actions, metadata field actions, and drop workflows."""

    def _play_selected(self, controller: MetadataController, tree) -> None:
        selected = self._playback_selection_controller().selected_track(controller, tree)
        if selected is None:
            return
        if self.player.load_file(selected.filepath):
            self._playback_controller = controller
            self._playback_tree = tree
            self.player.play()
            self._record_playback(controller, selected.filename, selected.filepath)
            self.logger.info("Playing %s", selected.filename)

    def _record_playback(self, controller: MetadataController, filename: str, filepath: str) -> None:
        track = controller.get_track_info(filename)
        self.playback_history = record_playback(
            self.playback_history,
            filepath=filepath,
            filename=filename,
            metadata=track.metadata if track else {},
        )
        self._sync_playback_history_to_controllers()
        self._save_config()

    def _play_relative_track(self, offset: int) -> None:
        tree = self._playback_tree
        controller = self._playback_controller
        if tree is None or controller is None:
            return
        target_item = self._playback_selection_controller().relative_item(
            tree,
            offset=offset,
            shuffle=self.player.shuffle_enabled(),
        )
        if target_item is None:
            return
        self._select_and_play(controller, tree, target_item)

    def _play_next_track(self) -> None:
        if self.player.repeat_enabled():
            self.player.restart_current_track()
            return
        self._play_relative_track(1)

    def _select_and_play(self, controller: MetadataController, tree, item_id) -> None:
        tree.selection_set(item_id)
        tree.focus(item_id)
        tree.see(item_id)
        self._play_selected(controller, tree)

    def _add_single_file(self, controller: MetadataController, tree) -> None:
        try:
            ruta_archivo = abrir_selector_archivo(self.file_handler)
            if not ruta_archivo:
                return
            result = agregar_a_lista(
                ruta_archivo,
                controller,
                tree,
                self.file_handler,
                self.song_info,
                translator=self.t,
            )
            self._handle_action_result(result)
            if result.success and result.data:
                filename = result.data.get("filename")
                if filename:
                    for item_id in tree.get_children():
                        item = tree.item(item_id)
                        item_filename = self._filename_from_tree_item(item)
                        if item_filename == filename:
                            tree.selection_set(item_id)
                            tree.focus(item_id)
                            tree.see(item_id)
                            self._load_song_preview(controller, filename)
                            break
        except Exception as exc:
            self.logger.error("Error adding song: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.could_not_add_song", error=exc))

    def _move_to_main(self) -> None:
        selection = self.tree_nueva.selection()
        if not selection:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.select_song_to_move"))
            return
        item = self.tree_nueva.item(selection[0])
        filename = self._filename_from_tree_item(item)
        if not filename:
            return
        result = self.song_actions.mover_cancion(
            self.controller_nueva,
            self.controller_principal,
            filename,
            self.tree_nueva,
            self.tree_principal,
            self.preview,
        )
        self._handle_action_result(result)
        if result.success and result.data:
            moved_filename = result.data.get("filename")
            if isinstance(moved_filename, str):
                self._position_moved_song_in_main(moved_filename)

    def _move_between_libraries_by_drag(
        self,
        origin_controller: MetadataController,
        origin_tree,
        destination_controller: MetadataController,
        destination_tree,
        filename: str,
    ) -> bool:
        if not destination_controller.carpeta:
            messagebox.showwarning(self.t("dialog.no_destination"), self.t("action.no_destination"))
            return False
        result = self.song_actions.mover_cancion(
            origin_controller,
            destination_controller,
            filename,
            origin_tree,
            destination_tree,
            self.preview,
        )
        self._handle_action_result(result)
        if result.success and result.data:
            moved_filename = result.data.get("filename")
            if isinstance(moved_filename, str):
                self._select_filename_in_tree(destination_tree, moved_filename)
                self._load_song_preview(destination_controller, moved_filename)
            return True
        return False

    def _position_moved_song_in_main(self, filename: str) -> None:
        if filename not in self.controller_principal.archivos:
            return
        total = len(self.controller_principal.archivos)
        position = request_track_position(
            self.root,
            self.t,
            title=self.t("move_position.title"),
            prompt=self.t("move_position.prompt", name=filename, total=total),
            total=total,
            initial=max(0, total - 1),
            min_position=0,
            max_position=max(0, total - 1),
        )
        if position is None:
            self._select_filename_in_tree(self.tree_principal, filename)
            return
        order = [name for name in self.controller_principal.archivos if name != filename]
        insert_at = max(0, min(int(position), len(order)))
        order[insert_at:insert_at] = [filename]
        self.controller_principal.reorder_files(order)
        result = self.controller_principal.apply_track_numbers_from_order()
        for name in self.controller_principal.archivos:
            self.song_info.invalidate(os.path.join(self.controller_principal.carpeta, name))
        self.controller_principal.set_sort_mode(SortMode.TRACK_NUMBER)
        self._refresh_library_tree(self.controller_principal, self.tree_principal)
        self._set_sort_widget_for_controller(self.controller_principal, SortMode.TRACK_NUMBER)
        self._select_filename_in_tree(self.tree_principal, filename)
        self._load_song_preview(self.controller_principal, filename)
        if not result.success:
            self._handle_action_result(result)

    def _show_incoming_folder_guide(self) -> None:
        if not self._ensure_incoming_context():
            return
        actions = [
            (
                "incoming_guide.open_global",
                "incoming_guide.open_global_desc",
                lambda: self._set_global_metadata_view(True),
            ),
            (
                "incoming_guide.clear_metadata",
                "incoming_guide.clear_metadata_desc",
                self._show_clear_metadata_modal,
            ),
            (
                "incoming_guide.edit_metadata",
                "incoming_guide.edit_metadata_desc",
                self._show_edit_metadata_modal,
            ),
            (
                "incoming_guide.cover",
                "incoming_guide.cover_desc",
                self._select_preview_cover,
            ),
            (
                "incoming_guide.prepare_playlist",
                "incoming_guide.prepare_playlist_desc",
                self._prepare_active_playlist,
            ),
            (
                "incoming_guide.move_selected",
                "incoming_guide.move_selected_desc",
                self._move_to_main,
            ),
        ]
        show_incoming_folder_guide(self.root, self.t, actions)

    def _ensure_incoming_context(self) -> bool:
        if not self.controller_nueva.archivos:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return False
        self.tree_principal.selection_clear(0, "end")
        selection = self.tree_nueva.selection()
        if not selection:
            first_item = self.tree_nueva.get_children()[0]
            self.tree_nueva.selection_set(first_item)
            self.tree_nueva.focus(first_item)
            self.tree_nueva.see(first_item)
            selection = self.tree_nueva.selection()
        item = self.tree_nueva.item(selection[0])
        filename = self._filename_from_tree_item(item)
        if filename:
            self._load_song_preview(self.controller_nueva, filename)
        return True

    def _show_context_menu(self, event, controller: MetadataController, tree) -> None:
        other_controller = self.controller_principal if controller == self.controller_nueva else self.controller_nueva
        other_tree = self.tree_principal if controller == self.controller_nueva else self.tree_nueva
        self.song_actions.mostrar_boton_contextual(
            self.root,
            controller,
            other_controller,
            tree,
            other_tree,
            self.preview,
            event,
            on_result=self._handle_action_result,
        )

    def _apply_to_selection(self) -> None:
        metadata = self._metadata_apply_controller().metadata_from_vars(self.meta_vars)
        if not metadata:
            messagebox.showwarning(self.t("dialog.metadata"), self.t("message.no_metadata_to_apply"))
            return

        target = self._metadata_apply_controller().first_selected_target(
            [
                (self.tree_principal, self.controller_principal),
                (self.tree_nueva, self.controller_nueva),
            ],
            self._filename_from_tree_item,
        )
        if not target:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return

        controller, tree, filename = target
        if not self._create_metadata_backup_for_groups([(controller, tree, [filename])], metadata):
            return
        apply_result = self._metadata_apply_controller().apply_single(
            controller=controller,
            tree=tree,
            filename=filename,
            metadata=metadata,
            cover_path=controller.portada_path,
            song_info=self.song_info,
        )
        if apply_result.success:
            self._record_undo_action("undo.metadata")
            self._load_song_preview(controller, filename)
            self._refresh_changed_library_pairs([(controller, tree, [filename])], apply_result.changed_pairs)
            messagebox.showinfo(self.t("dialog.done"), self.t("message.metadata_applied"))
        else:
            messagebox.showerror(
                self.t("dialog.error"),
                "\n".join(apply_result.result.errors)
                if apply_result.result.errors
                else self.t("message.could_not_apply_metadata"),
            )

    def _apply_to_all(self) -> None:
        metadata = self._metadata_apply_controller().metadata_from_vars(self.meta_vars)
        if not metadata:
            messagebox.showwarning(self.t("dialog.metadata"), self.t("message.no_metadata_to_apply"))
            return

        target = self._metadata_apply_controller().all_files_target(
            primary_controller=self.controller_principal,
            primary_tree=self.tree_principal,
            incoming_controller=self.controller_nueva,
            incoming_tree=self.tree_nueva,
        )
        if not target:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return
        controller, active_tree, filenames = target

        validation = controller.validar_datos(metadata)
        if not validation.success:
            proceed = messagebox.askyesno(
                self.t("dialog.metadata"),
                self.t("message.validation_warning", message=validation.message),
            )
            if not proceed:
                return

        groups = [(controller, active_tree, filenames)]
        if not self._confirm_metadata_change_preview(groups, metadata):
            return

        backup_path = self._create_metadata_backup_for_groups(groups, metadata)
        if not backup_path:
            return

        progress = self._begin_progress(
            title=self.t("progress.metadata_title"),
            message=self.t("progress.metadata_body"),
            total=len(filenames),
        )
        try:
            success_count, errors = self._metadata_apply_controller().apply_all(
                controller=controller,
                metadata=metadata,
                song_info=self.song_info,
                progress_callback=progress.update,
            )
        finally:
            progress.close()
        if success_count:
            self._record_undo_action("undo.metadata")
            message = self.t("message.updated_files", count=success_count)
            message += f"\n{self.t('message.backup_created', path=backup_path)}"
            if errors:
                message += self.t("message.errors_count", count=len(errors))
                self._show_toast(self.t("toast.partial"), kind="warning")
            else:
                self._show_toast(self.t("toast.done"), kind="success")
            messagebox.showinfo(self.t("dialog.done"), message)
            selection = active_tree.selection()
            if selection:
                item = active_tree.item(selection[0])
                filename = self._filename_from_tree_item(item)
                if filename:
                    self._load_song_preview(controller, filename)
            self._refresh_library_tree(controller, active_tree)
        else:
            messagebox.showerror(
                self.t("dialog.error"),
                "\n".join(errors) if errors else self.t("message.could_not_apply_metadata"),
            )

    def _clear_metadata_fields(self) -> None:
        for variable in self.meta_vars.values():
            variable.set("")

    def _select_cover(self) -> None:
        cover_path = self.file_handler.seleccionar_imagen()
        if not cover_path:
            return
        self._apply_cover_to_targets(cover_path)

    def _handle_drop(self, event) -> None:
        try:
            payload = self._drop_controller().payload_from_raw(event.data, splitlist=self.root.tk.splitlist)
            for folder in payload.folders:
                folder_path = Path(folder)
                if messagebox.askyesno(
                    self.t("dialog.folder_detected"),
                    self.t("message.load_folder_into_main", name=folder_path.name),
                ):
                    self._load_folder(self.controller_principal, self.tree_principal, folder=folder)

            if payload.image_files and not payload.audio_files:
                self._apply_cover_to_targets(payload.image_files[0])
                return

            if payload.audio_files:
                if not self.controller_principal.carpeta:
                    messagebox.showwarning(
                        self.t("dialog.no_destination"),
                        self.t("message.load_main_before_drop"),
                    )
                    return

                result = self._drop_controller().add_audio_files(
                    payload.audio_files,
                    controller=self.controller_principal,
                    song_info=self.song_info,
                    translator=self.t,
                )
                if result.added:
                    self._refresh_library_tree(self.controller_principal, self.tree_principal)
                    messagebox.showinfo(
                        self.t("dialog.files_added"),
                        self.t("message.added_dropped_files", count=result.added),
                    )
        except Exception as exc:
            self.logger.error("Error handling drop event: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.could_not_process_drop", error=exc))

    def _handle_library_drop(self, event, controller: MetadataController, tree) -> None:
        try:
            payload = self._drop_controller().payload_from_raw(event.data, splitlist=self.root.tk.splitlist)
            library_name = self._library_debug_name(controller, tree)
            library_label = (
                self.t("panel.main_library")
                if library_name == "main_library"
                else self.t("panel.incoming_library")
            )

            for folder in payload.folders:
                folder_path = Path(folder)
                if messagebox.askyesno(
                    self.t("dialog.folder_detected"),
                    self.t("message.load_folder_into_library", name=folder_path.name, library=library_label),
                ):
                    self._load_folder(controller, tree, folder=folder)

            if payload.image_files:
                targets = self._drop_cover_targets(controller, tree, getattr(event, "y", 0))
                self._apply_cover_to_targets(payload.image_files[0], targets=targets, apply_entire_folder=False)
                return

            if payload.audio_files:
                if not controller.carpeta:
                    messagebox.showwarning(
                        self.t("dialog.no_destination"),
                        self.t("message.load_library_before_drop"),
                    )
                    return
                result = self._drop_controller().add_audio_files(
                    payload.audio_files,
                    controller=controller,
                    song_info=self.song_info,
                    translator=self.t,
                )
                if result.added:
                    self._refresh_library_tree(controller, tree)
                    messagebox.showinfo(
                        self.t("dialog.files_added"),
                        self.t("message.added_dropped_files", count=result.added),
                    )
        except Exception as exc:
            self.logger.error("Error handling library drop event: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.could_not_process_drop", error=exc))

    def _drop_cover_targets(self, controller: MetadataController, tree, y: int):
        filenames = [
            self._filename_from_tree_item(tree.item(item_id))
            for item_id in tree.selection()
            if self._filename_from_tree_item(tree.item(item_id))
        ]
        if not filenames:
            item_id = tree.identify_row(y)
            if item_id:
                filename = self._filename_from_tree_item(tree.item(item_id))
                if filename:
                    tree.selection_set(item_id)
                    filenames = [filename]
        return [(controller, tree, filenames)] if filenames else []

    def _handle_action_result(self, result) -> None:
        if result is None:
            return
        if result.success:
            if hasattr(self, "tree_principal"):
                self._refresh_library_tree(self.controller_principal, self.tree_principal)
            if hasattr(self, "tree_nueva"):
                self._refresh_library_tree(self.controller_nueva, self.tree_nueva)
            messagebox.showinfo(self.t("dialog.done"), result.message)
        else:
            detail = self._format_action_error(result)
            messagebox.showerror(self.t("dialog.error"), detail)

    def _format_action_error(self, result) -> str:
        return format_action_error(result, self.t)

