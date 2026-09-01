# Cover Workflow Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract cover-art UI orchestration from `MetadataWorkflowMixin` into an independently testable `CoverWorkflow` without changing visible behavior.

**Architecture:** `CoverWorkflow` composes the existing `CoverController`, `DropController`, and `SongInfo` with two frozen callable-port dataclasses. `MokaMusicApp` remains the composition root, while five compatibility wrappers preserve all current Tkinter bindings and cross-workflow callers.

**Tech Stack:** Python 3.10+, Tkinter/ttk, tkinterdnd2, Pillow, `unittest`, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-31-cover-workflow-extraction-design.md`

## Global Constraints

- Preserve existing layout, labels, colors, focus order, dialog sequence, and progress behavior.
- Do not change `CoverController` behavior or cover file formats.
- Do not rename translation keys or change user-facing messages.
- Do not introduce an event bus, dependency-injection framework, or new third-party package.
- Keep `_select_preview_cover`, `_handle_cover_drop`, `_apply_cover_to_targets`, `_apply_auto_cover_from_folder`, and `_apply_auto_cover_targets` as compatibility wrappers.
- Do not expose `MokaMusicApp`, arbitrary attribute lookup, or a generic context dictionary through either port.
- Catch unexpected exceptions only at the drop-event boundary; always close an opened progress UI with `try/finally`.

## File Structure

- Create `app/ui/workflows/__init__.py`: export `CoverWorkflow`, `CoverUiPort`, and `CoverLibraryPort`.
- Create `app/ui/workflows/cover_workflow.py`: typed ports and all cover UI orchestration.
- Create `tests/test_cover_workflow.py`: coordinator characterization tests using fakes, without a Tk root.
- Modify `app/ui/app.py`: construct and wire `CoverWorkflow` after `_setup_ui()` and before `_bind_events()`.
- Modify `app/ui/metadata_workflow.py`: replace cover orchestration with five one-line compatibility wrappers and remove unused imports.
- Modify `tests/test_ui_library_refresh.py`: verify compatibility wrappers delegate exact arguments.

---

### Task 1: Define ports and target/drop entry behavior

**Files:**

- Create: `app/ui/workflows/__init__.py`
- Create: `app/ui/workflows/cover_workflow.py`
- Create: `tests/test_cover_workflow.py`

**Interfaces:**

- Consumes: `CoverController.cover_targets(...)`, `DropController.payload_from_raw(...)`, and injected callables only.
- Produces: `CoverTarget`, `ProgressPort`, `BeginProgress`, `CoverUiPort`, `CoverLibraryPort`, and `CoverWorkflow` with `targets()`, `preview_targets()`, `select_preview_cover()`, and `handle_cover_drop(raw_data: str)`.

- [ ] **Step 1: Write the test fixtures and failing target-selection tests**

Create `tests/test_cover_workflow.py` with these concrete fakes and tests:

```python
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
```

- [ ] **Step 2: Run the target tests and verify the expected import failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow.CoverWorkflowTests.test_targets_delegate_selection_and_preview_state tests.test_cover_workflow.CoverWorkflowTests.test_preview_targets_require_controller_filename_and_tree -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'app.ui.workflows'`.

- [ ] **Step 3: Add the typed port contracts and target methods**

Create `app/ui/workflows/cover_workflow.py` with these contracts and initial coordinator:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from ...controllers.cover_controller import CoverController
from ...controllers.drop_controller import DropController

CoverTarget = tuple[object, object, list[str]]


class ProgressPort(Protocol):
    def update(self, completed: int, total: int | None = None, detail: str = "") -> bool: ...

    def close(self) -> None: ...


class BeginProgress(Protocol):
    def __call__(self, *, title: str, message: str, total: int) -> ProgressPort: ...


