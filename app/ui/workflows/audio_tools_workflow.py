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
