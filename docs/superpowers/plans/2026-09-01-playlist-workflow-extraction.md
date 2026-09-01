# Playlist Workflow Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract playlist numbering, insertion, preparation, and active-target orchestration from `MetadataWorkflowMixin` into an independently testable `PlaylistWorkflow`.

**Architecture:** Add a composed UI workflow with frozen `PlaylistUiPort` and `PlaylistLibraryPort` dataclasses. Keep mutation rules in the existing `PlaylistWorkflowController`; make `MokaMusicApp` the composition root and leave four compatibility wrappers in the mixin.

**Tech Stack:** Python 3, `unittest`, `unittest.mock`, dataclasses, typing protocols, Tkinter callbacks, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-01-playlist-workflow-extraction-design.md`

## Global Constraints

- Preserve playlist numbering, filename formatting, plan semantics, and backup contents exactly.
- Preserve dialog order, labels, translations, default positions, sort changes, progress behavior, toast behavior, keyboard shortcuts, and widget layout.
- Do not move export, import, rename-from-metadata, or `_active_library_view_target` behavior.
- Do not add an event bus, dependency-injection framework, external package, or visual redesign.
- Keep `PlaylistWorkflowController` free of Tkinter and presentation concerns.
- Work on local `main`; a GitHub branch is created only when explicitly requested.

---

### Task 1: Define the playlist workflow boundary and target resolution

**Files:**
- Create: `app/ui/workflows/playlist_workflow.py`
- Modify: `app/ui/workflows/__init__.py`
- Create: `tests/test_playlist_workflow.py`

**Interfaces:**
- Consumes: `PlaylistWorkflowController`, `SortMode`, and application callbacks supplied through ports.
- Produces: `PlaylistUiPort`, `PlaylistLibraryPort`, `PlaylistWorkflow.active_target() -> tuple[object, object] | None`, and reusable `ProgressPort`/`BeginProgress` protocols local to the module.

- [ ] **Step 1: Write the failing target-resolution tests**

Create `tests/test_playlist_workflow.py` with a reusable fixture and these concrete cases:

```python
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
        self.preview_state = [None, None]
        self.selections = []
        self.warnings = []
        self.infos = []
        self.errors = []
        self.toasts = []
        self.progress = FakeProgress()
        self.controller = Mock()
        self.song_info = Mock()
        self.primary_tree = object()
        self.incoming_tree = object()

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
            tree_for_controller=lambda controller: (
                self.primary_tree if controller is self.primary else self.incoming_tree
            ),
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
```

- [ ] **Step 2: Run the tests and verify the import fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow -v
```

Expected: `ModuleNotFoundError` for `app.ui.workflows.playlist_workflow`.

- [ ] **Step 3: Add the typed ports and target resolution**

Create `app/ui/workflows/playlist_workflow.py` with these exact public interfaces:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from ...controllers.playlist_workflow_controller import PlaylistWorkflowController, PlaylistWorkflowPlan
from ...models import ActionResult, SortMode

PlaylistTarget = tuple[object, object]
PlaylistSelection = tuple[object, object, list[str]]


class ProgressPort(Protocol):
    def update(self, completed: int, total: int | None = None, detail: str = "") -> bool:
        pass

    def close(self) -> None:
        pass


class BeginProgress(Protocol):
    def __call__(self, *, title: str, message: str, total: int) -> ProgressPort:
        pass


@dataclass(frozen=True)
class PlaylistUiPort:
    translate: Callable[..., str]
    show_warning: Callable[[str, str], object]
    ask_yes_no: Callable[[str, str], bool]
    show_info: Callable[[str, str], object]
    show_error: Callable[[str, str], object]
    request_position: Callable[..., Optional[int]]
    request_plan_preview: Callable[[PlaylistWorkflowPlan, Callable[[list[str]], PlaylistWorkflowPlan]], Optional[PlaylistWorkflowPlan]]
    begin_progress: BeginProgress
    show_toast: Callable[[str, str], None]
    present_action_result: Callable[[ActionResult], None]


