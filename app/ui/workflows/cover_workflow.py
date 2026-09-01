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
            (controller, tree, filenames) for controller, tree, filenames, _cover_path in cover_plan.groups
        ]
        if not self.library.create_backups(backup_groups, {"__cover__": "auto"}):
            return
        self._apply_auto_cover_plan(cover_plan.groups, backup_groups, cover_plan.planned_count)

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
