import os
from typing import Callable, Optional

from ..models import FilterMode, SortMode
from ..ui_helpers.widgets import LibraryListbox


QUALITY_BADGE_FILTERS = {
    FilterMode.LOW_BITRATE,
    FilterMode.BITRATE_128,
    FilterMode.BITRATE_256,
    FilterMode.BITRATE_320,
}


class LibraryUiController:
    def __init__(
        self,
        *,
        translator: Callable[..., str],
        theme_colors: Callable[[], dict[str, str]],
        filename_from_item: Callable[[dict[str, object]], str],
        short_name: Callable[[str], str],
    ) -> None:
        self.t = translator
        self.theme_colors = theme_colors
        self.filename_from_item = filename_from_item
        self.short_name = short_name

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def update_treeview(
        self,
        *,
        tree,
        files: list[str],
        controller,
        panel: Optional[dict[str, object]],
    ) -> None:
        tree.delete(*tree.get_children())
        duplicate_set = controller.duplicate_filenames() if controller and controller.carpeta else set()
        filter_mode = panel.get("filter_mode", FilterMode.ALL) if panel else FilterMode.ALL
        for index, filename in enumerate(files):
            display_name = self.song_display_name(controller, filename)
            issue_keys = self.issue_keys(controller, filename, duplicate_set)
            quality_badge = self.quality_badge(controller, filename) if filter_mode in QUALITY_BADGE_FILTERS else ""
            display_name = self.display_name_with_badges(display_name, issue_keys, quality_badge=quality_badge)
            full_path = os.path.join(controller.carpeta, filename) if controller and controller.carpeta else filename
            row_tag = "even_row" if (index + 1) % 2 == 0 else "odd_row"
            issue_tags = tuple(f"issue_{key}" for key in issue_keys)
            tree.insert("", "end", text=display_name, values=(index, full_path), tags=(filename, row_tag, *issue_tags))
        if not files:
            message = self.empty_library_message(controller, panel)
            tree.insert("", "end", text=message, values=("", ""), tags=("placeholder",))
            self._show_empty_state(panel, message)
        else:
            self._hide_empty_state(panel)
        self.apply_tree_colors(tree)
        tree.xview_moveto(0)
        tree.yview_moveto(0)

    def refresh_library_tree(
        self,
        *,
        controller,
        tree,
        panel: Optional[dict[str, object]],
        filter_mode_from_text: Callable[[str], FilterMode],
    ) -> list[str]:
        if not panel:
            files = controller.get_sorted_files()
            self.update_treeview(tree=tree, files=files, controller=controller, panel=panel)
            return files

        query = self.panel_search_query(panel)
        filter_mode = filter_mode_from_text(panel["filter_var"].get())
        panel["filter_mode"] = filter_mode
        files = controller.filter_files(query, filter_mode)
        self.update_treeview(tree=tree, files=files, controller=controller, panel=panel)
        self.update_result_label(panel)
        return files

    def sort_files(
        self,
        *,
        controller,
        sort_option: str,
        sort_mode_from_text: Callable[[str], SortMode],
    ) -> None:
        controller.set_sort_mode(sort_mode_from_text(sort_option))

    def can_reorder_current_view(self, *, controller, tree, panel: Optional[dict[str, object]]) -> bool:
        if not panel:
            return True
        query = self.panel_search_query(panel)
        filter_mode = panel.get("filter_mode", FilterMode.ALL)
        return not query and filter_mode == FilterMode.ALL and self.visible_filenames(tree) == controller.archivos

    def empty_library_message(self, controller, panel: Optional[dict[str, object]] = None) -> str:
        if controller is None or not controller.carpeta:
            return self.t("library.empty.no_folder")
        if not controller.archivos:
            return self.t("library.empty.no_audio")
        query = ""
        filter_mode = FilterMode.ALL
        if panel:
            query = self.panel_search_query(panel)
            filter_mode = panel.get("filter_mode", FilterMode.ALL)
        if query or filter_mode != FilterMode.ALL:
            return self.t("library.empty.no_results")
        return self.t("library.empty.no_audio")

    def song_display_name(self, controller, filename: str) -> str:
        fallback = self.short_name(filename)
        if controller is None:
            return fallback
        cached = controller.get_track_info(filename)
        metadata = cached.metadata if cached else {}
        title = str(metadata.get("title", "") or "").strip() or fallback
        artist = str(metadata.get("artist", "") or "").strip()
        if artist and artist.lower() not in title.lower():
            return f"{artist} - {title}"
        return title

    def issue_keys(self, controller, filename: str, duplicate_set: set[str]) -> list[str]:
        if controller is None:
            return []
        issue_getter = getattr(controller, "issue_keys_for_file", None)
        if issue_getter is None:
            return []
        return list(issue_getter(filename, duplicate_set))

    def display_name_with_badges(
        self,
        display_name: str,
        issue_keys: list[str],
        *,
        quality_badge: str = "",
    ) -> str:
        badges: list[str] = []
        metadata_issues = {"missing_artist", "missing_album", "missing_year", "missing_track"}
        if any(issue in metadata_issues for issue in issue_keys):
            badges.append("[META]")
        if "missing_cover" in issue_keys:
            badges.append("[COVER]")
        if "duplicate" in issue_keys:
            badges.append("[DUP]")
        if "low_bitrate" in issue_keys:
            badges.append("[LOW]")
        if "possibly_corrupt" in issue_keys:
            badges.append("[ERR]")
        if quality_badge:
            badges.append(f"[{quality_badge}]")
        if not badges:
            return display_name
        return f"{display_name} {' '.join(badges)}"

    def quality_badge(self, controller, filename: str) -> str:
        if controller is None:
            return ""
        cached = controller.get_track_info(filename)
        quality = cached.audio_quality if cached else {}
        try:
            bitrate = int(quality.get("bitrate_kbps", 0) or 0)
        except (TypeError, ValueError):
            return ""
        return f"{bitrate} kbps" if bitrate > 0 else ""

    def count_file_rows(self, tree) -> int:
        return sum(
            1
            for item_id in tree.get_children()
            if self.filename_from_item(tree.item(item_id))
        )

    def visible_filenames(self, tree) -> list[str]:
        return [
            filename
            for item_id in tree.get_children()
            if (filename := self.filename_from_item(tree.item(item_id)))
        ]

    def panel_search_query(self, panel: dict[str, object]) -> str:
        if panel.get("search_placeholder_active"):
            return ""
        search_var = panel.get("search_var")
        return str(search_var.get()).strip() if search_var is not None else ""

    def update_result_label(self, panel: dict[str, object]) -> None:
        controller = panel["controller"]
        tree = panel["tree"]
        label = panel["result_label"]
        label.configure(
            text=self.t(
                "filter.results",
                shown=self.count_file_rows(tree),
                total=len(controller.archivos),
            )
        )

    def apply_tree_colors(self, tree) -> None:
        colors = self.theme_colors()
        if isinstance(tree, LibraryListbox):
            tree.configure(
                background=colors["surface"],
                foreground=colors["text"],
                selectbackground=colors["highlight"],
                selectforeground=colors["highlight_text"],
            )
        tree.tag_configure("odd_row", background=colors["surface"], foreground=colors["text"])
        tree.tag_configure("even_row", background=colors["surface_alt"], foreground=colors["text"])
        tree.tag_configure("placeholder", background=colors["surface"], foreground=colors["text_secondary"])
        tree.tag_configure("issue_missing_artist", foreground=colors["warning"])
        tree.tag_configure("issue_missing_album", foreground=colors["warning"])
        tree.tag_configure("issue_missing_year", foreground=colors["warning"])
        tree.tag_configure("issue_missing_track", foreground=colors["warning"])
        tree.tag_configure("issue_missing_cover", foreground=colors["text_secondary"])
        tree.tag_configure("issue_duplicate", foreground=colors["error"])
        tree.tag_configure("issue_low_bitrate", foreground=colors["warning"])
        tree.tag_configure("issue_possibly_corrupt", foreground=colors["error"])

    def apply_empty_state_colors(self, panel: dict[str, object]) -> None:
        colors = self.theme_colors()
        frame = panel.get("empty_state_frame")
        label = panel.get("empty_state_label")
        if frame is not None:
            frame.configure(background=colors["surface"])
            for child in frame.winfo_children():
                self._set_child_background(child, colors["surface"])
        if label is not None:
            label.configure(background=colors["surface"], foreground=colors["text_secondary"])

    def _show_empty_state(self, panel: Optional[dict[str, object]], message: str) -> None:
        if not panel:
            return
        frame = panel.get("empty_state_frame")
        label = panel.get("empty_state_label")
        if frame is None or label is None:
            return
        label.configure(text=message)
        self.apply_empty_state_colors(panel)
        frame.grid()
        frame.tkraise()

    def _hide_empty_state(self, panel: Optional[dict[str, object]]) -> None:
        if not panel:
            return
        frame = panel.get("empty_state_frame")
        if frame is not None:
            frame.grid_remove()

    def _set_child_background(self, widget, color: str) -> None:
        try:
            widget.configure(background=color)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._set_child_background(child, color)
