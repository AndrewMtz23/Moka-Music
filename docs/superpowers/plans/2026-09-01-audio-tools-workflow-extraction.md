# Audio Tools Workflow Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract audio audit and conversion orchestration from `MetadataWorkflowMixin` into a focused, independently tested `AudioToolsWorkflow`, reducing the mixin by roughly 145–160 lines without changing observable behavior.

**Architecture:** Add a framework-light workflow under `app/ui/workflows/` whose frozen port dataclasses receive every UI, library, and service dependency. The Tk application composes those adapters once, while the mixin retains four compatibility wrappers so menus and event bindings do not change. Service algorithms and existing modal implementations remain untouched.

**Tech Stack:** Python 3, Tkinter adapters, `dataclasses`, `typing.Protocol`, `pathlib.Path`, `pytest`, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-01-audio-tools-workflow-extraction-design.md`

## Global Constraints

- Work directly on local `main`; do not create a local feature branch or worktree.
- Preserve all current translation keys, titles, messages, column order, column widths, toast kinds, and modal behavior exactly.
- Do not change the algorithms or public APIs in `audio_audit_service.py` or `audio_conversion_service.py`.
- Keep rename-by-template, folder organization, file-plan, playlist validation, and smart-playlist behavior in `MetadataWorkflowMixin`.
- Keep `_analyze_audio_quality`, `_detect_advanced_duplicates`, `_validate_audio_files`, and `_convert_selected_audio` as compatibility wrappers.
- Move `_audio_tool_targets` and `_refresh_libraries_after_conversion` into the workflow as private behavior.
- Use tests as the characterization contract before removing code from the mixin.
- Do not introduce new dependencies or visual redesigns.

---

## File Map

- Create `app/ui/workflows/audio_tools_workflow.py`: ports, target resolution, audit orchestration, conversion orchestration, result presentation, and destination refresh.
- Create `tests/test_audio_tools_workflow.py`: focused unit tests using fake ports and service functions; no Tk root required.
- Modify `app/ui/workflows/__init__.py`: export the workflow and its three port dataclasses.
- Modify `app/ui/app.py`: compose concrete Tk/library/service adapters and initialize the workflow.
- Modify `app/ui/metadata_workflow.py`: replace four implementations with delegation wrappers and remove imports/helpers that moved.
- Modify `tests/test_ui_library_refresh.py`: characterize the compatibility wrappers and application-level composition seam.

---

### Task 1: Define the Audio Tools Boundary and Target Resolution

**Files:**
- Create: `app/ui/workflows/audio_tools_workflow.py`
- Create: `tests/test_audio_tools_workflow.py`
- Modify: `app/ui/workflows/__init__.py`

**Interfaces:**
- Consumes: controller-like objects exposing `archivos`, `carpeta`, and `refresh_library()`; progress objects exposing `update(completed, total=None, detail="") -> bool` and `close() -> None`.
- Produces: `AudioTarget = tuple[object, object, list[str]]`, `AudioToolsUiPort`, `AudioToolsLibraryPort`, `AudioToolsOperations`, and `AudioToolsWorkflow.targets() -> list[AudioTarget]`.

- [ ] **Step 1: Write failing target-resolution tests**

Create `tests/test_audio_tools_workflow.py` with reusable fakes and two characterization tests:

```python
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.audio_conversion_service import AudioConversionItem, AudioConversionResult
from app.ui.workflows.audio_tools_workflow import (
    AudioToolsLibraryPort,
    AudioToolsOperations,
    AudioToolsUiPort,
    AudioToolsWorkflow,
)


class FakeProgress:
    def __init__(self) -> None:
        self.updates: list[tuple[object, ...]] = []
        self.closed = False

    def update(self, *args) -> bool:
        self.updates.append(args)
        return True

    def close(self) -> None:
        self.closed = True


class Harness:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []
        self.progress = FakeProgress()
        self.selections: list[tuple[object, object, list[str]]] = []
        self.active: tuple[object, object] | None = None
        self.library_pairs: list[tuple[object, object]] = []
        self.options: dict[str, object] | None = None
        self.quality_rows: list[dict[str, object]] = []
        self.duplicate_rows: list[dict[str, object]] = []
        self.validation_rows: list[dict[str, object]] = []
        self.conversion_items: list[AudioConversionItem] = []
        self.conversion_result = AudioConversionResult(0, [], [])

        self.workflow = AudioToolsWorkflow(
            ui=AudioToolsUiPort(
                translate=lambda key, **values: key if not values else f"{key}:{values}",
                show_warning=lambda title, message: self.events.append(("warning", title, message)),
                show_info=lambda title, message: self.events.append(("info", title, message)),
                show_error=lambda title, message: self.events.append(("error", title, message)),
                show_audit=lambda title, rows, columns: self.events.append(
                    ("audit", title, rows, columns)
                ),
                request_conversion_options=lambda count: self._request_options(count),
                begin_progress=lambda **kwargs: self._begin_progress(**kwargs),
                show_toast=lambda message, kind: self.events.append(("toast", message, kind)),
            ),
            library=AudioToolsLibraryPort(
                selected_targets=lambda: self.selections,
                active_target=lambda: self.active,
                library_targets=lambda: self.library_pairs,
                refresh_tree=lambda controller, tree: self.events.append(
                    ("refresh_tree", controller, tree)
                ),
            ),
            operations=AudioToolsOperations(
                build_quality_rows=lambda groups: self.quality_rows,
                detect_duplicates=lambda groups: self.duplicate_rows,
                validate_files=lambda groups: self.validation_rows,
                build_conversion_items=self._build_items,
                convert_files=self._convert,
            ),
        )

    def _request_options(self, count: int) -> dict[str, object] | None:
        self.events.append(("request_options", count))
        return self.options

    def _begin_progress(self, **kwargs) -> FakeProgress:
        self.events.append(("begin_progress", kwargs))
        return self.progress

    def _build_items(self, *args, **kwargs) -> list[AudioConversionItem]:
        self.events.append(("build_items", args, kwargs))
        return self.conversion_items

    def _convert(self, *args, **kwargs) -> AudioConversionResult:
        self.events.append(("convert", args, kwargs))
        return self.conversion_result


