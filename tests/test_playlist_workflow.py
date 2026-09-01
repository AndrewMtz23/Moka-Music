import os
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.controllers.playlist_workflow_controller import PlaylistApplyResult
from app.models import ActionResult, SortMode
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

    def test_number_tracks_warns_when_no_library_has_files(self):
        self.primary.archivos = []
        self.incoming.archivos = []

        self.workflow.number_tracks()

        self.assertEqual(self.warnings, [("dialog.no_files", "message.no_loaded_files")])
        self.primary.apply_track_numbers_from_order.assert_not_called()

    def test_number_tracks_rejects_a_view_that_cannot_be_reordered(self):
        self.library = replace(self.library, can_reorder=lambda _controller, _tree: False)
        self.workflow = PlaylistWorkflow(
            controller=self.controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

        self.workflow.number_tracks()

        self.assertEqual(self.warnings, [("dialog.selection", "message.reorder_needs_full_view")])
        self.primary.apply_track_numbers_from_order.assert_not_called()

    def test_number_tracks_declined_confirmation_stops_before_backup(self):
        self.ui = replace(self.ui, ask_yes_no=lambda _title, _body: False)
        self.workflow = PlaylistWorkflow(
            controller=self.controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

        self.workflow.number_tracks()

        self.library.create_backups.assert_not_called()
        self.primary.apply_track_numbers_from_order.assert_not_called()

    def test_number_tracks_backup_failure_stops_before_mutation(self):
        self.library = replace(self.library, create_backups=Mock(return_value=None))
        self.workflow = PlaylistWorkflow(
            controller=self.controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

        self.workflow.number_tracks()

        self.primary.apply_track_numbers_from_order.assert_not_called()

    def test_number_tracks_success_invalidates_refreshes_preview_and_presents_result(self):
        result = ActionResult.ok("done")
        self.primary.apply_track_numbers_from_order.return_value = result
        self.preview_state[:] = [self.primary, "primary.mp3"]

        self.workflow.number_tracks()

        self.library.create_backups.assert_called_once_with(
            [(self.primary, self.primary_tree, ["primary.mp3"])],
            {"track_number": "order"},
        )
        self.song_info.invalidate.assert_called_once_with(os.path.join("primary", "primary.mp3"))
        self.library.refresh_tree.assert_called_once_with(self.primary, self.primary_tree)
        self.library.reload_preview.assert_called_once_with(self.primary, "primary.mp3")
        self.ui.present_action_result.assert_called_once_with(result)

    def test_insert_selected_warns_without_selection(self):
        self.workflow.insert_selected()

        self.assertEqual(self.warnings, [("dialog.selection", "message.no_song_selected")])
        self.controller.build_insert_plan.assert_not_called()

    def test_insert_selected_rejects_two_library_selection(self):
        self.selections = [
            (self.primary, self.primary_tree, ["primary.mp3"]),
            (self.incoming, self.incoming_tree, ["incoming.mp3"]),
        ]

        self.workflow.insert_selected()

        self.assertEqual(self.warnings, [("dialog.selection", "playlist_insert.one_library")])
        self.controller.build_insert_plan.assert_not_called()

    def test_insert_selected_cancelled_position_stops_before_plan(self):
        self.selections = [(self.primary, self.primary_tree, ["primary.mp3"])]
        self.ui.request_position.return_value = None

        self.workflow.insert_selected()

        self.controller.build_insert_plan.assert_not_called()

    def test_insert_selected_converts_ui_position_before_building_plan(self):
        self.selections = [(self.primary, self.primary_tree, ["primary.mp3"])]
        self.ui.request_position.return_value = 0
        self.controller.build_insert_plan.return_value = SimpleNamespace(items=[])

        self.workflow.insert_selected()

        self.controller.build_insert_plan.assert_called_once_with(
            controller=self.primary,
            tree=self.primary_tree,
            filenames=["primary.mp3"],
            position=1,
        )
        self.assertEqual(self.infos, [("dialog.done", "change_preview.no_changes")])

    def test_insert_selected_cancelled_preview_stops_before_execution(self):
        self.selections = [(self.primary, self.primary_tree, ["primary.mp3"])]
        plan = SimpleNamespace(items=[object()])
        self.controller.build_insert_plan.return_value = plan
        self.ui.request_plan_preview.side_effect = None
        self.ui.request_plan_preview.return_value = None

        self.workflow.insert_selected()

        self.controller.execute_plan.assert_not_called()

    def test_prepare_active_warns_without_loaded_library(self):
        self.primary.archivos = []
        self.incoming.archivos = []

        self.workflow.prepare_active()

        self.assertEqual(self.warnings, [("dialog.no_files", "message.no_loaded_files")])
        self.controller.build_plan_from_order.assert_not_called()

    def test_prepare_active_rejects_a_view_that_cannot_be_reordered(self):
        self.library = replace(self.library, can_reorder=lambda _controller, _tree: False)
        self.workflow = PlaylistWorkflow(
            controller=self.controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

        self.workflow.prepare_active()

        self.assertEqual(self.warnings, [("dialog.selection", "message.reorder_needs_full_view")])
        self.controller.build_plan_from_order.assert_not_called()

    def test_insert_selected_uses_insert_success_message(self):
        self.selections = [(self.primary, self.primary_tree, ["primary.mp3"])]
        plan = SimpleNamespace(
            controller=self.primary,
            tree=self.primary_tree,
            final_order=["primary.mp3"],
            items=[object()],
        )
        self.controller.build_insert_plan.return_value = plan
        self.workflow._execute_plan = Mock()

        self.workflow.insert_selected()

        self.workflow._execute_plan.assert_called_once_with(plan, "playlist_insert.done")

    def test_prepare_active_uses_prepare_success_message(self):
        plan = SimpleNamespace(
            controller=self.incoming,
            tree=self.incoming_tree,
            final_order=["incoming.mp3"],
            items=[object()],
        )
        self.controller.build_plan_from_order.return_value = plan
        self.workflow._execute_plan = Mock()

        self.workflow.prepare_active()

        self.workflow._execute_plan.assert_called_once_with(plan, "playlist_prepare.done")

    def test_execute_plan_refreshes_sort_preview_undo_and_insert_feedback(self):
        plan = SimpleNamespace(
            controller=self.primary,
            tree=self.primary_tree,
            final_order=["renamed.mp3"],
            items=[object()],
        )
        result = PlaylistApplyResult(
            track_numbers_updated=1,
            renamed=1,
            errors=[],
            changed_pairs={(id(self.primary), id(self.primary_tree))},
            preview_filename="renamed.mp3",
            backup_path=Path("backup.json"),
        )
        self.preview_state[:] = [self.primary, "primary.mp3"]
        self.controller.execute_plan.return_value = result

        self.workflow._execute_plan(plan, "playlist_insert.done")

        self.assertTrue(self.progress.closed)
        self.library.refresh_changed.assert_called_once_with(
            [(self.primary, self.primary_tree, ["renamed.mp3"])],
            result.changed_pairs,
        )
        self.primary.set_sort_mode.assert_called_once_with(SortMode.TRACK_NUMBER)
        self.library.sync_sort.assert_called_once_with(self.primary, SortMode.TRACK_NUMBER)
        self.library.select_filename.assert_called_once_with(self.primary_tree, "renamed.mp3")
        self.library.reload_preview.assert_called_once_with(self.primary, "renamed.mp3")
        self.library.record_undo_paths.assert_called_once_with("undo.playlist", [Path("backup.json")])
        self.assertEqual(self.toasts, [("toast.done", "success")])
        self.assertEqual(self.infos[0][0], "dialog.done")
        self.assertIn("playlist_insert.done", self.infos[0][1])

    def test_execute_plan_closes_progress_when_controller_raises(self):
        plan = SimpleNamespace(items=[object()])
        self.controller.execute_plan.side_effect = RuntimeError("write failed")

        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.workflow._execute_plan(plan, "playlist_insert.done")

        self.assertTrue(self.progress.closed)

    def test_execute_plan_failure_reports_errors_without_undo(self):
        plan = SimpleNamespace(
            controller=self.primary,
            tree=self.primary_tree,
            final_order=["primary.mp3"],
            items=[object()],
        )
        self.controller.execute_plan.return_value = PlaylistApplyResult(
            track_numbers_updated=0,
            renamed=0,
            errors=["failed"],
            changed_pairs=set(),
            preview_filename=None,
            backup_path=Path("backup.json"),
        )

        self.workflow._execute_plan(plan, "playlist_insert.done")

        self.library.record_undo_paths.assert_not_called()
        self.assertEqual(self.errors, [("dialog.error", "failed")])


if __name__ == "__main__":
    unittest.main()