@dataclass(frozen=True)
class CoverUiPort:
    translate: Callable[..., str]
    current_song: Callable[[], Optional[dict[str, Any]]]
    select_image: Callable[[], Optional[str]]
    validate_image: Callable[[str], bool]
    update_preview_cover: Callable[[str], None]
    split_drop_data: Callable[[str], list[str] | tuple[str, ...]]
    show_warning: Callable[[str, str], object]
    ask_yes_no: Callable[[str, str], bool]
    show_info: Callable[[str, str], object]
    show_error: Callable[[str, str], object]
    begin_progress: BeginProgress
    show_toast: Callable[[str, str], None]
    log_drop_error: Callable[[Exception], None]


@dataclass(frozen=True)
class CoverLibraryPort:
    selected_targets: Callable[[], list[CoverTarget]]
    preview_state: Callable[[], tuple[object | None, Optional[str]]]
    tree_for_controller: Callable[[object], object | None]
    create_backups: Callable[[list[CoverTarget], dict[str, str]], bool]
    refresh_changed: Callable[[list[CoverTarget], set[tuple[int, int]]], None]
    reload_preview: Callable[[object, str], None]
    record_undo: Callable[[str], None]


class CoverWorkflow:
    def __init__(
        self,
        *,
        cover_controller: CoverController,
        drop_controller: DropController,
        song_info: object,
        ui: CoverUiPort,
        library: CoverLibraryPort,
    ) -> None:
        self.cover_controller = cover_controller
        self.drop_controller = drop_controller
        self.song_info = song_info
        self.ui = ui
        self.library = library

    def targets(self) -> list[CoverTarget]:
        preview_controller, preview_filename = self.library.preview_state()
        return self.cover_controller.cover_targets(
            selections=self.library.selected_targets(),
            preview_controller=preview_controller,
            preview_filename=preview_filename,
            tree_for_controller=self.library.tree_for_controller,
        )

    def preview_targets(self) -> list[CoverTarget]:
        controller, filename = self.library.preview_state()
        if controller is None or not filename:
            return []
        tree = self.library.tree_for_controller(controller)
        if tree is None:
            return []
        return [(controller, tree, [filename])]
```

Create `app/ui/workflows/__init__.py`:

```python
from .cover_workflow import CoverLibraryPort, CoverUiPort, CoverWorkflow

__all__ = ["CoverLibraryPort", "CoverUiPort", "CoverWorkflow"]
```

- [ ] **Step 4: Run the target tests and verify they pass**

Run the command from Step 2.

Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 5: Add failing selection and drop-entry tests**

Append these tests to `CoverWorkflowTests`:

```python
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
    self.drop_controller.payload_from_raw.return_value = DropPayload(
        image_files=["first.png", "second.png"]
    )
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
```

- [ ] **Step 6: Run the four new tests and verify missing methods fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow.CoverWorkflowTests.test_select_preview_cover_warns_without_active_song tests.test_cover_workflow.CoverWorkflowTests.test_select_preview_cover_applies_selected_image_to_preview_target tests.test_cover_workflow.CoverWorkflowTests.test_cover_drop_without_image_warns tests.test_cover_workflow.CoverWorkflowTests.test_cover_drop_applies_first_image_to_preview_target tests.test_cover_workflow.CoverWorkflowTests.test_cover_drop_exception_is_logged_and_shown -v
```

Expected: failures identifying missing `select_preview_cover` and `handle_cover_drop` methods.

- [ ] **Step 7: Implement the selection and drop entry methods**

Add to `CoverWorkflow`:

```python
def select_preview_cover(self) -> None:
    if not self.ui.current_song():
        self.ui.show_warning(self.ui.translate("dialog.selection"), self.ui.translate("preview.no_active_song"))
        return
    cover_path = self.ui.select_image()
    if cover_path:
        self.apply_cover(cover_path, targets=self.preview_targets())

def handle_cover_drop(self, raw_data: str) -> None:
    try:
        payload = self.drop_controller.payload_from_raw(raw_data, splitlist=self.ui.split_drop_data)
        if not payload.image_files:
            self.ui.show_warning(
                self.ui.translate("dialog.cover_selected"),
                self.ui.translate("message.no_image_dropped"),
            )
            return
        self.apply_cover(payload.image_files[0], targets=self.preview_targets())
    except Exception as exc:
        self.ui.log_drop_error(exc)
        self.ui.show_error(
            self.ui.translate("dialog.error"),
            self.ui.translate("message.could_not_process_drop", error=exc),
        )
```