def controller(folder: str, filenames: list[str]):
    return SimpleNamespace(carpeta=folder, archivos=filenames.copy(), refresh_library=lambda: None)


def test_targets_prefer_explicit_selections() -> None:
    harness = Harness()
    selected_controller = controller("selected", ["all.mp3"])
    selected = [(selected_controller, "selected-tree", ["picked.mp3"])]
    harness.selections = selected
    harness.active = (controller("active", ["fallback.mp3"]), "active-tree")

    assert harness.workflow.targets() == selected


def test_targets_fall_back_to_all_files_in_active_library() -> None:
    harness = Harness()
    active_controller = controller("active", ["one.mp3", "two.flac"])
    harness.active = (active_controller, "active-tree")

    assert harness.workflow.targets() == [
        (active_controller, "active-tree", ["one.mp3", "two.flac"])
    ]
    assert harness.workflow.targets()[0][2] is not active_controller.archivos
```

- [ ] **Step 2: Run the tests and verify the boundary is missing**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.ui.workflows.audio_tools_workflow'`.

- [ ] **Step 3: Implement the ports and target resolution**

Create `app/ui/workflows/audio_tools_workflow.py` with these exact public definitions:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ...services.audio_conversion_service import AudioConversionItem, AudioConversionResult

AudioTarget = tuple[object, object, list[str]]
LibraryTarget = tuple[object, object]
AuditColumn = tuple[str, str, int]


class ProgressPort(Protocol):
    def update(self, completed: int, total: int | None = None, detail: str = "") -> bool: ...

    def close(self) -> None: ...


class BeginProgress(Protocol):
    def __call__(self, *, title: str, message: str, total: int) -> ProgressPort: ...


@dataclass(frozen=True)
class AudioToolsUiPort:
    translate: Callable[..., str]
    show_warning: Callable[[str, str], object]
    show_info: Callable[[str, str], object]
    show_error: Callable[[str, str], object]
    show_audit: Callable[[str, list[dict[str, object]], list[AuditColumn]], object]
    request_conversion_options: Callable[[int], dict[str, object] | None]
    begin_progress: BeginProgress
    show_toast: Callable[[str, str], None]


@dataclass(frozen=True)
class AudioToolsLibraryPort:
    selected_targets: Callable[[], list[AudioTarget]]
    active_target: Callable[[], LibraryTarget | None]
    library_targets: Callable[[], list[LibraryTarget]]
    refresh_tree: Callable[[object, object], None]


@dataclass(frozen=True)
class AudioToolsOperations:
    build_quality_rows: Callable[[list[AudioTarget]], list[dict[str, object]]]
    detect_duplicates: Callable[[list[AudioTarget]], list[dict[str, object]]]
    validate_files: Callable[[list[AudioTarget]], list[dict[str, object]]]
    build_conversion_items: Callable[..., list[AudioConversionItem]]
    convert_files: Callable[..., AudioConversionResult]


class AudioToolsWorkflow:
    def __init__(
        self,
        *,
        ui: AudioToolsUiPort,
        library: AudioToolsLibraryPort,
        operations: AudioToolsOperations,
    ) -> None:
        self.ui = ui
        self.library = library
        self.operations = operations

    def targets(self) -> list[AudioTarget]:
        selections = self.library.selected_targets()
        if selections:
            return selections
        target = self.library.active_target()
        if target is None:
            return []
        controller, tree = target
        return [(controller, tree, controller.archivos.copy())]
