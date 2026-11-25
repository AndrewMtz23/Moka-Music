import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.i18n import I18n
from app.models.audio_edit_project import (
    AudioEditClip,
    AudioEditEffect,
    AudioEditMarker,
    AudioEditMode,
    AudioEditProcessing,
    AudioEditProject,
    AudioEditTrack,
)
from app.views.audio_editor_dashboard import AudioEditorDashboard
from app.views.audio_effect_chain_dialog import edit_audio_effect_chain


class AudioEditorDashboardTests(unittest.TestCase):
    def _create_editor(self) -> AudioEditorDashboard:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)

        def cleanup() -> None:
            editor.close()
            root.update()
            root.destroy()

        self.addCleanup(cleanup)
        return editor

    def test_preview_transport_restores_previous_playback_when_window_closes(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        snapshot = object()
        played = []
        paused = []
        resumed = []
        stopped = []
        restored = []
        editor = AudioEditorDashboard(
            root,
            source_paths=[],
            translate=I18n().t,
            colors=colors,
            playback_snapshot=snapshot,
            play_preview=played.append,
            pause_preview=lambda: paused.append(True),
            resume_preview=lambda: resumed.append(True),
            stop_preview=lambda: stopped.append(True),
            restore_playback=restored.append,
        )
        try:
            clip = AudioEditClip(Path("source.wav"), 0, 1, id="clip")
            project = AudioEditProject(tracks=(AudioEditTrack("sequence", "Sequence", (clip,)),))
            preview_path = editor._temp_dir / "preview.wav"
            preview_path.write_bytes(b"preview")
            editor._project = project
            editor._preview_path = preview_path
            editor._preview_project_snapshot = project
            self.assertEqual(editor._play_pause_button.cget("text"), "▶")
            self.assertEqual(str(editor._stop_button.cget("state")), "disabled")
            editor._toggle_preview()
            self.assertEqual(played, [preview_path])
            self.assertTrue(editor._preview_active)
            self.assertEqual(editor._play_pause_button.cget("text"), "⏸")
            editor._toggle_preview()
            self.assertEqual(paused, [True])
            self.assertEqual(editor._play_pause_button.cget("text"), "▶")
            editor._toggle_preview()
            self.assertEqual(resumed, [True])
            self.assertEqual(editor._play_pause_button.cget("text"), "⏸")
            editor._stop()
            self.assertEqual(editor._play_pause_button.cget("text"), "▶")
        finally:
            editor.close()
            root.update()
            root.destroy()

        self.assertEqual(stopped, [True])
        self.assertEqual(restored, [snapshot])

    def test_clip_gain_and_pan_controls_apply_to_multiple_clips_with_undo_redo(self):
        editor = self._create_editor()
        editor._clips = [
            AudioEditClip(Path("first.wav"), 0, 2, id="first", gain_db=-3, pan=-0.25),
            AudioEditClip(Path("second.wav"), 0, 2, timeline_start=2, id="second", gain_db=6, pan=0.5),
        ]
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="second")
        editor._selection_changed("second")
        self.assertEqual(editor._clip_gain_var.get(), "")
        self.assertEqual(editor._clip_pan_var.get(), "")

        editor._clip_gain_var.set("-6")
        editor._clip_pan_var.set("-75")
        editor._apply_clip_mix()

        self.assertEqual(
            [(clip.gain_db, clip.pan) for clip in editor._project.tracks[0].clips],
            [(-6.0, -0.75), (-6.0, -0.75)],
        )
        editor._undo()
        self.assertEqual(
            [(clip.gain_db, clip.pan) for clip in editor._project.tracks[0].clips],
            [(-3.0, -0.25), (6.0, 0.5)],
        )
        editor._redo()
        self.assertEqual(
            [(clip.gain_db, clip.pan) for clip in editor._project.tracks[0].clips],
            [(-6.0, -0.75), (-6.0, -0.75)],
        )

    def test_clip_mix_controls_reject_out_of_range_values_without_changing_project(self):
        editor = self._create_editor()
        editor._clips = [AudioEditClip(Path("source.wav"), 0, 2, id="clip")]
        editor._refresh_project()
        editor.timeline.select_single_clip("clip")
        editor._clip_gain_var.set("13")
        editor._clip_pan_var.set("0")

        editor._apply_clip_mix()

        self.assertEqual((editor._clips[0].gain_db, editor._clips[0].pan), (0.0, 0.0))
        self.assertIn("No se pudo aplicar", editor._status_var.get())

    def test_clip_mix_is_preserved_when_switching_modes(self):
        editor = self._create_editor()
        editor._clips = [AudioEditClip(Path("source.wav"), 0, 2, id="clip", gain_db=-9, pan=-0.4)]
        editor._refresh_project()

        editor._switch_mode(AudioEditMode.MULTITRACK)
        self.assertEqual((editor._tracks[0].clips[0].gain_db, editor._tracks[0].clips[0].pan), (-9, -0.4))
        editor._switch_mode(AudioEditMode.SEQUENCE)

        self.assertEqual((editor._clips[0].gain_db, editor._clips[0].pan), (-9, -0.4))

    def test_processing_dialog_changes_multiple_selected_clips_and_supports_undo(self):
        editor = self._create_editor()
        editor._clips = [
            AudioEditClip(Path("first.wav"), 0, 2, id="first"),
            AudioEditClip(Path("second.wav"), 0, 2, timeline_start=2, id="second"),
        ]
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="first")
        processing = AudioEditProcessing(low_gain_db=3, compressor_enabled=True, bypassed=True)

        with patch("app.views.audio_editor_dashboard.edit_audio_processing", return_value=processing):
            editor._edit_clip_processing()

        self.assertEqual([clip.processing for clip in editor._clips], [processing, processing])
        editor._undo()
        self.assertEqual([clip.processing for clip in editor._clips], [AudioEditProcessing(), AudioEditProcessing()])

    def test_fx_chain_changes_multiple_selected_clips_and_is_undoable(self):
        editor = self._create_editor()
        editor._clips = [
            AudioEditClip(Path("first.wav"), 0, 2, id="first"),
            AudioEditClip(Path("second.wav"), 0, 2, timeline_start=2, id="second"),
        ]
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="first")
        chain = (AudioEditEffect("delay", wet=0.4, delay_ms=240), AudioEditEffect("reverb"))

        with patch("app.views.audio_editor_dashboard.edit_audio_effect_chain", return_value=chain):
            editor._edit_clip_effects()

        self.assertEqual([clip.effects for clip in editor._clips], [chain, chain])
        editor._undo()
        self.assertEqual([clip.effects for clip in editor._clips], [(), ()])

    def test_fx_chain_dialog_adds_and_reorders_effects(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()

        def find_widgets(parent, widget_type):
            found = []
            for child in parent.winfo_children():
                if isinstance(child, widget_type):
                    found.append(child)
                found.extend(find_widgets(child, widget_type))
            return found

        def drive_dialog(dialog):
            buttons = {button.cget("text"): button for button in find_widgets(dialog, ttk.Button)}
            buttons[I18n().t("audio_editor.fx_add_delay")].invoke()
            buttons[I18n().t("audio_editor.fx_add_reverb")].invoke()
            lists = find_widgets(dialog, tk.Listbox)
            lists[0].selection_clear(0, tk.END)
            lists[0].selection_set(1)
            lists[0].event_generate("<<ListboxSelect>>")
            buttons[I18n().t("audio_editor.fx_move_up")].invoke()
            buttons[I18n().t("audio_editor.apply_processing")].invoke()

        try:
            with patch.object(tk.Toplevel, "wait_window", autospec=True, side_effect=drive_dialog):
                result = edit_audio_effect_chain(root, (), I18n().t)
            self.assertEqual(
                [effect.kind.value for effect in result],
                ["reverb", "delay"],
            )
        finally:
            root.destroy()

    def test_right_click_context_menu_removes_the_clicked_clip(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)
        try:
            first = AudioEditClip(Path("first.wav"), 0, 2, id="first")
            second = AudioEditClip(Path("second.wav"), 0, 2, timeline_start=2, id="second")
            editor._clips = [first, second]
            editor._refresh_project()
            event = SimpleNamespace(x=100, y=70, x_root=100, y_root=70)
            with patch("app.views.audio_timeline.tk.Menu") as menu_factory:
                editor.timeline._show_clip_context_menu(event)
                delete_call = next(
                    call
                    for call in menu_factory.return_value.add_command.call_args_list
                    if call.kwargs["label"] == I18n().t("audio_editor.delete_clip")
                )
                delete_call.kwargs["command"]()

            self.assertEqual([clip.id for clip in editor._clips], ["second"])
        finally:
            editor.close()
            root.update()
            root.destroy()

    def test_keyboard_shortcuts_run_from_timeline_but_not_source_list(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)
        try:
            for sequence in ("<space>", "<Delete>", "<Control-z>", "<Control-y>", "<Control-Shift-Z>"):
                self.assertTrue(editor.bind(sequence), f"Missing binding for {sequence}")

            action = unittest.mock.Mock()
            with patch.object(editor, "focus_get", return_value=editor.source_list):
                result = editor._run_shortcut(SimpleNamespace(), action)
            self.assertIsNone(result)
            action.assert_not_called()

            with patch.object(editor, "focus_get", return_value=editor.timeline.canvas):
                result = editor._run_shortcut(SimpleNamespace(), action)
            self.assertEqual(result, "break")
            action.assert_called_once_with()
        finally:
            editor.close()
            root.update()
            root.destroy()

    def test_ctrl_click_selects_multiple_clips_and_delete_removes_the_group(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)
        try:
            editor._clips = [
                AudioEditClip(Path("first.wav"), 0, 2, id="first"),
                AudioEditClip(Path("second.wav"), 0, 2, timeline_start=2, id="second"),
                AudioEditClip(Path("third.wav"), 0, 2, timeline_start=4, id="third"),
            ]
            editor._refresh_project()
            editor.timeline._select_at_pointer(SimpleNamespace(x=100, y=70, state=0))
            editor.timeline._select_at_pointer(SimpleNamespace(x=250, y=70, state=0x0004))

            self.assertEqual(editor.timeline.selected_clip_ids, ["first", "second"])
            self.assertEqual(editor.timeline.selected_clip_id, "second")

            editor._remove_selected_clip()

            self.assertEqual([clip.id for clip in editor._clips], ["third"])
            self.assertEqual(editor.timeline.selected_clip_ids, ["third"])
        finally:
            editor.close()
            root.update()
            root.destroy()

    def test_group_edits_use_relative_ranges_and_move_clips_together(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)
        try:
            editor._mode = AudioEditMode.MULTITRACK
            editor._tracks = [
                AudioEditTrack("track-1", "Track 1", (AudioEditClip(Path("first.wav"), 10, 15, id="first"),)),
                AudioEditTrack(
                    "track-2",
                    "Track 2",
                    (AudioEditClip(Path("second.wav"), 20, 25, timeline_start=3, id="second"),),
                ),
            ]
            editor._selected_track_id = "track-1"
            editor._refresh_project()
            editor.timeline.set_selection(["first", "second"], primary_id="first")
            editor._selection_changed("first")

            editor._fade_in_var.set("0.5")
            editor._fade_out_var.set("0.25")
            editor._apply_fades()
            editor._range_start_var.set("1")
            editor._range_end_var.set("4")
            editor._trim_selected_clip()

            self.assertEqual(
                [
                    (clip.source_start, clip.source_end, clip.fade_in, clip.fade_out)
                    for track in editor._tracks
                    for clip in track.clips
                ],
                [(11, 14, 0.5, 0.25), (21, 24, 0.5, 0.25)],
            )

            editor._range_start_var.set("0.5")
            editor._range_end_var.set("1")
            editor._remove_selected_range()
            self.assertEqual(len(editor.timeline.selected_clip_ids), 4)
            editor.timeline.set_playhead_position(5)
            self.assertEqual(editor.timeline.playhead_position, 5)
            editor._move_selected_clip_to_cursor()

            self.assertEqual(
                [[clip.timeline_start for clip in track.clips] for track in editor._tracks],
                [[5, 5.5], [8, 8.5]],
            )
        finally:
            editor.close()
            root.update()
            root.destroy()

    def test_group_split_applies_to_each_selected_clip_at_shared_cursor(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)
        try:
            editor._mode = AudioEditMode.MULTITRACK
            editor._tracks = [
                AudioEditTrack("track-1", "Track 1", (AudioEditClip(Path("first.wav"), 10, 16, id="first"),)),
                AudioEditTrack("track-2", "Track 2", (AudioEditClip(Path("second.wav"), 20, 26, id="second"),)),
            ]
            editor._selected_track_id = "track-1"
            editor._refresh_project()
            editor.timeline.set_selection(["first", "second"], primary_id="first")
            editor._selection_changed("first")
            editor.timeline.set_playhead_position(3)
            event = SimpleNamespace(x=100, y=70, x_root=100, y_root=70)
            with patch("app.views.audio_timeline.tk.Menu") as menu_factory:
                editor.timeline._show_clip_context_menu(event)
                self.assertGreaterEqual(menu_factory.return_value.add_command.call_count, 10)

            editor._split_at_cursor()

            self.assertEqual(
                [[(clip.source_start, clip.source_end) for clip in track.clips] for track in editor._tracks],
                [[(10, 13), (13, 16)], [(20, 23), (23, 26)]],
            )
        finally:
            editor.close()
            root.update()
            root.destroy()

    def test_snap_aligns_cursor_and_group_move_to_clip_edges_and_can_be_disabled(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        root.withdraw()
        colors = {
            "background": "#101010",
            "field": "#202020",
            "text": "#f0f0f0",
            "highlight": "#4a90e2",
            "highlight_text": "#ffffff",
            "surface": "#181818",
            "border": "#505050",
            "border_soft": "#303030",
            "text_secondary": "#a0a0a0",
            "surface_alt": "#282828",
            "warning": "#e6b450",
            "error": "#e06060",
        }
        editor = AudioEditorDashboard(root, source_paths=[], translate=I18n().t, colors=colors)
        try:
            editor._mode = AudioEditMode.MULTITRACK
            editor._tracks = [
                AudioEditTrack(
                    "track-1",
                    "Track 1",
                    (
                        AudioEditClip(Path("first.wav"), 0, 2, id="first"),
                        AudioEditClip(Path("second.wav"), 0, 2, timeline_start=5, id="second"),
                    ),
                ),
                AudioEditTrack(
                    "track-2",
                    "Track 2",
                    (AudioEditClip(Path("third.wav"), 0, 2, timeline_start=10, id="third"),),
                ),
            ]
            editor._markers = [AudioEditMarker(8, "M1")]
            editor._selected_track_id = "track-1"
            editor._refresh_project()

            self.assertEqual(editor.timeline.snap_position(4.9), 5)
            self.assertEqual(editor.timeline.snap_position(7.9), 8)
            self.assertEqual(editor.timeline.snap_clip_start("first", 2.95), 3)
            editor.timeline._select_at_pointer(SimpleNamespace(x=378, y=20, state=0))
            self.assertEqual(editor.timeline.playhead_position, 5)

            editor.timeline.set_selection(["first", "third"], primary_id="first")
            editor._selection_changed("first")
            editor.timeline.set_playhead_position(2.95)
            editor._move_selected_clip_to_cursor()

            self.assertEqual(
                [[clip.timeline_start for clip in track.clips] for track in editor._tracks],
                [[3, 5], [13]],
            )

            editor._snap_var.set(False)
            editor._toggle_snap()
            self.assertEqual(editor.timeline.snap_position(4.9), 4.9)
            self.assertEqual(editor.timeline.snap_clip_start("first", 2.95), 2.95)
        finally:
            editor.close()
            root.update()
            root.destroy()

    def test_copy_paste_preserves_clip_properties_and_undo_redo(self):
        editor = self._create_editor()
        original = AudioEditClip(
            Path("source.wav"),
            3,
            7,
            timeline_start=0,
            fade_in=0.5,
            fade_out=0.75,
            id="original",
            gain_db=-6,
            pan=-0.5,
            effects=(AudioEditEffect("delay", wet=0.4, delay_ms=240),),
        )
        editor._clips = [original, AudioEditClip(Path("other.wav"), 0, 2, timeline_start=4, id="other")]
        editor._refresh_project()
        editor.timeline.select_single_clip("original")
        editor.timeline.set_playhead_position(4)

        editor._copy_selected_clips()
        editor._paste_clips()

        self.assertEqual([clip.id for clip in editor._clips[:1]], ["original"])
        pasted = editor._clips[1]
        self.assertNotEqual(pasted.id, original.id)
        self.assertEqual(pasted.source_path, original.source_path)
        self.assertEqual((pasted.source_start, pasted.source_end), (3, 7))
        self.assertEqual((pasted.fade_in, pasted.fade_out), (0.5, 0.75))
        self.assertEqual((pasted.gain_db, pasted.pan), (-6, -0.5))
        self.assertEqual(pasted.effects, original.effects)
        self.assertEqual(pasted.timeline_start, 4)
        pasted_project = editor._project

        editor._undo()
        self.assertEqual(editor._project.tracks[0].clips, tuple([original, editor._clips[1]]))
        editor._redo()
        self.assertEqual(editor._project, pasted_project)

    def test_cut_updates_internal_clipboard_and_can_be_undone(self):
        editor = self._create_editor()
        original = AudioEditClip(Path("source.wav"), 1, 3, id="original")
        remaining = AudioEditClip(Path("remaining.wav"), 0, 2, timeline_start=2, id="remaining")
        editor._clips = [original, remaining]
        editor._refresh_project()
        editor.timeline.select_single_clip("original")

        editor._cut_selected_clips()

        self.assertEqual([clip.id for clip in editor._clips], ["remaining"])
        self.assertEqual(len(editor._clipboard), 1)
        self.assertEqual(editor._clipboard[0].clip.id, "original")
        editor._undo()
        self.assertEqual([clip.id for clip in editor._clips], ["original", "remaining"])

    def test_sequence_duplicate_inserts_a_new_clip_after_selection(self):
        editor = self._create_editor()
        original = AudioEditClip(Path("source.wav"), 1, 4, id="original")
        following = AudioEditClip(Path("following.wav"), 0, 2, timeline_start=3, id="following")
        editor._clips = [original, following]
        editor._refresh_project()
        editor.timeline.select_single_clip("original")

        editor._duplicate_selected_clips()

        self.assertEqual([clip.id for clip in editor._clips][0], "original")
        self.assertNotEqual(editor._clips[1].id, original.id)
        self.assertEqual(editor._clips[1].source_path, original.source_path)
        self.assertEqual(
            [clip.source_path for clip in editor._clips],
            [
                Path("source.wav"),
                Path("source.wav"),
                Path("following.wav"),
            ],
        )
        self.assertEqual([clip.timeline_start for clip in editor._clips], [0, 3, 6])

    def test_paste_in_multitrack_mode_flattens_clip_group_on_selected_track(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 2, 4, id="first")
        second = AudioEditClip(Path("second.wav"), 5, 7, timeline_start=1, id="second")
        editor._mode = AudioEditMode.MULTITRACK
        editor._tracks = [
            AudioEditTrack("track-1", "Track 1", (first,)),
            AudioEditTrack("track-2", "Track 2", (second,)),
        ]
        editor._selected_track_id = "track-1"
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="first")
        editor._copy_selected_clips()
        editor.timeline.set_playhead_position(5)

        editor._paste_clips()

        self.assertEqual(len(editor._tracks[0].clips), 3)
        pasted = editor._tracks[0].clips[1:]
        self.assertEqual([clip.source_path for clip in pasted], [Path("first.wav"), Path("second.wav")])
        self.assertEqual([clip.timeline_start for clip in pasted], [5, 6])
        self.assertNotEqual(pasted[0].id, first.id)
        self.assertNotEqual(pasted[1].id, second.id)
        self.assertEqual(len(editor._tracks[1].clips), 1)

    def test_duplicate_group_preserves_relative_positions_and_track_placement(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 2, timeline_start=1, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 3, timeline_start=4, id="second")
        editor._mode = AudioEditMode.MULTITRACK
        editor._tracks = [
            AudioEditTrack("track-1", "Track 1", (first,)),
            AudioEditTrack("track-2", "Track 2", (second,)),
        ]
        editor._selected_track_id = "track-1"
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="first")

        editor._duplicate_selected_clips()

        self.assertEqual([clip.timeline_start for clip in editor._tracks[0].clips], [1, 7])
        self.assertEqual([clip.timeline_start for clip in editor._tracks[1].clips], [4, 10])
        self.assertEqual(editor._tracks[0].clips[1].source_path, first.source_path)
        self.assertNotEqual(editor._tracks[0].clips[1].id, first.id)
        self.assertNotEqual(editor._tracks[1].clips[1].id, second.id)

    def test_dragging_selected_group_moves_all_clips_by_same_time_and_track_delta(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 2, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 2, timeline_start=4, id="second")
        third = AudioEditClip(Path("third.wav"), 0, 2, timeline_start=10, id="third")
        editor._mode = AudioEditMode.MULTITRACK
        editor._tracks = [
            AudioEditTrack("track-1", "Track 1", (first,)),
            AudioEditTrack("track-2", "Track 2", (second, third)),
            AudioEditTrack("track-3", "Track 3"),
        ]
        editor._selected_track_id = "track-1"
        editor._refresh_project()
        editor.attributes("-alpha", 0)
        editor.deiconify()
        editor.update()
        editor.timeline.set_selection(["first", "third"], primary_id="first")
        editor.timeline._select_at_pointer(SimpleNamespace(x=100, y=70, state=0))
        self.assertEqual(editor.timeline._drag_clip_id, "first")
        self.assertEqual(editor.timeline.selected_clip_ids, ["first", "third"])
        editor.timeline._move_clip_at_pointer(SimpleNamespace(x=400, y=205))

        self.assertEqual(editor._tracks[0].clips, ())
        self.assertEqual([clip.id for clip in editor._tracks[1].clips], ["second", "first"])
        self.assertEqual([clip.timeline_start for clip in editor._tracks[1].clips], [4, 5])
        self.assertEqual([clip.id for clip in editor._tracks[2].clips], ["third"])
        self.assertEqual(editor._tracks[2].clips[0].timeline_start, 15)

    def test_dragging_group_rejects_a_track_shift_outside_available_tracks(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 2, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 2, id="second")
        editor._mode = AudioEditMode.MULTITRACK
        editor._tracks = [
            AudioEditTrack("track-1", "Track 1", (first,)),
            AudioEditTrack("track-2", "Track 2", (second,)),
        ]
        editor._selected_track_id = "track-1"
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="first")
        original_project = editor._project

        editor._move_clip_on_timeline("first", 1, 5)

        self.assertEqual(editor._project, original_project)
        self.assertEqual(editor._undo_stack, [])
        self.assertEqual(editor._status_var.get(), I18n().t("audio_editor.invalid_group_track_destination"))

    def test_clipboard_shortcuts_are_bound_and_ignored_in_text_entries(self):
        editor = self._create_editor()
        for sequence in ("<Control-c>", "<Control-x>", "<Control-v>", "<Control-d>"):
            self.assertTrue(editor.bind(sequence), f"Missing binding for {sequence}")

        action = Mock()
        text_entry = tk.Entry(editor)
        with patch.object(editor, "focus_get", return_value=editor.timeline.canvas):
            self.assertEqual(editor._run_shortcut(SimpleNamespace(), action), "break")
        with patch.object(editor, "focus_get", return_value=text_entry):
            self.assertIsNone(editor._run_shortcut(SimpleNamespace(), action))
        action.assert_called_once_with()

    def test_crossfade_between_selected_sequence_clips_is_undoable(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 10, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 8, timeline_start=10, id="second")
        third = AudioEditClip(Path("third.wav"), 0, 4, timeline_start=18, id="third")
        editor._clips = [first, second, third]
        editor._refresh_project()
        editor.timeline.set_selection(["first", "second"], primary_id="second")
        editor._crossfade_duration_var.set("2")

        editor._apply_crossfade()

        self.assertEqual(editor._clips[1].crossfade_in, 2)
        self.assertEqual([clip.timeline_start for clip in editor._clips], [0, 8, 16])
        self.assertEqual(editor._project.duration, 20)
        editor._undo()
        self.assertEqual([clip.timeline_start for clip in editor._clips], [0, 10, 18])
        self.assertEqual(editor._clips[1].crossfade_in, 0)
        editor._redo()
        self.assertEqual(editor._clips[1].crossfade_in, 2)

    def test_crossfade_can_be_adjusted_by_dragging_its_timeline_handle(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 4, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 3, timeline_start=3, crossfade_in=1, id="second")
        editor._clips = [first, second]
        editor._refresh_project()

        editor.timeline._select_at_pointer(SimpleNamespace(x=264, y=100, state=0))
        editor.timeline._move_clip_at_pointer(SimpleNamespace(x=204, y=100))

        self.assertEqual(editor._clips[1].crossfade_in, 2)
        self.assertEqual(editor._clips[1].timeline_start, 2)
        self.assertTrue(editor.timeline.canvas.find_withtag("transition:first:second"))

    def test_copying_only_the_incoming_clip_does_not_copy_its_unselected_transition(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 4, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 3, timeline_start=3, crossfade_in=1, id="second")
        editor._clips = [first, second]
        editor._refresh_project()
        editor.timeline.select_single_clip("second")
        editor._copy_selected_clips()
        editor.timeline.set_playhead_position(6)

        editor._paste_clips()

        self.assertEqual(editor._clipboard[0].clip.crossfade_in, 0)
        self.assertEqual(editor._clips[-1].crossfade_in, 0)
        self.assertEqual(editor._clips[-1].timeline_start, 6)

    def test_crossfade_requires_two_adjacent_clips_on_the_same_track(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 4, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 3, timeline_start=4, id="second")
        editor._clips = [first, second]
        editor._refresh_project()
        editor.timeline.select_single_clip("first")
        editor._crossfade_duration_var.set("1")

        editor._apply_crossfade()

        self.assertEqual(editor._clips[1].crossfade_in, 0)
        self.assertEqual(editor._status_var.get(), I18n().t("audio_editor.select_adjacent_clips"))

    def test_removing_a_clip_clears_the_orphaned_incoming_transition(self):
        editor = self._create_editor()
        first = AudioEditClip(Path("first.wav"), 0, 4, id="first")
        second = AudioEditClip(Path("second.wav"), 0, 3, timeline_start=3, crossfade_in=1, id="second")
        third = AudioEditClip(Path("third.wav"), 0, 2, timeline_start=6, id="third")
        editor._clips = [first, second, third]
        editor._refresh_project()
        editor.timeline.select_single_clip("first")

        editor._remove_selected_clip()

        self.assertEqual([clip.id for clip in editor._clips], ["second", "third"])
        self.assertEqual(editor._clips[0].crossfade_in, 0)
        self.assertEqual(editor._clips[0].timeline_start, 0)

    def test_preview_render_uses_the_project_with_crossfade(self):
        editor = self._create_editor()
        editor._play_preview = lambda _path: None
        editor._clips = [
            AudioEditClip(Path("first.wav"), 0, 4, id="first", gain_db=-3, pan=-0.5),
            AudioEditClip(
                Path("second.wav"),
                0,
                3,
                timeline_start=3,
                crossfade_in=1,
                id="second",
                gain_db=6,
                pan=0.5,
                effects=(AudioEditEffect("delay", wet=0.3, delay_ms=240),),
            ),
        ]
        editor._refresh_project()
        project = editor._project

        with patch("app.views.audio_editor_dashboard.render_audio_project", return_value=Path("preview.wav")) as render:
            editor._start_preview()
            editor._render_thread.join(timeout=3)

        render.assert_called_once()
        self.assertEqual(render.call_args.args[0], project)


if __name__ == "__main__":
    unittest.main()
