from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .playlist_export_service import METADATA_EXPORT_KEYS


@dataclass(frozen=True)
class MetadataImportItem:
    filename: str
    metadata: dict[str, str]
    source_path: str = ""


def load_metadata_import_items(path: str | Path) -> list[MetadataImportItem]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return extract_metadata_import_items(payload)


def extract_metadata_import_items(payload: Any) -> list[MetadataImportItem]:
    tracks = _payload_tracks(payload)
    items: list[MetadataImportItem] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        filename = str(track.get("filename", "") or "").strip()
        metadata = track.get("metadata", {})
        if not filename or not isinstance(metadata, dict):
            continue
        clean_metadata = {
            key: str(value or "")
            for key, value in metadata.items()
            if key in METADATA_EXPORT_KEYS and str(value or "").strip()
        }
        if clean_metadata:
            items.append(
                MetadataImportItem(
                    filename=filename,
                    metadata=clean_metadata,
                    source_path=str(track.get("path", "") or ""),
                )
            )
    return items


def filter_import_items_for_library(
    items: list[MetadataImportItem],
    available_filenames: list[str],
) -> list[MetadataImportItem]:
    available = set(available_filenames)
    return [item for item in items if item.filename in available]


def _payload_tracks(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        tracks = payload.get("tracks", [])
        return tracks if isinstance(tracks, list) else []
    if isinstance(payload, list):
        return payload
    return []