@dataclass(frozen=True)
class PlaylistLibraryPort:
    selected_targets: Callable[[], list[PlaylistSelection]]
    preview_state: Callable[[], tuple[object | None, Optional[str]]]
    set_preview_filename: Callable[[Optional[str]], None]
    tree_for_controller: Callable[[object], object | None]
    primary_target: Callable[[], PlaylistTarget]
    incoming_target: Callable[[], PlaylistTarget]
    can_reorder: Callable[[object, object], bool]
    create_backups: Callable[[list[PlaylistSelection], dict[str, str]], Optional[Path]]
    refresh_tree: Callable[[object, object], None]
    refresh_changed: Callable[[list[PlaylistSelection], set[tuple[int, int]]], None]
    sync_sort: Callable[[object, SortMode], None]
    select_filename: Callable[[object, str], None]
    reload_preview: Callable[[object, str], None]
    record_undo_paths: Callable[[str, list[Path]], None]


class PlaylistWorkflow:
    def __init__(self, *, controller: PlaylistWorkflowController, song_info: object, ui: PlaylistUiPort, library: PlaylistLibraryPort) -> None:
        self.controller = controller
        self.song_info = song_info
        self.ui = ui
        self.library = library

    def active_target(self) -> PlaylistTarget | None:
        selections = self.library.selected_targets()
        if len(selections) > 1:
            self.ui.show_warning(self.ui.translate("dialog.selection"), self.ui.translate("playlist_insert.one_library"))
            return None
        if selections:
            controller, tree, _filenames = selections[0]
            return controller, tree
        preview_controller, _preview_filename = self.library.preview_state()
        if preview_controller is not None and preview_controller.archivos:
            tree = self.library.tree_for_controller(preview_controller)
            if tree is not None:
                return preview_controller, tree
        incoming = self.library.incoming_target()
        if incoming[0].archivos:
            return incoming
        primary = self.library.primary_target()
        if primary[0].archivos:
            return primary
        return None
```

Export `PlaylistLibraryPort`, `PlaylistUiPort`, and `PlaylistWorkflow` from `app/ui/workflows/__init__.py`.

- [ ] **Step 4: Run focused tests and Ruff**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow -v
.\.venv\Scripts\ruff.exe check app\ui\workflows tests\test_playlist_workflow.py
```

Expected: target-resolution tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 5: Commit the boundary**

```powershell
git add app\ui\workflows\playlist_workflow.py app\ui\workflows\__init__.py tests\test_playlist_workflow.py
git commit -m "refactor: define playlist workflow boundary"
```

### Task 2: Move track numbering orchestration

**Files:**
- Modify: `app/ui/workflows/playlist_workflow.py`
- Modify: `tests/test_playlist_workflow.py`

**Interfaces:**
- Consumes: `PlaylistLibraryPort.create_backups`, `refresh_tree`, `reload_preview`, and `PlaylistUiPort.present_action_result` from Task 1.
- Produces: `PlaylistWorkflow.number_tracks() -> None` and private `_numbering_target() -> PlaylistTarget | None`.

- [ ] **Step 1: Add failing numbering characterization tests**

Add tests asserting these exact boundaries:

```python
def test_number_tracks_declined_confirmation_stops_before_backup(self):
    self.ui = replace(self.ui, ask_yes_no=lambda _title, _body: False)
    self.workflow = PlaylistWorkflow(controller=self.controller, song_info=self.song_info, ui=self.ui, library=self.library)

    self.workflow.number_tracks()

    self.library.create_backups.assert_not_called()
    self.primary.apply_track_numbers_from_order.assert_not_called()

def test_number_tracks_success_invalidates_refreshes_preview_and_presents_result(self):
    result = ActionResult.ok("done")
    self.primary.apply_track_numbers_from_order = Mock(return_value=result)
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
```

Also add cases for no loaded files, a non-reorderable view, and backup failure. Import `os`, `replace`, and `ActionResult`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow.PlaylistWorkflowTests.test_number_tracks_success_invalidates_refreshes_preview_and_presents_result -v
```

Expected: FAIL because `PlaylistWorkflow.number_tracks` does not exist.

- [ ] **Step 3: Implement track numbering with current behavior**

Add `_numbering_target()` with preview → principal → incoming precedence. Implement `number_tracks()` using the existing translation keys, `{ "track_number": "order" }` backup payload, `controller.apply_track_numbers_from_order()`, per-file cache invalidation, full-tree refresh, conditional preview reload, and `present_action_result(result)`. Do not record a second undo entry; current numbering behavior relies on the metadata backup path and action-result presentation.

The method must return before mutation on missing files, filtered view, declined confirmation, or falsey backup result.

- [ ] **Step 4: Run focused tests and the controller tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow tests.test_playlist_workflow_controller -v
.\.venv\Scripts\ruff.exe check app\ui\workflows\playlist_workflow.py tests\test_playlist_workflow.py
```

