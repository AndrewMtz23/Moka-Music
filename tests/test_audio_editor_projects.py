import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip, AudioEditProject, AudioEditTrack
from app.services.audio_project_storage import load_editor_project, save_editor_project
from app.services.audio_waveform_service import AudioWaveform
from app.ui.theme import THEME_PRESETS
from app.views.audio_editor_dashboard import AudioEditorDashboard


class EditorProjectTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = AudioEditorDashboard(
            self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"]
        )
        self.addCleanup(self.cleanup)
        self.path = Path(self.folder.name) / "mix.moka-project.json"

    def cleanup(self):
        self.editor._project_path = None
        self.editor._session_path = None
        self.editor.close()
        self.root.destroy()

    def add_clip(self):
        self.editor._clips = [AudioEditClip(Path(self.folder.name) / "missing.wav", 0, 3, id="clip")]
        self.editor._refresh_project()

    def test_save_as_cancel_keeps_document_and_dirty_state(self):
        self.add_clip()
        with patch("app.views.audio_editor_projects.filedialog.asksaveasfilename", return_value=""):
            self.assertFalse(self.editor._save_project_as())
        self.assertIsNone(self.editor._project_path)
        self.assertTrue(self.editor._project_is_dirty())

    def test_save_as_then_undo_returns_to_clean(self):
        self.add_clip()
        with patch("app.views.audio_editor_projects.filedialog.asksaveasfilename", return_value=str(self.path)):
            self.assertTrue(self.editor._save_project_as())
        self.assertFalse(self.editor._project_is_dirty())
        self.editor.timeline.select_single_clip("clip")
        self.editor._remove_selected_clip()
        self.assertTrue(self.editor._project_is_dirty())
        self.editor._undo()
        self.assertFalse(self.editor._project_is_dirty())
        self.assertEqual(load_editor_project(self.path)[0], self.editor._project)

    def test_new_cancel_preserves_everything(self):
        self.add_clip()
        before = self.editor._project
        with patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=None):
            self.assertFalse(self.editor._new_editor_project())
        self.assertEqual(self.editor._project, before)

    def test_new_discards_and_ignores_previous_loader_results(self):
        self.add_clip()
        old_queue = self.editor._results
        old_cancel = self.editor._cancel_event
        with patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=False):
            self.assertTrue(self.editor._new_editor_project())
        old_queue.put(("loaded", Path("old.wav"), AudioWaveform(3, (0.5,))))
        self.editor._poll_results()
        self.assertTrue(old_cancel.is_set())
        self.assertEqual(self.editor._clips, [])
        self.assertEqual(self.editor._waveforms, {})
        self.assertFalse(self.editor._project_is_dirty())

    def test_invalid_open_does_not_replace_current_project(self):
        self.add_clip()
        before = self.editor._project
        self.path.write_text("[]")
        with (
            patch("app.views.audio_editor_projects.filedialog.askopenfilename", return_value=str(self.path)),
            patch("app.views.audio_editor_projects.messagebox.showerror") as error,
        ):
            self.assertFalse(self.editor._open_editor_project())
        error.assert_called_once()
        self.assertEqual(self.editor._project, before)

    def test_open_empty_project_replaces_current_and_clears_history(self):
        save_editor_project(self.path, AudioEditProject(tracks=(AudioEditTrack("sequence", "Sequence"),)), [])
        self.add_clip()
        with (
            patch("app.views.audio_editor_projects.filedialog.askopenfilename", return_value=str(self.path)),
            patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=False),
        ):
            self.assertTrue(self.editor._open_editor_project())
        self.assertEqual(self.editor._clips, [])
        self.assertEqual(self.editor._undo_stack, [])
        self.assertEqual(self.editor._project_path, self.path)
        self.assertFalse(self.editor._project_is_dirty())

    def test_failed_save_as_keeps_original_path(self):
        self.add_clip()
        old_path = Path(self.folder.name) / "previous.json"
        self.editor._project_path = old_path
        with (
            patch("app.views.audio_editor_projects.filedialog.asksaveasfilename", return_value=str(self.path)),
            patch("app.views.audio_editor_projects.save_editor_project", side_effect=OSError("write failed")),
            patch("app.views.audio_editor_projects.messagebox.showerror"),
        ):
            self.assertFalse(self.editor._save_project_as())
        self.assertEqual(self.editor._project_path, old_path)
        self.assertTrue(self.editor._project_is_dirty())

    def test_source_list_changes_are_dirty(self):
        self.editor._paths = [Path(self.folder.name) / "source.wav"]
        self.editor._refresh_source_list()
        self.assertTrue(self.editor._project_is_dirty())
        self.assertIn("*", self.editor.title())

    def test_named_close_discard_restores_saved_state_in_recovery(self):
        self.add_clip()
        self.editor._session_path = Path(self.folder.name) / "session.json"
        with patch("app.views.audio_editor_projects.filedialog.asksaveasfilename", return_value=str(self.path)):
            self.assertTrue(self.editor._save_project_as())
        saved = self.editor._project
        self.editor._clips = []
        self.editor._refresh_project()
        with patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=False):
            self.assertTrue(self.editor._prepare_project_close())
        self.assertEqual(load_editor_project(self.editor._session_path)[0], saved)
        self.assertEqual(load_editor_project(self.path)[0], saved)

    def test_named_close_cancel_leaves_recovery_untouched(self):
        self.add_clip()
        self.editor._project_path = self.path
        self.editor._session_path = Path(self.folder.name) / "session.json"
        with patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=None):
            self.assertFalse(self.editor._prepare_project_close())
        self.assertFalse(self.editor._session_path.exists())

    def test_open_with_missing_sources_preserves_references_and_marks_error(self):
        self.add_clip()
        missing = self.editor._clips[0].source_path
        save_editor_project(self.path, self.editor._project, [missing])
        with (
            patch("app.views.audio_editor_projects.filedialog.askopenfilename", return_value=str(self.path)),
            patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=False),
        ):
            self.assertTrue(self.editor._open_editor_project())
        self.assertEqual(self.editor._paths, [missing])
        self.assertIn(missing, self.editor._failed_paths)
        self.assertEqual(self.editor._clips[0].source_path, missing)

    def test_failed_save_prevents_new_project(self):
        self.add_clip()
        before = self.editor._project
        with (
            patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=True),
            patch.object(self.editor, "_save_editor_project", return_value=False),
        ):
            self.assertFalse(self.editor._new_editor_project())
        self.assertEqual(self.editor._project, before)

    def test_recovery_restores_named_document_identity(self):
        self.add_clip()
        session = Path(self.folder.name) / "session.json"
        self.editor._session_path = session
        with patch("app.views.audio_editor_projects.filedialog.asksaveasfilename", return_value=str(self.path)):
            self.assertTrue(self.editor._save_project_as())
        self.assertTrue(self.editor._prepare_project_close())
        restored = AudioEditorDashboard(
            self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"], project_path=session
        )
        try:
            self.assertEqual(restored._project_path, self.path)
            self.assertEqual(restored._project, self.editor._project)
            self.assertFalse(restored._project_is_dirty())
        finally:
            restored._session_path = None
            restored._project_path = None
            restored.close()

    def test_reopen_current_file_after_saving_uses_latest_saved_contents(self):
        self.add_clip()
        with patch("app.views.audio_editor_projects.filedialog.asksaveasfilename", return_value=str(self.path)):
            self.assertTrue(self.editor._save_project_as())
        self.editor._clips = []
        self.editor._refresh_project()
        with (
            patch("app.views.audio_editor_projects.filedialog.askopenfilename", return_value=str(self.path)),
            patch("app.views.audio_editor_projects.messagebox.askyesnocancel", return_value=True),
        ):
            self.assertTrue(self.editor._open_editor_project())
        self.assertEqual(self.editor._clips, [])
        self.assertEqual(self.editor._project, load_editor_project(self.path)[0])