```

Export the new names from `app/ui/workflows/__init__.py`:

```python
from .audio_tools_workflow import (
    AudioToolsLibraryPort,
    AudioToolsOperations,
    AudioToolsUiPort,
    AudioToolsWorkflow,
)
```

Add all four strings to `__all__`.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit the boundary**

```powershell
git add app/ui/workflows/audio_tools_workflow.py app/ui/workflows/__init__.py tests/test_audio_tools_workflow.py
git commit -m "refactor: define audio tools workflow boundary"
```

---

### Task 2: Move the Three Audio Audit Flows

**Files:**
- Modify: `app/ui/workflows/audio_tools_workflow.py`
- Modify: `tests/test_audio_tools_workflow.py`

**Interfaces:**
- Consumes: `AudioToolsWorkflow.targets()` and the three operation callables defined in Task 1.
- Produces: `analyze_quality() -> None`, `detect_duplicates() -> None`, and `validate_files() -> None` with the existing translation keys and column schemas.

- [ ] **Step 1: Write failing characterization tests for audits**

Append these tests:

```python
def test_analyze_quality_warns_when_no_target_exists() -> None:
    harness = Harness()

    harness.workflow.analyze_quality()

    assert harness.events == [
        ("warning", "dialog.no_files", "message.no_loaded_files")
    ]


def test_analyze_quality_builds_rows_and_preserves_column_schema() -> None:
    harness = Harness()
    group = (controller("music", ["song.mp3"]), "tree", ["song.mp3"])
    harness.selections = [group]
    harness.quality_rows = [{"filename": "song.mp3", "bitrate_kbps": 128}]

    harness.workflow.analyze_quality()

    event = harness.events[-1]
    assert event[:3] == ("audit", "audio_tools.quality_title", harness.quality_rows)
    assert [column[0] for column in event[3]] == [
        "filename", "title", "artist", "duration", "bitrate_kbps",
        "sample_rate", "channels", "format", "low_bitrate", "possibly_corrupt",
    ]
    assert [column[2] for column in event[3]] == [260, 180, 160, 80, 90, 90, 80, 80, 90, 90]


def test_duplicate_audit_reports_empty_result_without_opening_modal() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.mp3"]), "tree", ["song.mp3"])]

    harness.workflow.detect_duplicates()

    assert harness.events == [
        ("info", "audio_tools.duplicates_title", "audio_tools.no_duplicates")
    ]


def test_duplicate_audit_opens_modal_with_existing_schema() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["a.mp3"]), "tree", ["a.mp3"])]
    harness.duplicate_rows = [{"filename": "a.mp3", "issue": "same"}]

    harness.workflow.detect_duplicates()

    event = harness.events[-1]
    assert event[:3] == ("audit", "audio_tools.duplicates_title", harness.duplicate_rows)
    assert event[3] == [
        ("filename", "audio_tools.filename", 360),
        ("title", "audio_tools.title", 180),
        ("artist", "audio_tools.artist", 160),
        ("duration", "audio_tools.duration", 130),
        ("issue", "audio_tools.issue", 180),
    ]


def test_validation_reports_empty_result_without_opening_modal() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.mp3"]), "tree", ["song.mp3"])]

    harness.workflow.validate_files()

    assert harness.events == [
        ("info", "audio_tools.validation_title", "audio_tools.no_validation_issues")
    ]


def test_validation_opens_modal_with_existing_schema() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["bad.mp3"]), "tree", ["bad.mp3"])]
    harness.validation_rows = [{"filename": "bad.mp3", "issues": "broken"}]

    harness.workflow.validate_files()

    event = harness.events[-1]
    assert event[:3] == ("audit", "audio_tools.validation_title", harness.validation_rows)
    assert event[3] == [
        ("filename", "audio_tools.filename", 260),
        ("path", "audio_tools.path", 360),
        ("format", "audio_tools.format", 100),
        ("issues", "audio_tools.issues", 220),
    ]
```

- [ ] **Step 2: Run the audit tests and verify the methods are absent**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: the six new tests fail with `AttributeError` for `analyze_quality`, `detect_duplicates`, or `validate_files`.

- [ ] **Step 3: Implement the audit methods**

Add the three public methods. Use this helper so all three preserve the same no-files behavior:

```python
    def _require_targets(self) -> list[AudioTarget]:
        groups = self.targets()
        if not groups:
            self.ui.show_warning(
                self.ui.translate("dialog.no_files"),
                self.ui.translate("message.no_loaded_files"),
            )
        return groups
