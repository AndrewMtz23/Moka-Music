from __future__ import annotations

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
