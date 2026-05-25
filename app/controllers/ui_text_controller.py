from typing import Callable

from ..models import FilterMode


TEXT_WIDGET_KEYS: dict[str, tuple[str, str]] = {
    "main_library_frame": ("text", "panel.main_library"),
    "incoming_library_frame": ("text", "panel.incoming_library"),
    "main_select_folder": ("text", "button.select_folder"),
    "incoming_select_folder": ("text", "button.select_folder"),
    "main_close_folder": ("text", "button.close_folder"),
    "incoming_close_folder": ("text", "button.close_folder"),
    "main_search_label": ("text", "search.label"),
    "incoming_search_label": ("text", "search.label"),
    "main_filter_label": ("text", "filter.label"),
    "incoming_filter_label": ("text", "filter.label"),
    "add_song_button": ("text", "button.add_song"),
    "move_to_main_button": ("text", "button.move_to_main"),
    "metadata_frame": ("text", "metadata.global"),
    "artist_label": ("text", "metadata.artist"),
    "album_artist_label": ("text", "metadata.album_artist"),
    "genre_label": ("text", "metadata.genre"),
    "album_label": ("text", "metadata.album"),
    "year_label": ("text", "metadata.year"),
    "comment_label": ("text", "metadata.comment"),
    "apply_selected_button": ("text", "button.apply_selected"),
    "batch_edit_button": ("text", "button.batch_edit"),
    "apply_all_button": ("text", "button.apply_all"),
    "clear_fields_button": ("text", "button.clear_fields"),
    "quick_actions_frame": ("text", "quick_actions.title"),
    "quick_remove_feat_button": ("text", "quick_actions.remove_feat"),
    "quick_remove_parentheses_button": ("text", "quick_actions.remove_parentheses"),
    "quick_title_only_button": ("text", "quick_actions.title_only"),
    "quick_title_from_file_button": ("text", "quick_actions.title_from_file"),
    "quick_number_tracks_button": ("text", "quick_actions.number_tracks"),
    "quick_insert_position_button": ("text", "quick_actions.insert_position"),
    "quick_copy_artist_button": ("text", "quick_actions.copy_artist"),
    "quick_rename_metadata_button": ("text", "quick_actions.rename_from_metadata"),
    "quick_auto_cover_button": ("text", "quick_actions.auto_cover"),
    "incoming_global_metadata_button": ("text", "button.global_metadata"),
    "incoming_prepare_folder_button": ("text", "button.prepare_folder"),
    "preset_label": ("text", "presets.label"),
    "apply_preset_button": ("text", "presets.apply"),
    "create_preset_button": ("text", "presets.create"),
    "delete_preset_button": ("text", "presets.delete"),
}


class UiTextController:
    def __init__(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def refresh_text_widgets(self, widgets: dict[str, object]) -> None:
        for name, (option, key) in TEXT_WIDGET_KEYS.items():
            widget = widgets.get(name)
            if widget is not None:
                widget.configure(**{option: self.t(key)})

    def refresh_tree_headings(self, tree) -> None:
        tree.heading("#0", text=self.t("tree.song_name"))
        tree.heading("path", text=self.t("tree.file_path"))

    def refresh_sort_widgets(
        self,
        sort_widgets: list[tuple[object, object, object]],
        *,
        sort_options: list[str],
        sort_text_for_mode: Callable[[object], str],
    ) -> None:
        for sort_menu, sort_var, controller in sort_widgets:
            sort_menu.configure(values=sort_options)
            sort_var.set(sort_text_for_mode(controller._sort_mode))

    def refresh_library_panels(
        self,
        panels: list[dict[str, object]],
        *,
        filter_options: list[str],
        filter_text_for_mode: Callable[[FilterMode], str],
        refresh_search_placeholder: Callable[[dict[str, object]], None],
        apply_tree_colors: Callable[[object], None],
        refresh_library_tree: Callable[[object, object], None],
    ) -> None:
        for panel in panels:
            filter_var = panel["filter_var"]
            filter_menu = panel["filter_menu"]
            current_mode = panel.get("filter_mode", FilterMode.ALL)
            filter_menu.configure(values=filter_options)
            filter_var.set(filter_text_for_mode(current_mode))
            refresh_search_placeholder(panel)
            apply_tree_colors(panel["tree"])
            refresh_library_tree(panel["controller"], panel["tree"])
