import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.ui.workflows.playlist_workflow import PlaylistLibraryPort, PlaylistUiPort, PlaylistWorkflow


class FakeProgress:
    def __init__(self):
        self.closed = False

    def update(self, *_args) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class PlaylistWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.primary = SimpleNamespace(archivos=["primary.mp3"], carpeta="primary")
        self.incoming = SimpleNamespace(archivos=["incoming.mp3"], carpeta="incoming")
        self.primary.apply_track_numbers_from_order = Mock()
        self.incoming.apply_track_numbers_from_order = Mock()
        self.primary.set_sort_mode = Mock()
        self.incoming.set_sort_mode = Mock()
        self.primary_tree = object()
        self.incoming_tree = object()
        self.preview_state = [None, None]
        self.selections = []
        self.warnings = []
        self.infos = []
        self.errors = []
        self.toasts = []
        self.progress = FakeProgress()
        self.controller = Mock()
        self.song_info = Mock()

        self.ui = PlaylistUiPort(
            translate=lambda key, **kwargs: f"{key}:{kwargs}" if kwargs else key,
            show_warning=lambda title, body: self.warnings.append((title, body)),
            ask_yes_no=lambda _title, _body: True,
            show_info=lambda title, body: self.infos.append((title, body)),
            show_error=lambda title, body: self.errors.append((title, body)),
            request_position=Mock(return_value=0),
            request_plan_preview=Mock(side_effect=lambda plan, _rebuild: plan),
            begin_progress=lambda **_kwargs: self.progress,
            show_toast=lambda message, kind: self.toasts.append((message, kind)),
            present_action_result=Mock(),
        )
        self.library = PlaylistLibraryPort(
            selected_targets=lambda: self.selections,
            preview_state=lambda: (self.preview_state[0], self.preview_state[1]),
            set_preview_filename=lambda filename: self.preview_state.__setitem__(1, filename),
            tree_for_controller=self._tree_for_controller,
            primary_target=lambda: (self.primary, self.primary_tree),
            incoming_target=lambda: (self.incoming, self.incoming_tree),
            can_reorder=lambda _controller, _tree: True,
            create_backups=Mock(return_value=Path("backup.json")),
            refresh_tree=Mock(),
            refresh_changed=Mock(),
            sync_sort=Mock(),
            select_filename=Mock(),
            reload_preview=Mock(),
            record_undo_paths=Mock(),
        )
        self.workflow = PlaylistWorkflow(
            controller=self.controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

    def _tree_for_controller(self, controller):
        if controller is self.primary:
            return self.primary_tree
        if controller is self.incoming:
            return self.incoming_tree
        return None

    def test_active_target_rejects_selections_from_two_libraries(self):
        self.selections = [
            (self.primary, self.primary_tree, ["primary.mp3"]),
            (self.incoming, self.incoming_tree, ["incoming.mp3"]),
        ]

        self.assertIsNone(self.workflow.active_target())

        self.assertEqual(self.warnings, [("dialog.selection", "playlist_insert.one_library")])

    def test_active_target_prefers_selection_then_preview_then_incoming(self):
        self.selections = [(self.primary, self.primary_tree, ["primary.mp3"])]
        self.assertEqual(self.workflow.active_target(), (self.primary, self.primary_tree))

        self.selections = []
        self.preview_state[0] = self.primary
        self.assertEqual(self.workflow.active_target(), (self.primary, self.primary_tree))

        self.preview_state[0] = None
        self.assertEqual(self.workflow.active_target(), (self.incoming, self.incoming_tree))


if __name__ == "__main__":
    unittest.main()
