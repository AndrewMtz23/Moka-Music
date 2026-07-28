import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
    analyze_audio_quality: Callable[[], None]
    detect_advanced_duplicates: Callable[[], None]
    validate_audio_files: Callable[[], None]
    convert_audio: Callable[[], None]
    rename_files_by_template: Callable[[], None]
    organize_files_by_folders: Callable[[], None]
    validate_playlist: Callable[[], None]
    generate_smart_playlist: Callable[[], None]
    show_backup_history: Callable[[], None]
    undo_last_metadata_change: Callable[[], None]
    undo: Callable[[], None]
    redo: Callable[[], None]
    change_language: Callable[[str], None]
    get_current_language: Callable[[], str]
    detect_system_language: Callable[[], None]
    report_missing_translations: Callable[[], None]
    show_quick_guide: Callable[[], None]
    show_shortcuts: Callable[[], None]
    view_logs: Callable[[], None]
    open_backup_folder: Callable[[], None]
    show_system_diagnostics: Callable[[], None]
    show_about: Callable[[], None]


class MenuController:
    def __init__(
        self,
        root,
        translator: Callable[..., str],
        callbacks: MenuCallbacks,
        theme_colors: dict[str, str] | None = None,
    ) -> None:
        self.root = root
        self.t = translator
        self.callbacks = callbacks
        self.theme_colors = dict(theme_colors or {})
        self.menu_bar_frame = None

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def set_theme_colors(self, theme_colors: dict[str, str]) -> None:
        self.theme_colors = dict(theme_colors)

    def build(self) -> tk.Menu:
        menubar = self._menu(self.root)

        file_menu = self._menu(menubar, tearoff=0)
        file_menu.add_command(label=self.t("menu.open_main_folder"), command=self.callbacks.open_main_folder)
        file_menu.add_command(label=self.t("menu.open_incoming_folder"), command=self.callbacks.open_incoming_folder)
        file_menu.add_cascade(label=self.t("menu.open_recent"), menu=self._build_recent_menu(file_menu))
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.export_playlist"), command=self.callbacks.export_playlist)
        file_menu.add_command(
            label=self.t("menu.export_library_view_json"), command=self.callbacks.export_library_view_json
        )
        file_menu.add_command(label=self.t("menu.export_selected"), command=self.callbacks.export_selected)
        file_menu.add_command(label=self.t("menu.export_library_report"), command=self.callbacks.export_library_report)
        file_menu.add_command(label=self.t("menu.import_metadata_json"), command=self.callbacks.import_metadata_json)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.select_cover"), command=self.callbacks.select_cover)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.exit"), command=self.callbacks.exit_app)
        menubar.add_cascade(label=self.t("menu.file"), menu=file_menu)

        edit_menu = self._menu(menubar, tearoff=0)
        edit_menu.add_command(label=self.t("menu.select_all"), accelerator="Ctrl+A", command=self.callbacks.select_all)
        edit_menu.add_command(label=self.t("menu.deselect_all"), command=self.callbacks.deselect_all)
        edit_menu.add_command(label=self.t("menu.invert_selection"), command=self.callbacks.invert_selection)
        edit_menu.add_separator()
        edit_menu.add_command(label=self.t("menu.undo"), accelerator="Ctrl+Z", command=self.callbacks.undo)
        edit_menu.add_command(label=self.t("menu.redo"), accelerator="Ctrl+Y", command=self.callbacks.redo)
        menubar.add_cascade(label=self.t("menu.edit"), menu=edit_menu)

        theme_menu = self._menu(menubar, tearoff=0)
        theme_menu.add_command(label=self.t("menu.customize_theme"), command=self.callbacks.show_theme_settings)
        theme_menu.add_command(label=self.t("menu.save_theme_as"), command=self.callbacks.save_current_theme)
        theme_menu.add_command(label=self.t("menu.manage_themes"), command=self.callbacks.manage_custom_themes)
        theme_menu.add_separator()
        theme_menu.add_command(label=self.t("menu.import_theme"), command=self.callbacks.import_theme)
        theme_menu.add_command(label=self.t("menu.export_theme"), command=self.callbacks.export_theme)
        theme_menu.add_separator()
        theme_menu.add_command(
            label=self.t("menu.fullscreen"), accelerator="F11", command=self.callbacks.toggle_fullscreen
        )
        menubar.add_cascade(label=self.t("menu.theme"), menu=theme_menu)

        tools_menu = self._menu(menubar, tearoff=0)
        tools_menu.add_command(label=self.t("menu.quality_report"), command=self.callbacks.show_quality_report)
        tools_menu.add_command(label=self.t("menu.library_stats"), command=self.callbacks.show_library_stats)
        tools_menu.add_command(label=self.t("menu.library_compare"), command=self.callbacks.show_library_comparison)
        tools_menu.add_command(label=self.t("menu.playback_history"), command=self.callbacks.show_playback_history)
        metadata_menu = self._menu(tools_menu, tearoff=0)
        metadata_menu.add_command(
            label=self.t("menu.complete_metadata_online"), command=self.callbacks.complete_metadata_online
        )
        metadata_menu.add_command(label=self.t("menu.find_missing_covers"), command=self.callbacks.find_missing_covers)
        metadata_menu.add_command(label=self.t("menu.normalize_metadata"), command=self.callbacks.normalize_metadata)
        metadata_menu.add_command(
            label=self.t("menu.search_replace_metadata"), command=self.callbacks.search_replace_metadata
        )
        tools_menu.add_cascade(label=self.t("menu.metadata_tools"), menu=metadata_menu)
        audio_menu = self._menu(tools_menu, tearoff=0)
        audio_menu.add_command(label=self.t("menu.analyze_audio_quality"), command=self.callbacks.analyze_audio_quality)
        audio_menu.add_command(
            label=self.t("menu.detect_advanced_duplicates"), command=self.callbacks.detect_advanced_duplicates
        )
        audio_menu.add_command(label=self.t("menu.validate_audio_files"), command=self.callbacks.validate_audio_files)
        audio_menu.add_separator()
        audio_menu.add_command(label=self.t("menu.convert_audio"), command=self.callbacks.convert_audio)
        tools_menu.add_cascade(label=self.t("menu.audio_tools"), menu=audio_menu)
        organization_menu = self._menu(tools_menu, tearoff=0)
        organization_menu.add_command(
            label=self.t("menu.rename_by_template"), command=self.callbacks.rename_files_by_template
        )
        organization_menu.add_command(
            label=self.t("menu.organize_files"), command=self.callbacks.organize_files_by_folders
        )
        organization_menu.add_separator()
        organization_menu.add_command(label=self.t("menu.validate_playlist"), command=self.callbacks.validate_playlist)
        organization_menu.add_command(
            label=self.t("menu.generate_smart_playlist"), command=self.callbacks.generate_smart_playlist
        )
        tools_menu.add_cascade(label=self.t("menu.organization_tools"), menu=organization_menu)
        tools_menu.add_command(label=self.t("menu.backup_history"), command=self.callbacks.show_backup_history)
        tools_menu.add_command(
            label=self.t("menu.undo_last_metadata"), command=self.callbacks.undo_last_metadata_change
        )
        menubar.add_cascade(label=self.t("menu.tools"), menu=tools_menu)

        language_menu = self._menu(menubar, tearoff=0)
        language_menu.add_command(
            label=self._language_label("menu.language_es", "es"), command=lambda: self.callbacks.change_language("es")
        )
        language_menu.add_command(
            label=self._language_label("menu.language_en", "en"), command=lambda: self.callbacks.change_language("en")
        )
        language_menu.add_separator()
        language_menu.add_command(
            label=self.t("menu.detect_system_language"), command=self.callbacks.detect_system_language
        )
        language_menu.add_command(
            label=self.t("menu.report_missing_translations"), command=self.callbacks.report_missing_translations
        )
        menubar.add_cascade(label=self.t("menu.language"), menu=language_menu)

        help_menu = self._menu(menubar, tearoff=0)
        help_menu.add_command(label=self.t("menu.quick_guide"), command=self.callbacks.show_quick_guide)
        help_menu.add_command(label=self.t("menu.shortcuts"), command=self.callbacks.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label=self.t("menu.view_logs"), command=self.callbacks.view_logs)
        help_menu.add_command(label=self.t("menu.open_backup_folder"), command=self.callbacks.open_backup_folder)
        help_menu.add_command(label=self.t("menu.system_diagnostics"), command=self.callbacks.show_system_diagnostics)
        help_menu.add_separator()
        help_menu.add_command(label=self.t("menu.about"), command=self.callbacks.show_about)
        menubar.add_cascade(label=self.t("menu.help"), menu=help_menu)

        return menubar

    def _build_recent_menu(self, parent_menu) -> tk.Menu:
        recent_menu = self._menu(parent_menu, tearoff=0)
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
        try:
            self.root.config(menu="")
        except tk.TclError:
            pass
        self._destroy_menu_bar()
        self.menu_bar_frame = self.build_menu_bar()
        pack_options = {"side": "top", "fill": "x"}
        packed_children = self.root.pack_slaves()
        if packed_children:
            pack_options["before"] = packed_children[0]
        self.menu_bar_frame.pack(**pack_options)

    def build_menu_bar(self) -> tk.Frame:
        colors = self._normalized_colors()
        frame = tk.Frame(
            self.root,
            background=colors["surface"],
            borderwidth=0,
            highlightthickness=0,
        )
        self._add_menu_button(frame, "menu.file", self._build_file_menu)
        self._add_menu_button(frame, "menu.edit", self._build_edit_menu)
        self._add_menu_button(frame, "menu.theme", self._build_theme_menu)
        self._add_menu_button(frame, "menu.tools", self._build_tools_menu)
        self._add_menu_button(frame, "menu.language", self._build_language_menu)
        self._add_menu_button(frame, "menu.help", self._build_help_menu)
        return frame

    def _destroy_menu_bar(self) -> None:
        if self.menu_bar_frame is not None:
            try:
                self.menu_bar_frame.destroy()
            except tk.TclError:
                pass
            self.menu_bar_frame = None

    def _add_menu_button(self, parent: tk.Frame, label_key: str, builder: Callable[[object], tk.Menu]) -> tk.Menubutton:
        colors = self._normalized_colors()
        button_options = {
            "text": self.t(label_key),
            "background": colors["surface"],
            "foreground": colors["text"],
            "activebackground": colors["surface_alt"],
            "activeforeground": colors["text"],
            "borderwidth": 0,
            "relief": "flat",
            "padx": 8,
            "pady": 3,
        }
        menu_font = self.root.option_get("Menu.Font", "")
        if menu_font:
            button_options["font"] = menu_font
        button = tk.Menubutton(parent, **button_options)
        button.pack(side="left")
        menu = builder(button)
        button.configure(menu=menu)
        return button

    def _build_file_menu(self, parent) -> tk.Menu:
        file_menu = self._menu(parent, tearoff=0)
        file_menu.add_command(label=self.t("menu.open_main_folder"), command=self.callbacks.open_main_folder)
        file_menu.add_command(label=self.t("menu.open_incoming_folder"), command=self.callbacks.open_incoming_folder)
        file_menu.add_cascade(label=self.t("menu.open_recent"), menu=self._build_recent_menu(file_menu))
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.export_playlist"), command=self.callbacks.export_playlist)
        file_menu.add_command(
            label=self.t("menu.export_library_view_json"), command=self.callbacks.export_library_view_json
        )
        file_menu.add_command(label=self.t("menu.export_selected"), command=self.callbacks.export_selected)
        file_menu.add_command(label=self.t("menu.export_library_report"), command=self.callbacks.export_library_report)
        file_menu.add_command(label=self.t("menu.import_metadata_json"), command=self.callbacks.import_metadata_json)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.select_cover"), command=self.callbacks.select_cover)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.exit"), command=self.callbacks.exit_app)
        return file_menu

    def _build_edit_menu(self, parent) -> tk.Menu:
        edit_menu = self._menu(parent, tearoff=0)
        edit_menu.add_command(label=self.t("menu.select_all"), accelerator="Ctrl+A", command=self.callbacks.select_all)
        edit_menu.add_command(label=self.t("menu.deselect_all"), command=self.callbacks.deselect_all)
        edit_menu.add_command(label=self.t("menu.invert_selection"), command=self.callbacks.invert_selection)
        edit_menu.add_separator()
        edit_menu.add_command(label=self.t("menu.undo"), accelerator="Ctrl+Z", command=self.callbacks.undo)
        edit_menu.add_command(label=self.t("menu.redo"), accelerator="Ctrl+Y", command=self.callbacks.redo)
        return edit_menu

    def _build_theme_menu(self, parent) -> tk.Menu:
        theme_menu = self._menu(parent, tearoff=0)
        theme_menu.add_command(label=self.t("menu.customize_theme"), command=self.callbacks.show_theme_settings)
        theme_menu.add_command(label=self.t("menu.save_theme_as"), command=self.callbacks.save_current_theme)
        theme_menu.add_command(label=self.t("menu.manage_themes"), command=self.callbacks.manage_custom_themes)
        theme_menu.add_separator()
        theme_menu.add_command(label=self.t("menu.import_theme"), command=self.callbacks.import_theme)
        theme_menu.add_command(label=self.t("menu.export_theme"), command=self.callbacks.export_theme)
        theme_menu.add_separator()
        theme_menu.add_command(
            label=self.t("menu.fullscreen"), accelerator="F11", command=self.callbacks.toggle_fullscreen
        )
        return theme_menu

    def _build_tools_menu(self, parent) -> tk.Menu:
        tools_menu = self._menu(parent, tearoff=0)
        tools_menu.add_command(label=self.t("menu.quality_report"), command=self.callbacks.show_quality_report)
        tools_menu.add_command(label=self.t("menu.library_stats"), command=self.callbacks.show_library_stats)
        tools_menu.add_command(label=self.t("menu.library_compare"), command=self.callbacks.show_library_comparison)
        tools_menu.add_command(label=self.t("menu.playback_history"), command=self.callbacks.show_playback_history)
        metadata_menu = self._menu(tools_menu, tearoff=0)
        metadata_menu.add_command(
            label=self.t("menu.complete_metadata_online"), command=self.callbacks.complete_metadata_online
        )
        metadata_menu.add_command(label=self.t("menu.find_missing_covers"), command=self.callbacks.find_missing_covers)
        metadata_menu.add_command(label=self.t("menu.normalize_metadata"), command=self.callbacks.normalize_metadata)
        metadata_menu.add_command(
            label=self.t("menu.search_replace_metadata"), command=self.callbacks.search_replace_metadata
        )
        tools_menu.add_cascade(label=self.t("menu.metadata_tools"), menu=metadata_menu)
        audio_menu = self._menu(tools_menu, tearoff=0)
        audio_menu.add_command(label=self.t("menu.analyze_audio_quality"), command=self.callbacks.analyze_audio_quality)
        audio_menu.add_command(
            label=self.t("menu.detect_advanced_duplicates"), command=self.callbacks.detect_advanced_duplicates
        )
        audio_menu.add_command(label=self.t("menu.validate_audio_files"), command=self.callbacks.validate_audio_files)
        audio_menu.add_separator()
        audio_menu.add_command(label=self.t("menu.convert_audio"), command=self.callbacks.convert_audio)
        tools_menu.add_cascade(label=self.t("menu.audio_tools"), menu=audio_menu)
        organization_menu = self._menu(tools_menu, tearoff=0)
        organization_menu.add_command(
            label=self.t("menu.rename_by_template"), command=self.callbacks.rename_files_by_template
        )
        organization_menu.add_command(
            label=self.t("menu.organize_files"), command=self.callbacks.organize_files_by_folders
        )
        organization_menu.add_separator()
        organization_menu.add_command(label=self.t("menu.validate_playlist"), command=self.callbacks.validate_playlist)
        organization_menu.add_command(
            label=self.t("menu.generate_smart_playlist"), command=self.callbacks.generate_smart_playlist
        )
        tools_menu.add_cascade(label=self.t("menu.organization_tools"), menu=organization_menu)
        tools_menu.add_command(label=self.t("menu.backup_history"), command=self.callbacks.show_backup_history)
        tools_menu.add_command(
            label=self.t("menu.undo_last_metadata"), command=self.callbacks.undo_last_metadata_change
        )
        return tools_menu

    def _build_language_menu(self, parent) -> tk.Menu:
        language_menu = self._menu(parent, tearoff=0)
        language_menu.add_command(
            label=self._language_label("menu.language_es", "es"), command=lambda: self.callbacks.change_language("es")
        )
        language_menu.add_command(
            label=self._language_label("menu.language_en", "en"), command=lambda: self.callbacks.change_language("en")
        )
        language_menu.add_separator()
        language_menu.add_command(
            label=self.t("menu.detect_system_language"), command=self.callbacks.detect_system_language
        )
        language_menu.add_command(
            label=self.t("menu.report_missing_translations"), command=self.callbacks.report_missing_translations
        )
        return language_menu

    def _build_help_menu(self, parent) -> tk.Menu:
        help_menu = self._menu(parent, tearoff=0)
        help_menu.add_command(label=self.t("menu.quick_guide"), command=self.callbacks.show_quick_guide)
        help_menu.add_command(label=self.t("menu.shortcuts"), command=self.callbacks.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label=self.t("menu.view_logs"), command=self.callbacks.view_logs)
        help_menu.add_command(label=self.t("menu.open_backup_folder"), command=self.callbacks.open_backup_folder)
        help_menu.add_command(label=self.t("menu.system_diagnostics"), command=self.callbacks.show_system_diagnostics)
        help_menu.add_separator()
        help_menu.add_command(label=self.t("menu.about"), command=self.callbacks.show_about)
        return help_menu

    def _language_label(self, label_key: str, language: str) -> str:
        label = self.t(label_key)
        return f"✓ {label}" if self.callbacks.get_current_language() == language else label

    def _menu(self, parent, *, tearoff: int | None = None) -> tk.Menu:
        options = self._menu_options()
        if tearoff is not None:
            options["tearoff"] = tearoff
        return tk.Menu(parent, **options)

    def _menu_options(self) -> dict[str, object]:
        colors = self._normalized_colors()
        return {
            "background": colors["surface"],
            "foreground": colors["text"],
            "activebackground": colors["primary"],
            "activeforeground": colors["button_text"],
            "disabledforeground": colors["disabled"],
            "selectcolor": colors["primary"],
            "borderwidth": 0,
            "relief": "flat",
        }

    def _normalized_colors(self) -> dict[str, str]:
        colors = self.theme_colors
        return {
            "surface": colors.get("surface", "#ffffff"),
            "surface_alt": colors.get("surface_alt", "#eeeeee"),
            "text": colors.get("text", "#111111"),
            "primary": colors.get("primary", "#111111"),
            "button_text": colors.get("button_text", "#ffffff"),
            "disabled": colors.get("disabled", "#a1a1a1"),
        }