- [ ] **Step 8: Run all Task 1 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow -v
```

Expected: all seven Task 1 tests pass.

- [ ] **Step 9: Commit Task 1**

```powershell
git add app/ui/workflows/__init__.py app/ui/workflows/cover_workflow.py tests/test_cover_workflow.py
git commit -m "refactor: define cover workflow ports"
```

---

### Task 2: Implement manual cover application

**Files:**

- Modify: `app/ui/workflows/cover_workflow.py`
- Modify: `tests/test_cover_workflow.py`

**Interfaces:**

- Consumes: `CoverTarget`, both port dataclasses, `CoverController.apply_manual_cover(...)`, and `CoverApplyResult`.
- Produces: functional `apply_cover(...)`, `_folder_targets(...)`, and `_present_result(...)` methods used by Task 3 and compatibility wrappers in Task 4.

- [ ] **Step 1: Add failing pre-mutation tests**

Append:

```python
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
```

- [ ] **Step 2: Run the pre-mutation tests and verify `apply_cover` is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow.CoverWorkflowTests.test_apply_cover_stops_for_invalid_image tests.test_cover_workflow.CoverWorkflowTests.test_apply_cover_warns_when_no_target_exists tests.test_cover_workflow.CoverWorkflowTests.test_apply_cover_declined_confirmation_stops_before_backup tests.test_cover_workflow.CoverWorkflowTests.test_apply_cover_backup_failure_stops_before_mutation -v
```

Expected: failures identifying the missing `apply_cover` method.

- [ ] **Step 3: Implement validation, target expansion, confirmation, and backup**

Add `apply_cover` and `_folder_targets`:

```python
def apply_cover(
    self,
    cover_path: str,
    targets: Optional[list[CoverTarget]] = None,
    *,
    apply_entire_folder: bool = True,
) -> None:
    if not self.ui.validate_image(cover_path):
        return
    resolved_targets = targets if targets is not None else self.targets()
    if not resolved_targets:
        self.ui.show_warning(self.ui.translate("dialog.selection"), self.ui.translate("message.no_cover_target"))
        return
    backup_targets = self._folder_targets(resolved_targets) if apply_entire_folder else resolved_targets
    target_count = sum(len(filenames) for _controller, _tree, filenames in backup_targets)
    self.ui.update_preview_cover(cover_path)
    if not self.ui.ask_yes_no(
        self.ui.translate("dialog.confirm"),
        self.ui.translate(
            "message.apply_cover_to_count",
            count=target_count,
            name=os.path.basename(cover_path),
        ),
    ):
        return
    if not self.library.create_backups(backup_targets, {"__cover__": os.path.basename(cover_path)}):
        return
    self._apply_manual_cover(resolved_targets, cover_path, target_count, apply_entire_folder)

def _folder_targets(self, targets: list[CoverTarget]) -> list[CoverTarget]:
    folder_targets: list[CoverTarget] = []
    seen_controllers: set[int] = set()
    for controller, tree, _filenames in targets:
        if id(controller) in seen_controllers:
            continue
        seen_controllers.add(id(controller))
        folder_targets.append((controller, tree, controller.archivos.copy()))
    return folder_targets
```

- [ ] **Step 4: Run the pre-mutation tests**

Run the Step 2 command.

Expected: all four tests pass.

- [ ] **Step 5: Add failing success, partial, failure, and progress-close tests**

Append:

```python
def test_manual_cover_success_refreshes_preview_records_undo_and_reports_success(self):
    targets = [(self.controller, self.tree, ["song.mp3"])]
    self.controller.archivos = ["song.mp3", "other.mp3"]
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
    result = CoverApplyResult(1, ["bad.mp3"], False, set())
    self.cover_controller.apply_manual_cover.return_value = result

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
```

