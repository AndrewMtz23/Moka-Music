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

    def insert_selected(self) -> None:
        selections = self.library.selected_targets()
        if not selections:
            self.ui.show_warning(
                self.ui.translate("dialog.selection"),
                self.ui.translate("message.no_song_selected"),
            )
            return
        if len(selections) > 1:
            self.ui.show_warning(
                self.ui.translate("dialog.selection"),
                self.ui.translate("playlist_insert.one_library"),
            )
            return

        controller, tree, filenames = selections[0]
        if not controller.archivos:
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

        position = self.ui.request_position(
            title=self.ui.translate("playlist_insert.title"),
            prompt=self.ui.translate("playlist_insert.prompt", count=len(filenames), total=len(controller.archivos)),
            total=len(controller.archivos),
            initial=0,
            min_position=0,
            max_position=max(0, len(controller.archivos) - 1),
            confirm_text=self.ui.translate("playlist_insert.confirm_position"),
        )
        if position is None:
            return

        plan = self.controller.build_insert_plan(
            controller=controller,
            tree=tree,
            filenames=filenames,
            position=position + 1,
        )
        confirmed_plan = self._confirm_plan(plan)
        if confirmed_plan is not None:
            self._execute_plan(confirmed_plan, "playlist_insert.done")

    def prepare_active(self) -> None:
        target = self.active_target()
        if target is None:
            self.ui.show_warning(
                self.ui.translate("dialog.no_files"),
                self.ui.translate("message.no_loaded_files"),
            )
            return

        controller, tree = target
        if not self.library.can_reorder(controller, tree):
            self.ui.show_warning(
                self.ui.translate("dialog.selection"),
                self.ui.translate("message.reorder_needs_full_view"),
            )
            return
        plan = self.controller.build_plan_from_order(
            controller=controller,
            tree=tree,
            final_order=controller.archivos.copy(),
        )
        confirmed_plan = self._confirm_plan(plan)
        if confirmed_plan is not None:
            self._execute_plan(confirmed_plan, "playlist_prepare.done")

    def _confirm_plan(self, plan: PlaylistWorkflowPlan) -> PlaylistWorkflowPlan | None:
        if not plan.items:
            self.ui.show_info(
                self.ui.translate("dialog.done"),
                self.ui.translate("change_preview.no_changes"),
            )
            return None
        return self.ui.request_plan_preview(
            plan,
            lambda final_order: self.controller.build_plan_from_order(
                controller=plan.controller,
                tree=plan.tree,
                final_order=final_order,
            ),
        )

    def _execute_plan(self, plan: PlaylistWorkflowPlan, done_key: str) -> None:
        progress = self.ui.begin_progress(
            title=self.ui.translate("progress.playlist_title"),
            message=self.ui.translate("progress.playlist_body"),
            total=len(plan.items) * 2,
        )
        preview_controller, preview_filename = self.library.preview_state()
        try:
            result = self.controller.execute_plan(
                plan,
                song_info=self.song_info,
                preview_controller=preview_controller,
                preview_filename=preview_filename,
                progress_callback=progress.update,
            )
        finally:
            progress.close()

        self.library.set_preview_filename(result.preview_filename)
        groups = [(plan.controller, plan.tree, plan.final_order)]
        self.library.refresh_changed(groups, result.changed_pairs)
        plan.controller.set_sort_mode(SortMode.TRACK_NUMBER)
        self.library.sync_sort(plan.controller, SortMode.TRACK_NUMBER)

        if preview_controller is plan.controller and result.preview_filename:
            self.library.select_filename(plan.tree, result.preview_filename)
            self.library.reload_preview(plan.controller, result.preview_filename)

        if result.success:
            if result.backup_path:
                self.library.record_undo_paths("undo.playlist", [result.backup_path])
            message = self.ui.translate(
                done_key,
                tracks=result.track_numbers_updated,
                renamed=result.renamed,
            )
            if result.backup_path:
                message += f"\n{self.ui.translate('message.backup_created', path=result.backup_path)}"
            self.ui.show_toast(self.ui.translate("toast.done"), "success")
            self.ui.show_info(self.ui.translate("dialog.done"), message)
            return

        self.ui.show_error(
            self.ui.translate("dialog.error"),
            "\n".join(result.errors) if result.errors else self.ui.translate("message.could_not_apply_metadata"),
        )
