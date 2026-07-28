import logging
import queue
import tkinter as tk
from tkinter import ttk
from typing import Optional

from tkinterdnd2 import DND_FILES, TkinterDnD

from ..controllers.backup_controller import BackupController
from ..controllers.cleanup_controller import CleanupController
from ..controllers.cleanup_preset_controller import CleanupPresetController
from ..controllers.config_controller import ConfigController
from ..controllers.cover_controller import CoverController
from ..controllers.drop_controller import DropController
from ..controllers.library_ui_controller import LibraryUiController
from ..controllers.menu_controller import MenuController
from ..controllers.metadata_apply_controller import MetadataApplyController
from ..controllers.metadata_controller import MetadataController
from ..controllers.metadata_dialog_controller import MetadataDialogController
from ..controllers.playback_selection_controller import PlaybackSelectionController
from ..controllers.rename_controller import RenameController
from ..controllers.selection_controller import SelectionController
from ..controllers.song_actions_controller import SongActions
from ..controllers.ui_text_controller import UiTextController
from ..controllers.undo_controller import UndoController
from ..i18n import I18n
from ..services.online_metadata_service import MusicBrainzClient
from ..services.song_info_service import SongInfo
from ..ui_helpers.file_dialogs import FileHandler
from ..views.library_panel import build_library_panel
from ..views.metadata_panel import build_metadata_panel
from ..views.player_panel import PlayerControls
from ..views.preview_panel import PreviewPanel
from .app_lifecycle import AppLifecycleMixin
from .interaction_workflow import InteractionWorkflowMixin
from .library_workflow import LibraryWorkflowMixin
from .metadata_workflow import MetadataWorkflowMixin
from .theme import StyleManager