- [ ] **Step 6: Run the result tests and verify `_apply_manual_cover` fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow.CoverWorkflowTests.test_manual_cover_success_refreshes_preview_records_undo_and_reports_success tests.test_cover_workflow.CoverWorkflowTests.test_manual_cover_partial_success_reports_warning_and_keeps_undo tests.test_cover_workflow.CoverWorkflowTests.test_manual_cover_total_failure_shows_error_without_undo tests.test_cover_workflow.CoverWorkflowTests.test_manual_cover_closes_progress_when_controller_raises -v
```

Expected: failures identifying the missing `_apply_manual_cover` method.

- [ ] **Step 7: Implement mutation and result presentation**

Add:

```python
def _apply_manual_cover(
    self,
    targets: list[CoverTarget],
    cover_path: str,
    target_count: int,
    apply_entire_folder: bool,
) -> None:
    progress = self.ui.begin_progress(
        title=self.ui.translate("progress.cover_title"),
        message=self.ui.translate("progress.cover_body"),
        total=target_count,
    )
    preview_controller, preview_filename = self.library.preview_state()
    try:
        result = self.cover_controller.apply_manual_cover(
            targets=targets,
            cover_path=cover_path,
            song_info=self.song_info,
            preview_controller=preview_controller,
            preview_filename=preview_filename,
            progress_callback=progress.update,
            apply_entire_folder=apply_entire_folder,
        )
    finally:
        progress.close()
    self.library.refresh_changed(targets, result.changed_pairs)
    self._refresh_preview(result.affected_preview)
    self._present_result(result.success_count, result.errors, "message.cover_applied")

def _refresh_preview(self, affected_preview: bool) -> None:
    controller, filename = self.library.preview_state()
    if affected_preview and controller is not None and filename:
        self.library.reload_preview(controller, filename)

def _present_result(self, success_count: int, errors: list[str], done_key: str) -> None:
    if success_count:
        self.library.record_undo("undo.cover")
        message = self.ui.translate(done_key, count=success_count)
        if errors:
            message += self.ui.translate("message.errors_count", count=len(errors))
            self.ui.show_toast(self.ui.translate("toast.partial"), "warning")
        else:
            self.ui.show_toast(self.ui.translate("toast.done"), "success")
        self.ui.show_info(self.ui.translate("dialog.done"), message)
        return
    self.ui.show_error(
        self.ui.translate("dialog.error"),
        "\n".join(errors) if errors else self.ui.translate("message.could_not_apply_metadata"),
    )
```

- [ ] **Step 8: Run all cover workflow tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow -v
```

Expected: all Task 1 and Task 2 tests pass.

- [ ] **Step 9: Commit Task 2**

```powershell
git add app/ui/workflows/cover_workflow.py tests/test_cover_workflow.py
git commit -m "refactor: isolate manual cover workflow"
```

---

### Task 3: Implement automatic cover application

**Files:**

- Modify: `app/ui/workflows/cover_workflow.py`
- Modify: `tests/test_cover_workflow.py`

**Interfaces:**

- Consumes: Task 2 `_present_result`, `_refresh_preview`, port contracts, `CoverController.build_auto_cover_plan(...)`, and `CoverController.apply_cover_plan(...)`.
- Produces: `apply_auto_cover()` and `apply_auto_cover_targets(targets: list[CoverTarget])` used by metadata tools and Task 4 wrappers.

- [ ] **Step 1: Add failing automatic-cover guard tests**

Append:

```python
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
```

- [ ] **Step 2: Run the guard tests and verify missing methods fail**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow.CoverWorkflowTests.test_auto_cover_warns_without_targets tests.test_cover_workflow.CoverWorkflowTests.test_auto_cover_warns_when_plan_has_no_groups tests.test_cover_workflow.CoverWorkflowTests.test_auto_cover_confirmation_includes_missing_count_and_can_decline -v
```

Expected: failures identifying missing automatic-cover methods.

- [ ] **Step 3: Implement guards, confirmation, and backup**

Add:

```python
def apply_auto_cover(self) -> None:
    targets = self.targets()
    if not targets:
        self.ui.show_warning(self.ui.translate("dialog.selection"), self.ui.translate("message.no_cover_target"))
        return
    self.apply_auto_cover_targets(targets)

