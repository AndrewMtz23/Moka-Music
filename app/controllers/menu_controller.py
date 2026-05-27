from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import tkinter as tk

RecentFolder = dict[str, str]


@dataclass
class MenuCallbacks:
    open_main_folder: Callable[[], None]
    open_incoming_folder: Callable[[], None]
    get_recent_folders: Callable[[], list[RecentFolder]]
    open_recent_folder: Callable[[RecentFolder], None]
    clear_recent_folders: Callable[[], None]
    export_playlist: Callable[[], None]
    export_library_view_json: Callable[[], None]
    export_selected: Callable[[], None]
    export_library_report: Callable[[], None]
    import_metadata_json: Callable[[], None]
    select_cover: Callable[[], None]
    exit_app: Callable[[], None]
    change_theme: Callable[[str], None]
    show_theme_settings: Callable[[], None]
    save_current_theme: Callable[[], None]
    manage_custom_themes: Callable[[], None]
    import_theme: Callable[[], None]
    export_theme: Callable[[], None]
    toggle_fullscreen: Callable[[], None]
    select_all: Callable[[], None]
    deselect_all: Callable[[], None]
    invert_selection: Callable[[], None]
    show_quality_report: Callable[[], None]
    show_library_stats: Callable[[], None]
    show_library_comparison: Callable[[], None]
    show_playback_history: Callable[[], None]
    complete_metadata_online: Callable[[], None]
    find_missing_covers: Callable[[], None]
    normalize_metadata: Callable[[], None]
    search_replace_metadata: Callable[[], None]
    convert_audio: Callable[[], None]
    show_backup_history: Callable[[], None]
    undo_last_metadata_change: Callable[[], None]
    undo: Callable[[], None]
    redo: Callable[[], None]
    change_language: Callable[[str], None]
    show_about: Callable[[], None]


