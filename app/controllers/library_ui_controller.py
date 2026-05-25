import os
from typing import Callable, Optional

from ..models import FilterMode, SortMode
from ..ui_helpers.widgets import LibraryListbox


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
        for index, filename in enumerate(files, start=1):
            display_name = self.song_display_name(controller, filename)
            full_path = os.path.join(controller.carpeta, filename) if controller and controller.carpeta else filename
            row_tag = "even_row" if index % 2 == 0 else "odd_row"
            tree.insert("", "end", text=display_name, values=(index, full_path), tags=(filename, row_tag))
        if not files:
            tree.insert(
                "",
                "end",
                text=self.empty_library_message(controller, panel),
                values=("", ""),
                tags=("placeholder",),
            )
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
