import tkinter as tk
import unittest
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.i18n import I18n
from app.models import TrackInfo
from app.ui.app_lifecycle import AppLifecycleMixin
from app.ui.theme import THEME_PRESETS, StyleManager
from app.views.modals.theme_settings_modal import (
    apply_preview_layout,
    apply_preview_palette,
    build_preview_widgets,
    request_theme_selection,
)


class ThemeLivePreviewTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.manager = StyleManager(self.root)
        self.t = I18n("es").t

    def test_current_playing_song_and_real_rows_are_snapshotted(self):
        app = AppLifecycleMixin()
        track = TrackInfo("real.mp3", "real.mp3", {"title": "Real song", "track_number": "302"}, 187, b"cover")
        item = {"text": "Real song", "values": (302,), "tags": ("real.mp3",)}
        tree = SimpleNamespace(get_children=lambda: ("0",), item=lambda _id: item)
        app.player = SimpleNamespace(
            details=SimpleNamespace(track=track), playback=SimpleNamespace(current_file="real.mp3")
        )
        app.preview = SimpleNamespace(current_song_data={"title": "Other selected song"})
        app._playback_tree = tree
        app._library_panels = []
        context = app._theme_preview_context()
        self.assertEqual(context["song"]["title"], "Real song")
        self.assertEqual(context["rows"][0]["text"], "302. Real song")
        self.assertTrue(context["rows"][0]["selected"])
        context["song"]["title"] = "Changed snapshot"
        self.assertEqual(track.metadata["title"], "Real song")

    def test_preview_uses_artwork_and_does_not_change_global_theme(self):
        cover = BytesIO()
        Image.new("RGB", (64, 64), "red").save(cover, format="PNG")
        context = {
            "song": {
                "title": "My song",
                "album": "My album",
                "artist": "My artist",
                "track_number": 0,
                "duration": 187,
                "cover_art": cover.getvalue(),
            },
            "rows": [{"text": "0. My song", "selected": True, "issue": ""}],
            "total": 860,
        }
        frame = tk.Frame(self.root)
        widgets = build_preview_widgets(frame, self.t, context)
        background = self.root.cget("background")
        for name in THEME_PRESETS:
            palette = THEME_PRESETS[name]
            apply_preview_palette(widgets, palette)
            apply_preview_layout(widgets, 1.3, "comfortable")
            widgets["song_preview"].apply_appearance(palette, 1.3, "comfortable")
            self.assertEqual(self.root.cget("background"), background)
            self.assertEqual(widgets["selected_row"].cget("text"), "0. My song")
            self.assertIsNotNone(widgets["song_preview"].photo)
            self.assertIn("0", widgets["song_preview"].info.cget("text"))
        self.assertEqual(widgets["song_preview"].title.cget("text"), "My song")
        self.assertIn("My album", widgets["song_preview"].subtitle.cget("text"))

    def test_closing_dialog_does_not_apply_theme(self):
        initial = self.root.cget("background")

        def close():
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

        self.root.after(100, close)
        result = request_theme_selection(
            self.root, self.t, "rose", preview_context={"song": {}, "rows": [], "total": 0}
        )
        self.assertIsNone(result)
        self.assertEqual(self.root.cget("background"), initial)
