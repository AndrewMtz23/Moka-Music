import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip, AudioEditMode, AudioEditTrack
from app.services.audio_waveform_service import AudioWaveform
from app.ui.theme import THEME_PRESETS, StyleManager
from app.views.audio_editor_dashboard import AudioEditorDashboard
from app.views.audio_effect_chain_dialog import edit_audio_effect_chain
from app.views.audio_timeline import AudioTimeline


class WaveformRangeTests(unittest.TestCase):
    def test_different_source_ranges_draw_different_amplitudes(self):
        path = Path("synthetic.wav")
        view = SimpleNamespace(
            pixels_per_second=60,
            colors=THEME_PRESETS["forest"],
            selected_clip_ids=[],
            selected_clip_id=None,
            waveforms={path: AudioWaveform(6, (0.1,) * 20 + (0.5,) * 20 + (0.9,) * 20)},
            canvas=Mock(),
        )
        AudioTimeline._draw_clip(view, AudioEditClip(path, 0, 2), 48, 182)
        quiet = [call.args[3] - call.args[1] for call in view.canvas.create_line.call_args_list]
        view.canvas.reset_mock()
        AudioTimeline._draw_clip(view, AudioEditClip(path, 4, 6), 48, 182)
        loud = [call.args[3] - call.args[1] for call in view.canvas.create_line.call_args_list]
        self.assertGreater(min(loud), max(quiet) * 4)


class EditorLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = AudioEditorDashboard(
            self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"]
        )
        self.addCleanup(self.cleanup_editor)

    def cleanup_editor(self):
        self.editor.close()
        self.root.update()
        self.root.destroy()

    def select_clip(self):
        clip = AudioEditClip(Path("example.wav"), 0, 10, id="clip")
        self.editor._clips = [clip]
        self.editor._refresh_project()
        self.editor.timeline.select_single_clip(clip.id)
        self.editor._selection_changed(clip.id)
        return clip

    def test_panel_toggles_do_not_edit_project_or_history(self):
        self.select_clip()
        project = self.editor._project
        self.assertFalse(self.editor._inspector_visible)
        self.editor._toggle_inspector()
        self.assertTrue(self.editor._inspector_visible)
        self.editor._toggle_sources()
        self.editor._toggle_inspector()
        self.assertEqual(self.editor._project, project)
        self.assertEqual(self.editor._undo_stack, [])

    def test_empty_selection_clears_and_disables_properties(self):
        self.select_clip()
        self.editor.timeline.select_single_clip(None)
        self.editor._selection_changed(None)
        self.assertEqual(self.editor._range_start_var.get(), "")
        self.assertEqual(self.editor._clip_gain_var.get(), "")
        self.assertTrue(self.editor._property_entries[0].instate(["disabled"]))

    def test_theme_refresh_preserves_selection_and_project(self):
        self.select_clip()
        project = self.editor._project
        self.editor.refresh_theme(THEME_PRESETS["light"])
        self.assertEqual(self.editor.timeline.canvas.cget("background"), THEME_PRESETS["light"]["background"])
        self.assertEqual(self.editor.source_list.cget("background"), THEME_PRESETS["light"]["field"])
        self.assertEqual(self.editor._project, project)
        self.assertEqual(self.editor.timeline.selected_clip_id, "clip")

    def test_single_clip_context_menu_offers_split_and_properties(self):
        self.select_clip()
        event = SimpleNamespace(x=100, y=80, x_root=100, y_root=80)
        with (
            patch.object(self.editor.timeline, "_clip_id_at_pointer", return_value="clip"),
            patch("app.views.audio_timeline.tk.Menu") as menu,
        ):
            self.editor.timeline._show_clip_context_menu(event)
        labels = [call.kwargs.get("label") for call in menu.return_value.add_command.call_args_list]
        self.assertIn(self.editor.translate("audio_editor.split_at_cursor"), labels)
        self.assertIn(self.editor.translate("audio_editor.properties"), labels)

    def test_mixed_pan_is_preserved_when_only_gain_changes(self):
        self.editor._clips = [
            AudioEditClip(Path("a.wav"), 0, 2, id="a", pan=-0.5),
            AudioEditClip(Path("b.wav"), 0, 2, timeline_start=2, id="b", pan=0.5),
        ]
        self.editor._refresh_project()
        self.editor.timeline.set_selection(["a", "b"], primary_id="a")
        self.editor._selection_changed("a")
        self.assertEqual(self.editor._clip_pan_var.get(), "")
        self.editor._clip_gain_var.set("-3")
        self.editor._apply_clip_mix()
        self.assertEqual([(clip.gain_db, clip.pan) for clip in self.editor._clips], [(-3, -0.5), (-3, 0.5)])
        self.editor._undo()
        self.assertEqual([clip.gain_db for clip in self.editor._clips], [0, 0])

    def test_render_completion_keeps_empty_properties_disabled(self):
        self.editor._render_busy = True
        self.editor._set_render_controls_busy(True)
        self.editor._render_busy = False
        self.editor._set_render_controls_busy(False)
        self.assertTrue(self.editor._property_entries[0].instate(["disabled"]))

    def test_fit_project_uses_viewport_without_forced_horizontal_overflow(self):
        self.select_clip()
        self.editor.transient("")
        self.editor.attributes("-alpha", 0)
        self.editor.deiconify()
        self.editor.update()
        self.editor._fit_project()
        viewport = self.editor.timeline.canvas.winfo_width()
        region = self.editor.timeline.canvas.cget("scrollregion").split()
        self.assertLessEqual(float(region[2]), viewport + 1)

    def test_markers_do_not_modify_project_during_render(self):
        self.select_clip()
        before = self.editor._project
        self.editor._render_busy = True
        try:
            self.editor.timeline._add_marker_at_pointer(SimpleNamespace(x=200, y=80))
        finally:
            self.editor._render_busy = False
        self.assertEqual(self.editor._project, before)
        self.assertEqual(self.editor._undo_stack, [])

    def test_primary_track_controls_match_primary_clip_in_multi_selection(self):
        self.editor._mode = AudioEditMode.MULTITRACK
        self.editor._tracks = [
            AudioEditTrack("a", "A", (AudioEditClip(Path("a.wav"), 0, 2, id="a"),), muted=True),
            AudioEditTrack("b", "B", (AudioEditClip(Path("b.wav"), 0, 2, id="b"),), solo=True),
        ]
        self.editor._refresh_project()
        self.editor.timeline.set_selection(["a", "b"], primary_id="b")
        self.editor._selection_changed("b")
        self.assertFalse(self.editor._mute_button.instate(["selected"]))
        self.assertTrue(self.editor._solo_button.instate(["selected"]))

    def test_context_availability_and_theme_follow_current_state(self):
        self.select_clip()
        self.assertFalse(self.editor._context_action_enabled("paste"))
        self.assertFalse(self.editor._context_action_enabled("split"))
        self.editor.timeline.playhead_position = 5
        self.assertTrue(self.editor._context_action_enabled("split"))
        self.editor._copy_selected_clips()
        self.assertTrue(self.editor._context_action_enabled("paste"))
        self.editor._render_busy = True
        self.assertFalse(self.editor._context_action_enabled("split"))
        self.editor._render_busy = False
        self.editor.refresh_theme(THEME_PRESETS["forest"])
        menu = self.editor.timeline._context_menu()
        self.assertEqual(str(menu.cget("background")), THEME_PRESETS["forest"]["surface"])
        menu.destroy()

    def test_fx_list_uses_editor_palette(self):
        def inspect(dialog):
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            try:
                listing = next(widget for widget in descendants(dialog) if isinstance(widget, tk.Listbox))
                self.assertEqual(listing.cget("background"), self.editor.colors["field"])
                self.assertEqual(listing.cget("foreground"), self.editor.colors["text"])
            finally:
                dialog.destroy()

        with patch.object(tk.Toplevel, "wait_window", autospec=True, side_effect=inspect):
            edit_audio_effect_chain(self.editor, (), self.editor.translate)

    def test_minimum_window_with_large_font_keeps_header_and_timeline_usable(self):
        manager = StyleManager(self.root)
        manager.set_appearance_options(font_scale=1.3, density="comfortable")
        self.editor.refresh_theme(manager.get_theme_colors(), manager.base_font)
        self.editor.transient("")
        self.editor.attributes("-alpha", 0)
        self.editor.geometry("860x520")
        self.editor.deiconify()
        self.editor._show_properties()
        for _ in range(3):
            self.editor.update()
        header = self.editor._editor_title.master
        self.assertLessEqual(header.winfo_reqwidth(), self.editor.winfo_width())
        self.assertGreaterEqual(self.editor.timeline.canvas.winfo_width(), 400)

    def test_menu_action_does_not_run_during_render(self):
        self.editor._render_busy = True
        action = Mock()
        self.editor._run_editor_action(action)
        action.assert_not_called()
        self.editor._render_busy = False


if __name__ == "__main__":
    unittest.main()