```

Add these exact methods:

```python
    def analyze_quality(self) -> None:
        groups = self._require_targets()
        if not groups:
            return
        rows = self.operations.build_quality_rows(groups)
        self.ui.show_audit(
            self.ui.translate("audio_tools.quality_title"),
            rows,
            [
                ("filename", self.ui.translate("audio_tools.filename"), 260),
                ("title", self.ui.translate("audio_tools.title"), 180),
                ("artist", self.ui.translate("audio_tools.artist"), 160),
                ("duration", self.ui.translate("audio_tools.duration"), 80),
                ("bitrate_kbps", self.ui.translate("audio_tools.bitrate"), 90),
                ("sample_rate", self.ui.translate("audio_tools.sample_rate"), 90),
                ("channels", self.ui.translate("audio_tools.channels"), 80),
                ("format", self.ui.translate("audio_tools.format"), 80),
                ("low_bitrate", self.ui.translate("audio_tools.low_bitrate"), 90),
                ("possibly_corrupt", self.ui.translate("audio_tools.corrupt"), 90),
            ],
        )

    def detect_duplicates(self) -> None:
        groups = self._require_targets()
        if not groups:
            return
        rows = self.operations.detect_duplicates(groups)
        title = self.ui.translate("audio_tools.duplicates_title")
        if not rows:
            self.ui.show_info(title, self.ui.translate("audio_tools.no_duplicates"))
            return
        self.ui.show_audit(
            title,
            rows,
            [
                ("filename", self.ui.translate("audio_tools.filename"), 360),
                ("title", self.ui.translate("audio_tools.title"), 180),
                ("artist", self.ui.translate("audio_tools.artist"), 160),
                ("duration", self.ui.translate("audio_tools.duration"), 130),
                ("issue", self.ui.translate("audio_tools.issue"), 180),
            ],
        )

    def validate_files(self) -> None:
        groups = self._require_targets()
        if not groups:
            return
        rows = self.operations.validate_files(groups)
        title = self.ui.translate("audio_tools.validation_title")
        if not rows:
            self.ui.show_info(title, self.ui.translate("audio_tools.no_validation_issues"))
            return
        self.ui.show_audit(
            title,
            rows,
            [
                ("filename", self.ui.translate("audio_tools.filename"), 260),
                ("path", self.ui.translate("audio_tools.path"), 360),
                ("format", self.ui.translate("audio_tools.format"), 100),
                ("issues", self.ui.translate("audio_tools.issues"), 220),
            ],
        )
```

- [ ] **Step 4: Run audit tests and static checks**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: `8 passed`.

Run: `python -m ruff check app/ui/workflows/audio_tools_workflow.py tests/test_audio_tools_workflow.py`

Expected: `All checks passed!`.

- [ ] **Step 5: Commit the audit extraction**

```powershell
git add app/ui/workflows/audio_tools_workflow.py tests/test_audio_tools_workflow.py
git commit -m "refactor: isolate audio audit workflow"
```

---

### Task 3: Isolate Conversion Input and Item Planning

**Files:**
- Modify: `app/ui/workflows/audio_tools_workflow.py`
- Modify: `tests/test_audio_tools_workflow.py`

**Interfaces:**
- Consumes: `library.selected_targets()`, `ui.request_conversion_options(count)`, and `operations.build_conversion_items(...)`.
- Produces: the first half of `convert_selected() -> None`, including explicit-selection enforcement, cancellation, flat-output planning, preserve-structure planning, and build-error presentation.

- [ ] **Step 1: Write failing tests for selection and flat planning**

Append:

```python
def test_conversion_requires_explicit_selection() -> None:
    harness = Harness()
    harness.active = (controller("music", ["fallback.mp3"]), "tree")

    harness.workflow.convert_selected()

    assert harness.events == [
        ("warning", "dialog.selection", "audio_conversion.no_selection")
    ]


def test_conversion_cancellation_stops_before_item_planning() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.mp3"]), "tree", ["song.mp3"])]

    harness.workflow.convert_selected()

    assert harness.events == [("request_options", 1)]


def test_conversion_builds_flat_items_from_all_selected_libraries(tmp_path: Path) -> None:
    harness = Harness()
    first = controller(str(tmp_path / "one"), ["a.mp3"])
    second = controller(str(tmp_path / "two"), ["b.flac"])
    harness.selections = [
        (first, "tree-one", ["a.mp3"]),
        (second, "tree-two", ["b.flac"]),
    ]
    harness.options = {
        "destination": str(tmp_path / "out"),
        "format": ".mp3",
        "bitrate": "320k",
        "overwrite": False,
        "preserve_structure": False,
    }

    harness.workflow.convert_selected()

    build = next(event for event in harness.events if event[0] == "build_items")
    assert build[1] == (
        [str(tmp_path / "one" / "a.mp3"), str(tmp_path / "two" / "b.flac")],
        str(tmp_path / "out"),
        ".mp3",
    )
    assert build[2] == {"bitrate": "320k"}
```

- [ ] **Step 2: Run the tests and verify `convert_selected` is missing**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: the three new tests fail with `AttributeError: 'AudioToolsWorkflow' object has no attribute 'convert_selected'`.

- [ ] **Step 3: Implement selection, option request, and flat planning**

Start `convert_selected()` with the existing control flow:

```python
    def convert_selected(self) -> None:
        selections = self.library.selected_targets()
        if not selections:
            self.ui.show_warning(
                self.ui.translate("dialog.selection"),
                self.ui.translate("audio_conversion.no_selection"),
            )
            return

        source_groups = [
            (controller, [str(Path(controller.carpeta) / filename) for filename in filenames])
            for controller, _tree, filenames in selections
        ]
        sources = [source for _controller, group in source_groups for source in group]
        options = self.ui.request_conversion_options(len(sources))
        if not options:
            return

        try:
            items = self._build_conversion_items(source_groups, sources, options)
        except Exception as exc:
            self.ui.show_error(
                self.ui.translate("dialog.error"),
                self.ui.translate("audio_conversion.failed", error=exc),
            )
            return
