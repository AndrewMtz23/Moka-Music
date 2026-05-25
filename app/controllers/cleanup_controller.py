import os
from dataclasses import dataclass
from typing import Any

from ..utils.text_cleanup import build_quick_cleanup_metadata


CleanupSelection = tuple[Any, object, list[str]]
CleanupPlanItem = tuple[Any, object, str, dict[str, str]]


@dataclass
class CleanupExecutionResult:
    success_count: int
    errors: list[str]
    changed_pairs: set[tuple[int, int]]
    affected_preview: bool
    changed_groups: list[CleanupSelection]


class CleanupController:
    def __init__(self, song_info=None) -> None:
        self.song_info = song_info

    def set_song_info(self, song_info) -> None:
        self.song_info = song_info

    def action_options(self) -> list[tuple[str, str]]:
        return [
            ("remove_feat", "quick_actions.remove_feat"),
            ("remove_parentheses", "quick_actions.remove_parentheses"),
            ("title_only", "quick_actions.title_only"),
            ("title_from_file", "quick_actions.title_from_file"),
            ("copy_artist", "quick_actions.copy_artist"),
        ]

    def normalize_presets(self, raw_presets) -> list[dict[str, object]]:
        presets: list[dict[str, object]] = []
        allowed_actions = {action for action, _label_key in self.action_options()}
        if not isinstance(raw_presets, list):
            return presets
        for preset in raw_presets:
            if not isinstance(preset, dict):
                continue
            name = str(preset.get("name", "") or "").strip()
            actions = [
                str(action)
                for action in preset.get("actions", [])
                if str(action) in allowed_actions
            ]
            if name and actions:
                presets.append({"name": name, "actions": actions})
        return presets

    def build_plan(
        self,
        selections: list[CleanupSelection],
        actions: list[str],
    ) -> list[CleanupPlanItem]:
        plan: list[CleanupPlanItem] = []
        for controller, tree, filenames in selections:
            for filename in filenames:
                metadata = self._metadata_for(controller, filename)
                updates: dict[str, str] = {}
                working_metadata = dict(metadata)
                for action in actions:
                    action_updates = build_quick_cleanup_metadata(action, filename, working_metadata)
                    if action_updates:
                        updates.update(action_updates)
                        working_metadata.update(action_updates)
                normalized_updates = {
                    key: value
                    for key, value in updates.items()
                    if str(metadata.get(key, "") or "").strip() != str(value or "").strip()
                }
                if normalized_updates:
                    plan.append((controller, tree, filename, normalized_updates))
        return plan

    def selected_count(self, selections: list[CleanupSelection]) -> int:
        return sum(len(filenames) for _controller, _tree, filenames in selections)

    def action_label(self, actions: list[str], preset_name: str, translator) -> str:
        if preset_name:
            return preset_name
        action_names = dict(self.action_options())
        return " + ".join(
            translator(action_names.get(action, "quick_actions.title"))
            for action in actions
        )

    def backup_metadata(self, actions: list[str], action_label: str, preset_name: str) -> dict[str, object]:
        if len(actions) == 1:
            return {"quick_action": actions[0]}
        return {
            "quick_preset": preset_name or action_label,
            "quick_actions": actions,
        }

    def preview_changes(self, plan: list[CleanupPlanItem], field_label) -> list[tuple[str, str, str, str]]:
        changes: list[tuple[str, str, str, str]] = []
        for controller, _tree, filename, updates in plan:
            cached = controller.get_track_info(filename)
            current_metadata = cached.metadata if cached else {}
            for field, new_value in updates.items():
                changes.append(
                    (
                        filename,
                        field_label(field),
                        str(current_metadata.get(field, "") or "").strip() or "-",
                        str(new_value or "").strip() or "-",
                    )
                )
        return changes

    def groups_from_plan(self, plan: list[CleanupPlanItem]) -> list[CleanupSelection]:
        grouped: dict[tuple[int, int], CleanupSelection] = {}
        for controller, tree, filename, _updates in plan:
            key = (id(controller), id(tree))
            if key not in grouped:
                grouped[key] = (controller, tree, [])
            grouped[key][2].append(filename)
        return list(grouped.values())

    def execute_plan(
        self,
        plan: list[CleanupPlanItem],
        *,
        preview_controller=None,
        preview_filename: str | None = None,
    ) -> CleanupExecutionResult:
        success_count = 0
        errors: list[str] = []
        changed_pairs: set[tuple[int, int]] = set()
        affected_preview = False

        for controller, tree, filename, updates in plan:
            result = controller.aplicar_cambios_a_archivo(filename, updates)
            if result.success:
                success_count += 1
                self._invalidate_song(controller, filename)
                changed_pairs.add((id(controller), id(tree)))
                if controller is preview_controller and filename == preview_filename:
                    affected_preview = True
            else:
                errors.extend(result.errors or [result.message])

        return CleanupExecutionResult(
            success_count=success_count,
            errors=errors,
            changed_pairs=changed_pairs,
            affected_preview=affected_preview,
            changed_groups=self.groups_from_plan(plan),
        )

    def _metadata_for(self, controller, filename: str) -> dict[str, str]:
        cached = controller.get_track_info(filename)
        if cached:
            return dict(cached.metadata)
        return controller.metadata_editor.obtener_metadatos(
            os.path.join(controller.carpeta, filename)
        ) or {}

    def _invalidate_song(self, controller, filename: str) -> None:
        if self.song_info and controller.carpeta:
            self.song_info.invalidate(os.path.join(controller.carpeta, filename))
