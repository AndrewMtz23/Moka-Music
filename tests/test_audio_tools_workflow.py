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


def test_analyze_quality_warns_when_no_target_exists() -> None:
    harness = Harness()

    harness.workflow.analyze_quality()

    assert harness.events == [("warning", "dialog.no_files", "message.no_loaded_files")]


def test_analyze_quality_builds_rows_and_preserves_column_schema() -> None:
    harness = Harness()
    group = (controller("music", ["song.mp3"]), "tree", ["song.mp3"])
    harness.selections = [group]
    harness.quality_rows = [{"filename": "song.mp3", "bitrate_kbps": 128}]

    harness.workflow.analyze_quality()

    event = harness.events[-1]
    assert event[:3] == ("audit", "audio_tools.quality_title", harness.quality_rows)
    assert [column[0] for column in event[3]] == [
        "filename",
        "title",
        "artist",
        "duration",
        "bitrate_kbps",
        "sample_rate",
        "channels",
        "format",
        "low_bitrate",
        "possibly_corrupt",
    ]
    assert [column[2] for column in event[3]] == [260, 180, 160, 80, 90, 90, 80, 80, 90, 90]


def test_duplicate_audit_reports_empty_result_without_opening_modal() -> None:
    harness = Harness()
    harness.selections = [(controller("music", ["song.mp3"]), "tree", ["song.mp3"])]

    harness.workflow.detect_duplicates()

    assert harness.events == [("info", "audio_tools.duplicates_title", "audio_tools.no_duplicates")]


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

    assert harness.events == [("info", "audio_tools.validation_title", "audio_tools.no_validation_issues")]


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


def test_conversion_requires_explicit_selection() -> None:
    harness = Harness()
    harness.active = (controller("music", ["fallback.mp3"]), "tree")

    harness.workflow.convert_selected()

    assert harness.events == [("warning", "dialog.selection", "audio_conversion.no_selection")]


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
        "error",
        "dialog.error",
        "audio_conversion.failed:{'error': ValueError('bad format')}",
    )
    assert not any(event[0] == "begin_progress" for event in harness.events)
