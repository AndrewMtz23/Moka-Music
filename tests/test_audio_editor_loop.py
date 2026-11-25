import importlib
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip
from app.services.playback.audio_player import AudioPlayer
from app.ui.theme import THEME_PRESETS
from app.views.audio_editor_dashboard import AudioEditorDashboard


class EditorLoopTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = AudioEditorDashboard(
            self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"]
        )
        self.editor.attributes("-alpha", 0)
        self.editor._clips = [AudioEditClip(Path("source.wav"), 0, 10, id="a")]
        self.editor._refresh_project()
        self.editor.deiconify()
        self.editor.update()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.editor.close()
        self.root.update()
        self.root.destroy()

    def select_region(self):
        timeline = self.editor.timeline
        timeline.snap_enabled = False
        timeline._select_at_pointer(SimpleNamespace(x=204, y=15, state=1))
        timeline._drag_motion(SimpleNamespace(x=384, y=15, state=1))
        timeline._move_clip_at_pointer(SimpleNamespace(x=384, y=15, state=1))

    def test_shift_ruler_selects_region_without_editing(self):
        before = self.editor._project
        self.select_region()
        self.assertEqual(self.editor.timeline.selection_region, (2, 5))
        self.assertTrue(self.editor.timeline.canvas.find_withtag("region-selection"))
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)

    def test_region_escape_keeps_previous_selection(self):
        self.select_region()
        timeline = self.editor.timeline
        timeline._select_at_pointer(SimpleNamespace(x=144, y=15, state=1))
        timeline._drag_motion(SimpleNamespace(x=444, y=15, state=1))
        timeline.cancel_drag()
        timeline._move_clip_at_pointer(SimpleNamespace(x=444, y=15, state=1))
        self.assertEqual(timeline.selection_region, (2, 5))

    def test_cached_loop_uses_loop_callback_and_absolute_position(self):
        self.select_region()
        editor = self.editor
        editor._loop_var.set(True)
        editor._play_preview = Mock()
        editor._play_loop_preview = Mock()
        path = editor._temp_dir / "region.wav"
        path.write_bytes(b"preview")
        editor._preview_path = path
        editor._preview_project_snapshot = editor._project
        editor._preview_region_snapshot = (2, 5)
        editor._start_preview()
        editor._play_loop_preview.assert_called_once_with(path)
        editor._play_preview.assert_not_called()
        editor._playback_position = lambda: 1.25
        editor._preview_is_playing = lambda: True
        editor.after_cancel(editor._playback_poll_id)
        editor._refresh_playback_display()
        self.assertEqual(editor.timeline.playhead_position, 3.25)
        editor._clear_preview_region()
        self.assertFalse(editor._preview_active)
        self.assertFalse(editor._loop_var.get())
        self.assertIsNone(editor._preview_path)

    def test_render_snapshot_includes_region_but_export_does_not(self):
        self.select_region()
        editor = self.editor
        editor._loop_var.set(True)
        editor._play_preview = Mock()
        editor._play_loop_preview = Mock()
        with patch("app.views.audio_editor_dashboard.render_audio_project", return_value=Path("region.wav")) as render:
            editor._start_preview()
            editor._render_thread.join(timeout=5)
        self.assertEqual(render.call_args.kwargs["preview_region"], (2, 5))
        editor.after_cancel(editor._render_poll_id)
        editor._poll_render_results()
        self.assertEqual(editor._preview_region_snapshot, (2, 5))
        editor._play_loop_preview.assert_called_once_with(Path("region.wav"))
        with patch("app.views.audio_editor_dashboard.export_audio_project", return_value=Path("export.wav")) as export:
            editor._start_render("export", output_folder=editor._temp_dir, base_name="mix")
            editor._render_thread.join(timeout=5)
        self.assertNotIn("preview_region", export.call_args.kwargs)
        editor._finish_render()

    def test_region_change_invalidates_cache_and_clamps_after_shortening(self):
        self.select_region()
        editor = self.editor
        path = editor._temp_dir / "old.wav"
        path.write_bytes(b"preview")
        editor._preview_path = path
        editor.timeline.set_preview_region((3, 7))
        self.assertIsNone(editor._preview_path)
        self.assertFalse(path.exists())
        editor._clips = [AudioEditClip(Path("source.wav"), 0, 4, id="a")]
        editor._refresh_project()
        self.assertEqual(editor.timeline.selection_region, (3, 4))

    def test_space_on_loop_checkbox_only_toggles_checkbox(self):
        self.select_region()
        editor = self.editor
        checkbox = next(
            widget
            for widget in editor._render_control_states
            if isinstance(widget, ttk.Checkbutton) and str(widget.cget("variable")) == str(editor._loop_var)
        )
        checkbox.focus_force()
        editor.update()
        with patch.object(editor, "_start_preview") as start:
            checkbox.event_generate("<KeyPress-space>")
            editor.update()
            self.assertTrue(editor._loop_var.get())
            start.assert_not_called()

    def test_loop_without_region_is_rejected(self):
        self.editor._loop_var.set(True)
        self.editor._toggle_region_loop()
        self.assertFalse(self.editor._loop_var.get())

    def test_project_switch_clears_region(self):
        self.select_region()
        self.editor._loop_var.set(True)
        self.editor._replace_editor_project(self.editor._project, [], None)
        self.assertIsNone(self.editor.timeline.selection_region)
        self.assertFalse(self.editor._loop_var.get())


class NativeLoopTests(unittest.TestCase):
    def test_native_loop_wraps_position_and_pause_resume_preserves_loop(self):
        with patch.object(importlib.import_module("app.services.playback.audio_player"), "pygame") as pygame:
            player = AudioPlayer()
            player.current_track = "region.wav"
            player.duration = 3
            player.play(loop=True)
            self.assertEqual(pygame.mixer.music.play.call_args.kwargs["loops"], -1)
            pygame.mixer.music.get_pos.return_value = 7250
            self.assertAlmostEqual(player.get_position(), 1.25)
            player.pause()
            player.play()
            pygame.mixer.music.unpause.assert_called_once()
            self.assertAlmostEqual(player.get_position(), 1.25)
            player.stop()
            player.play()
            self.assertNotIn("loops", pygame.mixer.music.play.call_args.kwargs)