```

Implement `_build_conversion_items` initially with the flat branch below. Leave `convert_selected()` ending immediately after the `try/except` block; Task 4 adds execution.

```python
    def _build_conversion_items(
        self,
        source_groups: list[tuple[object, list[str]]],
        sources: list[str],
        options: dict[str, object],
    ) -> list[AudioConversionItem]:
        return self.operations.build_conversion_items(
            sources,
            str(options["destination"]),
            str(options["format"]),
            bitrate=options.get("bitrate"),
        )
```

- [ ] **Step 4: Add preserve-structure and build-error tests**

Append:

```python
def test_conversion_preserves_each_library_root(tmp_path: Path) -> None:
    harness = Harness()
    first = controller(str(tmp_path / "one"), ["a.mp3"])
    second = controller(str(tmp_path / "two"), ["b.mp3"])
    harness.selections = [(first, "one", ["a.mp3"]), (second, "two", ["b.mp3"])]
    harness.options = {
        "destination": str(tmp_path / "out"),
        "format": ".flac",
        "bitrate": None,
        "preserve_structure": True,
    }

    harness.workflow.convert_selected()

    builds = [event for event in harness.events if event[0] == "build_items"]
    assert len(builds) == 2
    assert builds[0][2] == {
        "bitrate": None,
        "preserve_structure": True,
        "source_root": str(tmp_path / "one"),
    }
    assert builds[1][2]["source_root"] == str(tmp_path / "two")


def test_conversion_item_build_error_is_presented_and_stops() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.mp3"]), "tree", ["song.mp3"])]
    harness.options = {"destination": "out", "format": ".invalid"}

    def fail(*args, **kwargs):
        raise ValueError("bad format")

    object.__setattr__(harness.workflow.operations, "build_conversion_items", fail)

    harness.workflow.convert_selected()

    assert harness.events[-1] == (
        "error", "dialog.error", "audio_conversion.failed:{'error': ValueError('bad format')}"
    )
    assert not any(event[0] == "begin_progress" for event in harness.events)
```

- [ ] **Step 5: Complete `_build_conversion_items` and run tests**

Replace `_build_conversion_items` with the complete version:

```python
    def _build_conversion_items(
        self,
        source_groups: list[tuple[object, list[str]]],
        sources: list[str],
        options: dict[str, object],
    ) -> list[AudioConversionItem]:
        if bool(options.get("preserve_structure")):
            items: list[AudioConversionItem] = []
            for controller, group_sources in source_groups:
                items.extend(
                    self.operations.build_conversion_items(
                        group_sources,
                        str(options["destination"]),
                        str(options["format"]),
                        bitrate=options.get("bitrate"),
                        preserve_structure=True,
                        source_root=controller.carpeta,
                    )
                )
            return items
        return self.operations.build_conversion_items(
            sources,
            str(options["destination"]),
            str(options["format"]),
            bitrate=options.get("bitrate"),
        )
```

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: `13 passed`.

- [ ] **Step 6: Commit conversion planning**

```powershell
git add app/ui/workflows/audio_tools_workflow.py tests/test_audio_tools_workflow.py
git commit -m "refactor: isolate audio conversion planning"
```

---

### Task 4: Isolate Conversion Execution, Feedback, and Refresh

**Files:**
- Modify: `app/ui/workflows/audio_tools_workflow.py`
- Modify: `tests/test_audio_tools_workflow.py`

**Interfaces:**
- Consumes: the items/options built in Task 3, `operations.convert_files`, `ui.begin_progress`, and `library.library_targets`.
- Produces: complete conversion orchestration plus `_refresh_destination(destination: str) -> None` and `_present_result(result: AudioConversionResult) -> None`.

- [ ] **Step 1: Write the successful conversion test**

Append:

```python
def test_conversion_executes_with_progress_refreshes_matching_library_and_reports_success(
    tmp_path: Path,
) -> None:
    harness = Harness()
    destination = tmp_path / "out"
    selected_controller = controller(str(tmp_path / "source"), ["song.wav"])
    refresh_calls: list[str] = []
    matching = SimpleNamespace(
        carpeta=str(destination),
        archivos=[],
        refresh_library=lambda: refresh_calls.append("controller"),
    )
    other = controller(str(tmp_path / "other"), [])
    item = AudioConversionItem(tmp_path / "source" / "song.wav", destination / "song.mp3", "320k")
    harness.selections = [(selected_controller, "source-tree", ["song.wav"])]
    harness.options = {
        "destination": str(destination), "format": ".mp3", "bitrate": "320k",
        "overwrite": True, "preserve_structure": False,
    }
    harness.conversion_items = [item]
    harness.conversion_result = AudioConversionResult(1, [], [item])
    harness.library_pairs = [(matching, "matching-tree"), (other, "other-tree")]

    harness.workflow.convert_selected()

    assert ("begin_progress", {
        "title": "audio_conversion.title",
        "message": "audio_conversion.progress",
        "total": 1,
    }) in harness.events
    conversion = next(event for event in harness.events if event[0] == "convert")
    assert conversion[1] == ([item],)
    assert conversion[2] == {"overwrite": True, "progress_callback": harness.progress.update}
    assert harness.progress.closed
    assert refresh_calls == ["controller"]
    assert ("refresh_tree", matching, "matching-tree") in harness.events
    assert ("refresh_tree", other, "other-tree") not in harness.events
    assert harness.events[-2:] == [
        ("toast", "audio_conversion.done:{'count': 1}", "success"),
        ("info", "dialog.done", "audio_conversion.done:{'count': 1}"),
    ]