def apply_auto_cover_targets(self, targets: list[CoverTarget]) -> None:
    cover_plan = self.cover_controller.build_auto_cover_plan(targets)
    if not cover_plan.groups:
        self.ui.show_warning(self.ui.translate("dialog.cover_selected"), self.ui.translate("auto_cover.not_found"))
        return
    message = self.ui.translate(
        "auto_cover.confirm",
        count=cover_plan.planned_count,
        covers=len(cover_plan.groups),
    )
    if cover_plan.missing:
        message += self.ui.translate("auto_cover.missing_count", count=len(cover_plan.missing))
    if not self.ui.ask_yes_no(self.ui.translate("dialog.confirm"), message):
        return
    backup_groups = [
        (controller, tree, filenames)
        for controller, tree, filenames, _cover_path in cover_plan.groups
    ]
    if not self.library.create_backups(backup_groups, {"__cover__": "auto"}):
        return
    self._apply_auto_cover_plan(cover_plan.groups, backup_groups, cover_plan.planned_count)
```

- [ ] **Step 4: Run the guard tests**

Run the Step 2 command.

Expected: all three tests pass.

- [ ] **Step 5: Add failing automatic success and progress-close tests**

Append:

```python
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
```

- [ ] **Step 6: Run success tests and verify the plan-application helper is missing**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow.CoverWorkflowTests.test_auto_cover_success_updates_preview_refreshes_and_reports_success tests.test_cover_workflow.CoverWorkflowTests.test_auto_cover_closes_progress_when_controller_raises -v
```

Expected: failures identifying the missing `_apply_auto_cover_plan` method.

- [ ] **Step 7: Implement automatic plan application**

Add:

```python
def _apply_auto_cover_plan(
    self,
    groups: list[tuple[object, object, list[str], str]],
    backup_groups: list[CoverTarget],
    planned_count: int,
) -> None:
    progress = self.ui.begin_progress(
        title=self.ui.translate("progress.cover_title"),
        message=self.ui.translate("progress.cover_body"),
        total=planned_count,
    )
    preview_controller, preview_filename = self.library.preview_state()
    try:
        result = self.cover_controller.apply_cover_plan(
            groups,
            song_info=self.song_info,
            preview_controller=preview_controller,
            preview_filename=preview_filename,
            progress_callback=progress.update,
        )
    finally:
        progress.close()
    if result.preview_cover_path:
        self.ui.update_preview_cover(result.preview_cover_path)
    self.library.refresh_changed(backup_groups, result.changed_pairs)
    self._refresh_preview(result.affected_preview)
    self._present_result(result.success_count, result.errors, "auto_cover.done")
```

- [ ] **Step 8: Run the focused and existing cover tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cover_workflow tests.test_cover_controller tests.test_cover_service -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 3**

```powershell
git add app/ui/workflows/cover_workflow.py tests/test_cover_workflow.py
git commit -m "refactor: isolate automatic cover workflow"
```

---

### Task 4: Wire the coordinator and remove mixin orchestration

**Files:**

- Modify: `app/ui/app.py:1-107`
- Modify: `app/ui/metadata_workflow.py:1-248`
- Modify: `tests/test_ui_library_refresh.py`

**Interfaces:**

- Consumes: `CoverWorkflow`, `CoverUiPort`, and `CoverLibraryPort` from Tasks 1–3.
- Produces: `MokaMusicApp.cover_workflow`, `_setup_cover_workflow()`, and five stable compatibility wrappers with the original signatures.

- [ ] **Step 1: Write failing compatibility-wrapper tests**

Add this fake near the other test fakes in `tests/test_ui_library_refresh.py`:

```python
class FakeCoverWorkflow:
    def __init__(self):
        self.calls = []

    def select_preview_cover(self):
        self.calls.append(("select",))

    def handle_cover_drop(self, raw_data):
        self.calls.append(("drop", raw_data))

    def apply_cover(self, cover_path, targets=None, *, apply_entire_folder=True):
        self.calls.append(("apply", cover_path, targets, apply_entire_folder))

    def apply_auto_cover(self):
        self.calls.append(("auto",))

    def apply_auto_cover_targets(self, targets):
        self.calls.append(("auto_targets", targets))
```

