import gc
import shutil
import tkinter as tk
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip, AudioEditMode, AudioEditProject, AudioEditTrack
from app.services.audio_project_storage import load_editor_project
from app.services.audio_waveform_service import AudioWaveform
from app.ui.theme import THEME_PRESETS
from app.views.audio_editor_dashboard import AudioEditorDashboard


class EditorRelinkTests(unittest.TestCase):
    def setUp(self):
        # Collect destroyed Tk objects on the main thread before audio workers run.
        gc.collect()
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.old = Path(self.folder.name) / "missing.wav"
        self.new = Path(self.folder.name) / "moved.wav"
        self.new.write_bytes(b"audio")
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = AudioEditorDashboard(
            self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"]
        )
        self.editor._paths = [self.old]
        self.editor._clips = [
            AudioEditClip(self.old, 1, 5, fade_in=0.5, gain_db=-3, id="a"),
            AudioEditClip(self.old, 2, 6, timeline_start=4, pan=0.5, id="b"),
        ]
        self.editor._failed_paths.add(self.old)
        self.editor._refresh_project()
        self.editor._refresh_source_list()
        self.editor._saved_document_state = self.editor._project_state()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.editor._project_path = None
        self.editor._session_path = None
        self.editor.close()
        self.root.destroy()
        self.editor = None
        self.root = None
        gc.collect()

    def apply(self, duration=8):
        return self.editor._apply_source_relink(self.old, self.new, AudioWaveform(duration, (0.5,) * 20))

    def test_relink_preserves_clips_and_undo_restores_sources_and_clean_state(self):
        before = self.editor._project
        self.assertTrue(self.apply())
        self.assertEqual(self.editor._paths, [self.new])
        self.assertEqual(self.editor._clips, [replace(clip, source_path=self.new) for clip in before.tracks[0].clips])
        self.assertEqual(len(self.editor._undo_stack), 1)
        self.editor._undo()
        self.assertEqual(self.editor._project, before)
        self.assertEqual(self.editor._paths, [self.old])
        self.assertFalse(self.editor._project_is_dirty())
        self.editor._redo()
        self.assertEqual(self.editor._paths, [self.new])
        self.assertTrue(all(clip.source_path == self.new for clip in self.editor._clips))

    def test_short_replacement_is_rejected_atomically(self):
        before = self.editor._project_state()
        self.assertFalse(self.apply(4))
        self.assertEqual(self.editor._project_state(), before)
        self.assertEqual(self.editor._undo_stack, [])

    def test_missing_clip_reference_available_without_source_row(self):
        self.editor._paths = []
        self.assertEqual(self.editor._missing_source_paths(), [self.old])
        self.assertTrue(self.apply())
        self.assertEqual(self.editor._paths, [])
        self.assertTrue(all(clip.source_path == self.new for clip in self.editor._clips))

    def test_dialog_cancel_does_not_change_project(self):
        before = self.editor._project_state()
        with patch("app.views.audio_editor_relink.filedialog.askopenfilename", return_value=""):
            self.editor._browse_relink_source(self.old)
        self.assertEqual(self.editor._project_state(), before)
        self.assertIsNone(self.editor._pending_relink)

    def test_worker_result_after_switch_is_ignored(self):
        with patch("app.views.audio_editor_relink.extract_waveform", return_value=AudioWaveform(8, (0.5,))):
            self.editor._start_source_relink(self.old, self.new)
            self.editor._relink_thread.join(5)
        old_queue = self.editor._results
        self.editor._replace_editor_project(AudioEditProject(), [], None)
        self.assertIsNot(self.editor._results, old_queue)
        self.assertIsNone(self.editor._pending_relink)
        self.assertEqual(self.editor._project.duration, 0)

    def test_async_validation_then_save_keeps_new_paths(self):
        with patch("app.views.audio_editor_relink.extract_waveform", return_value=AudioWaveform(8, (0.5,))):
            self.editor._start_source_relink(self.old, self.new)
            self.editor._relink_thread.join(5)
        self.editor.after_cancel(self.editor._poll_id)
        self.editor._poll_results()
        self.assertEqual(self.editor._paths, [self.new])
        self.editor._project_path = Path(self.folder.name) / "project.json"
        self.assertTrue(self.editor._save_editor_project())
        project, sources = load_editor_project(self.editor._project_path)
        self.assertEqual(sources, [self.new])
        self.assertTrue(all(clip.source_path == self.new for track in project.tracks for clip in track.clips))

    def test_relink_multitrack_preserves_lane_settings_and_selection(self):
        clips = tuple(self.editor._clips)
        self.editor._mode = AudioEditMode.MULTITRACK
        self.editor._tracks = [
            AudioEditTrack("one", "First", (clips[0],), volume=0.5),
            AudioEditTrack("two", "Second", (clips[1],), muted=True),
        ]
        self.editor._refresh_project()
        self.editor.timeline.set_selection(["a", "b"], primary_id="b")
        before = self.editor._project
        self.assertTrue(self.apply())
        for previous, current in zip(before.tracks, self.editor._project.tracks, strict=True):
            self.assertEqual(
                current, replace(previous, clips=tuple(replace(c, source_path=self.new) for c in previous.clips))
            )
        self.assertEqual(self.editor.timeline.selected_clip_ids, ["a", "b"])
        self.assertEqual(self.editor.timeline.selected_clip_id, "b")

    def test_completed_validation_waits_for_render(self):
        with patch("app.views.audio_editor_relink.extract_waveform", return_value=AudioWaveform(8, (0.5,))):
            self.editor._start_source_relink(self.old, self.new)
            self.editor._relink_thread.join(5)
        self.editor._render_busy = True
        self.editor.after_cancel(self.editor._poll_id)
        self.editor._poll_results()
        self.assertEqual(self.editor._paths, [self.old])
        self.assertIsNotNone(self.editor._pending_relink)
        self.editor._render_busy = False
        self.editor._finish_source_relink()
        self.assertEqual(self.editor._paths, [self.new])

    def test_duplicate_source_rows_are_merged_and_undo_restores_them(self):
        self.editor._paths.append(self.new)
        self.assertTrue(self.apply())
        self.assertEqual(self.editor._paths, [self.new])
        self.editor._undo()
        self.assertEqual(self.editor._paths, [self.old, self.new])

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for audio validation")
    def test_relink_reads_real_audio_without_modifying_it(self):
        with wave.open(str(self.new), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\0" * (8000 * 8 * 2))
        original = self.new.read_bytes()
        self.editor._start_source_relink(self.old, self.new)
        self.editor._relink_thread.join(10)
        self.assertFalse(self.editor._relink_thread.is_alive())
        self.editor.after_cancel(self.editor._poll_id)
        self.editor._poll_results()
        self.assertEqual(self.editor._paths, [self.new])
        self.assertEqual(self.new.read_bytes(), original)

    def test_undo_relink_keeps_later_imports(self):
        self.assertTrue(self.apply())
        extra = Path(self.folder.name) / "added.wav"
        self.editor._paths.append(extra)
        self.editor._undo()
        self.assertEqual(self.editor._paths, [self.old, extra])
        self.editor._redo()
        self.assertEqual(self.editor._paths, [self.new, extra])

    def test_undo_relink_does_not_restore_later_removed_sources(self):
        extra = Path(self.folder.name) / "removed.wav"
        self.editor._paths.append(extra)
        self.assertTrue(self.apply())
        self.editor._paths.remove(extra)
        self.editor._undo()
        self.assertEqual(self.editor._paths, [self.old])
        self.editor._redo()
        self.assertEqual(self.editor._paths, [self.new])

    def test_redo_does_not_resurrect_replacement_row_removed_after_relink(self):
        self.assertTrue(self.apply())
        self.editor._paths = [self.old]
        self.editor._undo()
        self.assertEqual(self.editor._paths, [self.old])
        self.editor._redo()
        self.assertEqual(self.editor._paths, [self.old])
        self.assertTrue(all(clip.source_path == self.new for clip in self.editor._clips))

    def test_async_failure_keeps_original(self):
        before = self.editor._project_state()
        with patch("app.views.audio_editor_relink.extract_waveform", side_effect=ValueError("bad audio")):
            self.editor._start_source_relink(self.old, self.new)
            self.editor._relink_thread.join(5)
        self.editor.after_cancel(self.editor._poll_id)
        self.editor._poll_results()
        self.assertEqual(self.editor._project_state(), before)
        self.assertIsNone(self.editor._pending_relink)