```

- [ ] **Step 2: Write error and partial-result tests**

Append:

```python
def test_missing_ffmpeg_closes_progress_and_shows_specific_error(tmp_path: Path) -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.wav"]), "tree", ["song.wav"])]
    harness.options = {"destination": str(tmp_path), "format": ".mp3"}

    def fail(*args, **kwargs):
        raise RuntimeError("ffmpeg is not available")

    object.__setattr__(harness.workflow.operations, "convert_files", fail)

    harness.workflow.convert_selected()

    assert harness.progress.closed
    assert harness.events[-1] == (
        "error", "dialog.error", "audio_conversion.ffmpeg_missing"
    )


def test_unexpected_conversion_error_closes_progress_and_includes_detail(tmp_path: Path) -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.wav"]), "tree", ["song.wav"])]
    harness.options = {"destination": str(tmp_path), "format": ".mp3"}

    def fail(*args, **kwargs):
        raise OSError("disk unavailable")

    object.__setattr__(harness.workflow.operations, "convert_files", fail)

    harness.workflow.convert_selected()

    assert harness.progress.closed
    assert harness.events[-1] == (
        "error", "dialog.error", "audio_conversion.failed:{'error': OSError('disk unavailable')}"
    )


def test_partial_conversion_limits_visible_errors_to_five(tmp_path: Path) -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.wav"]), "tree", ["song.wav"])]
    harness.options = {"destination": str(tmp_path / "out"), "format": ".mp3"}
    harness.conversion_result = AudioConversionResult(2, [f"error-{index}" for index in range(7)], [])

    harness.workflow.convert_selected()

    assert harness.events[-2][0:2] == ("toast", "toast.partial")
    warning = harness.events[-1]
    assert warning[0:2] == ("warning", "audio_conversion.title")
    assert "audio_conversion.done_with_errors:{'count': 2, 'errors': 7}" in warning[2]
    assert all(f"error-{index}" in warning[2] for index in range(5))
    assert "error-5" not in warning[2]
    assert "message.more_errors:{'count': 2}" in warning[2]
```

- [ ] **Step 3: Run the tests and confirm execution is incomplete**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: the four new tests fail because the Task 3 implementation stops after item planning.

- [ ] **Step 4: Implement execution and guaranteed progress cleanup**

Continue `convert_selected()` after item planning:

```python
        progress = self.ui.begin_progress(
            title=self.ui.translate("audio_conversion.title"),
            message=self.ui.translate("audio_conversion.progress"),
            total=len(items),
        )
        try:
            result = self.operations.convert_files(
                items,
                overwrite=bool(options.get("overwrite")),
                progress_callback=progress.update,
            )
        except RuntimeError:
            self.ui.show_error(
                self.ui.translate("dialog.error"),
                self.ui.translate("audio_conversion.ffmpeg_missing"),
            )
            return
        except Exception as exc:
            self.ui.show_error(
                self.ui.translate("dialog.error"),
                self.ui.translate("audio_conversion.failed", error=exc),
            )
            return
        finally:
            progress.close()

        self._refresh_destination(str(options["destination"]))
        self._present_result(result)
```

- [ ] **Step 5: Implement refresh and result presentation**

Implement destination refresh exactly as follows:

```python
    def _refresh_destination(self, destination: str) -> None:
        destination_path = Path(destination).resolve()
        for controller, tree in self.library.library_targets():
            if controller.carpeta and Path(controller.carpeta).resolve() == destination_path:
                controller.refresh_library()
                self.library.refresh_tree(controller, tree)
```

Implement `_present_result` with this exact observable behavior:

```python
    def _present_result(self, result: AudioConversionResult) -> None:
        if result.errors:
            self.ui.show_toast(self.ui.translate("toast.partial"), "warning")
            detail = self.ui.translate(
                "audio_conversion.done_with_errors",
                count=result.converted,
                errors=len(result.errors),
            )
            detail += "\n\n" + "\n".join(result.errors[:5])
            if len(result.errors) > 5:
                detail += self.ui.translate(
                    "message.more_errors",
                    count=len(result.errors) - 5,
                )
            self.ui.show_warning(self.ui.translate("audio_conversion.title"), detail)
            return

        message = self.ui.translate("audio_conversion.done", count=result.converted)
        self.ui.show_toast(message, "success")
        self.ui.show_info(self.ui.translate("dialog.done"), message)