Append these tests to `UiLibraryRefreshTests`:

```python
def test_cover_compatibility_wrappers_delegate_exact_arguments(self):
    app = self.make_app()
    app.cover_workflow = FakeCoverWorkflow()
    event = type("Event", (), {"data": "cover.png"})()
    targets = [(app.controller_principal, app.tree_principal, ["song.mp3"])]

    app._select_preview_cover()
    app._handle_cover_drop(event)
    app._apply_cover_to_targets("cover.png", targets=targets, apply_entire_folder=False)
    app._apply_auto_cover_from_folder()
    app._apply_auto_cover_targets(targets)

    self.assertEqual(
        app.cover_workflow.calls,
        [
            ("select",),
            ("drop", "cover.png"),
            ("apply", "cover.png", targets, False),
            ("auto",),
            ("auto_targets", targets),
        ],
    )
```

- [ ] **Step 2: Run the wrapper test and verify it fails against old orchestration**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ui_library_refresh.UiLibraryRefreshTests.test_cover_compatibility_wrappers_delegate_exact_arguments -v
```

Expected: failure because the old methods do not delegate to `cover_workflow`.

- [ ] **Step 3: Construct `CoverWorkflow` in `MokaMusicApp`**

In `app/ui/app.py`, import `messagebox` and the workflow types:

```python
from tkinter import messagebox, ttk

from .workflows import CoverLibraryPort, CoverUiPort, CoverWorkflow
```

Change initialization order:

```python
self._setup_main_menu()
self._setup_ui()
self._setup_cover_workflow()
self._bind_events()
```

Add:

```python
def _setup_cover_workflow(self) -> None:
    ui = CoverUiPort(
        translate=self.t,
        current_song=self.preview.get_current_song,
        select_image=self.file_handler.seleccionar_imagen,
        validate_image=self.file_handler.validar_imagen,
        update_preview_cover=self.preview.update_cover_from_file,
        split_drop_data=self.root.tk.splitlist,
        show_warning=messagebox.showwarning,
        ask_yes_no=messagebox.askyesno,
        show_info=messagebox.showinfo,
        show_error=messagebox.showerror,
        begin_progress=self._begin_progress,
        show_toast=lambda message, kind: self._show_toast(message, kind=kind),
        log_drop_error=lambda exc: self.logger.error("Error handling cover drop: %s", exc),
    )
    library = CoverLibraryPort(
        selected_targets=self._selected_filenames_by_controller,
        preview_state=lambda: (self._preview_controller, self._preview_filename),
        tree_for_controller=self._tree_for_controller,
        create_backups=lambda groups, metadata: bool(
            self._create_metadata_backup_for_groups(groups, metadata)
        ),
        refresh_changed=self._refresh_changed_library_pairs,
        reload_preview=self._load_song_preview,
        record_undo=self._record_undo_action,
    )
    self.cover_workflow = CoverWorkflow(
        cover_controller=self._cover_controller(),
        drop_controller=self._drop_controller(),
        song_info=self.song_info,
        ui=ui,
        library=library,
    )
```

- [ ] **Step 4: Replace mixin cover orchestration with wrappers**

In `app/ui/metadata_workflow.py`, replace the cover section with exactly these methods:

```python
def _select_preview_cover(self) -> None:
    self.cover_workflow.select_preview_cover()

def _handle_cover_drop(self, event) -> None:
    self.cover_workflow.handle_cover_drop(event.data)

def _apply_cover_to_targets(self, cover_path: str, targets=None, *, apply_entire_folder: bool = True) -> None:
    self.cover_workflow.apply_cover(
        cover_path,
        targets=targets,
        apply_entire_folder=apply_entire_folder,
    )

def _apply_auto_cover_from_folder(self) -> None:
    self.cover_workflow.apply_auto_cover()

def _apply_auto_cover_targets(self, targets) -> None:
    self.cover_workflow.apply_auto_cover_targets(targets)
