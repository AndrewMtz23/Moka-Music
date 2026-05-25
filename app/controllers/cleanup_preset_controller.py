from dataclasses import dataclass
from typing import Optional


@dataclass
class PresetUpsertResult:
    presets: list[dict[str, object]]
    replaced: bool


class CleanupPresetController:
    def refresh_menu(self, presets: list[dict[str, object]], menu, variable) -> None:
        names = [str(preset["name"]) for preset in presets]
        menu.configure(values=names)
        current = variable.get()
        if names and current not in names:
            variable.set(names[0])
        elif not names:
            variable.set("")

    def selected_preset(
        self,
        presets: list[dict[str, object]],
        selected_name: str,
    ) -> Optional[dict[str, object]]:
        for preset in presets:
            if str(preset.get("name", "")) == selected_name.strip():
                return preset
        return None

    def preset_index_by_name(self, presets: list[dict[str, object]], name: str) -> Optional[int]:
        normalized_name = name.strip().lower()
        for index, preset in enumerate(presets):
            if str(preset.get("name", "")).strip().lower() == normalized_name:
                return index
        return None

    def upsert_preset(
        self,
        presets: list[dict[str, object]],
        *,
        name: str,
        actions: list[str],
        replace_existing: bool,
    ) -> PresetUpsertResult:
        preset = {"name": name, "actions": actions}
        existing = self.preset_index_by_name(presets, name)
        updated = list(presets)
        if existing is None:
            updated.append(preset)
            return PresetUpsertResult(updated, replaced=False)
        if replace_existing:
            updated[existing] = preset
            return PresetUpsertResult(updated, replaced=True)
        return PresetUpsertResult(updated, replaced=False)

    def delete_preset(self, presets: list[dict[str, object]], name: str) -> list[dict[str, object]]:
        return [candidate for candidate in presets if str(candidate.get("name", "")) != name]