```

- [ ] **Step 6: Run focused tests and complexity check**

Run: `python -m pytest tests/test_audio_tools_workflow.py -q`

Expected: `17 passed`.

Run: `python -m ruff check app/ui/workflows/audio_tools_workflow.py --select C901`

Expected: `All checks passed!`; keep `convert_selected` below Ruff's complexity threshold by delegating planning, refresh, and presentation to private methods.

- [ ] **Step 7: Commit conversion execution**

```powershell
git add app/ui/workflows/audio_tools_workflow.py tests/test_audio_tools_workflow.py
git commit -m "refactor: isolate audio conversion execution"
```

---

### Task 5: Compose the Workflow and Reduce the Mixin to Wrappers

**Files:**
- Modify: `app/ui/app.py:25-180`
- Modify: `app/ui/metadata_workflow.py:1-30,330-409,549-628`
- Modify: `tests/test_ui_library_refresh.py`

**Interfaces:**
- Consumes: all Task 1 ports and Task 2–4 workflow methods.
- Produces: `MokaMusicApp._setup_audio_tools_workflow() -> None`, `self.audio_tools_workflow`, and four compatibility wrappers with unchanged names/signatures.

- [ ] **Step 1: Add a failing wrapper-delegation test**

Add this fake next to `FakePlaylistWorkflow` in `tests/test_ui_library_refresh.py`:

```python
class FakeAudioToolsWorkflow:
    def __init__(self):
        self.calls = []

    def analyze_quality(self):
        self.calls.append("quality")

    def detect_duplicates(self):
        self.calls.append("duplicates")

    def validate_files(self):
        self.calls.append("validate")

    def convert_selected(self):
        self.calls.append("convert")
```

Add this test to `UiLibraryRefreshTests`:

```python
    def test_audio_tools_compatibility_wrappers_delegate_to_workflow(self):
        app = self.make_app()
        app.audio_tools_workflow = FakeAudioToolsWorkflow()

        app._analyze_audio_quality()
        app._detect_advanced_duplicates()
        app._validate_audio_files()
        app._convert_selected_audio()

        self.assertEqual(
            app.audio_tools_workflow.calls,
            ["quality", "duplicates", "validate", "convert"],
        )
```

- [ ] **Step 2: Run the wrapper test and verify it fails**

Run: `python -m pytest tests/test_ui_library_refresh.py::UiLibraryRefreshTests::test_audio_tools_compatibility_wrappers_delegate_to_workflow -q`

Expected: FAIL because the existing methods still execute their inline implementations.

- [ ] **Step 3: Replace the mixin implementations with four wrappers**

In `app/ui/metadata_workflow.py`, replace the extracted methods with:

```python
    def _analyze_audio_quality(self) -> None:
        self.audio_tools_workflow.analyze_quality()

    def _detect_advanced_duplicates(self) -> None:
        self.audio_tools_workflow.detect_duplicates()

    def _validate_audio_files(self) -> None:
        self.audio_tools_workflow.validate_files()

    def _convert_selected_audio(self) -> None:
        self.audio_tools_workflow.convert_selected()
```

Delete `_audio_tool_targets` and `_refresh_libraries_after_conversion`. Remove the now-unused audit/conversion service imports and audio modal imports. Keep `Path` because other mixin methods still use it.

- [ ] **Step 4: Compose concrete adapters in `MokaMusicApp`**

Add these imports to `app/ui/app.py` in their Ruff-sorted groups:

```python
from ..services.audio_audit_service import build_audio_quality_rows, detect_advanced_duplicates, validate_audio_files
from ..services.audio_conversion_service import build_conversion_items, convert_audio_files
from ..views.modals.audio_audit_modal import show_audio_audit_modal
from ..views.modals.audio_conversion_modal import request_audio_conversion_options
```

Add these names to the existing `.workflows` import block:

```python
    AudioToolsLibraryPort,
    AudioToolsOperations,
    AudioToolsUiPort,
    AudioToolsWorkflow,
```

Add `self._setup_audio_tools_workflow()` immediately after `self._setup_playlist_workflow()` and before `_bind_events()`.

Implement:

```python
    def _setup_audio_tools_workflow(self) -> None:
        ui = AudioToolsUiPort(
            translate=self.t,
            show_warning=messagebox.showwarning,
            show_info=messagebox.showinfo,
            show_error=messagebox.showerror,
            show_audit=lambda title, rows, columns: show_audio_audit_modal(
                self.root, self.t, title, rows, columns
            ),
            request_conversion_options=lambda count: request_audio_conversion_options(
                self.root, self.t, count
            ),
            begin_progress=self._begin_progress,
            show_toast=lambda message, kind: self._show_toast(message, kind=kind),
        )
        library = AudioToolsLibraryPort(
            selected_targets=self._selected_filenames_by_controller,
            active_target=self.playlist_workflow.active_target,
            library_targets=lambda: [
                (self.controller_principal, self.tree_principal),
                (self.controller_nueva, self.tree_nueva),
            ],
            refresh_tree=self._refresh_library_tree,
        )
        operations = AudioToolsOperations(
            build_quality_rows=build_audio_quality_rows,
            detect_duplicates=detect_advanced_duplicates,
            validate_files=validate_audio_files,
            build_conversion_items=build_conversion_items,
            convert_files=convert_audio_files,
        )
        self.audio_tools_workflow = AudioToolsWorkflow(
            ui=ui,
            library=library,
            operations=operations,
        )
