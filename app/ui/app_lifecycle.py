from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from ..constants import APP_NAME, UISettings
from ..controllers.config_controller import AppConfig, ConfigController
from ..controllers.cover_controller import CoverController
from ..controllers.drop_controller import DropController
from ..controllers.library_ui_controller import LibraryUiController
from ..controllers.metadata_apply_controller import MetadataApplyController
from ..controllers.metadata_dialog_controller import MetadataDialogController
from ..controllers.menu_controller import MenuCallbacks, MenuController
from ..controllers.playback_selection_controller import PlaybackSelectionController
from ..controllers.playlist_workflow_controller import PlaylistWorkflowController
from ..controllers.rename_controller import RenameController
from ..controllers.selection_controller import SelectionController
from ..controllers.ui_text_controller import UiTextController
from ..i18n import normalize_language
from ..models import FilterMode, SortMode


class AppLifecycleMixin:
    """Window lifecycle, menu, config, theme, language, and controller accessors."""

    def _setup_window(self) -> None:
        width, height = UISettings.WINDOW_DEFAULT_SIZE
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(*UISettings.WINDOW_MIN_SIZE)
        try:
            icon_path = Path("assets") / "Moka.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _setup_main_menu(self) -> None:
        self._menu_controller().install()

    def _menu_controller(self) -> MenuController:
        callbacks = MenuCallbacks(
            open_main_folder=lambda: self._load_folder(self.controller_principal, self.tree_principal),
            open_incoming_folder=lambda: self._load_folder(self.controller_nueva, self.tree_nueva),
            select_cover=self._select_cover,
            exit_app=self._on_close,
            change_theme=self._change_theme,
            show_quality_report=self._show_quality_report,
            show_backup_history=self._show_backup_history,
            undo_last_metadata_change=self._undo_last_metadata_change,
            change_language=self._change_language,
            show_about=self._show_about,
        )
        if self.menu_controller is None:
            self.menu_controller = MenuController(self.root, self.t, callbacks)
        else:
            self.menu_controller.set_translator(self.t)
            self.menu_controller.callbacks = callbacks
        return self.menu_controller


    def _sort_options(self) -> list[str]:
        return [
            self.t("sort.manual"),
            self.t("sort.by_name"),
            self.t("sort.by_artist"),
            self.t("sort.by_album"),
            self.t("sort.by_track_number"),
            self.t("sort.by_duration"),
            self.t("sort.by_date"),
        ]

    def _filter_options(self) -> list[str]:
        return [
            self.t("filter.all"),
            self.t("filter.missing_artist"),
            self.t("filter.missing_album"),
            self.t("filter.missing_year"),
            self.t("filter.missing_track"),
            self.t("filter.missing_cover"),
            self.t("filter.duplicates"),
        ]

    def _filter_text_for_mode(self, mode: FilterMode) -> str:
        mapping = {
            FilterMode.ALL: self.t("filter.all"),
            FilterMode.MISSING_ARTIST: self.t("filter.missing_artist"),
            FilterMode.MISSING_ALBUM: self.t("filter.missing_album"),
            FilterMode.MISSING_YEAR: self.t("filter.missing_year"),
            FilterMode.MISSING_TRACK: self.t("filter.missing_track"),
            FilterMode.MISSING_COVER: self.t("filter.missing_cover"),
            FilterMode.DUPLICATES: self.t("filter.duplicates"),
        }
        return mapping.get(mode, self.t("filter.all"))

    def _filter_mode_from_text(self, value: str) -> FilterMode:
        mapping = {
            self.t("filter.all"): FilterMode.ALL,
            self.t("filter.missing_artist"): FilterMode.MISSING_ARTIST,
            self.t("filter.missing_album"): FilterMode.MISSING_ALBUM,
            self.t("filter.missing_year"): FilterMode.MISSING_YEAR,
            self.t("filter.missing_track"): FilterMode.MISSING_TRACK,
            self.t("filter.missing_cover"): FilterMode.MISSING_COVER,
            self.t("filter.duplicates"): FilterMode.DUPLICATES,
        }
        return mapping.get(value, FilterMode.ALL)

    def _sort_text_for_mode(self, mode: SortMode) -> str:
        mapping = {
            SortMode.MANUAL: self.t("sort.manual"),
            SortMode.FILENAME: self.t("sort.by_name"),
            SortMode.ARTIST: self.t("sort.by_artist"),
            SortMode.ALBUM: self.t("sort.by_album"),
            SortMode.TRACK_NUMBER: self.t("sort.by_track_number"),
            SortMode.DURATION: self.t("sort.by_duration"),
            SortMode.DATE_ADDED: self.t("sort.by_date"),
        }
        return mapping.get(mode, self.t("sort.by_name"))

    def _sort_mode_from_text(self, value: str) -> SortMode:
        mapping = {
            self.t("sort.manual"): SortMode.MANUAL,
            self.t("sort.by_name"): SortMode.FILENAME,
            self.t("sort.by_artist"): SortMode.ARTIST,
            self.t("sort.by_album"): SortMode.ALBUM,
            self.t("sort.by_track_number"): SortMode.TRACK_NUMBER,
            self.t("sort.by_duration"): SortMode.DURATION,
            self.t("sort.by_date"): SortMode.DATE_ADDED,
        }
        return mapping.get(value, SortMode.FILENAME)

    def _load_config(self) -> None:
        try:
            config = self._config_controller().load(default_language=self.current_language)
            self.current_theme = config.theme
            self._change_language(config.language)
            self._change_theme(self.current_theme)
            self.player.volume_scale.set(config.volume)
            self.player.set_playback_modes(
                repeat=config.repeat,
                shuffle=config.shuffle,
            )
            self.cleanup_presets = self._normalize_cleanup_presets(config.cleanup_presets)
            self._refresh_cleanup_preset_menu()

            if config.main_folder and Path(config.main_folder).exists():
                self._load_folder(self.controller_principal, self.tree_principal, folder=config.main_folder)
            if config.incoming_folder and Path(config.incoming_folder).exists():
                self._load_folder(self.controller_nueva, self.tree_nueva, folder=config.incoming_folder)
        except Exception as exc:
            self.logger.warning("Could not load config: %s", exc)
            self._change_theme("light")

    def _save_config(self) -> None:
        self._config_controller().save(
            AppConfig(
                theme=self.current_theme,
                language=self.current_language,
                volume=self.player.volume_scale.get(),
                repeat=self.player.repeat_enabled(),
                shuffle=self.player.shuffle_enabled(),
                main_folder=self.controller_principal.carpeta,
                incoming_folder=self.controller_nueva.carpeta,
                cleanup_presets=self.cleanup_presets,
            )
        )

    def _config_controller(self) -> ConfigController:
        if not hasattr(self, "config_controller"):
            self.config_controller = ConfigController()
        return self.config_controller

    def _show_about(self) -> None:
        messagebox.showinfo(
            self.t("dialog.about_title"),
            f"{APP_NAME}\n\n{self.t('about.body')}",
        )

    def _show_quality_report(self) -> None:
        sections: list[str] = []
        for name, controller in (
            (self.t("panel.main_library"), self.controller_principal),
            (self.t("panel.incoming_library"), self.controller_nueva),
        ):
            if not controller.archivos:
                continue
            report = controller.get_quality_report()
            issues = (
                report["missing_artist"]
                + report["missing_album"]
                + report["missing_year"]
                + report["missing_track"]
                + report["duplicate_tracks"]
            )
            lines = [
                self.t("quality.library", name=name),
                self.t("quality.total", count=report["total"]),
                self.t("quality.missing_artist", count=report["missing_artist"]),
                self.t("quality.missing_album", count=report["missing_album"]),
                self.t("quality.missing_year", count=report["missing_year"]),
                self.t("quality.missing_track", count=report["missing_track"]),
                self.t(
                    "quality.duplicates",
                    groups=report["duplicate_groups"],
                    tracks=report["duplicate_tracks"],
                ),
            ]
            if issues == 0:
                lines.append(self.t("quality.ok"))
            sections.append("\n".join(lines))

        if not sections:
            messagebox.showinfo(self.t("quality.title"), self.t("quality.empty"))
            return

        messagebox.showinfo(self.t("quality.title"), "\n\n".join(sections))

    def _change_theme(self, theme: str) -> None:
        self.current_theme = theme
        try:
            self.style_manager.set_theme(theme)
            for panel in self._library_panels:
                self._apply_tree_colors(panel["tree"])
        except Exception as exc:
            self.logger.error("Error changing theme to %s: %s", theme, exc)

    def _change_language(self, language: str) -> None:
        self.current_language = normalize_language(language)
        self.i18n.set_language(self.current_language)
        self.t = self.i18n.t
        self.file_handler.set_translator(self.t)
        self.song_actions.set_translator(self.t)
        self._backup_controller().set_translator(self.t)
        self._library_ui_controller().set_translator(self.t)
        self._metadata_dialog_controller().set_translator(self.t)
        self._ui_text_controller().set_translator(self.t)
        self.controller_principal.set_translator(self.t)
        self.controller_nueva.set_translator(self.t)
        if hasattr(self, "player"):
            self.player.set_translator(self.t)
        if hasattr(self, "preview"):
            self.preview.set_translator(self.t)
        self._refresh_static_texts()

    def _refresh_static_texts(self) -> None:
        self.root.title(self.t("app.window_title"))
        self._setup_main_menu()
        self._ui_text_controller().refresh_text_widgets(self._ui_text_widgets)
        if hasattr(self, "tree_principal"):
            self._ui_text_controller().refresh_tree_headings(self.tree_principal)
        if hasattr(self, "tree_nueva"):
            self._ui_text_controller().refresh_tree_headings(self.tree_nueva)
        self._ui_text_controller().refresh_sort_widgets(
            self._sort_widgets,
            sort_options=self._sort_options(),
            sort_text_for_mode=self._sort_text_for_mode,
        )
        self._ui_text_controller().refresh_library_panels(
            self._library_panels,
            filter_options=self._filter_options(),
            filter_text_for_mode=self._filter_text_for_mode,
            refresh_search_placeholder=self._refresh_search_placeholder,
            apply_tree_colors=self._apply_tree_colors,
            refresh_library_tree=self._refresh_library_tree,
        )
        self._refresh_cleanup_preset_menu()
        if hasattr(self, "global_metadata_toggle_button"):
            key = "button.back_to_libraries" if getattr(self, "_global_metadata_view_active", False) else "button.global_metadata"
            self.global_metadata_toggle_button.configure(text=self.t(key))

    def _install_search_placeholder(self, entry, variable) -> None:
        panel = self._get_library_panel_for_search(variable)
        if panel is None:
            return
        colors = self.style_manager.get_theme_colors()
        placeholder = self.t("search.placeholder")

        def show_placeholder() -> None:
            if variable.get():
                return
            panel["search_placeholder_active"] = True
            variable.set(placeholder)
            entry.configure(foreground=colors["text_secondary"])

        def hide_placeholder() -> None:
            if panel.get("search_placeholder_active"):
                panel["search_placeholder_active"] = False
                variable.set("")
                entry.configure(foreground=colors["text"])

        entry.bind("<FocusIn>", lambda _event: hide_placeholder(), add="+")
        entry.bind("<FocusOut>", lambda _event: show_placeholder(), add="+")
        show_placeholder()

    def _refresh_search_placeholder(self, panel: dict[str, object]) -> None:
        entry = panel.get("search_entry")
        variable = panel.get("search_var")
        if entry is None or variable is None:
            return
        colors = self.style_manager.get_theme_colors()
        if panel.get("search_placeholder_active"):
            variable.set(self.t("search.placeholder"))
            entry.configure(foreground=colors["text_secondary"])
        else:
            entry.configure(foreground=colors["text"])

    def _get_library_panel_for_search(self, variable) -> Optional[dict[str, object]]:
        return self._selection_controller().panel_for_search(self._library_panels, variable)


    def _selection_controller(self) -> SelectionController:
        if not hasattr(self, "selection_controller"):
            self.selection_controller = SelectionController(self._filename_from_tree_item)
        return self.selection_controller

    def _library_ui_controller(self) -> LibraryUiController:
        if not hasattr(self, "library_ui_controller"):
            self.library_ui_controller = LibraryUiController(
                translator=self.t,
                theme_colors=self.style_manager.get_theme_colors,
                filename_from_item=self._filename_from_tree_item,
                short_name=self.file_handler.obtener_nombre_corto,
            )
        else:
            self.library_ui_controller.set_translator(self.t)
        return self.library_ui_controller

    def _cover_controller(self) -> CoverController:
        if not hasattr(self, "cover_controller"):
            self.cover_controller = CoverController()
        return self.cover_controller

    def _drop_controller(self) -> DropController:
        if not hasattr(self, "drop_controller"):
            self.drop_controller = DropController()
        return self.drop_controller

    def _rename_controller(self) -> RenameController:
        if not hasattr(self, "rename_controller"):
            self.rename_controller = RenameController()
        return self.rename_controller

    def _playlist_workflow_controller(self) -> PlaylistWorkflowController:
        if not hasattr(self, "playlist_workflow_controller"):
            self.playlist_workflow_controller = PlaylistWorkflowController(self._rename_controller())
        return self.playlist_workflow_controller

    def _metadata_apply_controller(self) -> MetadataApplyController:
        if not hasattr(self, "metadata_apply_controller"):
            self.metadata_apply_controller = MetadataApplyController()
        return self.metadata_apply_controller

    def _metadata_dialog_controller(self) -> MetadataDialogController:
        if not hasattr(self, "metadata_dialog_controller"):
            self.metadata_dialog_controller = MetadataDialogController(self.t)
        else:
            self.metadata_dialog_controller.set_translator(self.t)
        return self.metadata_dialog_controller

    def _playback_selection_controller(self) -> PlaybackSelectionController:
        if not hasattr(self, "playback_selection_controller"):
            self.playback_selection_controller = PlaybackSelectionController(self._filename_from_tree_item)
        return self.playback_selection_controller

    def _ui_text_controller(self) -> UiTextController:
        if not hasattr(self, "ui_text_controller"):
            self.ui_text_controller = UiTextController(self.t)
        else:
            self.ui_text_controller.set_translator(self.t)
        return self.ui_text_controller


    def _on_close(self) -> None:
        if not messagebox.askokcancel(self.t("dialog.exit"), self.t("message.close_app", app_name=APP_NAME)):
            return
        try:
            self._save_config()
            self.player.cleanup()
            self.song_info.clear_cache()
            self.logger.info("Application closed cleanly")
        except Exception as exc:
            self.logger.error("Error while closing app: %s", exc)
        finally:
            self.root.quit()
            self.root.destroy()



