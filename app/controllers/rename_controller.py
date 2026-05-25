import os
from dataclasses import dataclass
from typing import Callable, Optional

from ..services.file_service import sanitize_filename
from ..services.playlist_naming_service import playlist_filename_from_metadata
from ..utils.ui_formatting import filename_from_metadata


@dataclass(frozen=True)
class RenamePlanItem:
    controller: object
    tree: object
    old_name: str
    new_name: str


@dataclass
class RenameApplyResult:
    renamed: int
    errors: list[str]
    changed_pairs: set[tuple[int, int]]
    preview_filename: Optional[str]


class RenameController:
    def build_plan(
        self,
        selections: list[tuple[object, object, list[str]]],
        *,
        filename_builder: Callable[[object, str, set[str]], str] | None = None,
    ) -> list[RenamePlanItem]:
        plan: list[RenamePlanItem] = []
        for controller, tree, filenames in selections:
            used_names = set(controller.archivos)
            for filename in filenames:
                new_name = (
                    filename_builder(controller, filename, used_names)
                    if filename_builder
                    else self.filename_from_metadata(controller, filename, used_names)
                )
                if new_name and new_name != filename:
                    plan.append(RenamePlanItem(controller, tree, filename, new_name))
                    used_names.discard(filename)
                    used_names.add(new_name)
        return plan

    def filename_from_metadata(self, controller, filename: str, used_names: set[str]) -> str:
        cached = controller.get_track_info(filename)
        metadata = cached.metadata if cached else {}
        return filename_from_metadata(
            filename,
            metadata,
            used_names,
            sanitize_filename,
        )

    def playlist_filename_from_metadata(
        self,
        controller,
        filename: str,
        used_names: set[str],
        *,
        track_number: int | None = None,
    ) -> str:
        cached = controller.get_track_info(filename)
        metadata = cached.metadata if cached else {}
        return playlist_filename_from_metadata(
            filename,
            metadata,
            used_names,
            track_number=track_number,
        )

    def execute_plan(
        self,
        plan: list[RenamePlanItem],
        *,
        song_info,
        preview_controller,
        preview_filename: Optional[str],
    ) -> RenameApplyResult:
        renamed = 0
        errors: list[str] = []
        changed_pairs: set[tuple[int, int]] = set()
        updated_preview_filename = preview_filename

        for item in plan:
            source_path = os.path.join(item.controller.carpeta, item.old_name)
            destination_path = os.path.join(item.controller.carpeta, item.new_name)
            try:
                os.rename(source_path, destination_path)
                item.controller.rename_file(item.old_name, item.new_name)
                song_info.invalidate(source_path)
                song_info.invalidate(destination_path)
                if item.controller is preview_controller and preview_filename == item.old_name:
                    updated_preview_filename = item.new_name
                changed_pairs.add((id(item.controller), id(item.tree)))
                renamed += 1
            except Exception as exc:
                errors.append(f"{item.old_name}: {exc}")

        return RenameApplyResult(
            renamed=renamed,
            errors=errors,
            changed_pairs=changed_pairs,
            preview_filename=updated_preview_filename,
        )
