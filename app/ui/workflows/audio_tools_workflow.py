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
            self._build_conversion_items(source_groups, sources, options)
        except Exception as exc:
            self.ui.show_error(
                self.ui.translate("dialog.error"),
                self.ui.translate("audio_conversion.failed", error=exc),
            )
            return

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

    def _require_targets(self) -> list[AudioTarget]:
        groups = self.targets()
        if not groups:
            self.ui.show_warning(
                self.ui.translate("dialog.no_files"),
                self.ui.translate("message.no_loaded_files"),
            )
        return groups
