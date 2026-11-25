import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from app.ui.app import MokaMusicApp
from app.ui.workflows.audio_editor_workflow import (
    AudioEditorLibraryPort,
    AudioEditorUiPort,
    AudioEditorWorkflow,
)


class AudioEditorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.selected_audio_paths = Mock(return_value=[Path("song.mp3")])
        self.show_warning = Mock()
        self.open_editor = Mock()
        self.workflow = AudioEditorWorkflow(
            library=AudioEditorLibraryPort(selected_audio_paths=self.selected_audio_paths),
            ui=AudioEditorUiPort(
                translate=lambda key, **_kwargs: key,
                show_warning=self.show_warning,
                open_editor=self.open_editor,
            ),
        )

    def test_open_passes_selected_tracks_to_dashboard(self):
        self.workflow.open()

        self.open_editor.assert_called_once_with([Path("song.mp3")])
        self.show_warning.assert_not_called()

    def test_saved_project_can_open_without_library_selection(self):
        self.selected_audio_paths.return_value = []
        workflow = AudioEditorWorkflow(
            library=self.workflow.library,
            ui=AudioEditorUiPort(
                translate=lambda key: key,
                show_warning=self.show_warning,
                open_editor=self.open_editor,
                has_saved_project=lambda: True,
            ),
        )
        workflow.open()
        self.open_editor.assert_called_once_with([])
        self.show_warning.assert_not_called()

    def test_open_without_selection_shows_warning(self):
        self.selected_audio_paths.return_value = []

        self.workflow.open()

        self.show_warning.assert_called_once_with("audio_editor.title", "audio_editor.select_tracks_first")
        self.open_editor.assert_not_called()

    def test_selected_library_filenames_are_resolved_against_library_folder(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "song.mp3"
            source.write_bytes(b"audio")
            app = SimpleNamespace(
                _selected_filenames_by_controller=lambda: [(SimpleNamespace(carpeta=folder), object(), ["song.mp3"])]
            )

            paths = MokaMusicApp._audio_editor_selected_paths(app)

        self.assertEqual(paths, [source])
        self.assertEqual(paths, [source])

    def test_exported_audio_in_incoming_folder_is_registered_and_refreshed(self):
        with TemporaryDirectory() as folder:
            output_path = Path(folder) / "edited.mp3"
            controller = SimpleNamespace(carpeta=folder, register_file=Mock())
            tree = object()
            app = SimpleNamespace(
                controller_nueva=controller,
                tree_nueva=tree,
                _refresh_library_tree=Mock(),
            )

            MokaMusicApp._audio_editor_export_completed(app, output_path)

        controller.register_file.assert_called_once_with("edited.mp3")
        app._refresh_library_tree.assert_called_once_with(controller, tree)

    def test_restoring_audio_editor_playback_reloads_track_and_position(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "song.mp3"
            source.write_bytes(b"audio")
            playback = SimpleNamespace(
                volume=0.5,
                set_volume=Mock(),
                seek_absolute=Mock(),
            )
            player = SimpleNamespace(
                stop=Mock(),
                load_file=Mock(return_value=True),
                playback=playback,
                play=Mock(),
                clear_file=Mock(),
                _sync_volume_icon=Mock(),
            )
            snapshot = SimpleNamespace(
                current_file=str(source),
                position=12.5,
                volume=0.8,
                is_playing=True,
            )
            app = SimpleNamespace(player=player, t=lambda key, **_kwargs: key)

            MokaMusicApp._audio_editor_restore_playback(app, snapshot)

        player.stop.assert_called_once_with()
        player.load_file.assert_called_once_with(str(source))
        playback.set_volume.assert_called_once_with(0.8)
        playback.seek_absolute.assert_called_once_with(12.5)
        player.play.assert_called_once_with()