Expected: all playlist workflow and controller tests pass; Ruff is clean.

- [ ] **Step 5: Commit numbering orchestration**

```powershell
git add app\ui\workflows\playlist_workflow.py tests\test_playlist_workflow.py
git commit -m "refactor: isolate playlist numbering workflow"
```

### Task 3: Move insertion and preparation through one executor

**Files:**
- Modify: `app/ui/workflows/playlist_workflow.py`
- Modify: `tests/test_playlist_workflow.py`

**Interfaces:**
- Consumes: `PlaylistWorkflowController.build_insert_plan`, `build_plan_from_order`, and `execute_plan`.
- Produces: `insert_selected() -> None`, `prepare_active() -> None`, and private `_execute_plan(plan: PlaylistWorkflowPlan, done_key: str) -> None`.

- [ ] **Step 1: Add failing validation and cancellation tests**

Add named tests for:

```python
def test_insert_selected_rejects_two_library_selection(self):
    self.selections = [
        (self.primary, self.primary_tree, ["primary.mp3"]),
        (self.incoming, self.incoming_tree, ["incoming.mp3"]),
    ]

    self.workflow.insert_selected()

    self.assertEqual(self.warnings, [("dialog.selection", "playlist_insert.one_library")])
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
```

Add separate assertions for no selection, cancelled position, no-change plan, cancelled preview, missing active target, and non-reorderable preparation.

- [ ] **Step 2: Run validation tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow.PlaylistWorkflowTests.test_insert_selected_converts_ui_position_before_building_plan -v
```

Expected: FAIL because `insert_selected` does not exist.

- [ ] **Step 3: Implement insertion and preparation up to confirmed plans**

Implement `insert_selected()` with current selection validation, request-position keyword arguments, one-based conversion, plan construction, no-change message, and preview callback. Implement `prepare_active()` using `active_target()`, current order, the same preview callback, and `playlist_prepare.done` as its result key.

Both methods must call `_execute_plan(confirmed_plan, done_key)` and must not contain controller execution, refresh, sorting, undo, or final feedback themselves.

- [ ] **Step 4: Add failing shared-executor tests**

Import `PlaylistApplyResult` from `app.controllers.playlist_workflow_controller` and `SortMode` from `app.models`. Use a result with a changed pair and backup path to assert:

```python
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
        [(self.primary, self.primary_tree, ["renamed.mp3"])], result.changed_pairs
    )
    self.assertEqual(self.primary.set_sort_mode.call_args.args, (SortMode.TRACK_NUMBER,))
    self.library.sync_sort.assert_called_once_with(self.primary, SortMode.TRACK_NUMBER)
    self.library.select_filename.assert_called_once_with(self.primary_tree, "renamed.mp3")
    self.library.reload_preview.assert_called_once_with(self.primary, "renamed.mp3")
    self.library.record_undo_paths.assert_called_once_with("undo.playlist", [Path("backup.json")])
    self.assertEqual(self.toasts, [("toast.done", "success")])
    self.assertEqual(self.infos[0][0], "dialog.done")
```

Add one exception test asserting progress closes and the exception propagates, plus one failed-result test asserting no undo and an error dialog containing controller errors.

Add one test for each public command that replaces `_execute_plan` with a mock and proves insertion passes `playlist_insert.done` while preparation passes `playlist_prepare.done`.

- [ ] **Step 5: Implement the shared executor**

`_execute_plan` must:

1. Open progress with `progress.playlist_title`, `progress.playlist_body`, and `len(plan.items) * 2`.
2. Call `controller.execute_plan` with `song_info`, current preview state, and `progress.update`.
3. Close progress in `finally`.
4. Store `result.preview_filename` through the library port.
5. Refresh changed pairs using `plan.final_order`.
6. Set controller and widget sorting to `SortMode.TRACK_NUMBER`.
7. Reselect and reload an affected preview.
8. On success, record a returned backup path, build the current localized message, append `message.backup_created`, show the success toast, and show information.
9. On failure, join `result.errors` or use `message.could_not_apply_metadata`, then show an error.

- [ ] **Step 6: Run focused tests and complexity checks**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow tests.test_playlist_workflow_controller -v
.\.venv\Scripts\ruff.exe check app\ui\workflows\playlist_workflow.py tests\test_playlist_workflow.py --select E,F,I,C901,PLR0912,PLR0915
```

