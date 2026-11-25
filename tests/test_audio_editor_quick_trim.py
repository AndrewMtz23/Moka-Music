import gc
import math
import shutil
import struct
import tkinter as tk
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip, AudioEditMode, AudioEditTrack
from app.services.audio_edit_service import export_audio_project
from app.services.audio_waveform_service import AudioWaveform
from app.ui.theme import THEME_PRESETS
from app.views.audio_editor_dashboard import AudioEditorDashboard


class QuickTrimTests(unittest.TestCase):
    def test_context_removes_only_target_marker_and_supports_undo_redo(self):
        e = self.editor
        e.transient("")
        e.deiconify()
        e.update()
        e._add_marker(4)
        e._add_marker(8)
        before = e._project
        target = before.markers[0]
        with patch("app.views.audio_timeline.tk.Menu") as menu:
            e.timeline._show_clip_context_menu(SimpleNamespace(x=326, y=300, x_root=326, y_root=300))
        entry = next(
            call.kwargs
            for call in menu.return_value.add_command.call_args_list
            if call.kwargs.get("label") == e.translate("audio_editor.remove_marker", marker=target.label)
        )
        entry["command"]()
        self.assertEqual(e._project.markers, (before.markers[1],))
        self.assertEqual(e._project.tracks, before.tracks)
        e._undo()
        self.assertEqual(e._project, before)
        e._redo()
        self.assertEqual(e._project.markers, (before.markers[1],))

    def test_remove_marker_ignores_busy_or_missing_id(self):
        e = self.editor
        e._add_marker(4)
        before = e._project
        history = len(e._undo_stack)
        e._render_busy = True
        e._remove_marker(before.markers[0].id)
        e._render_busy = False
        e._remove_marker("missing")
        self.assertEqual(e._project, before)
        self.assertEqual(len(e._undo_stack), history)

    def test_marker_target_includes_label_but_not_distant_space(self):
        e = self.editor
        e._add_marker(4)
        marker = e._project.markers[0]
        self.assertEqual(e.timeline._marker_at_pointer(SimpleNamespace(x=337, y=39)).id, marker.id)
        self.assertIsNone(e.timeline._marker_at_pointer(SimpleNamespace(x=400, y=300)))

    def test_context_quick_trim_order_and_real_actions(self):
        e = self.editor
        e.timeline.set_playhead_position(4)
        with (
            patch.object(e.timeline, "_clip_id_at_pointer", return_value="a"),
            patch("app.views.audio_timeline.tk.Menu") as menu,
        ):
            e.timeline._show_clip_context_menu(SimpleNamespace(x=500, y=80, x_root=500, y_root=80))
        entries = [call.kwargs for call in menu.return_value.add_command.call_args_list]
        labels = [entry["label"] for entry in entries]
        keys = ["start_here", "end_here", "listen_start", "listen_end"]
        indices = [labels.index(e.translate("audio_editor." + key)) for key in keys]
        self.assertEqual(indices, list(range(indices[0], indices[0] + 4)))
        self.assertLess(indices[-1], labels.index(e.translate("audio_editor.context_paste")))
        entries[indices[0]]["command"]()
        self.assertEqual(e._clips[0].source_start, 14)
        e._undo()
        entries[indices[1]]["command"]()
        self.assertEqual(e._clips[0].source_end, 14)
        e._undo()
        with patch.object(e, "_start_render"):
            entries[indices[2]]["command"]()
            self.assertEqual(e._audition_region, (0, 5))
            entries[indices[3]]["command"]()
            self.assertEqual(e._audition_region, (15, 20))

    def test_context_quick_actions_require_one_clip_and_idle_render(self):
        e = self.editor
        for selection, busy in (([], False), (["a", "b"], False), (["a"], True)):
            e.timeline.selected_clip_ids = set(selection)
            e._render_busy = busy
            for action in ("start_here", "end_here", "listen_start", "listen_end"):
                self.assertFalse(e._context_action_enabled(action))
        e._render_busy = False

    def test_double_click_requests_playback_from_pointer_without_editing(self):
        e = self.editor
        e.timeline.set_preview_region((6, 8))
        e._loop_var.set(True)
        before = e._project
        e._preview_active = True
        with patch.object(e, "_start_render") as render, patch.object(e, "_stop_active_preview") as stop:
            e.timeline._play_from_pointer(SimpleNamespace(x=324, y=80))
        render.assert_called_once_with("preview")
        stop.assert_called_once_with(restore=True)
        self.assertEqual(e._audition_region, (4, 20))
        self.assertEqual(e.timeline.playhead_position, 4)
        self.assertEqual(e.timeline.selection_region, (6, 8))
        self.assertTrue(e._loop_var.get())
        self.assertEqual(e._project, before)
        self.assertEqual(e._undo_stack, [])

    def test_play_from_position_ignores_busy_render_and_project_end(self):
        e = self.editor
        with patch.object(e, "_start_render") as render:
            e._render_busy = True
            e._play_from_position(4)
            e._render_busy = False
            e._play_from_position(20)
            e._play_from_position(30)
        render.assert_not_called()

    def test_play_from_position_renders_remainder_and_plays_once(self):
        e = self.editor
        e.timeline.set_preview_region((6, 8))
        e._loop_var.set(True)
        with patch("app.views.audio_editor_dashboard.render_audio_project", return_value=Path("preview.wav")) as render:
            e._play_from_position(12)
            e._render_thread.join(5)
            self.assertFalse(e._render_thread.is_alive())
            self.assertEqual(render.call_args.kwargs["preview_region"], (12, 20))
            e.after_cancel(e._render_poll_id)
            e._poll_render_results()
        e._play_preview.assert_called_once_with(Path("preview.wav"))
        e._play_loop_preview.assert_not_called()
        self.assertTrue(e._preview_is_audition)
        e._preview_path = None

    def test_tk_double_click_events_start_preview_instead_of_adding_marker(self):
        e = self.editor
        e.transient("")
        e.deiconify()
        e.update()
        before = e._project
        with patch.object(e, "_start_render") as render:
            for timestamp in (1000, 1100):
                e.timeline.canvas.event_generate("<ButtonPress-1>", x=324, y=80, time=timestamp)
                e.timeline.canvas.event_generate("<ButtonRelease-1>", x=324, y=80, time=timestamp + 25)
            e.update()
        render.assert_called_once_with("preview")
        self.assertEqual(e._audition_region, (4, 20))
        self.assertEqual(e._project, before)
        self.assertEqual(e._undo_stack, [])
        self.assertIsNone(e.timeline._drag_origin)

    def test_marker_is_available_explicitly_in_context_menu(self):
        e = self.editor
        for clip_id in ("a", None):
            with (
                patch.object(e.timeline, "_clip_id_at_pointer", return_value=clip_id),
                patch("app.views.audio_timeline.tk.Menu") as menu,
                patch.object(e.timeline, "on_marker_added") as add_marker,
            ):
                e.timeline._show_clip_context_menu(SimpleNamespace(x=324, y=80, x_root=324, y_root=80))
                entry = next(
                    call.kwargs
                    for call in menu.return_value.add_command.call_args_list
                    if call.kwargs.get("label") == e.translate("audio_editor.add_marker_here")
                )
                entry["command"]()
                add_marker.assert_called_once_with(4)

    def setUp(self):
        gc.collect()
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = AudioEditorDashboard(
            self.root,
            source_paths=[],
            translate=I18n("en").t,
            colors=THEME_PRESETS["dark"],
            play_preview=Mock(),
            play_loop_preview=Mock(),
        )
        self.editor.attributes("-alpha", 0)
        self.editor._clips = [AudioEditClip(Path("source.wav"), 10, 30, id="a")]
        self.editor._refresh_project()
        self.editor.timeline.select_single_clip("a")
        self.editor._selection_changed("a")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.editor._render_busy = False
        self.editor.close()
        self.root.update()
        self.root.destroy()
        gc.collect()

    def test_cursor_trim_uses_source_offset_and_is_undoable(self):
        e = self.editor
        before = e._project
        e.timeline.set_playhead_position(4)
        e._trim_at_cursor("left")
        self.assertEqual((e._clips[0].source_start, e._clips[0].source_end), (14, 30))
        self.assertEqual(e._clips[0].timeline_start, 0)
        self.assertEqual(len(e._undo_stack), 1)
        e._undo()
        self.assertEqual(e._project, before)
        e.timeline.set_playhead_position(12)
        e._trim_at_cursor("right")
        self.assertEqual(e._clips[0].source_end, 22)

    def test_numeric_trim_preserves_unchanged_rounded_boundary(self):
        e = self.editor
        e._clips = [AudioEditClip(Path("source.wav"), 0, 148.8195918367347, id="a")]
        e._refresh_project()
        e._selection_changed("a")
        before = e._project
        e._trim_selected_clip()
        self.assertEqual(e._project, before)
        self.assertEqual(e._undo_stack, [])
        e._range_start_var.set("10.12")
        e._trim_selected_clip()
        self.assertEqual(e._clips[0].source_start, 10.12)
        self.assertEqual(e._clips[0].source_end, 148.8195918367347)
        e._undo()
        self.assertEqual(e._project, before)

    def test_numeric_trim_can_restore_audio_only_with_known_source_bounds(self):
        e = self.editor
        before = e._project
        e._range_start_var.set("5")
        e._range_end_var.set("35")
        e._trim_selected_clip()
        self.assertEqual(e._project, before)
        self.assertEqual(e._undo_stack, [])
        e._waveforms[Path("source.wav")] = AudioWaveform(40, (0.5,) * 20)
        e._trim_selected_clip()
        self.assertEqual((e._clips[0].source_start, e._clips[0].source_end), (5, 35))
        self.assertEqual(len(e._undo_stack), 1)
        restored = e._project
        e._range_end_var.set("41")
        e._trim_selected_clip()
        self.assertEqual(e._project, restored)
        self.assertEqual(len(e._undo_stack), 1)
        e._undo()
        self.assertEqual(e._project, before)

    def test_numeric_trim_preserves_precise_start_when_only_end_changes(self):
        e = self.editor
        e._clips = [AudioEditClip(Path("source.wav"), 10.123456, 30, id="a")]
        e._refresh_project()
        e._selection_changed("a")
        e._range_end_var.set("25")
        e._trim_selected_clip()
        self.assertEqual((e._clips[0].source_start, e._clips[0].source_end), (10.123456, 25))

    def test_numeric_trim_unchanged_inward_rounding_does_not_create_edit(self):
        e = self.editor
        e._clips = [AudioEditClip(Path("source.wav"), 10.123654, 30.123456, id="a")]
        e._refresh_project()
        e._selection_changed("a")
        before = e._project
        e._trim_selected_clip()
        self.assertEqual(e._project, before)
        self.assertEqual(e._undo_stack, [])

    def test_numeric_trim_is_blocked_during_render(self):
        e = self.editor
        before = e._project
        e._range_start_var.set("12")
        e._render_busy = True
        e._trim_selected_clip()
        self.assertEqual(e._project, before)
        self.assertEqual(e._undo_stack, [])

    def test_keyboard_navigation_is_precise_clamped_and_does_not_edit(self):
        e = self.editor
        before = e._project_state()
        e.timeline.set_preview_region((2, 4))
        e.timeline.set_playhead_position(2)
        e._navigate_cursor("forward", step=0.01)
        self.assertAlmostEqual(e.timeline.playhead_position, 2.01)
        self.assertIn("00:02.01", e._status_var.get())
        e._navigate_cursor("backward", step=0.1)
        self.assertAlmostEqual(e.timeline.playhead_position, 1.91)
        e._navigate_cursor("backward", step=100)
        self.assertEqual(e.timeline.playhead_position, 0)
        e._navigate_cursor("forward", step=100)
        self.assertEqual(e.timeline.playhead_position, 20)
        self.assertEqual(e._project_state(), before)
        self.assertEqual(e.timeline.selection_region, (2, 4))
        self.assertEqual(e._undo_stack, [])

    def test_navigation_uses_selection_bounds_and_reveals_cursor(self):
        e = self.editor
        e._mode = AudioEditMode.MULTITRACK
        e._tracks = [
            AudioEditTrack(
                "t",
                "Track",
                (
                    AudioEditClip(Path("source.wav"), 0, 20, timeline_start=100, id="a"),
                    AudioEditClip(Path("source.wav"), 0, 5, timeline_start=150, id="b"),
                ),
            )
        ]
        e._refresh_project()
        e.transient("")
        e.deiconify()
        e.update()
        e.timeline.set_selection(["a", "b"])
        e._navigate_cursor("start")
        self.assertEqual(e.timeline.playhead_position, 100)
        e._navigate_cursor("end")
        self.assertEqual(e.timeline.playhead_position, 155)
        canvas = e.timeline.canvas
        x = canvas.coords("playhead")[0] - canvas.canvasx(0)
        self.assertTrue(0 <= x <= canvas.winfo_width())
        e.timeline.select_single_clip(None)
        e._navigate_cursor("start")
        self.assertEqual(e.timeline.playhead_position, 0)

    def test_navigation_stops_audition_but_is_blocked_during_render(self):
        e = self.editor
        e._preview_active = True
        e._stop_preview = Mock()
        e._render_busy = True
        e._navigate_cursor("end")
        self.assertEqual(e.timeline.playhead_position, 0)
        self.assertTrue(e._preview_active)
        e._render_busy = False
        e._navigate_cursor("end")
        self.assertFalse(e._preview_active)
        self.assertEqual(e.timeline.playhead_position, 20)

    def test_arrow_binding_only_moves_cursor_with_timeline_focus(self):
        e = self.editor
        e.transient("")
        e.deiconify()
        e.update()
        e.timeline.canvas.focus_force()
        e.update()
        e.timeline.canvas.event_generate("<Shift-Right>")
        e.update()
        self.assertAlmostEqual(e.timeline.playhead_position, 0.01)
        entry = tk.Entry(e)
        entry.place(x=10, y=10)
        e.update()
        entry.focus_force()
        e.update()
        self.assertEqual(e.focus_get(), entry)
        entry.event_generate("<Right>")
        e.update()
        self.assertAlmostEqual(e.timeline.playhead_position, 0.01)

    def test_multitrack_start_keeps_other_endpoint(self):
        e = self.editor
        e._mode = AudioEditMode.MULTITRACK
        e._tracks = [
            AudioEditTrack("t", "Track", (AudioEditClip(Path("source.wav"), 10, 30, timeline_start=7, id="a"),))
        ]
        e._refresh_project()
        e.timeline.select_single_clip("a")
        e.timeline.set_playhead_position(11)
        e._trim_at_cursor("left")
        clip = e._project.tracks[0].clips[0]
        self.assertEqual((clip.source_start, clip.timeline_start, clip.timeline_end), (14, 11, 27))

    def test_invalid_boundary_busy_and_multiple_selection_do_not_edit(self):
        e = self.editor
        before = e._project
        for position in (0, 20, 25):
            e.timeline.set_playhead_position(position)
            e._trim_at_cursor("left")
            e._trim_at_cursor("right")
            self.assertEqual(e._project, before)
        e.timeline.set_playhead_position(3)
        e._render_busy = True
        e._trim_at_cursor("left")
        self.assertEqual(e._project, before)
        e._render_busy = False
        e.timeline.selected_clip_ids = {"a", "other"}
        e._trim_at_cursor("left")
        self.assertEqual(e._project, before)

    def test_audition_preserves_region_and_project_and_renders_five_seconds(self):
        e = self.editor
        e.timeline.set_preview_region((6, 8))
        e._loop_var.set(True)
        before = e._project
        with patch.object(e, "_start_render") as render:
            e._audition_edge("right")
        render.assert_called_once_with("preview")
        self.assertEqual(e._requested_preview_region(), (15, 20))
        self.assertEqual(e.timeline.selection_region, (6, 8))
        self.assertTrue(e._loop_var.get())
        self.assertEqual(e._project, before)
        self.assertEqual(len(e._undo_stack), 0)
        e._invalidate_preview()
        self.assertEqual(e._requested_preview_region(), (6, 8))

    def test_short_audition_is_clamped_and_uses_one_shot_callback(self):
        e = self.editor
        e._clips = [AudioEditClip(Path("short.wav"), 10, 12, id="a")]
        e._refresh_project()
        e.timeline.select_single_clip("a")
        with patch("app.views.audio_editor_dashboard.render_audio_project", return_value=Path("preview.wav")) as render:
            e._audition_edge("left")
            e._render_thread.join(5)
            self.assertFalse(e._render_thread.is_alive())
            self.assertEqual(render.call_args.kwargs["preview_region"], (0, 2))
            e.after_cancel(e._render_poll_id)
            e._poll_render_results()
        e._play_preview.assert_called_once_with(Path("preview.wav"))
        e._play_loop_preview.assert_not_called()
        e._preview_path = None

    def test_audition_position_does_not_wrap_and_normal_play_restores_loop(self):
        e = self.editor
        e._preview_is_audition = True
        e._preview_region_snapshot = (15, 20)
        e._audition_region = (15, 20)
        e._preview_active = True
        e._playback_position = lambda: 5.1
        e._preview_is_playing = lambda: True
        e.after_cancel(e._playback_poll_id)
        e._refresh_playback_display()
        self.assertEqual(e.timeline.playhead_position, 20)
        e._preview_active = False
        with patch.object(e, "_start_preview"):
            e._toggle_preview()
        self.assertIsNone(e._audition_region)

    def test_cancel_after_render_before_poll_does_not_start_audition(self):
        e = self.editor
        path = e._temp_dir / "cancelled.wav"
        path.write_bytes(b"preview")
        e._audition_region = (0, 5)
        e._render_busy = True
        e._render_results.put(("complete", ("preview", path, e._project, (0, 5), True)))
        e._render_cancel.set()
        e.after_cancel(e._render_poll_id)
        e._poll_render_results()
        e._play_preview.assert_not_called()
        self.assertFalse(path.exists())
        self.assertIsNone(e._audition_region)
        self.assertFalse(e._render_busy)

    def test_cancelled_worker_clears_pending_audition(self):
        e = self.editor
        e._audition_region = (0, 5)
        e._render_results.put(("cancelled", "cancelled"))
        e.after_cancel(e._render_poll_id)
        e._poll_render_results()
        self.assertIsNone(e._audition_region)

    def test_controls_disable_without_single_selection_and_summary_updates(self):
        e = self.editor
        self.assertTrue(all(str(button.cget("state")) == "normal" for button in e._quick_trim_buttons))
        e.timeline.set_playhead_position(4)
        e._trim_at_cursor("left")
        self.assertIn("14.00", e._range_hint.cget("text"))
        self.assertIn("16.00", e._range_hint.cget("text"))
        e.timeline.select_single_clip(None)
        e._sync_property_selection()
        self.assertTrue(all(str(button.cget("state")) == "disabled" for button in e._quick_trim_buttons))
        with patch.object(e, "_start_render") as render:
            e._audition_edge("left")
        render.assert_not_called()

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_export_contains_retained_audio_after_both_cursor_cuts(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            rate = 44100
            samples = [
                int(8000 * math.sin(2 * math.pi * (220 if i < rate else 440 if i < 3 * rate else 880) * i / rate))
                for i in range(4 * rate)
            ]
            with wave.open(str(source), "wb") as audio:
                audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
            original = source.read_bytes()
            e = self.editor
            e._clips = [AudioEditClip(source, 0, 4, id="a")]
            e._refresh_project()
            e.timeline.select_single_clip("a")
            e.timeline.set_playhead_position(1)
            e._trim_at_cursor("left")
            e.timeline.set_playhead_position(2)
            e._trim_at_cursor("right")
            output = export_audio_project(e._project, Path(folder), "trimmed", ".wav")
            with wave.open(str(output), "rb") as audio:
                self.assertAlmostEqual(audio.getnframes() / audio.getframerate(), 2, places=3)
                data = audio.readframes(audio.getnframes())
                values = struct.unpack(f"<{len(data) // 2}h", data)[:: audio.getnchannels()]
                for start in (0, len(values) - rate // 2):
                    segment = values[start : start + rate // 2]
                    crossings = sum(a <= 0 < b for a, b in zip(segment, segment[1:], strict=False))
                    self.assertAlmostEqual(crossings / 0.5, 440, delta=4)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
