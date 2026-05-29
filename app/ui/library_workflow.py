from __future__ import annotations

import os
from tkinter import messagebox
from typing import Optional

from ..controllers.metadata_controller import MetadataController
from ..models import FilterMode, SortMode
from ..utils.ui_formatting import filename_from_tree_item


class LibraryWorkflowMixin:
    """Library loading, rendering, reorder, selection, and preview workflows."""

    def _load_folder(self, controller: MetadataController, tree, *, folder: Optional[str] = None) -> None:
        try:
            selected_folder = folder or self.file_handler.seleccionar_carpeta()
            if not selected_folder:
                return
            panel_name = self._library_debug_name(controller, tree)
            self.logger.info("[%s] Loading folder: %s", panel_name, selected_folder)
            files = controller.cargar_archivos_mp3(selected_folder)
            self.logger.info(
                "[%s] Controller loaded %s files from %s",
                panel_name,
                len(files),
                controller.carpeta,
            )
            self._refresh_library_tree(controller, tree)
            rendered_count = len(tree.get_children())
            self.logger.info(
                "[%s] Rendered %s rows after folder load",
                panel_name,
                rendered_count,
            )
            if files:
                children = tree.get_children()
                if children:
                    first_item = children[0]
                    tree.selection_set(first_item)
                    tree.focus(first_item)
                    filename = self._filename_from_tree_item(tree.item(first_item))
                    if filename:
                        self._load_song_preview(controller, filename)
            else:
                self.preview.clear_preview()
            target = "incoming" if controller is self.controller_nueva else "main"
            self._remember_recent_folder(selected_folder, target)
            self._setup_main_menu()
            self._save_config()
            self.logger.info("Loaded folder %s with %s files", selected_folder, len(files))
        except Exception as exc:
            self.logger.error("Error loading folder: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.could_not_load_folder", error=exc))

    def _clear_library_folder(self, controller: MetadataController, tree) -> None:
        if not controller.carpeta and not controller.archivos:
            return
        if controller is self._preview_controller:
            self._preview_controller = None
            self._preview_filename = None
            self.preview.clear_preview()
        if controller is self._playback_controller:
            self._playback_controller = None
            self._playback_tree = None
            self.player.stop()
        controller.clear_library()
        tree.selection_clear(0, "end")
        self._refresh_library_tree(controller, tree)
        self._save_config()

    def _refresh_library_folder(self, controller: MetadataController, tree) -> None:
        if not controller.carpeta:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return
        selected = [
            self._filename_from_tree_item(tree.item(item_id))
            for item_id in tree.selection()
            if self._filename_from_tree_item(tree.item(item_id))
        ]
        try:
            files = controller.refresh_library()
            self._sync_playback_history_to_controllers()
            self._refresh_library_tree(controller, tree)
            restored = False
            for filename in selected:
                if filename in controller.archivos:
                    restored = True
                    self._select_filename_in_tree(tree, filename)
                    break
            if not restored and files:
                children = tree.get_children()
                if children:
                    tree.selection_set(children[0])
                    tree.focus(children[0])
            self._show_toast(self.t("library.refresh_done", count=len(files)), kind="success")
        except Exception as exc:
            self.logger.error("Error refreshing library: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("library.refresh_failed", error=exc))

    def _delete_selected_from_library(self, controller: MetadataController, tree) -> None:
        selections = self._selection_controller().selected_filenames_by_controller([(controller, tree)])
        if not selections:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_song_selected"))
            return
        _controller, _tree, filenames = selections[0]
        if not messagebox.askyesno(
            self.t("dialog.confirm"),
            self.t("library.delete_confirm", count=len(filenames)),
        ):
            return

        deleted = 0
        errors: list[str] = []
        for filename in filenames:
            result = self.song_actions.eliminar_cancion(controller, filename, tree, self.preview)
            if result.success:
                deleted += 1
            else:
                errors.extend(result.errors or [result.message])

        if controller is self._preview_controller and self._preview_filename in filenames:
            self._preview_controller = None
            self._preview_filename = None
            self.preview.clear_preview()
        if controller is self._playback_controller and self.player.playback.current_file:
            current_name = os.path.basename(self.player.playback.current_file)
            if current_name in filenames:
                self._playback_controller = None
                self._playback_tree = None
                self.player.stop()

        self._refresh_library_tree(controller, tree)
        if errors:
            messagebox.showwarning(
                self.t("dialog.error"),
                self.t("library.delete_partial", count=deleted, errors=len(errors)) + "\n\n" + "\n".join(errors[:5]),
            )
            self._show_toast(self.t("toast.partial"), kind="warning")
            return
        self._show_toast(self.t("library.delete_done", count=deleted), kind="success")

    def _update_treeview(self, tree, files: list[str]) -> None:
        panel_name = self._library_debug_name(self._controller_for_tree(tree), tree)
        self.logger.debug("[%s] Updating list widget with %s files", panel_name, len(files))
        controller = self._controller_for_tree(tree)
        self._library_ui_controller().update_treeview(
            tree=tree,
            files=files,
            controller=controller,
            panel=self._get_library_panel(controller, tree),
        )
        self.logger.info(
            "[%s] List widget now has %s file rows",
            panel_name,
            self._count_file_rows(tree),
        )

    def _empty_library_message(
        self,
        controller: Optional[MetadataController],
        panel: Optional[dict[str, object]] = None,
    ) -> str:
        return self._library_ui_controller().empty_library_message(controller, panel)

    def _filename_from_tree_item(self, item: dict[str, object]) -> str:
        return filename_from_tree_item(item)

    def _song_display_name(self, controller: Optional[MetadataController], filename: str) -> str:
        return self._library_ui_controller().song_display_name(controller, filename)

    def _count_file_rows(self, tree) -> int:
        return self._library_ui_controller().count_file_rows(tree)

    def _visible_filenames(self, tree) -> list[str]:
        return self._library_ui_controller().visible_filenames(tree)

    def _start_reorder_drag(self, event, controller: MetadataController, tree) -> None:
        item_id = tree.identify_row(event.y)
        if not item_id:
            self._reorder_drag = None
            return
        filename = self._filename_from_tree_item(tree.item(item_id))
        if not filename:
            self._reorder_drag = None
            return
        self._reorder_drag = {
            "controller": controller,
            "tree": tree,
            "source": int(item_id),
            "filename": filename,
        }

    def _finish_reorder_drag(self, event, controller: MetadataController, tree) -> None:
        drag = self._reorder_drag
        self._reorder_drag = None
        if not drag:
            return
        if drag.get("controller") is not controller or drag.get("tree") is not tree:
            target = self._library_target_from_pointer(event)
            if target is None:
                return
            destination_controller, destination_tree = target
            origin_controller = drag.get("controller")
            origin_tree = drag.get("tree")
            filename = str(drag.get("filename", "") or "")
            if destination_controller is origin_controller or not filename:
                return
            self._move_between_libraries_by_drag(
                origin_controller,
                origin_tree,
                destination_controller,
                destination_tree,
                filename,
            )
            return

        target_id = tree.identify_row(event.y)
        if not target_id:
            return
        source_index = int(drag["source"])
        target_index = int(target_id)
        if source_index == target_index:
            return

        if not self._can_reorder_current_view(controller, tree):
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.reorder_needs_full_view"))
            return

        filenames = self._visible_filenames(tree)
        if source_index >= len(filenames) or target_index >= len(filenames):
            return
        moved = filenames.pop(source_index)
        filenames.insert(target_index, moved)
        controller.reorder_files(filenames)

        result = controller.apply_track_numbers_from_order()
        controller.set_sort_mode(SortMode.TRACK_NUMBER)
        self._set_sort_widget_for_controller(controller, SortMode.TRACK_NUMBER)
        self._refresh_library_tree(controller, tree)
        for item_id in tree.get_children():
            if self._filename_from_tree_item(tree.item(item_id)) == moved:
                tree.selection_set(item_id)
                tree.focus(item_id)
                tree.see(item_id)
                self._load_song_preview(controller, moved)
                break
        self._handle_action_result(result)

    def _library_target_from_pointer(self, event):
        widget = None
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None
        for controller, tree in (
            (getattr(self, "controller_principal", None), getattr(self, "tree_principal", None)),
            (getattr(self, "controller_nueva", None), getattr(self, "tree_nueva", None)),
        ):
            current = widget
            while current is not None:
                if current is tree:
                    return controller, tree
                try:
                    current = current.master
                except Exception:
                    break
        return None

    def _can_reorder_current_view(self, controller: MetadataController, tree) -> bool:
        return self._library_ui_controller().can_reorder_current_view(
            controller=controller,
            tree=tree,
            panel=self._get_library_panel(controller, tree),
        )

    def _set_sort_widget_for_controller(self, controller: MetadataController, mode: SortMode) -> None:
        for sort_menu, sort_var, widget_controller in getattr(self, "_sort_widgets", []):
            if widget_controller is controller:
                sort_var.set(self._sort_text_for_mode(mode))
                sort_menu.configure(values=self._sort_options())
                return

    def _controller_for_tree(self, tree) -> Optional[MetadataController]:
        return self._selection_controller().controller_for_tree(
            tree,
            main_controller=getattr(self, "controller_principal", None),
            main_tree=getattr(self, "tree_principal", None),
            incoming_controller=getattr(self, "controller_nueva", None),
            incoming_tree=getattr(self, "tree_nueva", None),
            panels=getattr(self, "_library_panels", []),
        )

    def _library_debug_name(self, controller: Optional[MetadataController], tree=None) -> str:
        if controller is self.controller_principal or (
            tree is not None and hasattr(self, "tree_principal") and tree == self.tree_principal
        ):
            return "main_library"
        if controller is self.controller_nueva or (
            tree is not None and hasattr(self, "tree_nueva") and tree == self.tree_nueva
        ):
            return "incoming_library"
        return "unknown_library"

    def _apply_tree_colors(self, tree) -> None:
        self._library_ui_controller().apply_tree_colors(tree)

    def _sort_files(self, controller: MetadataController, tree, sort_option: str) -> None:
        controller.set_sort_mode(SortMode.TRACK_NUMBER)
        self._set_sort_widget_for_controller(controller, SortMode.TRACK_NUMBER)
        self._refresh_library_tree(controller, tree)

    def _refresh_library_tree(self, controller: MetadataController, tree) -> None:
        controller.set_sort_mode(SortMode.TRACK_NUMBER)
        self._set_sort_widget_for_controller(controller, SortMode.TRACK_NUMBER)
        panel_name = self._library_debug_name(controller, tree)
        panel = self._get_library_panel(controller, tree)
        query = self._panel_search_query(panel) if panel else ""
        files = self._library_ui_controller().refresh_library_tree(
            controller=controller,
            tree=tree,
            panel=panel,
            filter_mode_from_text=self._filter_mode_from_text,
        )
        if not panel:
            self.logger.info(
                "[%s] Refresh without panel: controller=%s rows=%s",
                panel_name,
                len(controller.archivos),
                len(files),
            )
            return
        filter_mode = panel.get("filter_mode", FilterMode.ALL)
        files = controller.filter_files(query, filter_mode)
        self.logger.info(
            "[%s] Refresh: controller=%s query=%r filter=%s visible=%s",
            panel_name,
            len(controller.archivos),
            query,
            filter_mode.name,
            len(files),
        )
        if not files:
            self.logger.warning(
                "[%s] Empty library view: %s",
                panel_name,
                self._empty_library_message(controller, panel),
            )

    def _panel_search_query(self, panel: dict[str, object]) -> str:
        return self._library_ui_controller().panel_search_query(panel)

    def _get_library_panel(self, controller: MetadataController, tree) -> Optional[dict[str, object]]:
        return self._selection_controller().panel_for_library(self._library_panels, controller, tree)

    def _tree_for_controller(self, controller: MetadataController):
        return self._selection_controller().tree_for_controller(
            controller,
            main_controller=getattr(self, "controller_principal", None),
            main_tree=getattr(self, "tree_principal", None),
            incoming_controller=getattr(self, "controller_nueva", None),
            incoming_tree=getattr(self, "tree_nueva", None),
        )

    def _update_result_label(self, panel: dict[str, object]) -> None:
        self._library_ui_controller().update_result_label(panel)

    def _on_song_select(self, controller: MetadataController, tree) -> None:
        selection = tree.selection()
        if not selection:
            return
        self._clear_other_library_selection(tree)
        item = tree.item(selection[0])
        filename = self._filename_from_tree_item(item)
        if filename:
            self._load_song_preview(controller, filename)

    def _clear_other_library_selection(self, active_tree) -> None:
        for tree in (getattr(self, "tree_principal", None), getattr(self, "tree_nueva", None)):
            if tree is not None and tree is not active_tree:
                tree.selection_clear(0, "end")

    def _active_selection_tree(self):
        for tree in (getattr(self, "tree_principal", None), getattr(self, "tree_nueva", None)):
            if tree is not None and tree.selection():
                return tree
        preview_controller = getattr(self, "_preview_controller", None)
        if preview_controller is not None:
            tree = self._tree_for_controller(preview_controller)
            if tree is not None:
                return tree
        for controller, tree in (
            (getattr(self, "controller_principal", None), getattr(self, "tree_principal", None)),
            (getattr(self, "controller_nueva", None), getattr(self, "tree_nueva", None)),
        ):
            if controller is not None and tree is not None and getattr(controller, "carpeta", ""):
                return tree
        return None

    def _select_all_in_active_library(self) -> str:
        tree = self._active_selection_tree()
        if tree is None:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_loaded_files"))
            return "break"
        children = tree.get_children()
        if children:
            tree.selection_set(*children)
            tree.focus(children[0])
            tree.see(children[0])
        return "break"

    def _deselect_all_in_active_library(self) -> None:
        tree = self._active_selection_tree()
        if tree is not None:
            tree.selection_clear(0, "end")

    def _invert_selection_in_active_library(self) -> None:
        tree = self._active_selection_tree()
        if tree is None:
            messagebox.showwarning(self.t("dialog.selection"), self.t("message.no_loaded_files"))
            return
        selected = set(tree.selection())
        next_selection = [item_id for item_id in tree.get_children() if item_id not in selected]
        tree.selection_clear(0, "end")
        if next_selection:
            tree.selection_set(*next_selection)
            tree.focus(next_selection[0])
            tree.see(next_selection[0])

    def _load_song_preview(self, controller: MetadataController, filename: str) -> None:
        if not controller.carpeta or not filename:
            return
        filepath = os.path.join(controller.carpeta, filename)
        self._preview_controller = controller
        self._preview_filename = filename
        metadata = self.song_info.get_metadata(filepath, use_cache=False)
        if metadata:
            cached = controller.get_track_info(filename)
            if cached:
                metadata = dict(metadata)
                metadata["audio_quality"] = cached.audio_quality
            self.preview.update_preview(metadata)
        else:
            self.preview.show_error_state(self.t("preview.could_not_read"))

