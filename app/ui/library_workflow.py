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
            self.logger.info("Loaded folder %s with %s files", selected_folder, len(files))
        except Exception as exc:
            self.logger.error("Error loading folder: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("message.could_not_load_folder", error=exc))

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
        if not drag or drag.get("controller") is not controller or drag.get("tree") is not tree:
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
        self._set_sort_widget_for_controller(controller, SortMode.MANUAL)

        result = controller.apply_track_numbers_from_order()
        self._refresh_library_tree(controller, tree)
        for item_id in tree.get_children():
            if self._filename_from_tree_item(tree.item(item_id)) == moved:
                tree.selection_set(item_id)
                tree.focus(item_id)
                tree.see(item_id)
                self._load_song_preview(controller, moved)
                break
        self._handle_action_result(result)

    def _can_reorder_current_view(self, controller: MetadataController, tree) -> bool:
        return self._library_ui_controller().can_reorder_current_view(
            controller=controller,
            tree=tree,
            panel=self._get_library_panel(controller, tree),
        )

    def _set_sort_widget_for_controller(self, controller: MetadataController, mode: SortMode) -> None:
        for sort_menu, sort_var, widget_controller in self._sort_widgets:
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
        self._library_ui_controller().sort_files(
            controller=controller,
            sort_option=sort_option,
            sort_mode_from_text=self._sort_mode_from_text,
        )
        self._refresh_library_tree(controller, tree)

    def _refresh_library_tree(self, controller: MetadataController, tree) -> None:
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
        item = tree.item(selection[0])
        filename = self._filename_from_tree_item(item)
        if filename:
            self._load_song_preview(controller, filename)

    def _load_song_preview(self, controller: MetadataController, filename: str) -> None:
        if not controller.carpeta or not filename:
            return
        filepath = os.path.join(controller.carpeta, filename)
        self._preview_controller = controller
        self._preview_filename = filename
        metadata = self.song_info.get_metadata(filepath, use_cache=False)
        if metadata:
            self.preview.update_preview(metadata)
        else:
            self.preview.show_error_state(self.t("preview.could_not_read"))

