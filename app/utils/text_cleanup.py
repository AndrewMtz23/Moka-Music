import re
from pathlib import Path


def compact_spaces(value: str) -> str:
    return re.sub(r"\s{2,}", " ", str(value or "")).strip()


def clean_text_edges(value: str) -> str:
    return compact_spaces(value).strip(" -_")


def remove_feature_text(value: str) -> str:
    value = re.sub(
        r"\s*[\(\[]?\s*(?:feat\.?|ft\.?|featuring)\s+[^)\]]+[\)\]]?\s*",
        " ",
        str(value or ""),
        flags=re.I,
    )
    value = re.split(r"\s*(?:,|&|\+| x | feat\.?| ft\.?| featuring )\s*", value, maxsplit=1, flags=re.I)[0]
    return clean_text_edges(value)


def remove_parenthetical_text(value: str) -> str:
    value = re.sub(r"\s*[\(\[][^\)\]]+[\)\]]\s*", " ", str(value or ""))
    return clean_text_edges(value)


def title_from_filename(filename: str) -> str:
    return Path(filename).stem.strip()


def build_quick_cleanup_metadata(action: str, filename: str, metadata: dict[str, str]) -> dict[str, str]:
    fallback_title = title_from_filename(filename)
    if action == "remove_feat":
        return {
            "title": remove_feature_text(str(metadata.get("title", "") or fallback_title)),
            "artist": remove_feature_text(str(metadata.get("artist", "") or "")),
        }
    if action == "remove_parentheses":
        title = str(metadata.get("title", "") or fallback_title)
        return {"title": remove_parenthetical_text(title)}
    if action == "title_only":
        title = str(metadata.get("title", "") or fallback_title)
        return {"title": title.strip(), "artist": "", "album_artist": ""}
    if action == "title_from_file":
        return {"title": fallback_title}
    if action == "copy_artist":
        artist = str(metadata.get("artist", "") or "").strip()
        return {"album_artist": artist}
    return {}
