import os
from typing import Callable


VISUAL_TREE_TAGS = {"odd_row", "even_row", "selected", "placeholder"}

METADATA_LABEL_KEYS = {
    "artist": "metadata.artist",
    "album_artist": "metadata.album_artist",
    "album": "metadata.album",
    "genre": "metadata.genre",
    "year": "metadata.year",
    "title": "preview.title_field",
    "track_number": "preview.track",
    "comment": "metadata.comment",
}

PREVIEW_LABEL_KEYS = {
    **METADATA_LABEL_KEYS,
    "artist": "preview.artist",
    "album_artist": "preview.album_artist",
    "album": "preview.album",
    "genre": "preview.genre",
    "year": "preview.year",
    "comment": "preview.comment",
}

QUICK_ACTION_LABEL_KEYS = {
    "remove_feat": "quick_actions.remove_feat",
    "remove_parentheses": "quick_actions.remove_parentheses",
    "title_only": "quick_actions.title_only",
    "title_from_file": "quick_actions.title_from_file",
    "copy_artist": "quick_actions.copy_artist",
}


def metadata_label_key(key: str) -> str:
    return METADATA_LABEL_KEYS.get(key, key)


def filename_from_tree_item(item: dict[str, object]) -> str:
    for tag in item.get("tags") or ():
        tag_text = str(tag)
        if tag_text not in VISUAL_TREE_TAGS:
            return tag_text
    return ""


def filename_from_metadata(
    filename: str,
    metadata: dict[str, str],
    used_names: set[str],
    sanitize_filename: Callable[[str], str],
) -> str:
    stem, extension = os.path.splitext(filename)
    title = str(metadata.get("title", "") or stem).strip()
    artist = str(metadata.get("artist", "") or "").strip()
    track = str(metadata.get("track_number", "") or "").strip()

    parts: list[str] = []
    try:
        track_number = int(track)
    except (TypeError, ValueError):
        track_number = 0
    if track_number > 0:
        parts.append(f"{track_number:02d}.")
    if artist:
        parts.append(f"{artist} -")
    parts.append(title)

    base_name = sanitize_filename(" ".join(parts).strip())
    candidate = f"{base_name}{extension}"
    suffix = 2
    while candidate in used_names and candidate != filename:
        candidate = f"{base_name} ({suffix}){extension}"
        suffix += 1
    return candidate


def backup_action_label(metadata, t: Callable[..., str]) -> str:
    if not isinstance(metadata, dict) or not metadata:
        return t("backup.action_unknown")
    if "quick_action" in metadata:
        return t(QUICK_ACTION_LABEL_KEYS.get(str(metadata.get("quick_action")), "quick_actions.title"))
    if "quick_preset" in metadata:
        return t("backup.action_preset", name=str(metadata.get("quick_preset", "")))
    if metadata.get("metadata_clear") == "folder":
        return t("metadata_clear.title")
    if metadata.get("track_number") == "order":
        return t("quick_actions.number_tracks")
    if "__cover__" in metadata:
        return t("backup.action_cover")
    return ", ".join(t(metadata_label_key(key)).rstrip(":") for key in metadata.keys())


def format_metadata_summary(metadata: dict[str, str], t: Callable[..., str]) -> str:
    return "\n".join(
        f"- {t(PREVIEW_LABEL_KEYS.get(key, key))}: {value}"
        for key, value in metadata.items()
    )


def format_action_error(result, t: Callable[..., str], limit: int = 8) -> str:
    errors = list(getattr(result, "errors", None) or [])
    message = str(getattr(result, "message", "") or "")
    if not errors:
        return message
    visible_errors = errors[:limit]
    detail = "\n".join(visible_errors)
    hidden_count = len(errors) - len(visible_errors)
    if hidden_count > 0:
        detail += t("message.more_errors", count=hidden_count)
    return f"{message}\n\n{detail}" if message else detail
