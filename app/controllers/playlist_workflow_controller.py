import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .rename_controller import RenameController
from ..models import ActionResult
from ..services.playlist_order_service import insert_at_position, renumber_order


@dataclass(frozen=True)
class PlaylistPlanItem:
    controller: object
    tree: object
    old_name: str
    new_name: str
    old_position: Optional[int]
    new_position: int
    track_number: int


@dataclass(frozen=True)
class PlaylistWorkflowPlan:
    controller: object
    tree: object
    original_order: list[str]
    final_order: list[str]
    items: list[PlaylistPlanItem]


@dataclass
class PlaylistApplyResult:
    track_numbers_updated: int
    renamed: int
    errors: list[str]
    changed_pairs: set[tuple[int, int]]
    preview_filename: Optional[str]
    backup_path: Optional[Path]

    @property
    def success(self) -> bool:
        return not self.errors


class PlaylistWorkflowController:
    def __init__(self, rename_controller: Optional[RenameController] = None) -> None:
        self.rename_controller = rename_controller or RenameController()

    def build_insert_plan(
        self,
        *,
        controller,
        tree,
        filenames: list[str],
        position: int,
    ) -> PlaylistWorkflowPlan:
        final_order = insert_at_position(controller.archivos, filenames, position)
        return self.build_plan_from_order(controller=controller, tree=tree, final_order=final_order)

    def build_plan_from_order(self, *, controller, tree, final_order: list[str]) -> PlaylistWorkflowPlan:
        original_order = list(controller.archivos)
        original_positions = {
            filename: index
            for index, filename in enumerate(original_order, start=1)
        }
        track_numbers = renumber_order(final_order, start=0)
        used_names: set[str] = set()
        items: list[PlaylistPlanItem] = []

        for new_position, filename in enumerate(final_order, start=1):
            track_number = track_numbers[filename]
            new_name = self.rename_controller.playlist_filename_from_metadata(
                controller,
                filename,
                used_names,
                track_number=track_number,
            )
            used_names.add(new_name)
            items.append(
                PlaylistPlanItem(
                    controller=controller,
                    tree=tree,
                    old_name=filename,
                    new_name=new_name,
                    old_position=original_positions.get(filename),
                    new_position=new_position,
                    track_number=track_number,
                )
            )

        return PlaylistWorkflowPlan(
            controller=controller,
            tree=tree,
            original_order=original_order,
            final_order=list(final_order),
            items=items,
        )

    def execute_plan(
        self,
        plan: PlaylistWorkflowPlan,
        *,
        song_info,
        preview_controller=None,
        preview_filename: Optional[str] = None,
        create_backup: bool = True,
    ) -> PlaylistApplyResult:
        errors: list[str] = []
        backup_path: Optional[Path] = None
        changed_pairs: set[tuple[int, int]] = set()

        if create_backup:
            try:
                backup_path = plan.controller.crear_respaldo_metadatos(
                    {
                        "track_number": "playlist_order",
                        "filename_format": "{track_number:03d} - {artist} - {title}",
                    },
                    plan.original_order,
                )
            except Exception as exc:
                errors.append(f"backup: {exc}")

        try:
            plan.controller.reorder_files(plan.final_order)
        except Exception as exc:
            errors.append(f"order: {exc}")

        updated = self._apply_track_numbers(plan, song_info=song_info, errors=errors)
        renamed, updated_preview = self._rename_items(
            plan,
            song_info=song_info,
            errors=errors,
            preview_controller=preview_controller,
            preview_filename=preview_filename,
        )

        final_names = [
            item.new_name if item.new_name else item.old_name
            for item in plan.items
        ]
        try:
            plan.controller.reorder_files(final_names)
        except Exception as exc:
            errors.append(f"final_order: {exc}")

        if updated or renamed:
            changed_pairs.add((id(plan.controller), id(plan.tree)))

        return PlaylistApplyResult(
            track_numbers_updated=updated,
            renamed=renamed,
            errors=errors,
            changed_pairs=changed_pairs,
            preview_filename=updated_preview,
            backup_path=backup_path,
        )

    def _apply_track_numbers(self, plan: PlaylistWorkflowPlan, *, song_info, errors: list[str]) -> int:
        updated = 0
        for item in plan.items:
            result = plan.controller.aplicar_cambios_a_archivo(
                item.old_name,
                {"track_number": str(item.track_number)},
            )
            if getattr(result, "success", False):
                updated += 1
                self._invalidate(song_info, plan.controller, item.old_name)
                continue
            message = getattr(result, "message", "") or "No se pudo actualizar track_number"
            errors.append(f"{item.old_name}: {message}")
        return updated

    def _rename_items(
        self,
        plan: PlaylistWorkflowPlan,
        *,
        song_info,
        errors: list[str],
        preview_controller,
        preview_filename: Optional[str],
    ) -> tuple[int, Optional[str]]:
        rename_items = [item for item in plan.items if item.old_name != item.new_name]
        if not rename_items:
            return 0, preview_filename

        temp_pairs: list[tuple[PlaylistPlanItem, str]] = []
        renamed = 0
        updated_preview = preview_filename

        for index, item in enumerate(rename_items, start=1):
            temp_name = self._temporary_name(item.old_name, index)
            if not self._rename_file(plan.controller, item.old_name, temp_name, errors):
                continue
            temp_pairs.append((item, temp_name))
            self._invalidate(song_info, plan.controller, item.old_name)
            self._invalidate(song_info, plan.controller, temp_name)

        for item, temp_name in temp_pairs:
            if not self._rename_file(plan.controller, temp_name, item.new_name, errors):
                continue
            renamed += 1
            self._invalidate(song_info, plan.controller, temp_name)
            self._invalidate(song_info, plan.controller, item.new_name)
            if plan.controller is preview_controller and preview_filename == item.old_name:
                updated_preview = item.new_name

        return renamed, updated_preview

    def _rename_file(self, controller, old_name: str, new_name: str, errors: list[str]) -> bool:
        source_path = os.path.join(controller.carpeta, old_name)
        destination_path = os.path.join(controller.carpeta, new_name)
        try:
            os.rename(source_path, destination_path)
            controller.rename_file(old_name, new_name)
            return True
        except Exception as exc:
            errors.append(f"{old_name}: {exc}")
            return False

    def _temporary_name(self, filename: str, index: int) -> str:
        stem, extension = os.path.splitext(filename)
        return f".mokamusic_tmp_{index}_{stem}{extension}"

    def _invalidate(self, song_info, controller, filename: str) -> None:
        if not song_info or not getattr(controller, "carpeta", ""):
            return
        song_info.invalidate(os.path.join(controller.carpeta, filename))

    def action_result(self, result: PlaylistApplyResult) -> ActionResult:
        if result.success:
            return ActionResult.ok(
                "Playlist actualizada.",
                data=result,
            )
        return ActionResult.fail(
            "No se pudo actualizar toda la playlist.",
            errors=result.errors,
            data=result,
        )
