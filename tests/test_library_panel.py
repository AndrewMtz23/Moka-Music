import tkinter as tk
import unittest
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock

from app.controllers.metadata_controller import MetadataController
from app.i18n import I18n
from app.views.library_panel import build_library_panel


class LibraryPanelTests(unittest.TestCase):
    def test_main_panel_has_separate_add_and_return_actions(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        self.addCleanup(root.destroy)
        parent = ttk.Panedwindow(root)
        add, transfer = Mock(), Mock()
        colors = {
            "surface": "#111827",
            "text": "#eeeeee",
            "text_secondary": "#aaaaaa",
            "highlight": "#334455",
            "highlight_text": "#ffffff",
        }
        callbacks = {
            name: Mock()
            for name in (
                "on_select_folder",
                "on_song_select",
                "on_play_selected",
                "on_start_reorder",
                "on_finish_reorder",
                "on_context_menu",
                "on_sort",
                "on_refresh",
                "on_clear_folder",
                "on_refresh_folder",
                "on_delete_selected",
            )
        }
        controller = MetadataController()
        panel = build_library_panel(
            parent,
            controller=controller,
            title="Principal",
            is_main=True,
            t=I18n("es").t,
            style_manager=SimpleNamespace(get_theme_colors=lambda: colors, base_font=("Segoe UI", 10)),
            sort_options=[],
            filter_options=[],
            on_action=add,
            on_move_to_incoming=transfer,
            **callbacks,
        )
        panel.action_button.invoke()
        panel.transfer_button.invoke()
        add.assert_called_once_with(controller, panel.tree)
        transfer.assert_called_once_with()
        self.assertEqual(panel.action_button.master, panel.transfer_button.master)
        self.assertEqual(panel.transfer_button.grid_info()["column"], 1)
        self.assertIn("secundaria", panel.transfer_button.cget("text"))