```

Delete `_cover_targets`, `_preview_cover_targets`, and `_folder_cover_targets`. Preserve `_save_preview_metadata` and `_refresh_changed_library_pairs` unchanged. Remove `import os` if Ruff confirms it is no longer used; keep `Path`, `messagebox`, and `simpledialog` because later methods still use them.

- [ ] **Step 5: Run compatibility and cover tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ui_library_refresh.UiLibraryRefreshTests.test_cover_compatibility_wrappers_delegate_exact_arguments tests.test_cover_workflow tests.test_cover_controller tests.test_cover_service -v
```

Expected: all tests pass.

- [ ] **Step 6: Run Ruff on changed files and fix only reported issues**

```powershell
.\.venv\Scripts\ruff.exe check app/ui/app.py app/ui/metadata_workflow.py app/ui/workflows tests/test_cover_workflow.py tests/test_ui_library_refresh.py
.\.venv\Scripts\ruff.exe format app/ui/app.py app/ui/metadata_workflow.py app/ui/workflows tests/test_cover_workflow.py tests/test_ui_library_refresh.py --check
```

Expected: both commands exit `0`. If formatting check fails, run the same `ruff format` command without `--check`, inspect the diff, and rerun both checks.

- [ ] **Step 7: Commit Task 4**

```powershell
git add app/ui/app.py app/ui/metadata_workflow.py app/ui/workflows tests/test_cover_workflow.py tests/test_ui_library_refresh.py
git commit -m "refactor: compose cover workflow in app"
```

---

### Task 5: Full verification and refactor acceptance

**Files:**

- Verify: `app/ui/metadata_workflow.py`
- Verify: all production and test Python files

**Interfaces:**

- Consumes: the completed workflow and compatibility layer.
- Produces: evidence that the refactor preserves behavior and meets structural constraints.

- [ ] **Step 1: Run the full unit-test suite**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: every discovered test passes with final status `OK`.

- [ ] **Step 2: Run project-wide lint and formatting verification**

```powershell
.\.venv\Scripts\ruff.exe check app tests tools
.\.venv\Scripts\ruff.exe format app tests tools --check
```

Expected: both commands exit `0` without diagnostics.

- [ ] **Step 3: Compile the changed modules and smoke-import the application**

```powershell
.\.venv\Scripts\python.exe -m py_compile app\ui\app.py app\ui\metadata_workflow.py app\ui\workflows\cover_workflow.py tests\test_cover_workflow.py
.\.venv\Scripts\python.exe -m unittest tests.test_smoke -v
```

Expected: compilation exits `0`; both smoke tests pass.

- [ ] **Step 4: Verify structural acceptance criteria**

```powershell
rg -n "def (_select_preview_cover|_handle_cover_drop|_apply_cover_to_targets|_apply_auto_cover_from_folder|_apply_auto_cover_targets|_cover_targets|_preview_cover_targets|_folder_cover_targets)" app/ui/metadata_workflow.py
$lines = Get-Content app/ui/metadata_workflow.py
"metadata_workflow_physical_lines=$($lines.Count)"
```

Expected:

- Exactly the five compatibility wrappers appear.
- `_cover_targets`, `_preview_cover_targets`, and `_folder_cover_targets` do not appear.
- `metadata_workflow.py` is smaller than its 1,956-line baseline.

- [ ] **Step 5: Inspect the final diff for accidental UI or copy changes**

```powershell
git diff 4744379..HEAD -- app/ui/app.py app/ui/metadata_workflow.py app/ui/workflows tests/test_cover_workflow.py tests/test_ui_library_refresh.py
```

Expected: only workflow extraction, wiring, tests, imports, and Ruff formatting are present; no theme values, geometry, labels, translation keys, or unrelated flows changed.

- [ ] **Step 6: Record final verification commit only if verification required a tracked correction**

If Steps 1–5 required a source or test correction, stage the exact corrected files and commit:

```powershell
git add app/ui/app.py app/ui/metadata_workflow.py app/ui/workflows tests/test_cover_workflow.py tests/test_ui_library_refresh.py
git commit -m "test: complete cover workflow verification"
```

If the working tree is clean, do not create an empty commit.
