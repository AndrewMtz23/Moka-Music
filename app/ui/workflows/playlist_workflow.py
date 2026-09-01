from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from ...controllers.playlist_workflow_controller import PlaylistWorkflowController, PlaylistWorkflowPlan
from ...models import ActionResult, SortMode

PlaylistTarget = tuple[object, object]
PlaylistSelection = tuple[object, object, list[str]]


class ProgressPort(Protocol):
    def update(self, completed: int, total: int | None = None, detail: str = "") -> bool: ...

    def close(self) -> None: ...


class BeginProgress(Protocol):
    def __call__(self, *, title: str, message: str, total: int) -> ProgressPort: ...


@dataclass(frozen=True)
class PlaylistUiPort:
    translate: Callable[..., str]
    show_warning: Callable[[str, str], object]
    ask_yes_no: Callable[[str, str], bool]
    show_info: Callable[[str, str], object]
    show_error: Callable[[str, str], object]
    request_position: Callable[..., Optional[int]]
    request_plan_preview: Callable[
        [PlaylistWorkflowPlan, Callable[[list[str]], PlaylistWorkflowPlan]], Optional[PlaylistWorkflowPlan]
    ]
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
    def __init__(
        self,
        *,
        controller: PlaylistWorkflowController,
        song_info: object,
        ui: PlaylistUiPort,
        library: PlaylistLibraryPort,
    ) -> None:
        self.controller = controller
        self.song_info = song_info
        self.ui = ui
        self.library = library

    def active_target(self) -> PlaylistTarget | None:
        selections = self.library.selected_targets()
        if len(selections) > 1:
            self.ui.show_warning(
                self.ui.translate("dialog.selection"),
                self.ui.translate("playlist_insert.one_library"),
            )
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

    def number_tracks(self) -> None:
        controller, tree = self._numbering_target()
        if tree is None or not controller.archivos:
            self.ui.show_warning(
                self.ui.translate("dialog.no_files"),
                self.ui.translate("message.no_loaded_files"),
            )
            return
        if not self.library.can_reorder(controller, tree):
            self.ui.show_warning(
                self.ui.translate("dialog.selection"),
                self.ui.translate("message.reorder_needs_full_view"),
            )
            return
        if not self.ui.ask_yes_no(
            self.ui.translate("dialog.confirm"),
            self.ui.translate("quick_actions.confirm_number_tracks", count=len(controller.archivos)),
        ):
            return
        if not self.library.create_backups(
            [(controller, tree, controller.archivos.copy())],
            {"track_number": "order"},
        ):
            return

        result = controller.apply_track_numbers_from_order()
        if result.success:
            for filename in controller.archivos:
                self.song_info.invalidate(os.path.join(controller.carpeta, filename))
            self.library.refresh_tree(controller, tree)
            preview_controller, preview_filename = self.library.preview_state()
            if preview_controller is controller and preview_filename:
                self.library.reload_preview(controller, preview_filename)
        self.ui.present_action_result(result)

    def _numbering_target(self) -> PlaylistTarget:
        preview_controller, _preview_filename = self.library.preview_state()
        if preview_controller is not None:
            return preview_controller, self.library.tree_for_controller(preview_controller)
        primary = self.library.primary_target()
        if primary[0].archivos:
            return primary
        return self.library.incoming_target()
