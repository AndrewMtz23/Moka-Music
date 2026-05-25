import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SingleMetadataApplyResult:
    result: object
    changed_pairs: set[tuple[int, int]]

    @property
    def success(self) -> bool:
        return bool(getattr(self.result, "success", False))


@dataclass
class BatchMetadataApplyResult:
    success_count: int
    errors: list[str]
    affected_preview: bool
    changed_pairs: set[tuple[int, int]]


@dataclass(frozen=True)
class PreviewMetadataTarget:
    controller: object
    tree: object
    filename: str
    current_song: dict[str, object]


class MetadataApplyController:
    def metadata_from_vars(self, meta_vars: dict[str, object]) -> dict[str, str]:
        return {
            key: value.get().strip()
            for key, value in meta_vars.items()
            if value.get().strip()
        }

    def first_selected_target(
        self,
        pairs: list[tuple[object, object]],
        filename_from_item,
    ) -> tuple[object, object, str] | None:
        for tree, controller in pairs:
            selection = tree.selection()
            if not selection or not controller.carpeta:
                continue
            filename = filename_from_item(tree.item(selection[0]))
            if filename:
                return controller, tree, filename
        return None

    def all_files_target(
        self,
        *,
        primary_controller,
        primary_tree,
        incoming_controller,
        incoming_tree,
    ) -> tuple[object, object, list[str]] | None:
        controller = primary_controller if primary_controller.archivos else incoming_controller
        tree = primary_tree if controller is primary_controller else incoming_tree
        if not controller.archivos:
            return None
        return controller, tree, controller.archivos.copy()

    def preview_target(
        self,
        *,
        controller,
        filename: Optional[str],
        current_song: dict[str, object] | None,
        tree_for_controller,
    ) -> PreviewMetadataTarget | None:
        if controller is None or not filename or not current_song:
            return None
        return PreviewMetadataTarget(
            controller=controller,
            tree=tree_for_controller(controller),
            filename=filename,
            current_song=current_song,
        )

    def selected_count(self, groups: list[tuple[object, object, list[str]]]) -> int:
        return sum(len(filenames) for _controller, _tree, filenames in groups)

    def apply_single(
        self,
        *,
        controller,
        tree,
        filename: str,
        metadata: dict[str, str],
        cover_path: Optional[str],
        song_info,
    ) -> SingleMetadataApplyResult:
        result = controller.aplicar_cambios_a_archivo(filename, metadata, cover_path)
        changed_pairs: set[tuple[int, int]] = set()
        if getattr(result, "success", False):
            if controller.carpeta:
                song_info.invalidate(os.path.join(controller.carpeta, filename))
            if tree is not None:
                changed_pairs.add((id(controller), id(tree)))
        return SingleMetadataApplyResult(result=result, changed_pairs=changed_pairs)

    def apply_groups(
        self,
        *,
        groups: list[tuple[object, object, list[str]]],
        metadata: dict[str, str],
        song_info,
        preview_controller,
        preview_filename: Optional[str],
    ) -> BatchMetadataApplyResult:
        total_success = 0
        all_errors: list[str] = []
        affected_preview = False
        changed_pairs: set[tuple[int, int]] = set()

        for controller, tree, filenames in groups:
            success_count, errors = controller.aplicar_cambios_a_archivos(
                filenames,
                metadata,
                controller.portada_path,
            )
            total_success += success_count
            all_errors.extend(errors)
            if success_count:
                changed_pairs.add((id(controller), id(tree)))
            for filename in filenames:
                if controller.carpeta:
                    song_info.invalidate(os.path.join(controller.carpeta, filename))
                if controller is preview_controller and filename == preview_filename:
                    affected_preview = True

        return BatchMetadataApplyResult(
            success_count=total_success,
            errors=all_errors,
            affected_preview=affected_preview,
            changed_pairs=changed_pairs,
        )

    def apply_all(self, *, controller, metadata: dict[str, str], song_info) -> tuple[int, list[str]]:
        success_count, errors = controller.aplicar_cambios(metadata)
        if success_count and controller.carpeta:
            for filename in controller.archivos:
                song_info.invalidate(os.path.join(controller.carpeta, filename))
        return success_count, errors
