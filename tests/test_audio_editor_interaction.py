import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip, AudioEditMode, AudioEditTrack
from app.services.audio_waveform_service import AudioWaveform
from app.ui.theme import THEME_PRESETS
from app.views.audio_editor_dashboard import AudioEditorDashboard


class EditorInteractionTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = AudioEditorDashboard(
            self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"]
        )
        self.editor.attributes("-alpha", 0)
        self.addCleanup(self.cleanup_editor)
        self.source = Path("new-source.wav")
        self.editor._paths = [self.source]
        self.editor._waveforms[self.source] = AudioWaveform(4, (0.5,) * 20)

    def cleanup_editor(self):
        self.editor.close()
        self.root.update()
        self.root.destroy()

    def sequence(self):
        self.editor._clips = [
            AudioEditClip(Path(name + ".wav"), 0, 10, timeline_start=index * 10, id=name)
            for index, name in enumerate(("a", "b", "c"))
        ]
        self.editor._refresh_project()
        self.editor.timeline.select_single_clip("a")
        self.editor._selection_changed("a")

    def multitrack(self):
        self.editor._mode = AudioEditMode.MULTITRACK
        self.editor._tracks = [
            AudioEditTrack("track", "Track", (AudioEditClip(Path("a.wav"), 0, 10, timeline_start=5, id="a"),))
        ]
        self.editor._refresh_project()
        self.editor.transient("")
        self.editor.deiconify()
        self.editor.update()
        self.editor.timeline.snap_enabled = False

    def test_trim_left_preview_commit_and_undo(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        before = self.editor._project
        timeline._select_at_pointer(SimpleNamespace(x=235, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=294, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        self.assertTrue(timeline.canvas.find_withtag("trim-preview"))
        timeline._move_clip_at_pointer(SimpleNamespace(x=294, y=90, state=0))
        clip = self.editor._tracks[0].clips[0]
        self.assertAlmostEqual(clip.source_start, 2)
        self.assertAlmostEqual(clip.timeline_start, 7)
        self.assertAlmostEqual(clip.timeline_end, 15)
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual(self.editor._project, before)

    def test_trim_escape_cancels_without_history(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        before = self.editor._project
        timeline._select_at_pointer(SimpleNamespace(x=533, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=474, y=90, state=0))
        timeline.cancel_drag()
        timeline._move_clip_at_pointer(SimpleNamespace(x=474, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)
        self.assertFalse(timeline.canvas.find_withtag("trim-preview"))

    def test_trim_right_sequence_ripples_following_clips(self):
        self.sequence()
        self.editor._trim_clip_on_timeline("a", "right", 7)
        self.assertEqual(self.editor._clips[0].duration, 7)
        self.assertEqual(self.editor._clips[1].timeline_start, 7)
        self.assertEqual(self.editor._clips[2].timeline_start, 17)
        self.assertEqual(len(self.editor._undo_stack), 1)

    def test_trim_right_gesture_clamps_to_positive_duration(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        timeline._select_at_pointer(SimpleNamespace(x=533, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=90, y=90, state=0))
        timeline._move_clip_at_pointer(SimpleNamespace(x=90, y=90, state=0))
        clip = self.editor._tracks[0].clips[0]
        self.assertAlmostEqual(clip.duration, 0.05)
        self.assertEqual(clip.timeline_start, 5)

    def test_sequence_left_trim_preview_matches_committed_interval(self):
        self.sequence()
        self.editor.deiconify()
        self.editor.update()
        timeline = self.editor.timeline
        timeline.snap_enabled = False
        timeline.pixels_per_second = 30
        timeline.redraw()
        timeline._select_at_pointer(SimpleNamespace(x=385, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=444, y=90, state=0))
        rectangle = timeline.canvas.find_withtag("trim-preview")[0]
        x1, _, x2, _ = timeline.canvas.coords(rectangle)
        self.assertEqual(x1, 384)
        self.assertEqual(x2, 624)
        timeline._move_clip_at_pointer(SimpleNamespace(x=444, y=90, state=0))
        self.assertEqual(self.editor._clips[1].timeline_start, 10)
        self.assertEqual(self.editor._clips[1].timeline_end, 18)

    def test_restore_right_edge_uses_source_limit_and_undo(self):
        self.multitrack()
        self.editor._waveforms[Path("a.wav")] = AudioWaveform(12, (0.5,) * 20)
        self.editor._refresh_project()
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        before = self.editor._project
        timeline._select_at_pointer(SimpleNamespace(x=533, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=700, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        timeline._move_clip_at_pointer(SimpleNamespace(x=700, y=90, state=0))
        self.assertEqual(self.editor._tracks[0].clips[0].source_end, 12)
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual(self.editor._project, before)

    def test_restore_first_sequence_left_edge_before_time_zero(self):
        self.editor._clips = [AudioEditClip(self.source, 2, 4, id="a")]
        self.editor._refresh_project()
        self.editor.deiconify()
        self.editor.update()
        timeline = self.editor.timeline
        timeline.snap_enabled = False
        timeline.pixels_per_second = 30
        timeline.redraw()
        timeline._select_at_pointer(SimpleNamespace(x=85, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=24, y=90, state=0))
        timeline._move_clip_at_pointer(SimpleNamespace(x=24, y=90, state=0))
        self.assertEqual(self.editor._clips[0].source_start, 0)
        self.assertEqual(self.editor._clips[0].timeline_start, 0)
        self.assertEqual(self.editor._clips[0].duration, 4)

    def test_restore_left_multitrack_stops_at_timeline_zero(self):
        self.multitrack()
        self.editor._tracks = [
            AudioEditTrack("track", "Track", (AudioEditClip(self.source, 2, 4, timeline_start=1, id="a"),))
        ]
        self.editor._refresh_project()
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        timeline._select_at_pointer(SimpleNamespace(x=115, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=24, y=90, state=0))
        timeline._move_clip_at_pointer(SimpleNamespace(x=24, y=90, state=0))
        clip = self.editor._tracks[0].clips[0]
        self.assertEqual((clip.source_start, clip.timeline_start, clip.timeline_end), (1, 0, 3))

    def test_restore_rejects_broken_crossfade_without_history(self):
        self.multitrack()
        source = Path("a.wav")
        self.editor._waveforms[source] = AudioWaveform(15, (0.5,) * 20)
        self.editor._tracks = [
            AudioEditTrack(
                "track",
                "Track",
                (
                    AudioEditClip(source, 0, 10, id="a"),
                    AudioEditClip(source, 0, 10, timeline_start=8, crossfade_in=2, id="b"),
                ),
            )
        ]
        self.editor._refresh_project()
        before = self.editor._project
        self.editor._trim_clip_on_timeline("a", "right", 12)
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)

    def test_sequence_restore_can_scroll_past_original_project_end(self):
        self.sequence()
        self.editor.deiconify()
        self.editor.update()
        timeline = self.editor.timeline
        self.editor._waveforms[Path("a.wav")] = AudioWaveform(200, (0.5,) * 20)
        self.editor._refresh_project()
        timeline.pixels_per_second = 30
        timeline.redraw()
        timeline._select_at_pointer(SimpleNamespace(x=383, y=90, state=0))
        timeline.canvas.xview_moveto(1)
        timeline._drag_motion(SimpleNamespace(x=timeline.canvas.winfo_width() - 5, y=90))
        if timeline._drag_scroll_id is not None:
            timeline.after_cancel(timeline._drag_scroll_id)
        before = float(timeline.canvas.cget("scrollregion").split()[2])
        timeline._autoscroll_tick()
        after = float(timeline.canvas.cget("scrollregion").split()[2])
        self.assertGreater(after, before)
        timeline.cancel_drag()

    def test_restore_fractional_source_limit_ignores_roundoff(self):
        self.multitrack()
        source = Path("a.wav")
        self.editor._waveforms[source] = AudioWaveform(12.3, (0.5,) * 20)
        clip = AudioEditClip(source, 0.1, 4.3, timeline_start=100.1, id="a")
        self.editor._tracks = [AudioEditTrack("track", "Track", (clip,))]
        self.editor._refresh_project()
        limit = clip.timeline_end + 12.3 - clip.source_end
        self.editor._trim_clip_on_timeline("a", "right", limit)
        self.assertEqual(self.editor._tracks[0].clips[0].source_end, 12.3)

    def fade_handle_event(self, side):
        timeline = self.editor.timeline
        item = timeline.canvas.find_withtag(f"fade-handle:a:{side}")[0]
        x1, y1, x2, y2 = timeline.canvas.coords(item)
        return SimpleNamespace(x=(x1 + x2) / 2, y=(y1 + y2) / 2, state=0)

    def test_fade_handle_preview_commits_once_and_undo_restores(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.select_single_clip("a")
        timeline.redraw()
        press = self.fade_handle_event("in")
        release = SimpleNamespace(x=press.x + 120, y=press.y, state=0)
        before = self.editor._project
        timeline._select_at_pointer(press)
        timeline._drag_motion(release)
        self.assertEqual(self.editor._project, before)
        self.assertTrue(timeline.canvas.find_withtag("fade-preview"))
        timeline._move_clip_at_pointer(release)
        self.assertEqual(self.editor._tracks[0].clips[0].fade_in, 2)
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual(self.editor._project, before)

    def test_fade_drag_cancel_and_click_do_not_edit(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.select_single_clip("a")
        timeline.redraw()
        press = self.fade_handle_event("in")
        before = self.editor._project
        timeline._select_at_pointer(press)
        timeline._move_clip_at_pointer(press)
        self.assertEqual(len(self.editor._undo_stack), 0)
        timeline._select_at_pointer(press)
        timeline._drag_motion(SimpleNamespace(x=press.x + 60, y=press.y, state=0))
        timeline.cancel_drag()
        timeline._move_clip_at_pointer(press)
        self.assertEqual(self.editor._project, before)
        self.assertFalse(timeline.canvas.find_withtag("fade-preview"))
        self.assertEqual(len(self.editor._undo_stack), 0)

    def test_fade_out_clamps_to_duration_minus_fade_in(self):
        self.multitrack()
        self.editor._fade_clip_on_timeline("a", "in", 3)
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        press = self.fade_handle_event("out")
        timeline._select_at_pointer(press)
        release = SimpleNamespace(x=press.x - 400, y=press.y, state=0)
        timeline._drag_motion(release)
        timeline._move_clip_at_pointer(release)
        clip = self.editor._tracks[0].clips[0]
        self.assertEqual((clip.fade_in, clip.fade_out), (3, 7))

    def test_crossfade_sides_have_no_fade_handles(self):
        self.multitrack()
        source = Path("a.wav")
        self.editor._tracks = [
            AudioEditTrack(
                "track",
                "Track",
                (
                    AudioEditClip(source, 0, 10, id="a"),
                    AudioEditClip(source, 0, 10, timeline_start=8, crossfade_in=2, id="b"),
                ),
            )
        ]
        self.editor._refresh_project()
        timeline = self.editor.timeline
        timeline.set_selection(["a", "b"], primary_id="a")
        timeline.redraw()
        self.assertFalse(timeline.canvas.find_withtag("fade-handle:a:out"))
        self.assertFalse(timeline.canvas.find_withtag("fade-handle:b:in"))
        self.assertTrue(timeline.canvas.find_withtag("fade-handle:a:in"))
        before = self.editor._project
        self.editor._fade_clip_on_timeline("a", "out", 2)
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)

    def long_timeline(self):
        self.multitrack()
        self.editor._tracks = [AudioEditTrack("track", "Track", (AudioEditClip(Path("a.wav"), 0, 180, id="a"),))]
        self.editor._refresh_project()
        self.editor.timeline.canvas.xview_moveto(0.35)

    def test_wheel_zoom_preserves_time_under_pointer(self):
        self.long_timeline()
        timeline = self.editor.timeline
        before = self.editor._project
        pointer = 217
        time = (timeline.canvas.canvasx(pointer) - 84) / timeline.pixels_per_second
        timeline._on_zoom_mousewheel(SimpleNamespace(delta=120, x=pointer))
        after = (timeline.canvas.canvasx(pointer) - 84) / timeline.pixels_per_second
        self.assertAlmostEqual(after, time, delta=1 / timeline.pixels_per_second)
        timeline._on_zoom_mousewheel(SimpleNamespace(delta=-120, x=pointer))
        after = (timeline.canvas.canvasx(pointer) - 84) / timeline.pixels_per_second
        self.assertAlmostEqual(after, time, delta=2 / timeline.pixels_per_second)
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)

    def test_zoom_buttons_preserve_viewport_center(self):
        self.long_timeline()
        timeline = self.editor.timeline
        center = timeline.canvas.winfo_width() / 2
        time = (timeline.canvas.canvasx(center) - 84) / timeline.pixels_per_second
        self.editor._zoom(1.25)
        after = (timeline.canvas.canvasx(center) - 84) / timeline.pixels_per_second
        self.assertAlmostEqual(after, time, delta=1 / timeline.pixels_per_second)

    def test_zoom_cancels_active_edit_without_history(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline._select_at_pointer(SimpleNamespace(x=414, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=474, y=90, state=0))
        before = self.editor._project
        timeline.zoom(1.25)
        timeline._move_clip_at_pointer(SimpleNamespace(x=474, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)
        self.assertIsNone(timeline._drag_scroll_id)

    def test_fit_cancels_edit_and_returns_to_start(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline._select_at_pointer(SimpleNamespace(x=414, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=474, y=90, state=0))
        before = self.editor._project
        self.editor._fit_project()
        timeline._move_clip_at_pointer(SimpleNamespace(x=474, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        self.assertAlmostEqual(timeline.canvas.xview()[0], 0)
        self.assertEqual(len(self.editor._undo_stack), 0)

    def test_zero_wheel_delta_does_not_zoom(self):
        self.long_timeline()
        timeline = self.editor.timeline
        before = timeline.pixels_per_second, timeline.canvas.xview()
        timeline._on_zoom_mousewheel(SimpleNamespace(delta=0, x=200))
        self.assertEqual((timeline.pixels_per_second, timeline.canvas.xview()), before)

    def test_horizontal_scrollbar_keeps_twenty_pixel_steps(self):
        self.long_timeline()
        timeline = self.editor.timeline
        before = timeline.canvas.canvasx(0)
        command = timeline.horizontal_scrollbar.cget("command")
        timeline.tk.call(command, "scroll", "1", "units")
        self.assertEqual(timeline.canvas.canvasx(0) - before, 20)
        timeline._on_mousewheel(SimpleNamespace(delta=120))
        self.assertEqual(timeline.canvas.canvasx(0), before)

    def test_zoom_limits_and_empty_fit_remain_finite(self):
        self.long_timeline()
        timeline = self.editor.timeline
        timeline.zoom(1000)
        self.assertEqual(timeline.pixels_per_second, 480)
        before = timeline.canvas.xview()
        timeline.zoom(1.25)
        self.assertEqual(timeline.canvas.xview(), before)
        timeline.zoom(0.000001)
        self.assertEqual(timeline.pixels_per_second, 0.05)
        self.editor._tracks = []
        self.editor._refresh_project()
        self.editor._fit_project()
        self.assertGreater(timeline.pixels_per_second, 0)
        self.assertEqual(timeline.canvas.xview()[0], 0)

    def test_trim_outward_is_noop(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.pixels_per_second = 30
        timeline.redraw()
        before = self.editor._project
        timeline._select_at_pointer(SimpleNamespace(x=533, y=90, state=0))
        timeline._drag_motion(SimpleNamespace(x=570, y=90, state=0))
        timeline._move_clip_at_pointer(SimpleNamespace(x=570, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        self.assertEqual(len(self.editor._undo_stack), 0)

    def test_remove_last_clip_and_restore_with_undo(self):
        self.editor._clips = [AudioEditClip(self.source, 0, 4, id="only")]
        self.editor._refresh_project()
        self.editor.timeline.select_single_clip("only")
        self.editor._remove_selected_clip()
        self.assertEqual(self.editor._clips, [])
        self.assertEqual(self.editor._project.duration, 0)
        self.editor._undo()
        self.assertEqual(self.editor._clips[0].id, "only")
        self.editor._redo()
        self.assertEqual(self.editor._clips, [])

    def test_remove_source_preserves_timeline_and_waveform(self):
        self.sequence()
        before = self.editor._project
        self.editor._refresh_source_list()
        self.editor.source_list.selection_set(0)
        self.editor._remove_selected_sources()
        self.assertEqual(self.editor._paths, [])
        self.assertEqual(self.editor._project, before)
        self.assertIn(self.source, self.editor._waveforms)

    def test_saved_empty_session_overrides_library_import_on_reopen(self):
        with TemporaryDirectory() as folder:
            saved = Path(folder) / "session.json"
            self.editor._project_path = saved
            self.editor._paths = []
            self.assertTrue(self.editor._save_editor_project())
            reopened = AudioEditorDashboard(
                self.root,
                source_paths=[self.source],
                translate=I18n("en").t,
                colors=THEME_PRESETS["dark"],
                project_path=saved,
            )
            try:
                self.assertEqual(reopened._paths, [])
                self.assertEqual(reopened._clips, [])
                self.assertEqual(reopened._auto_add_paths, set())
            finally:
                reopened.close()
                self.editor._project_path = None

    def test_editor_is_a_normal_resizable_window(self):
        self.assertEqual(str(self.editor.transient()), "")
        self.assertEqual(self.editor.resizable(), (1, 1))

    def test_sequence_drag_reorders_and_undo_restores(self):
        self.sequence()
        self.editor._move_clip_on_timeline("a", 0, 30)
        self.assertEqual([clip.id for clip in self.editor._clips], ["b", "c", "a"])
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual([clip.id for clip in self.editor._clips], ["a", "b", "c"])

    def test_source_drop_inserts_at_boundary_and_is_one_undo(self):
        self.sequence()
        self.editor._drop_source_paths([self.source, self.source], 0, 11)
        self.assertEqual(
            [clip.source_path for clip in self.editor._clips],
            [Path("a.wav"), self.source, self.source, Path("b.wav"), Path("c.wav")],
        )
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual([clip.id for clip in self.editor._clips], ["a", "b", "c"])

    def test_drag_preview_preserves_grab_offset_and_commits_once(self):
        self.multitrack()
        timeline = self.editor.timeline
        press = SimpleNamespace(x=414, y=90, state=0)
        release = SimpleNamespace(x=534, y=90, state=0)
        timeline._select_at_pointer(press)
        before = self.editor._project
        timeline._drag_motion(release)
        self.assertEqual(self.editor._project, before)
        self.assertTrue(timeline.canvas.find_withtag("drag-preview"))
        timeline._move_clip_at_pointer(release)
        self.assertAlmostEqual(self.editor._tracks[0].clips[0].timeline_start, 7)
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.assertFalse(timeline.canvas.find_withtag("drag-preview"))

    def test_escape_cancels_preview_and_history(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline._select_at_pointer(SimpleNamespace(x=414, y=90, state=0))
        before = self.editor._project
        timeline._drag_motion(SimpleNamespace(x=534, y=90, state=0))
        timeline.cancel_drag()
        timeline._move_clip_at_pointer(SimpleNamespace(x=534, y=90, state=0))
        self.assertEqual(self.editor._project, before)
        self.assertEqual(self.editor._undo_stack, [])
        self.assertIsNone(timeline._drag_scroll_id)

    def test_multitrack_source_drop_creates_lane_in_source_order(self):
        self.multitrack()
        self.editor._drop_source_paths([self.source, self.source], 1, 3)
        self.assertEqual(len(self.editor._tracks), 2)
        self.assertEqual([clip.timeline_start for clip in self.editor._tracks[1].clips], [3, 7])
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual(len(self.editor._tracks), 1)

    def test_edge_scroll_moves_view_without_editing_and_cancel_stops_timer(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline._select_at_pointer(SimpleNamespace(x=414, y=90, state=0))
        before = self.editor._project
        timeline._drag_motion(SimpleNamespace(x=timeline.canvas.winfo_width() - 5, y=90))
        self.assertIsNotNone(timeline._drag_scroll_id)
        timeline.after_cancel(timeline._drag_scroll_id)
        view = timeline.canvas.xview()
        timeline._autoscroll_tick()
        self.assertGreater(timeline.canvas.xview()[0], view[0])
        self.assertEqual(self.editor._project, before)
        self.editor._cancel_editor_drag()
        self.assertIsNone(timeline._drag_scroll_id)
        self.assertFalse(timeline.canvas.find_withtag("drag-preview"))

    def test_external_drop_outside_canvas_does_not_edit(self):
        self.multitrack()
        timeline = self.editor.timeline
        timeline.start_source_drag([("New source", 4)])
        timeline.update_source_drag(-10, 90)
        self.assertIsNone(timeline.finish_source_drag())
        self.assertEqual(self.editor._undo_stack, [])

    def test_source_drag_survives_background_project_refresh(self):
        self.multitrack()
        self.editor._refresh_source_list()
        listing = self.editor.source_list
        listing.selection_set(0)
        self.editor._source_press(
            SimpleNamespace(y=3, state=0, x_root=listing.winfo_rootx() + 10, y_root=listing.winfo_rooty() + 3)
        )
        canvas = self.editor.timeline.canvas
        pointer = SimpleNamespace(x_root=canvas.winfo_rootx() + 300, y_root=canvas.winfo_rooty() + 90)
        self.editor._source_motion(pointer)
        self.assertIsNotNone(self.editor._source_drag_ghost)
        self.assertTrue(self.editor._source_drag_ghost.winfo_exists())
        self.editor._refresh_project()
        self.editor._source_release(pointer)
        self.assertIsNone(self.editor._source_drag_ghost)
        self.assertEqual(len(self.editor._tracks[0].clips), 2)
        self.assertEqual(len(self.editor._undo_stack), 1)

    def test_source_divider_is_inside_gap_and_above_neighbor_widgets(self):
        self.multitrack()
        panel = self.editor._source_panel
        grip = self.editor._source_grip
        center = self.editor._timeline_center
        self.assertGreaterEqual(grip.winfo_rootx(), panel.winfo_rootx() + panel.winfo_width())
        self.assertLessEqual(grip.winfo_rootx() + grip.winfo_width(), center.winfo_rootx())

    def test_sources_width_is_adjustable_and_preserves_timeline_space(self):
        self.multitrack()
        self.editor._set_source_width(500)
        self.editor.update()
        self.assertEqual(int(self.editor._source_panel.cget("width")), 500)
        self.assertGreater(self.editor.timeline.canvas.winfo_width(), 400)
        self.editor.geometry("860x600")
        self.editor.update()
        self.assertLessEqual(int(self.editor._source_panel.cget("width")), 380)

    def test_unready_or_busy_source_drop_does_not_partially_insert(self):
        self.sequence()
        before = self.editor._project
        self.editor._drop_source_paths([self.source, Path("not-ready.wav")], 0, 11)
        self.assertEqual(self.editor._project, before)
        self.editor._render_busy = True
        self.editor._drop_source_paths([self.source], 0, 11)
        self.editor._render_busy = False
        self.assertEqual(self.editor._project, before)
        self.assertEqual(self.editor._undo_stack, [])


if __name__ == "__main__":
    unittest.main()
