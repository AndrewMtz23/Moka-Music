from __future__ import annotations

import re
from dataclasses import dataclass

from ..utils.text_cleanup import compact_spaces, clean_text_edges


METADATA_TOOL_FIELDS = ("title", "artist", "album", "album_artist", "genre", "year", "track_number", "comment")


@dataclass(frozen=True)
class MetadataToolPlanItem:
    controller: object
    tree: object
    filename: str
    updates: dict[str, str]


def normalize_metadata_values(metadata: dict[str, str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for field in METADATA_TOOL_FIELDS:
        original = str(metadata.get(field, "") or "")
        if not original:
            continue
        normalized = normalize_metadata_text(original, title_case=field in {"title", "artist", "album", "album_artist", "genre"})
        if normalized != original:
            updates[field] = normalized
    return updates


def normalize_metadata_text(value: str, *, title_case: bool = False) -> str:
    text = str(value or "")
    text = text.replace("_", " ")
    text = re.sub(r"\s*[-–—]\s*", " - ", text)
    text = re.sub(r"\s*/\s*", " / ", text)
    text = compact_spaces(text)
    text = clean_text_edges(text)
    if title_case:
        text = smart_title(text)
    return text


def smart_title(value: str) -> str:
    keep_lower = {"a", "al", "and", "con", "da", "de", "del", "el", "en", "for", "la", "las", "los", "of", "the", "to", "y"}
    words = str(value or "").split(" ")
    titled: list[str] = []
    for index, word in enumerate(words):
        if not word:
            continue
        if word.isupper() and len(word) <= 4:
            titled.append(word)
            continue
        lower = word.lower()
        if index > 0 and lower in keep_lower:
            titled.append(lower)
        else:
            titled.append(lower[:1].upper() + lower[1:])
    return " ".join(titled)


def build_normalize_plan(selections: list[tuple[object, object, list[str]]]) -> list[MetadataToolPlanItem]:
    plan: list[MetadataToolPlanItem] = []
    for controller, tree, filenames in selections:
        for filename in filenames:
            cached = controller.get_track_info(filename)
            metadata = dict(cached.metadata) if cached else {}
            updates = normalize_metadata_values(metadata)
            if updates:
                plan.append(MetadataToolPlanItem(controller, tree, filename, updates))
    return plan


def build_search_replace_plan(
    selections: list[tuple[object, object, list[str]]],
    *,
    field: str,
    search_text: str,
    replacement: str,
    case_sensitive: bool = False,
) -> list[MetadataToolPlanItem]:
    if field not in METADATA_TOOL_FIELDS or not search_text:
        return []
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(search_text), flags)
    plan: list[MetadataToolPlanItem] = []
    for controller, tree, filenames in selections:
        for filename in filenames:
            cached = controller.get_track_info(filename)
            metadata = dict(cached.metadata) if cached else {}
            current = str(metadata.get(field, "") or "")
            updated = pattern.sub(replacement, current)
            if updated != current:
                plan.append(MetadataToolPlanItem(controller, tree, filename, {field: updated}))
    return plan


def tool_plan_groups(plan: list[MetadataToolPlanItem]) -> list[tuple[object, object, list[str]]]:
    grouped: dict[tuple[int, int], tuple[object, object, list[str]]] = {}
    for item in plan:
        key = (id(item.controller), id(item.tree))
        if key not in grouped:
            grouped[key] = (item.controller, item.tree, [])
        grouped[key][2].append(item.filename)
    return list(grouped.values())


def tool_plan_preview(plan: list[MetadataToolPlanItem], field_label) -> list[tuple[str, str, str, str]]:
    changes: list[tuple[str, str, str, str]] = []
    for item in plan:
        cached = item.controller.get_track_info(item.filename)
        metadata = dict(cached.metadata) if cached else {}
        for field, new_value in item.updates.items():
            changes.append(
                (
                    item.filename,
                    field_label(field),
                    str(metadata.get(field, "") or "").strip() or "-",
                    str(new_value or "").strip() or "-",
                )
            )
    return changes
