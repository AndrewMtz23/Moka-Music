import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..services.cover_service import find_folder_cover, replace_folder_cover


@dataclass
class CoverPlan:
    groups: list[tuple[object, object, list[str], str]]
    missing: list[str] = field(default_factory=list)

    @property
    def planned_count(self) -> int:
        return sum(len(filenames) for _controller, _tree, filenames, _cover_path in self.groups)


@dataclass
class CoverApplyResult:
    success_count: int
    errors: list[str]
    affected_preview: bool
    changed_pairs: set[tuple[int, int]]
    preview_cover_path: Optional[str] = None


class CoverController:
    def cover_targets(
        self,
        *,
        selections: list[tuple[object, object, list[str]]],
        preview_controller,
        preview_filename: Optional[str],
        tree_for_controller: Callable[[object], object],
    ) -> list[tuple[object, object, list[str]]]:
        if selections:
            return selections
        if preview_controller is None or not preview_filename:
            return []
        tree = tree_for_controller(preview_controller)
        if tree is None:
            return []
        return [(preview_controller, tree, [preview_filename])]

    def build_auto_cover_plan(self, targets: list[tuple[object, object, list[str]]]) -> CoverPlan:
        groups: list[tuple[object, object, list[str], str]] = []
        missing: list[str] = []
        for controller, tree, filenames in targets:
            grouped: dict[str, list[str]] = {}
            for filename in filenames:
                cover_path = find_folder_cover(os.path.join(controller.carpeta, filename))
                if cover_path:
                    grouped.setdefault(cover_path, []).append(filename)
                else:
                    missing.append(filename)
            for cover_path, grouped_filenames in grouped.items():
                groups.append((controller, tree, grouped_filenames, cover_path))
        return CoverPlan(groups=groups, missing=missing)

    def apply_manual_cover(
        self,
        *,
        targets: list[tuple[object, object, list[str]]],
        cover_path: str,
        song_info,
        preview_controller,
        preview_filename: Optional[str],
    ) -> CoverApplyResult:
        groups: list[tuple[object, object, list[str], str]] = []
        seen_controllers: set[int] = set()
        for controller, tree, _filenames in targets:
            if id(controller) in seen_controllers:
                continue
            seen_controllers.add(id(controller))
            folder_cover_path = replace_folder_cover(cover_path, controller.carpeta)
            if not folder_cover_path:
                continue
            groups.append((controller, tree, controller.archivos.copy(), folder_cover_path))
        return self.apply_cover_plan(
            groups,
            song_info=song_info,
            preview_controller=preview_controller,
            preview_filename=preview_filename,
        )

    def apply_cover_plan(
        self,
        groups: list[tuple[object, object, list[str], str]],
        *,
        song_info,
        preview_controller,
        preview_filename: Optional[str],
    ) -> CoverApplyResult:
        total_success = 0
        all_errors: list[str] = []
        affected_preview = False
        preview_cover_path = None
        changed_pairs: set[tuple[int, int]] = set()

        for controller, tree, filenames, cover_path in groups:
            success_count, errors = controller.aplicar_cambios_a_archivos(filenames, {}, cover_path)
            total_success += success_count
            all_errors.extend(errors)
            if success_count:
                changed_pairs.add((id(controller), id(tree)))
            for filename in filenames:
                if controller.carpeta:
                    song_info.invalidate(os.path.join(controller.carpeta, filename))
                if controller is preview_controller and filename == preview_filename:
                    affected_preview = True
                    preview_cover_path = cover_path

        return CoverApplyResult(
            success_count=total_success,
            errors=all_errors,
            affected_preview=affected_preview,
            changed_pairs=changed_pairs,
            preview_cover_path=preview_cover_path,
        )
