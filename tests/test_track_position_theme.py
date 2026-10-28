import tkinter as tk
import unittest
from tkinter import ttk

from app.i18n import I18n
from app.ui.theme import THEME_PRESETS, StyleManager
from app.views.modals.track_position_modal import _theme_colors, request_track_position


class TrackPositionThemeTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.manager = StyleManager(self.root)

    def test_modal_palette_matches_active_styles_without_app_on_parent(self):
        nested_parent = ttk.Frame(self.root)
        for theme in THEME_PRESETS:
            with self.subTest(theme=theme):
                self.manager.set_theme(theme)
                palette = self.manager.get_theme_colors()
                for parent in (self.root, nested_parent):
                    colors = _theme_colors(parent)
                    self.assertEqual(colors["surface"], palette["surface"])
                    self.assertEqual(colors["text"], palette["text"])
                    self.assertEqual(colors["primary"], palette["primary"])
                    self.assertEqual(colors["primary_text"], palette["button_text"])
        self.manager.set_appearance_options(font_scale=1.0, density="normal", accent_color="#eeee00")
        self.assertEqual(_theme_colors(self.root)["primary_text"], self.manager.get_theme_colors()["button_text"])

    def test_dark_modal_uses_one_palette_and_keeps_position_value(self):
        self.manager.set_theme("dark")
        palette = self.manager.get_theme_colors()
        t = I18n("es").t
        observed = {}

        def inspect_modal():
            modal = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
            try:
                observed["background"] = modal.cget("background")
                container = modal.winfo_children()[0]
                observed["container"] = container.cget("background")
                header = container.winfo_children()[0]
                observed["header"] = header.cget("background")
                observed["title"] = header.winfo_children()[0].cget("foreground")
                controls = [child for row in container.winfo_children() for child in row.winfo_children()]
                confirm = next(
                    widget
                    for widget in controls
                    if isinstance(widget, ttk.Button) and widget.cget("text") == t("move_position.confirm")
                )
                confirm.invoke()
            finally:
                if modal.winfo_exists():
                    modal.destroy()

        self.root.after(50, inspect_modal)
        result = request_track_position(
            self.root, t, title="Position", prompt="Choose a track number", total=860, initial=302, max_position=9999
        )
        self.assertEqual(result, 302)
        self.assertEqual(
            observed,
            {
                "background": palette["surface"],
                "container": palette["surface"],
                "header": palette["primary"],
                "title": palette["button_text"],
            },
        )
