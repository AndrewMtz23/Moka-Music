from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, simpledialog

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
from ..services.custom_theme_service import export_custom_theme, import_custom_theme, public_theme_payload
from ..services.library_compare_service import compare_libraries
from ..services.playback_history_service import last_played_map, playback_history_summary, played_paths
from ..ui_helpers.feedback import ProgressDialog, show_toast
from ..views.modals.library_compare_modal import show_library_compare_modal
from ..views.modals.library_stats_modal import show_library_stats_modal
from ..views.modals.custom_theme_manager_modal import manage_custom_themes
from ..views.modals.playback_history_modal import show_playback_history_modal
from ..views.modals.theme_settings_modal import request_theme_selection


class AppLifecycleMixin:
    """Window lifecycle, menu, config, theme, language, and controller accessors."""

    def _setup_window(self) -> None:
        width, height = UISettings.WINDOW_DEFAULT_SIZE
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(*UISettings.WINDOW_MIN_SIZE)
        self._setup_window_icon()

    def _setup_window_icon(self) -> None:
        assets_dir = Path(__file__).resolve().parents[2] / "assets"

        try:
            icon_path = assets_dir / "Moka.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        try:
            logo_path = assets_dir / "logo.png"
            if logo_path.exists():
                self._window_icon = tk.PhotoImage(file=str(logo_path))
                self.root.iconphoto(True, self._window_icon)
        except Exception:
            pass

    def _setup_main_menu(self) -> None:
        self._menu_controller().install()

    def _menu_controller(self) -> MenuController:
        callbacks = MenuCallbacks(
            open_main_folder=lambda: self._load_folder(self.controller_principal, self.tree_principal),
            open_incoming_folder=lambda: self._load_folder(self.controller_nueva, self.tree_nueva),
            get_recent_folders=self._recent_folders,
            open_recent_folder=self._open_recent_folder,
            clear_recent_folders=self._clear_recent_folders,
            export_playlist=self._export_active_playlist,
            export_library_view_json=self._export_current_library_view_json,
            export_selected=self._export_selected_tracks,
            export_library_report=self._export_library_report,
            import_metadata_json=self._import_metadata_from_json,
            select_cover=self._select_cover,
            exit_app=self._on_close,
            change_theme=self._change_theme,
            show_theme_settings=self._show_theme_settings,
            save_current_theme=self._save_current_theme_as,
            manage_custom_themes=self._manage_custom_themes,
            import_theme=self._import_custom_theme,
            export_theme=self._export_current_theme,
            toggle_fullscreen=self._toggle_fullscreen,
            select_all=self._select_all_in_active_library,
            deselect_all=self._deselect_all_in_active_library,
            invert_selection=self._invert_selection_in_active_library,
            show_quality_report=self._show_quality_report,
            show_library_stats=self._show_library_stats,
            show_library_comparison=self._show_library_comparison,
            show_playback_history=self._show_playback_history,
            complete_metadata_online=self._complete_metadata_online,
            find_missing_covers=self._find_missing_covers,
            normalize_metadata=self._normalize_metadata_tool,
            search_replace_metadata=self._search_replace_metadata_tool,
            convert_audio=self._convert_selected_audio,
            show_backup_history=self._show_backup_history,
            undo_last_metadata_change=self._undo_last_metadata_change,
            undo=self._undo_last_action,
            redo=self._redo_last_action,
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
            self.t("sort.by_bitrate"),
            self.t("sort.by_date"),
            self.t("sort.by_last_played"),
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
            self.t("filter.low_bitrate"),
            self.t("filter.bitrate_128"),
            self.t("filter.bitrate_256"),
            self.t("filter.bitrate_320"),
            self.t("filter.possibly_corrupt"),
            self.t("filter.unplayed"),
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
            FilterMode.LOW_BITRATE: self.t("filter.low_bitrate"),
            FilterMode.BITRATE_128: self.t("filter.bitrate_128"),
            FilterMode.BITRATE_256: self.t("filter.bitrate_256"),
            FilterMode.BITRATE_320: self.t("filter.bitrate_320"),
            FilterMode.POSSIBLY_CORRUPT: self.t("filter.possibly_corrupt"),
            FilterMode.UNPLAYED: self.t("filter.unplayed"),
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
            self.t("filter.low_bitrate"): FilterMode.LOW_BITRATE,
            self.t("filter.bitrate_128"): FilterMode.BITRATE_128,
            self.t("filter.bitrate_256"): FilterMode.BITRATE_256,
            self.t("filter.bitrate_320"): FilterMode.BITRATE_320,
            self.t("filter.possibly_corrupt"): FilterMode.POSSIBLY_CORRUPT,
            self.t("filter.unplayed"): FilterMode.UNPLAYED,
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
            SortMode.BITRATE: self.t("sort.by_bitrate"),
            SortMode.DATE_ADDED: self.t("sort.by_date"),
            SortMode.LAST_PLAYED: self.t("sort.by_last_played"),
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
            self.t("sort.by_bitrate"): SortMode.BITRATE,
            self.t("sort.by_date"): SortMode.DATE_ADDED,
            self.t("sort.by_last_played"): SortMode.LAST_PLAYED,
        }
        return mapping.get(value, SortMode.FILENAME)

    def _load_config(self) -> None:
        try:
            config = self._config_controller().load(default_language=self.current_language)
            self.current_theme = config.theme
            self.current_font_scale = config.font_scale
            self.current_density = config.density
            self.current_accent_color = config.accent_color
            self.onboarding_seen = config.onboarding_seen
            self.recent_folders = [dict(item) for item in config.recent_folders]
            self.custom_themes = [dict(item) for item in config.custom_themes]
            self.style_manager.set_custom_themes(self.custom_themes)
            self._change_language(config.language)
            self._change_appearance(config.font_scale, config.density, config.accent_color)
            self._change_theme(self.current_theme)
            self.player.volume_scale.set(config.volume)
            self.player.set_playback_modes(
                repeat=config.repeat,
                shuffle=config.shuffle,
            )
            self.cleanup_presets = self._normalize_cleanup_presets(config.cleanup_presets)
            self.playback_history = [dict(item) for item in config.playback_history if isinstance(item, dict)]
            self._sync_playback_history_to_controllers()
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
                font_scale=self.current_font_scale,
                density=self.current_density,
                accent_color=self.current_accent_color,
                custom_themes=self.custom_themes,
                language=self.current_language,
                volume=self.player.volume_scale.get(),
                repeat=self.player.repeat_enabled(),
                shuffle=self.player.shuffle_enabled(),
                onboarding_seen=self.onboarding_seen,
                main_folder=self.controller_principal.carpeta,
                incoming_folder=self.controller_nueva.carpeta,
                recent_folders=self.recent_folders,
                cleanup_presets=self.cleanup_presets,
                playback_history=self.playback_history,
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

    def _show_first_run_welcome(self) -> None:
        if self.onboarding_seen:
            return
        self.onboarding_seen = True
        self._save_config()
        messagebox.showinfo(
            self.t("onboarding.title"),
            self.t("onboarding.body"),
        )

    def _begin_progress(self, *, title: str, message: str, total: int) -> ProgressDialog:
        return ProgressDialog(
            self.root,
            title=title,
            message=message,
            total=total,
            cancel_text=self.t("progress.cancel"),
        )

    def _show_toast(self, message: str, *, kind: str = "success") -> None:
        show_toast(self.root, message, kind=kind)

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
                self.t("quality.low_bitrate", count=report["low_bitrate"]),
                self.t("quality.possibly_corrupt", count=report["possibly_corrupt"]),
            ]
            if issues == 0:
                lines.append(self.t("quality.ok"))
            sections.append("\n".join(lines))

        if not sections:
            messagebox.showinfo(self.t("quality.title"), self.t("quality.empty"))
            return

        messagebox.showinfo(self.t("quality.title"), "\n\n".join(sections))

    def _show_library_stats(self) -> None:
        target = self._active_playlist_target()
        if target is None:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("quality.empty"))
            return
        controller, tree = target
        if not controller.archivos:
            messagebox.showwarning(self.t("dialog.no_files"), self.t("message.no_loaded_files"))
            return
        library_name = (
            self.t("panel.main_library")
            if controller is self.controller_principal or tree is self.tree_principal
            else self.t("panel.incoming_library")
        )
        show_library_stats_modal(self.root, self.t, library_name, controller.get_library_stats())

    def _show_library_comparison(self) -> None:
        if not self.controller_principal.archivos or not self.controller_nueva.archivos:
            messagebox.showwarning(self.t("library_compare.title"), self.t("library_compare.need_both"))
            return
        comparison = compare_libraries(
            self.controller_principal.archivos,
            self.controller_principal.metadata_cache_snapshot(),
            self.controller_nueva.archivos,
            self.controller_nueva.metadata_cache_snapshot(),
        )
        show_library_compare_modal(self.root, self.t, comparison)

    def _show_playback_history(self) -> None:
        if not self.playback_history:
            messagebox.showinfo(self.t("playback_history.title"), self.t("playback_history.empty"))
            return
        show_playback_history_modal(self.root, self.t, playback_history_summary(self.playback_history))

    def _show_theme_settings(self) -> None:
        appearance = request_theme_selection(
            self.root,
            self.t,
            self.current_theme,
            font_scale=self.current_font_scale,
            density=self.current_density,
            accent_color=self.current_accent_color,
            custom_themes=self.custom_themes,
        )
        if not appearance:
            return
        self._change_appearance(
            float(appearance["font_scale"]),
            str(appearance["density"]),
            str(appearance["accent_color"]),
        )
        self._change_theme(str(appearance["theme"]))
        self._save_config()

    def _save_current_theme_as(self) -> None:
        name = simpledialog.askstring(
            self.t("theme_custom.save_title"),
            self.t("theme_custom.name_prompt"),
            parent=self.root,
        )
        name = str(name or "").strip()
        if not name:
            return
        theme_id = self._custom_theme_id(name)
        custom_theme = {
            "id": theme_id,
            "name": name,
            "base_theme": self._custom_theme_base(),
            "font_scale": self.current_font_scale,
            "density": self.current_density,
            "accent_color": self.current_accent_color,
        }
        self.custom_themes = [
            theme
            for theme in getattr(self, "custom_themes", [])
            if theme.get("id") != theme_id
        ]
        self.custom_themes.append(custom_theme)
        self.style_manager.set_custom_themes(self.custom_themes)
        self._change_appearance(
            float(custom_theme["font_scale"]),
            str(custom_theme["density"]),
            str(custom_theme["accent_color"]),
        )
        self._change_theme(theme_id)
        self._setup_main_menu()
        self._save_config()
        self._show_toast(self.t("theme_custom.saved", name=name), kind="success")

    def _manage_custom_themes(self) -> None:
        result = manage_custom_themes(self.root, self.t, self.custom_themes)
        if not result:
            return
        self.custom_themes = [dict(theme) for theme in result.get("themes", []) if isinstance(theme, dict)]
        self.style_manager.set_custom_themes(self.custom_themes)
        if result.get("reset_factory"):
            self.current_theme = "light"
            self.current_font_scale = 1.0
            self.current_density = "normal"
            self.current_accent_color = ""
            self._change_appearance(1.0, "normal", "")
            self._change_theme("light")
        elif self.current_theme not in {theme.get("id") for theme in self.custom_themes} and self.current_theme.startswith("custom_"):
            self._change_theme("light")
        else:
            self._change_theme(self.current_theme)
        self._save_config()
        self._setup_main_menu()
        self._show_toast(self.t("theme_manager.saved"), kind="success")

    def _import_custom_theme(self) -> None:
        filepath = self.file_handler.seleccionar_tema_json()
        if not filepath:
            return
        try:
            theme = import_custom_theme(filepath, self.custom_themes)
        except Exception as exc:
            self.logger.error("Could not import custom theme: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("theme_custom.import_failed", error=exc))
            return
        self.custom_themes.append(theme)
        self.style_manager.set_custom_themes(self.custom_themes)
        self._change_appearance(float(theme["font_scale"]), str(theme["density"]), str(theme["accent_color"]))
        self._change_theme(str(theme["id"]))
        self._save_config()
        self._show_toast(self.t("theme_custom.imported", name=theme["name"]), kind="success")

    def _export_current_theme(self) -> None:
        theme = self._current_custom_theme_payload()
        initial_name = f"{theme['id']}.json"
        output_path = self.file_handler.seleccionar_destino_tema_json(initial_name=initial_name)
        if not output_path:
            return
        try:
            path = export_custom_theme(theme, output_path)
        except Exception as exc:
            self.logger.error("Could not export custom theme: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("theme_custom.export_failed", error=exc))
            return
        self._show_toast(self.t("theme_custom.exported", path=path), kind="success")

    def _current_custom_theme_payload(self) -> dict[str, object]:
        for theme in getattr(self, "custom_themes", []):
            if theme.get("id") == self.current_theme:
                return public_theme_payload(theme)
        name = self.t("theme_custom.current_theme_name")
        return {
            "id": self._custom_theme_id(name),
            "name": name,
            "base_theme": self._custom_theme_base(),
            "font_scale": self.current_font_scale,
            "density": self.current_density,
            "accent_color": self.current_accent_color,
        }

    def _custom_theme_base(self) -> str:
        custom_ids = {theme.get("id") for theme in getattr(self, "custom_themes", [])}
        if self.current_theme in custom_ids:
            for theme in self.custom_themes:
                if theme.get("id") == self.current_theme:
                    return str(theme.get("base_theme", "light") or "light")
        return self.current_theme if self.current_theme != "system" else "light"

    def _custom_theme_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return f"custom_{slug or 'tema'}"

    def _toggle_fullscreen(self) -> None:
        self.fullscreen_enabled = not getattr(self, "fullscreen_enabled", False)
        self.root.attributes("-fullscreen", self.fullscreen_enabled)

    def _exit_fullscreen(self) -> str | None:
        if getattr(self, "fullscreen_enabled", False):
            self.fullscreen_enabled = False
            self.root.attributes("-fullscreen", False)
            return "break"
        return None

    def _recent_folders(self) -> list[dict[str, str]]:
        return [dict(item) for item in getattr(self, "recent_folders", [])]

    def _remember_recent_folder(self, folder: str, target: str) -> None:
        folder = str(folder or "")
        if not folder:
            return
        target = target if target in {"main", "incoming"} else "main"
        next_recent = [
            item
            for item in getattr(self, "recent_folders", [])
            if item.get("folder") != folder or item.get("target") != target
        ]
        next_recent.insert(0, {"folder": folder, "target": target})
        self.recent_folders = next_recent[:10]

    def _open_recent_folder(self, item: dict[str, str]) -> None:
        folder = item.get("folder", "")
        if not folder or not Path(folder).exists():
            messagebox.showwarning(self.t("dialog.no_files"), self.t("menu.recent_folder_missing"))
            return
        if item.get("target") == "incoming":
            self._load_folder(self.controller_nueva, self.tree_nueva, folder=folder)
            return
        self._load_folder(self.controller_principal, self.tree_principal, folder=folder)

    def _clear_recent_folders(self) -> None:
        self.recent_folders = []
        self._setup_main_menu()
        self._save_config()

    def _sync_playback_history_to_controllers(self) -> None:
        history_paths = played_paths(self.playback_history)
        last_played = last_played_map(self.playback_history)
        self.controller_principal.set_playback_history(history_paths, last_played)
        self.controller_nueva.set_playback_history(history_paths, last_played)

    def _change_theme(self, theme: str) -> None:
        self.current_theme = theme
        try:
            self.style_manager.set_theme(theme)
            for panel in self._library_panels:
                self._apply_tree_colors(panel["tree"])
        except Exception as exc:
            self.logger.error("Error changing theme to %s: %s", theme, exc)

    def _change_appearance(self, font_scale: float, density: str, accent_color: str | None = None) -> None:
        self.current_font_scale = font_scale
        self.current_density = density
        if accent_color is not None:
            self.current_accent_color = accent_color
        try:
            self.style_manager.set_appearance_options(
                font_scale=font_scale,
                density=density,
                accent_color=self.current_accent_color,
            )
            for panel in self._library_panels:
                tree = panel["tree"]
                try:
                    tree.configure(font=self.style_manager.base_font)
                except Exception:
                    pass
                self._apply_tree_colors(tree)
        except Exception as exc:
            self.logger.error("Error changing appearance options: %s", exc)

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
            self.global_metadata_toggle_button.configure(text=self.t("button.global_metadata"))
        if hasattr(self, "back_to_libraries_button"):
            self.back_to_libraries_button.configure(text=self.t("button.back_to_libraries"))

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