Expected: all focused tests pass and no new complexity violations are reported.

- [ ] **Step 7: Commit playlist ordering orchestration**

```powershell
git add app\ui\workflows\playlist_workflow.py tests\test_playlist_workflow.py
git commit -m "refactor: isolate playlist ordering workflow"
```

### Task 4: Compose the workflow and reduce the mixin to delegation

**Files:**
- Modify: `app/ui/app.py:39-145`
- Modify: `app/ui/metadata_workflow.py:11,41,44,1225-1444`
- Modify: `tests/test_ui_library_refresh.py:124-320`

**Interfaces:**
- Consumes: all Task 1–3 workflow interfaces.
- Produces: `MokaMusicApp._setup_playlist_workflow() -> None` and four stable compatibility wrappers.

- [ ] **Step 1: Write failing compatibility-wrapper tests**

Add a `FakePlaylistWorkflow` to `tests/test_ui_library_refresh.py` that records `number_tracks`, `insert_selected`, `prepare_active`, and `active_target` calls. Assert:

```python
def test_playlist_compatibility_wrappers_delegate_to_workflow(self):
    app = MokaMusicApp.__new__(MokaMusicApp)
    app.playlist_workflow = FakePlaylistWorkflow()

    app._number_tracks_for_active_library()
    app._insert_selected_at_position()
    app._prepare_active_playlist()
    target = app._active_playlist_target()

    self.assertEqual(app.playlist_workflow.calls, ["number", "insert", "prepare", "target"])
    self.assertIs(target, app.playlist_workflow.target)
```

- [ ] **Step 2: Run the wrapper test and verify failure**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ui_library_refresh.UiLibraryRefreshTests.test_playlist_compatibility_wrappers_delegate_to_workflow -v
```

Expected: FAIL because the current methods execute application orchestration instead of delegating.

- [ ] **Step 3: Compose `PlaylistWorkflow` in `MokaMusicApp`**

Import the workflow types and the two existing modal functions into `app/ui/app.py`. Call `_setup_playlist_workflow()` after `_setup_cover_workflow()` and before `_bind_events()`.

Construct `PlaylistUiPort` with existing translations, `messagebox`, `_begin_progress`, `_show_toast`, `_handle_action_result`, and lambdas that adapt `request_track_position(self.root, self.t, **kwargs)` and `request_playlist_insert_preview(self.root, self.t, plan, rebuild)`.

Construct `PlaylistLibraryPort` with existing selection, preview, tree, backup, refresh, sorting, selection, reload, and undo callbacks. Use `setattr(self, "_preview_filename", filename)` only inside the `set_preview_filename` adapter. Supply `(controller_principal, tree_principal)` and `(controller_nueva, tree_nueva)` through dedicated target callbacks.

Implement the composition method with these adapters:

```python
def _setup_playlist_workflow(self) -> None:
    ui = PlaylistUiPort(
        translate=self.t,
        show_warning=messagebox.showwarning,
        ask_yes_no=messagebox.askyesno,
        show_info=messagebox.showinfo,
        show_error=messagebox.showerror,
        request_position=lambda **kwargs: request_track_position(self.root, self.t, **kwargs),
        request_plan_preview=lambda plan, rebuild: request_playlist_insert_preview(
            self.root, self.t, plan, rebuild
        ),
        begin_progress=self._begin_progress,
        show_toast=lambda message, kind: self._show_toast(message, kind=kind),
        present_action_result=self._handle_action_result,
    )
    library = PlaylistLibraryPort(
        selected_targets=self._selected_filenames_by_controller,
        preview_state=lambda: (self._preview_controller, self._preview_filename),
        set_preview_filename=lambda filename: setattr(self, "_preview_filename", filename),
        tree_for_controller=self._tree_for_controller,
        primary_target=lambda: (self.controller_principal, self.tree_principal),
        incoming_target=lambda: (self.controller_nueva, self.tree_nueva),
        can_reorder=self._can_reorder_current_view,
        create_backups=self._create_metadata_backup_for_groups,
        refresh_tree=self._refresh_library_tree,
        refresh_changed=self._refresh_changed_library_pairs,
        sync_sort=self._set_sort_widget_for_controller,
        select_filename=self._select_filename_in_tree,
        reload_preview=self._load_song_preview,
        record_undo_paths=self._record_undo_paths,
    )
    self.playlist_workflow = PlaylistWorkflow(
        controller=self._playlist_workflow_controller(),
        song_info=self.song_info,
        ui=ui,
        library=library,
    )