class MenuController:
    def __init__(self, root, translator: Callable[..., str], callbacks: MenuCallbacks) -> None:
        self.root = root
        self.t = translator
        self.callbacks = callbacks

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def build(self) -> tk.Menu:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=self.t("menu.open_main_folder"), command=self.callbacks.open_main_folder)
        file_menu.add_command(label=self.t("menu.open_incoming_folder"), command=self.callbacks.open_incoming_folder)
        file_menu.add_cascade(label=self.t("menu.open_recent"), menu=self._build_recent_menu(file_menu))
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.export_playlist"), command=self.callbacks.export_playlist)
        file_menu.add_command(label=self.t("menu.export_library_view_json"), command=self.callbacks.export_library_view_json)
        file_menu.add_command(label=self.t("menu.export_selected"), command=self.callbacks.export_selected)
        file_menu.add_command(label=self.t("menu.export_library_report"), command=self.callbacks.export_library_report)
        file_menu.add_command(label=self.t("menu.import_metadata_json"), command=self.callbacks.import_metadata_json)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.select_cover"), command=self.callbacks.select_cover)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.exit"), command=self.callbacks.exit_app)
        menubar.add_cascade(label=self.t("menu.file"), menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label=self.t("menu.select_all"), accelerator="Ctrl+A", command=self.callbacks.select_all)
        edit_menu.add_command(label=self.t("menu.deselect_all"), command=self.callbacks.deselect_all)
        edit_menu.add_command(label=self.t("menu.invert_selection"), command=self.callbacks.invert_selection)
        edit_menu.add_separator()
        edit_menu.add_command(label=self.t("menu.undo"), accelerator="Ctrl+Z", command=self.callbacks.undo)
        edit_menu.add_command(label=self.t("menu.redo"), accelerator="Ctrl+Y", command=self.callbacks.redo)
        menubar.add_cascade(label=self.t("menu.edit"), menu=edit_menu)

        theme_menu = tk.Menu(menubar, tearoff=0)
        theme_menu.add_command(label=self.t("menu.customize_theme"), command=self.callbacks.show_theme_settings)
        theme_menu.add_command(label=self.t("menu.save_theme_as"), command=self.callbacks.save_current_theme)
        theme_menu.add_command(label=self.t("menu.manage_themes"), command=self.callbacks.manage_custom_themes)
        theme_menu.add_separator()
        theme_menu.add_command(label=self.t("menu.import_theme"), command=self.callbacks.import_theme)
        theme_menu.add_command(label=self.t("menu.export_theme"), command=self.callbacks.export_theme)
        theme_menu.add_separator()
        theme_menu.add_command(label=self.t("menu.fullscreen"), accelerator="F11", command=self.callbacks.toggle_fullscreen)
        menubar.add_cascade(label=self.t("menu.theme"), menu=theme_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label=self.t("menu.quality_report"), command=self.callbacks.show_quality_report)
        tools_menu.add_command(label=self.t("menu.library_stats"), command=self.callbacks.show_library_stats)
        tools_menu.add_command(label=self.t("menu.library_compare"), command=self.callbacks.show_library_comparison)
        tools_menu.add_command(label=self.t("menu.playback_history"), command=self.callbacks.show_playback_history)
        metadata_menu = tk.Menu(tools_menu, tearoff=0)
        metadata_menu.add_command(label=self.t("menu.complete_metadata_online"), command=self.callbacks.complete_metadata_online)
        metadata_menu.add_command(label=self.t("menu.find_missing_covers"), command=self.callbacks.find_missing_covers)
        metadata_menu.add_command(label=self.t("menu.normalize_metadata"), command=self.callbacks.normalize_metadata)
        metadata_menu.add_command(label=self.t("menu.search_replace_metadata"), command=self.callbacks.search_replace_metadata)
        tools_menu.add_cascade(label=self.t("menu.metadata_tools"), menu=metadata_menu)
        tools_menu.add_command(label=self.t("menu.convert_audio"), command=self.callbacks.convert_audio)
        tools_menu.add_command(label=self.t("menu.backup_history"), command=self.callbacks.show_backup_history)
        tools_menu.add_command(label=self.t("menu.undo_last_metadata"), command=self.callbacks.undo_last_metadata_change)
        menubar.add_cascade(label=self.t("menu.tools"), menu=tools_menu)

        language_menu = tk.Menu(menubar, tearoff=0)
        language_menu.add_command(label=self.t("menu.language_es"), command=lambda: self.callbacks.change_language("es"))
        language_menu.add_command(label=self.t("menu.language_en"), command=lambda: self.callbacks.change_language("en"))
        menubar.add_cascade(label=self.t("menu.language"), menu=language_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=self.t("menu.about"), command=self.callbacks.show_about)
        menubar.add_cascade(label=self.t("menu.help"), menu=help_menu)

        return menubar

    def _build_recent_menu(self, parent_menu) -> tk.Menu:
        recent_menu = tk.Menu(parent_menu, tearoff=0)
        recent_folders = self.callbacks.get_recent_folders()
        if not recent_folders:
            recent_menu.add_command(label=self.t("menu.no_recent_folders"), state="disabled")
            return recent_menu

        for item in recent_folders:
            recent_menu.add_command(
                label=self._recent_folder_label(item),
                command=lambda recent=item: self.callbacks.open_recent_folder(recent),
            )
        recent_menu.add_separator()
        recent_menu.add_command(label=self.t("menu.clear_recent_folders"), command=self.callbacks.clear_recent_folders)
        return recent_menu

    def _recent_folder_label(self, item: RecentFolder) -> str:
        folder = item.get("folder", "")
        target = item.get("target", "main")
        target_label = self.t("panel.incoming_library") if target == "incoming" else self.t("panel.main_library")
        folder_name = Path(folder).name or folder
        return f"{target_label}: {folder_name}"

    def install(self) -> None:
        self.root.config(menu=self.build())