class MokaMusicApp(AppLifecycleMixin, MetadataWorkflowMixin, LibraryWorkflowMixin, InteractionWorkflowMixin):
    def __init__(self, root: TkinterDnD.Tk):
        self.root = root
        self.logger = logging.getLogger(__name__)
        self.i18n = I18n()
        self.t = self.i18n.t
        self.current_language = self.i18n.language
        self.root.title(self.t("app.window_title"))
        self._setup_window()

        self.style_manager = StyleManager(root)
        self.file_handler = FileHandler(translator=self.t)
        self.song_info = SongInfo()
        self.online_metadata = MusicBrainzClient()
        self.backup_controller = BackupController(self.t, self.song_info)
        self.cleanup_controller = CleanupController(self.song_info)
        self.cleanup_preset_controller = CleanupPresetController()
        self.config_controller = ConfigController()
        self.cover_controller = CoverController()
        self.drop_controller = DropController()
        self.rename_controller = RenameController()
        self.metadata_apply_controller = MetadataApplyController()
        self.metadata_dialog_controller = MetadataDialogController(self.t)
        self.playback_selection_controller = PlaybackSelectionController(self._filename_from_tree_item)
        self.ui_text_controller = UiTextController(self.t)
        self.undo_controller = UndoController()
        self.library_ui_controller = LibraryUiController(
            translator=self.t,
            theme_colors=self.style_manager.get_theme_colors,
            filename_from_item=self._filename_from_tree_item,
            short_name=self.file_handler.obtener_nombre_corto,
        )
        self.menu_controller: Optional[MenuController] = None
        self.selection_controller = SelectionController(self._filename_from_tree_item)
        self.song_actions = SongActions(translator=self.t)
        self.controller_principal = MetadataController(translator=self.t)
        self.controller_nueva = MetadataController(translator=self.t)

        self.current_theme = "light"
        self.current_font_scale = 1.0
        self.current_density = "normal"
        self.current_accent_color = ""
        self._playback_controller = None
        self._playback_tree = None
        self._preview_controller: Optional[MetadataController] = None
        self._preview_filename: Optional[str] = None
        self._reorder_drag: Optional[dict[str, object]] = None
        self._ui_text_widgets: dict[str, object] = {}
        self._sort_widgets: list[tuple[ttk.Combobox, tk.StringVar, MetadataController]] = []
        self._library_panels: list[dict[str, object]] = []
        self.cleanup_presets: list[dict[str, object]] = []
        self.playback_history: list[dict[str, object]] = []
        self.recent_folders: list[dict[str, str]] = []
        self.custom_themes: list[dict[str, object]] = []
        self.onboarding_seen = False
        self.fullscreen_enabled = False
        self._library_load_token_counter = 0
        self._library_load_tokens: dict[int, int] = {}
        self._library_load_queue: queue.Queue = queue.Queue()

        self._setup_main_menu()
        self._setup_ui()
        self._bind_events()
        self._load_config()
        self.root.after(200, self._show_first_run_welcome)

    def _setup_ui(self) -> None:
        main_panel = ttk.Frame(self.root)
        main_panel.pack(fill="both", expand=True, padx=14, pady=14)

        main_paned = ttk.PanedWindow(main_panel, orient="vertical")
        main_paned.pack(fill="both", expand=True)

        top_area = ttk.Frame(main_paned)
        self._global_metadata_view_active = False

        self.top_library_panel = ttk.PanedWindow(top_area, orient="horizontal")
        self.top_library_panel.pack(fill="both", expand=True)

        self.top_metadata_panel = ttk.Frame(top_area)
        metadata_toolbar = ttk.Frame(self.top_metadata_panel)
        metadata_toolbar.pack(fill="x", pady=(0, 4))
        self.back_to_libraries_button = ttk.Button(
            metadata_toolbar,
            text=self.t("button.back_to_libraries"),
            command=self._toggle_global_metadata_view,
            style="Secondary.TButton",
        )
        self.back_to_libraries_button.pack(side="right")

        self._setup_music_panel(self.top_library_panel, self.controller_principal, "panel.main_library", is_main=True)
        self._setup_music_panel(self.top_library_panel, self.controller_nueva, "panel.incoming_library", is_main=False)
        self._setup_metadata_panel(self.top_metadata_panel)

        lower_panel = ttk.Frame(main_paned)

        bottom_panel = ttk.PanedWindow(lower_panel, orient="horizontal")
        bottom_panel.pack(fill="both", expand=True)

        self.preview = PreviewPanel(bottom_panel, translator=self.t, show_inline_editor=False)
        self.preview.on_save_requested = self._save_preview_metadata
        self.preview.on_cover_requested = self._select_preview_cover
        self.preview.on_clear_metadata_requested = self._show_clear_metadata_modal
        self.preview.on_edit_metadata_requested = self._show_edit_metadata_modal
        self._register_cover_drop_target()

        self.player = PlayerControls(
            bottom_panel,
            translator=self.t,
            theme_colors=self.style_manager.get_theme_colors,
        )
        self.player.on_track_end = self._play_next_track
        self.player.on_next_requested = lambda: self._play_relative_track(1)
        self.player.on_prev_requested = lambda: self._play_relative_track(-1)
        try:
            bottom_panel.add(self.preview, weight=3)
            bottom_panel.add(self.player, weight=2)
        except tk.TclError:
            bottom_panel.add(self.preview)
            bottom_panel.add(self.player)

        try:
            main_paned.add(top_area, weight=4)
            main_paned.add(lower_panel, weight=2)
        except tk.TclError:
            main_paned.add(top_area)
            main_paned.add(lower_panel)

    def _toggle_global_metadata_view(self) -> None:
        self._set_global_metadata_view(not self._global_metadata_view_active)

    def _set_global_metadata_view(self, active: bool) -> None:
        self._global_metadata_view_active = active
        if active:
            self.top_library_panel.pack_forget()
            self.top_metadata_panel.pack(fill="both", expand=True)
            return

        self.top_metadata_panel.pack_forget()
        self.top_library_panel.pack(fill="both", expand=True)

    def _setup_music_panel(self, parent, controller: MetadataController, title_key: str, *, is_main: bool) -> None:
        bundle = build_library_panel(
            parent,
            controller=controller,
            title=self.t(title_key),
            is_main=is_main,
            t=self.t,
            style_manager=self.style_manager,
            sort_options=self._sort_options(),
            filter_options=self._filter_options(),
            on_select_folder=self._load_folder,
            on_song_select=self._on_song_select,
            on_play_selected=self._play_selected,
            on_start_reorder=self._start_reorder_drag,
            on_finish_reorder=self._finish_reorder_drag,
            on_context_menu=self._show_context_menu,
            on_sort=self._sort_files,
            on_refresh=self._schedule_library_refresh,
            on_action=(self._add_single_file if is_main else lambda _controller, _tree: self._move_to_main()),
            on_clear_folder=self._clear_library_folder,
            on_refresh_folder=self._refresh_library_folder,
            on_delete_selected=self._delete_selected_from_library,
            extra_action_text="" if is_main else self.t("button.global_metadata"),
            on_extra_action=None if is_main else self._toggle_global_metadata_view,
            second_extra_action_text="" if is_main else self.t("button.prepare_folder"),
            on_second_extra_action=None if is_main else self._show_incoming_folder_guide,
        )

        self._library_panels.append(bundle.panel_state(controller))
        self._sort_widgets.append((bundle.sort_menu, bundle.sort_var, controller))
        self._install_search_placeholder(bundle.search_entry, bundle.search_var)

        prefix = "main" if is_main else "incoming"
        self._ui_text_widgets[f"{prefix}_library_frame"] = bundle.frame
        self._ui_text_widgets[f"{prefix}_select_folder"] = bundle.select_button
        self._ui_text_widgets[f"{prefix}_close_folder"] = bundle.clear_button
        self._ui_text_widgets[f"{prefix}_empty_state_button"] = bundle.empty_state_button
        self._ui_text_widgets[f"{prefix}_search_label"] = bundle.search_label
        self._ui_text_widgets[f"{prefix}_filter_label"] = bundle.filter_label

        if is_main:
            self.tree_principal = bundle.tree
            self._ui_text_widgets["add_song_button"] = bundle.action_button
        else:
            self.tree_nueva = bundle.tree
            self._ui_text_widgets["move_to_main_button"] = bundle.action_button
            if bundle.extra_button is not None:
                self.global_metadata_toggle_button = bundle.extra_button
                self._ui_text_widgets["incoming_global_metadata_button"] = bundle.extra_button
            if bundle.second_extra_button is not None:
                self._ui_text_widgets["incoming_prepare_folder_button"] = bundle.second_extra_button

    def _setup_metadata_panel(self, parent) -> None:
        bundle = build_metadata_panel(
            parent,
            t=self.t,
            on_apply_selected=self._apply_to_selection,
            on_batch_edit=self._show_batch_edit_modal,
            on_apply_all=self._apply_to_all,
            on_clear_fields=self._clear_metadata_fields,
            on_quick_cleanup=self._apply_quick_cleanup,
            on_number_tracks=self._prepare_active_playlist,
            on_insert_position=self._insert_selected_at_position,
            on_rename_from_metadata=self._show_rename_from_metadata_preview,
            on_auto_cover=self._apply_auto_cover_from_folder,
            on_search_online=self._search_online_metadata,
            on_apply_preset=self._apply_selected_cleanup_preset,
            on_create_preset=self._show_create_cleanup_preset_modal,
            on_delete_preset=self._delete_selected_cleanup_preset,
        )
        self.meta_vars = bundle.meta_vars
        self.cleanup_preset_var = bundle.cleanup_preset_var
        self.cleanup_preset_menu = bundle.cleanup_preset_menu
        self._ui_text_widgets.update(bundle.text_widgets)

    def _bind_events(self) -> None:
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._handle_drop)
        self._register_library_drop_targets()
        self.root.bind("<Control-o>", lambda _event: self._load_folder(self.controller_principal, self.tree_principal))
        self.root.bind("<Control-n>", lambda _event: self._load_folder(self.controller_nueva, self.tree_nueva))
        self.root.bind("<Control-a>", lambda _event: self._select_all_in_active_library())
        self.root.bind("<Control-z>", lambda _event: self._undo_last_action())
        self.root.bind("<Control-y>", lambda _event: self._redo_last_action())
        self.root.bind("<F11>", lambda _event: self._toggle_fullscreen())
        self.root.bind("<Escape>", lambda _event: self._exit_fullscreen() or self._on_close())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _register_cover_drop_target(self) -> None:
        try:
            for widget in (self.preview.cover_frame, self.preview.cover_label, self.preview.cover_hint_label):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._handle_cover_drop)
        except Exception as exc:
            self.logger.warning("Could not register cover drop target: %s", exc)

    def _register_library_drop_targets(self) -> None:
        for panel in self._library_panels:
            controller = panel["controller"]
            tree = panel["tree"]
            for widget in (tree, panel.get("empty_state_frame")):
                if widget is None:
                    continue
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind(
                        "<<Drop>>", lambda event, c=controller, t=tree: self._handle_library_drop(event, c, t)
                    )
                except Exception as exc:
                    self.logger.warning("Could not register library drop target: %s", exc)


def iniciar_app() -> None:
    root = TkinterDnD.Tk()
    root.mokamusic_app = MokaMusicApp(root)
    root.mainloop()