```

- [ ] **Step 4: Replace orchestration with exact wrappers**

Replace the existing playlist methods in `MetadataWorkflowMixin` with:

```python
def _number_tracks_for_active_library(self) -> None:
    self.playlist_workflow.number_tracks()

def _insert_selected_at_position(self) -> None:
    self.playlist_workflow.insert_selected()

def _prepare_active_playlist(self) -> None:
    self.playlist_workflow.prepare_active()

def _active_playlist_target(self):
    return self.playlist_workflow.active_target()
```

Remove playlist-only imports of `SortMode`, `request_playlist_insert_preview`, and `request_track_position` from `metadata_workflow.py`. Keep `_active_library_view_target`, `_select_filename_in_tree`, and all export/import code in place.

- [ ] **Step 5: Run focused integration tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow tests.test_playlist_workflow_controller tests.test_ui_library_refresh -v
.\.venv\Scripts\python.exe -m unittest tests.test_smoke -v
```

Expected: workflow, controller, wrapper, UI refresh, and smoke tests pass.

- [ ] **Step 6: Verify structural reduction and imports**

```powershell
rg -n "def (_number_tracks_for_active_library|_insert_selected_at_position|_prepare_active_playlist|_active_playlist_target)" app\ui\metadata_workflow.py
rg -n "SortMode|request_track_position|request_playlist_insert_preview" app\ui\metadata_workflow.py
```

Expected: exactly four playlist wrapper definitions; the second command returns no matches.

- [ ] **Step 7: Commit application composition**

```powershell
git add app\ui\app.py app\ui\metadata_workflow.py tests\test_ui_library_refresh.py
git commit -m "refactor: compose playlist workflow in app"
```

### Task 5: Complete repository verification

**Files:**
- Verify: `app/ui/workflows/playlist_workflow.py`
- Verify: `app/ui/app.py`
- Verify: `app/ui/metadata_workflow.py`
- Verify: `tests/test_playlist_workflow.py`
- Verify: `tests/test_ui_library_refresh.py`

**Interfaces:**
- Consumes: the completed workflow and compatibility boundary.
- Produces: fresh evidence that the refactor preserves repository behavior and quality constraints.

- [ ] **Step 1: Run the full test suite**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Expected: all tests pass with zero failures and zero errors.

- [ ] **Step 2: Run repository-wide Ruff checks**

```powershell
.\.venv\Scripts\ruff.exe check app tests tools
.\.venv\Scripts\ruff.exe format app tests tools --check
```

Expected: `All checks passed!` and every file already formatted.

- [ ] **Step 3: Compile changed production modules**

```powershell
.\.venv\Scripts\python.exe -m py_compile app\ui\workflows\playlist_workflow.py app\ui\app.py app\ui\metadata_workflow.py
```

Expected: exit code 0 and no output.

- [ ] **Step 4: Check the final diff and size**

```powershell
git diff b315f48..HEAD --check
git diff b315f48..HEAD --stat
(Get-Content app\ui\metadata_workflow.py).Count
git status --short
```

Expected: no whitespace errors, approximately 200–220 lines removed from `metadata_workflow.py`, only scoped workflow/composition/test files changed, and a clean working tree.

- [ ] **Step 5: Review requirements line by line**

Confirm from the diff that no translation resources, layout files, styles, export/import behavior, `_active_library_view_target`, controller plan semantics, or external dependencies changed. If any appear, remove those unrelated changes and rerun Steps 1–4.
