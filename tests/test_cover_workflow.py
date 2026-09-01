import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from app.controllers.cover_controller import CoverApplyResult, CoverPlan
from app.controllers.drop_controller import DropPayload
from app.ui.workflows.cover_workflow import CoverLibraryPort, CoverUiPort, CoverWorkflow


class FakeProgress:
    def __init__(self):
        self.closed = False

    def update(self, *_args) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class CoverWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.controller = SimpleNamespace(archivos=["song.mp3", "other.mp3"])
        self.tree = object()
        self.preview_state = [self.controller, "song.mp3"]
        self.selected_targets = []
        self.warnings = []
        self.infos = []
        self.errors = []
        self.toasts = []
        self.backups = []
        self.refreshes = []
        self.reloads = []
        self.undo = []
        self.progress = FakeProgress()
        self.cover_controller = Mock()
        self.drop_controller = Mock()
        self.song_info = object()
        self.current_song = {"filename": "song.mp3"}
        self.selected_image = "cover.png"
        self.image_valid = True
        self.confirmed = True

        self.ui = CoverUiPort(
            translate=lambda key, **kwargs: f"{key}:{kwargs}" if kwargs else key,
            current_song=lambda: self.current_song,
            select_image=lambda: self.selected_image,
            validate_image=lambda _path: self.image_valid,
            update_preview_cover=Mock(),
            split_drop_data=lambda raw: tuple(raw.split("|")),
            show_warning=lambda title, body: self.warnings.append((title, body)),
            ask_yes_no=lambda _title, _body: self.confirmed,
            show_info=lambda title, body: self.infos.append((title, body)),
            show_error=lambda title, body: self.errors.append((title, body)),
            begin_progress=lambda **_kwargs: self.progress,
            show_toast=lambda message, kind: self.toasts.append((message, kind)),
            log_drop_error=Mock(),
        )
        self.library = CoverLibraryPort(
            selected_targets=lambda: self.selected_targets,
            preview_state=lambda: (self.preview_state[0], self.preview_state[1]),
            tree_for_controller=lambda controller: self.tree if controller is self.controller else None,
            create_backups=lambda groups, metadata: self.backups.append((groups, metadata)) or True,
            refresh_changed=lambda groups, changed: self.refreshes.append((groups, changed)),
            reload_preview=lambda controller, filename: self.reloads.append((controller, filename)),
            record_undo=lambda key: self.undo.append(key),
        )
        self.workflow = CoverWorkflow(
            cover_controller=self.cover_controller,
            drop_controller=self.drop_controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

    def test_targets_delegate_selection_and_preview_state(self):
        expected = [(self.controller, self.tree, ["song.mp3"])]
        self.cover_controller.cover_targets.return_value = expected

        self.assertEqual(self.workflow.targets(), expected)
        self.cover_controller.cover_targets.assert_called_once_with(
            selections=[],
            preview_controller=self.controller,
            preview_filename="song.mp3",
            tree_for_controller=self.library.tree_for_controller,
        )

    def test_preview_targets_require_controller_filename_and_tree(self):
        self.assertEqual(self.workflow.preview_targets(), [(self.controller, self.tree, ["song.mp3"])])
        self.preview_state[1] = None
        self.assertEqual(self.workflow.preview_targets(), [])

    def test_select_preview_cover_warns_without_active_song(self):
        self.current_song = None

        self.workflow.select_preview_cover()

        self.assertEqual(self.warnings, [("dialog.selection", "preview.no_active_song")])
        self.cover_controller.apply_manual_cover.assert_not_called()

    def test_select_preview_cover_applies_selected_image_to_preview_target(self):
        self.workflow.apply_cover = Mock()

        self.workflow.select_preview_cover()

        self.workflow.apply_cover.assert_called_once_with(
            "cover.png", targets=[(self.controller, self.tree, ["song.mp3"])]
        )

    def test_cover_drop_without_image_warns(self):
        self.drop_controller.payload_from_raw.return_value = DropPayload(audio_files=["song.mp3"])

        self.workflow.handle_cover_drop("song.mp3")

        self.assertEqual(self.warnings, [("dialog.cover_selected", "message.no_image_dropped")])

    def test_cover_drop_applies_first_image_to_preview_target(self):
        self.drop_controller.payload_from_raw.return_value = DropPayload(image_files=["first.png", "second.png"])
        self.workflow.apply_cover = Mock()

        self.workflow.handle_cover_drop("first.png|second.png")

        self.workflow.apply_cover.assert_called_once_with(
            "first.png", targets=[(self.controller, self.tree, ["song.mp3"])]
        )

    def test_cover_drop_exception_is_logged_and_shown(self):
        failure = RuntimeError("bad drop")
        self.drop_controller.payload_from_raw.side_effect = failure

        self.workflow.handle_cover_drop("broken")

        self.ui.log_drop_error.assert_called_once_with(failure)
        self.assertEqual(self.errors[0][0], "dialog.error")
        self.assertIn("message.could_not_process_drop", self.errors[0][1])

    def test_apply_cover_stops_for_invalid_image(self):
        self.image_valid = False

        self.workflow.apply_cover("bad.txt")

        self.cover_controller.apply_manual_cover.assert_not_called()
        self.assertEqual(self.backups, [])

    def test_apply_cover_warns_when_no_target_exists(self):
        self.cover_controller.cover_targets.return_value = []

        self.workflow.apply_cover("cover.png")

        self.assertEqual(self.warnings, [("dialog.selection", "message.no_cover_target")])

    def test_apply_cover_declined_confirmation_stops_before_backup(self):
        self.confirmed = False
        targets = [(self.controller, self.tree, ["song.mp3"])]

        self.workflow.apply_cover("cover.png", targets=targets)

        self.assertEqual(self.backups, [])
        self.cover_controller.apply_manual_cover.assert_not_called()

    def test_apply_cover_backup_failure_stops_before_mutation(self):
        self.library = replace(self.library, create_backups=lambda _groups, _metadata: False)
        self.workflow = CoverWorkflow(
            cover_controller=self.cover_controller,
            drop_controller=self.drop_controller,
            song_info=self.song_info,
            ui=self.ui,
            library=self.library,
        )

        self.workflow.apply_cover("cover.png", targets=[(self.controller, self.tree, ["song.mp3"])])

        self.cover_controller.apply_manual_cover.assert_not_called()

    def test_apply_cover_selected_only_preserves_targets_and_flag(self):
        targets = [(self.controller, self.tree, ["song.mp3"])]
        self.cover_controller.apply_manual_cover.return_value = CoverApplyResult(1, [], False, set())

        self.workflow.apply_cover("cover.png", targets=targets, apply_entire_folder=False)

        self.assertEqual(self.backups[0][0], targets)
        self.cover_controller.apply_manual_cover.assert_called_once()
        self.assertFalse(self.cover_controller.apply_manual_cover.call_args.kwargs["apply_entire_folder"])

    def test_manual_cover_success_refreshes_preview_records_undo_and_reports_success(self):
        targets = [(self.controller, self.tree, ["song.mp3"])]
        result = CoverApplyResult(2, [], True, {(id(self.controller), id(self.tree))}, "PORTADA.jpg")
        self.cover_controller.apply_manual_cover.return_value = result

        self.workflow.apply_cover("cover.png", targets=targets)

        self.assertTrue(self.progress.closed)
        self.assertEqual(self.refreshes, [(targets, result.changed_pairs)])
        self.assertEqual(self.reloads, [(self.controller, "song.mp3")])
        self.assertEqual(self.undo, ["undo.cover"])
        self.assertEqual(self.toasts, [("toast.done", "success")])
        self.assertEqual(self.infos[0][0], "dialog.done")

    def test_manual_cover_partial_success_reports_warning_and_keeps_undo(self):
        self.cover_controller.apply_manual_cover.return_value = CoverApplyResult(1, ["bad.mp3"], False, set())

        self.workflow.apply_cover("cover.png", targets=[(self.controller, self.tree, ["song.mp3"])])

        self.assertEqual(self.undo, ["undo.cover"])
        self.assertEqual(self.toasts, [("toast.partial", "warning")])
        self.assertIn("message.errors_count", self.infos[0][1])

    def test_manual_cover_total_failure_shows_error_without_undo(self):
        self.cover_controller.apply_manual_cover.return_value = CoverApplyResult(0, ["failed"], False, set())

        self.workflow.apply_cover("cover.png", targets=[(self.controller, self.tree, ["song.mp3"])])

        self.assertEqual(self.undo, [])
        self.assertEqual(self.errors, [("dialog.error", "failed")])

    def test_manual_cover_closes_progress_when_controller_raises(self):
        self.cover_controller.apply_manual_cover.side_effect = RuntimeError("write failed")

        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.workflow.apply_cover("cover.png", targets=[(self.controller, self.tree, ["song.mp3"])])

        self.assertTrue(self.progress.closed)

    def test_auto_cover_warns_without_targets(self):
        self.cover_controller.cover_targets.return_value = []

        self.workflow.apply_auto_cover()

        self.assertEqual(self.warnings, [("dialog.selection", "message.no_cover_target")])

    def test_auto_cover_warns_when_plan_has_no_groups(self):
        self.cover_controller.build_auto_cover_plan.return_value = CoverPlan(groups=[], missing=["song.mp3"])

        self.workflow.apply_auto_cover_targets([(self.controller, self.tree, ["song.mp3"])])

        self.assertEqual(self.warnings, [("dialog.cover_selected", "auto_cover.not_found")])
        self.assertEqual(self.backups, [])

    def test_auto_cover_confirmation_includes_missing_count_and_can_decline(self):
        self.cover_controller.build_auto_cover_plan.return_value = CoverPlan(
            groups=[(self.controller, self.tree, ["song.mp3"], "cover.jpg")],
            missing=["other.mp3"],
        )
        self.confirmed = False

        self.workflow.apply_auto_cover_targets([(self.controller, self.tree, ["song.mp3", "other.mp3"])])

        self.assertEqual(self.backups, [])
        self.cover_controller.apply_cover_plan.assert_not_called()

    def test_auto_cover_success_updates_preview_refreshes_and_reports_success(self):
        groups = [(self.controller, self.tree, ["song.mp3"], "cover.jpg")]
        self.cover_controller.build_auto_cover_plan.return_value = CoverPlan(groups=groups)
        result = CoverApplyResult(
            success_count=1,
            errors=[],
            affected_preview=True,
            changed_pairs={(id(self.controller), id(self.tree))},
            preview_cover_path="cover.jpg",
        )
        self.cover_controller.apply_cover_plan.return_value = result

        self.workflow.apply_auto_cover_targets([(self.controller, self.tree, ["song.mp3"])])

        self.ui.update_preview_cover.assert_called_once_with("cover.jpg")
        self.assertEqual(self.refreshes[0][1], result.changed_pairs)
        self.assertEqual(self.reloads, [(self.controller, "song.mp3")])
        self.assertEqual(self.undo, ["undo.cover"])
        self.assertEqual(self.toasts, [("toast.done", "success")])
        self.assertTrue(self.progress.closed)

    def test_auto_cover_closes_progress_when_controller_raises(self):
        groups = [(self.controller, self.tree, ["song.mp3"], "cover.jpg")]
        self.cover_controller.build_auto_cover_plan.return_value = CoverPlan(groups=groups)
        self.cover_controller.apply_cover_plan.side_effect = RuntimeError("write failed")

        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.workflow.apply_auto_cover_targets([(self.controller, self.tree, ["song.mp3"])])

        self.assertTrue(self.progress.closed)


if __name__ == "__main__":
    unittest.main()
