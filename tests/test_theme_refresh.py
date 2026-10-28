import tkinter as tk
import unittest
from io import BytesIO
from tkinter import ttk
from unittest.mock import Mock, patch

from PIL import Image, ImageTk

from app.i18n import I18n
from app.ui.app_lifecycle import AppLifecycleMixin
from app.ui.theme import THEME_PRESETS, StyleManager
from app.views.player_panel import PlayerControls
from app.views.preview_panel import PreviewPanel


class ThemeRefreshTests(unittest.TestCase):
    def test_player_native_surfaces_and_menu_follow_palette(self):
        playback = Mock(volume=0.5, available=True)
        playback.state.return_value.is_playing = False
        with (
            patch("app.views.player_panel.PlaybackController", return_value=playback),
            patch.object(PlayerControls, "_start_progress_loop"),
        ):
            player = PlayerControls(self.root, theme_colors=self.manager.get_theme_colors)
        self.addCleanup(player.cleanup)
        for name in THEME_PRESETS:
            self.manager.set_theme(name)
            player.refresh_theme()
            colors = self.manager.get_theme_colors()
            self.assertEqual(player.details.viewport.cget("background"), colors["background"])
            self.assertEqual(player.progress_bar.cget("background"), colors["surface"])
            self.assertEqual(player.mute_button.cget("background"), colors["surface"])
            self.assertEqual(str(player.more_menu.cget("selectcolor")), colors["highlight"])
            self.assertEqual(str(player.more_menu.cget("disabledforeground")), colors["disabled"])

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.manager = StyleManager(self.root)

    def test_existing_combobox_popup_and_widget_states_follow_each_theme(self):
        combo = ttk.Combobox(self.root, values=("a", "b"), state="readonly")
        popup = self.root.tk.call("ttk::combobox::PopdownWindow", str(combo))
        listbox = f"{popup}.f.l"
        for name in THEME_PRESETS:
            with self.subTest(theme=name):
                self.manager.set_theme(name)
                colors = self.manager.get_theme_colors()
                self.assertEqual(self.root.tk.call(listbox, "cget", "-background"), colors["field"])
                self.assertEqual(self.root.tk.call(listbox, "cget", "-foreground"), colors["text"])
                self.assertEqual(self.manager.style.lookup("TPanedwindow", "background"), colors["background"])
                self.assertEqual(
                    self.manager.style.lookup("Vertical.TScrollbar", "background", ("active",)),
                    colors["secondary_hover"],
                )
                future = ttk.Combobox(self.root, values=("a",))
                future_popup = self.root.tk.call("ttk::combobox::PopdownWindow", str(future))
                self.assertEqual(self.root.tk.call(f"{future_popup}.f.l", "cget", "-background"), colors["field"])
                future.destroy()

    def test_preview_placeholder_changes_color_but_artwork_is_preserved(self):
        preview = PreviewPanel(self.root, show_inline_editor=False)
        for name in ("dark", "rose", "light"):
            self.manager.set_theme(name)
            preview.refresh_theme(self.manager.get_theme_colors())
            actual = ImageTk.getimage(preview.default_cover).getpixel((0, 0))[:3]
            expected = Image.new("RGB", (1, 1), self.manager.get_theme_colors()["surface_alt"]).getpixel((0, 0))
            self.assertEqual(actual, expected)
        image = BytesIO()
        Image.new("RGB", (32, 32), "red").save(image, format="PNG")
        preview.update_preview({"title": "Song", "cover_art": image.getvalue()})
        cover = preview.cover_image
        self.manager.set_theme("dark")
        preview.refresh_theme(self.manager.get_theme_colors())
        self.assertIs(preview.cover_image, cover)
        with self.assertLogs(preview.logger, level="ERROR"):
            preview.update_preview({"title": "Broken cover", "cover_art": b"invalid image"})
        self.manager.set_theme("rose")
        preview.refresh_theme(self.manager.get_theme_colors())
        self.assertIs(preview.cover_image, preview.default_cover)

    def test_search_focus_reads_current_palette_after_theme_changes(self):
        app = AppLifecycleMixin()
        app.style_manager = self.manager
        app.t = I18n("es").t
        entry = ttk.Entry(self.root)
        variable = tk.StringVar(self.root)
        panel = {"search_entry": entry, "search_var": variable}
        app._get_library_panel_for_search = lambda _var: panel
        app._install_search_placeholder(entry, variable)
        self.manager.set_theme("dark")
        entry.event_generate("<FocusIn>")
        self.assertEqual(str(entry.cget("foreground")), self.manager.get_theme_colors()["text"])
        entry.event_generate("<FocusOut>")
        self.assertEqual(str(entry.cget("foreground")), self.manager.get_theme_colors()["text_secondary"])

    def test_theme_and_accent_refresh_share_all_components(self):
        app = AppLifecycleMixin()
        app.style_manager = self.manager
        app.logger = Mock()
        app.menu_controller = None
        app.player = Mock()
        app.preview = Mock()
        app._library_panels = [{"tree": Mock()}]
        app._apply_tree_colors = Mock()
        app._refresh_search_placeholder = Mock()
        ui = Mock()
        app._library_ui_controller = lambda: ui
        app.current_accent_color = ""
        app._change_theme("dark")
        app._change_appearance(1.0, "normal", "#bb2288")
        self.assertEqual(app._refresh_search_placeholder.call_count, 2)
        self.assertEqual(ui.apply_empty_state_colors.call_count, 2)
        self.assertEqual(app.preview.refresh_theme.call_count, 2)
        app.logger.error.assert_not_called()
