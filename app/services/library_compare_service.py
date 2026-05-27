from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.library_service import MetadataCache, fuzzy_duplicate_key_for, metadata_for


@dataclass(frozen=True)
class LibraryComparisonRow:
    incoming_filename: str
    incoming_artist: str
    incoming_title: str
    status: str
    matched_filename: str
    score: float


def compare_libraries(
    main_files: list[str],
    main_metadata_cache: MetadataCache,
    incoming_files: list[str],
    incoming_metadata_cache: MetadataCache,
    *,
    threshold: float = 0.92,
) -> dict[str, object]:
    main_keys = {
        filename: fuzzy_duplicate_key_for(filename, metadata_for(filename, main_metadata_cache))
        for filename in main_files
    }

    rows: list[LibraryComparisonRow] = []
    duplicate_count = 0
    for filename in incoming_files:
        metadata = metadata_for(filename, incoming_metadata_cache)
        incoming_key = fuzzy_duplicate_key_for(filename, metadata)
        matched_filename = ""
        best_score = 0.0

        if incoming_key:
            for main_filename, main_key in main_keys.items():
                if not main_key:
                    continue
                score = SequenceMatcher(None, incoming_key, main_key).ratio()
                if score > best_score:
                    best_score = score
                    matched_filename = main_filename

        status = "duplicate" if matched_filename and best_score >= threshold else "new"
        if status == "duplicate":
            duplicate_count += 1
        else:
            matched_filename = ""
            best_score = 0.0

        rows.append(
            LibraryComparisonRow(
                incoming_filename=filename,
                incoming_artist=str(metadata.get("artist", "") or ""),
                incoming_title=str(metadata.get("title", "") or ""),
                status=status,
                matched_filename=matched_filename,
                score=round(best_score * 100, 1),
            )
        )

    return {
        "total_incoming": len(incoming_files),
        "new_tracks": len(incoming_files) - duplicate_count,
        "duplicates": duplicate_count,
        "rows": rows,
    }