```

- [ ] **Step 5: Run workflow, wrapper, and service regression tests**

Run:

```powershell
python -m pytest tests/test_audio_tools_workflow.py tests/test_ui_library_refresh.py tests/test_audio_audit_service.py tests/test_audio_conversion_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Verify imports and line-count reduction**

Run:

```powershell
python -m ruff check app/ui/app.py app/ui/metadata_workflow.py app/ui/workflows/audio_tools_workflow.py tests/test_audio_tools_workflow.py tests/test_ui_library_refresh.py
(Get-Content app/ui/metadata_workflow.py).Count
rg -n "audio_audit_service|audio_conversion_service|audio_audit_modal|audio_conversion_modal" app/ui/metadata_workflow.py
```

Expected: Ruff passes; the mixin is approximately 1,436–1,451 lines; `rg` returns no matches in the mixin.

- [ ] **Step 7: Commit application composition**

```powershell
git add app/ui/app.py app/ui/metadata_workflow.py tests/test_ui_library_refresh.py
git commit -m "refactor: compose audio tools workflow in app"
```

---

### Task 6: Full Regression and Refactor Acceptance

**Files:**
- Verify: `app/ui/workflows/audio_tools_workflow.py`
- Verify: `app/ui/app.py`
- Verify: `app/ui/metadata_workflow.py`
- Verify: `tests/test_audio_tools_workflow.py`
- Verify: `tests/test_ui_library_refresh.py`

**Interfaces:**
- Consumes: the complete composed workflow from Tasks 1–5.
- Produces: evidence that formatting, lint, compilation, focused behavior, and the entire suite remain green.

- [ ] **Step 1: Format only touched Python files**

Run:

```powershell
python -m ruff format app/ui/workflows/audio_tools_workflow.py app/ui/workflows/__init__.py app/ui/app.py app/ui/metadata_workflow.py tests/test_audio_tools_workflow.py tests/test_ui_library_refresh.py
```

Expected: Ruff formats successfully; inspect the diff afterward because formatting may adjust line wrapping.

- [ ] **Step 2: Run complete lint and format verification**

Run:

```powershell
python -m ruff check .
python -m ruff format --check .
```

Expected: both commands exit 0.

- [ ] **Step 3: Compile and run the startup smoke tests**

Run:

```powershell
python -m compileall -q app tests
python -m unittest tests.test_smoke -v
```

Expected: compilation exits 0 with no syntax errors and both startup smoke tests pass.

- [ ] **Step 4: Run focused regression tests verbosely**

Run:

```powershell
python -m pytest tests/test_audio_tools_workflow.py tests/test_audio_audit_service.py tests/test_audio_conversion_service.py tests/test_ui_library_refresh.py -v
```

Expected: every focused test passes, including all four wrapper calls and conversion error paths.

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -q`

Expected: all tests pass; baseline before this refactor was 261 passing tests, so the total must be at least 279 after adding 18 or more focused/wrapper tests.

- [ ] **Step 6: Inspect the final diff and acceptance metrics**

Run:

```powershell
git diff --stat HEAD~4..HEAD
git diff --check HEAD~4..HEAD
(Get-Content app/ui/metadata_workflow.py).Count
python -m ruff check app/ui/metadata_workflow.py app/ui/workflows/audio_tools_workflow.py --select C901
git status --short
```

Expected:

- `git diff --check` prints nothing.
- `_convert_selected_audio` is a one-line delegation body and no longer triggers C901.
- `metadata_workflow.py` is reduced by roughly 145–160 lines from its 1,596-line baseline.
- Only the plan document may remain untracked/ignored before its documentation commit; no unrelated user files are staged.

- [ ] **Step 7: Commit any formatter-only adjustments, if present**

If Step 1 changed tracked files after Task 5, run:

```powershell
git add app/ui/workflows/audio_tools_workflow.py app/ui/workflows/__init__.py app/ui/app.py app/ui/metadata_workflow.py tests/test_audio_tools_workflow.py tests/test_ui_library_refresh.py
git commit -m "style: format audio tools workflow extraction"
```

If `git status --short` is already clean apart from this plan, do not create an empty commit.

---

## Acceptance Checklist

- [ ] The three audit actions retain their exact titles, empty-result messages, columns, order, and widths.
- [ ] Conversion still requires an explicit selection and does not use the audit fallback target.
- [ ] Flat and preserve-structure item planning retain their existing service-call semantics.
- [ ] RuntimeError during conversion retains the dedicated FFmpeg message; other exceptions retain the generic translated detail.
- [ ] Progress always closes, including every exception path.
- [ ] Destination refresh touches only loaded libraries whose resolved folder equals the conversion destination.
- [ ] Partial feedback includes no more than five concrete errors and reports the remaining count.
- [ ] All four original mixin entry points still exist and delegate exactly once.
- [ ] No service algorithm, modal layout, translation resource, rename flow, organization flow, or playlist flow changed.
- [ ] Full lint, formatting, compilation, and test suite pass.
