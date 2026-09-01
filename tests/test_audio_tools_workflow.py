from __future__ import annotations

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
                show_audit=lambda title, rows, columns: self.events.append(("audit", title, rows, columns)),
                request_conversion_options=lambda count: self._request_options(count),
                begin_progress=lambda **kwargs: self._begin_progress(**kwargs),
                show_toast=lambda message, kind: self.events.append(("toast", message, kind)),
            ),
            library=AudioToolsLibraryPort(
                selected_targets=lambda: self.selections,
                active_target=lambda: self.active,
                library_targets=lambda: self.library_pairs,
                refresh_tree=lambda controller, tree: self.events.append(("refresh_tree", controller, tree)),
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

    assert harness.workflow.targets() == [(active_controller, "active-tree", ["one.mp3", "two.flac"])]
    assert harness.workflow.targets()[0][2] is not active_controller.archivos
