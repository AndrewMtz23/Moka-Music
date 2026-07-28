from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path

SUPPORTED_PLAYLIST_EXPORTS = (".m3u", ".m3u8", ".pls", ".json")
SUPPORTED_LIBRARY_REPORT_EXPORTS = (".json", ".csv")
METADATA_EXPORT_KEYS = {"title", "artist", "album", "album_artist", "genre", "year", "track_number", "comment"}


def export_playlist(
    *,
    folder: str | Path,
    filenames: list[str],
    output_path: str | Path,
    metadata_by_filename: dict[str, dict[str, str]] | None = None,
) -> Path:
    destination = Path(output_path)
    suffix = destination.suffix.lower()
    if suffix not in SUPPORTED_PLAYLIST_EXPORTS:
        raise ValueError(f"Unsupported playlist format: {destination.suffix}")
    folder_path = Path(folder)
    metadata_by_filename = metadata_by_filename or {}

    if suffix in {".m3u", ".m3u8"}:
        content = build_m3u(folder_path, filenames, metadata_by_filename)
    elif suffix == ".pls":
        content = build_pls(folder_path, filenames, metadata_by_filename)
    else:
        content = build_json(folder_path, filenames, metadata_by_filename)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def build_m3u(folder: Path, filenames: list[str], metadata_by_filename: dict[str, dict[str, str]]) -> str:
    lines = ["#EXTM3U"]
    for filename in filenames:
        metadata = metadata_by_filename.get(filename, {})
        title = _display_title(filename, metadata)
        duration = int(float(metadata.get("duration", 0) or 0))
        lines.append(f"#EXTINF:{duration},{title}")
        lines.append(str((folder / filename).resolve()))
    return "\n".join(lines) + "\n"


def build_pls(folder: Path, filenames: list[str], metadata_by_filename: dict[str, dict[str, str]]) -> str:
    lines = ["[playlist]"]
    for index, filename in enumerate(filenames, start=1):
        metadata = metadata_by_filename.get(filename, {})
        lines.append(f"File{index}={(folder / filename).resolve()}")
        lines.append(f"Title{index}={_display_title(filename, metadata)}")
        lines.append(f"Length{index}={int(float(metadata.get('duration', 0) or 0))}")
    lines.append(f"NumberOfEntries={len(filenames)}")
    lines.append("Version=2")
    return "\n".join(lines) + "\n"


def build_json(folder: Path, filenames: list[str], metadata_by_filename: dict[str, dict[str, str]]) -> str:
    tracks = []
    for index, filename in enumerate(filenames, start=1):
        metadata = metadata_by_filename.get(filename, {})
        tracks.append(
            {
                "position": index,
                "filename": filename,
                "path": str((folder / filename).resolve()),
                "metadata": {key: value for key, value in metadata.items() if key in METADATA_EXPORT_KEYS},
                "duration": float(metadata.get("duration", 0) or 0),
            }
        )
    return json.dumps(
        {"folder": str(folder.resolve()), "track_count": len(tracks), "tracks": tracks}, indent=2, ensure_ascii=False
    )


def export_library_view_json(
    *,
    folder: str | Path,
    output_path: str | Path,
    filenames: list[str],
    metadata_by_filename: dict[str, dict[str, str]] | None = None,
    audio_quality_by_filename: dict[str, dict[str, object]] | None = None,
    duration_by_filename: dict[str, float] | None = None,
    library_position_by_filename: dict[str, int] | None = None,
    filter_info: dict[str, object] | None = None,
) -> Path:
    destination = Path(output_path)
    if destination.suffix.lower() != ".json":
        destination = destination.with_suffix(".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        build_library_view_json(
            folder=Path(folder),
            filenames=filenames,
            metadata_by_filename=metadata_by_filename or {},
            audio_quality_by_filename=audio_quality_by_filename or {},
            duration_by_filename=duration_by_filename or {},
            library_position_by_filename=library_position_by_filename or {},
            filter_info=filter_info or {},
        ),
        encoding="utf-8",
    )
    return destination


def export_library_report(
    *,
    folder: str | Path,
    output_path: str | Path,
    filenames: list[str],
    metadata_by_filename: dict[str, dict[str, str]] | None = None,
    audio_quality_by_filename: dict[str, dict[str, object]] | None = None,
    duration_by_filename: dict[str, float] | None = None,
    library_position_by_filename: dict[str, int] | None = None,
    issues_by_filename: dict[str, list[str]] | None = None,
    summary: dict[str, object] | None = None,
) -> Path:
    destination = Path(output_path)
    suffix = destination.suffix.lower()
    if suffix not in SUPPORTED_LIBRARY_REPORT_EXPORTS:
        destination = destination.with_suffix(".json")
        suffix = ".json"

    content = build_library_report(
        folder=Path(folder),
        filenames=filenames,
        metadata_by_filename=metadata_by_filename or {},
        audio_quality_by_filename=audio_quality_by_filename or {},
        duration_by_filename=duration_by_filename or {},
        library_position_by_filename=library_position_by_filename or {},
        issues_by_filename=issues_by_filename or {},
        summary=summary or {},
        output_format=suffix,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def build_library_view_json(
    *,
    folder: Path,
    filenames: list[str],
    metadata_by_filename: dict[str, dict[str, str]],
    audio_quality_by_filename: dict[str, dict[str, object]],
    duration_by_filename: dict[str, float],
    library_position_by_filename: dict[str, int],
    filter_info: dict[str, object],
) -> str:
    tracks = []
    for visible_position, filename in enumerate(filenames, start=1):
        metadata = metadata_by_filename.get(filename, {})
        tracks.append(
            {
                "visible_position": visible_position,
                "library_position": library_position_by_filename.get(filename, 0),
                "track_number": metadata.get("track_number", ""),
                "filename": filename,
                "path": str((folder / filename).resolve()),
                "metadata": {key: value for key, value in metadata.items() if key in METADATA_EXPORT_KEYS},
                "duration": float(duration_by_filename.get(filename, 0.0) or 0.0),
                "audio_quality": audio_quality_by_filename.get(filename, {}),
            }
        )
    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "folder": str(folder.resolve()),
        "filter": filter_info,
        "track_count": len(tracks),
        "tracks": tracks,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_library_report(
    *,
    folder: Path,
    filenames: list[str],
    metadata_by_filename: dict[str, dict[str, str]],
    audio_quality_by_filename: dict[str, dict[str, object]],
    duration_by_filename: dict[str, float],
    library_position_by_filename: dict[str, int],
    issues_by_filename: dict[str, list[str]],
    summary: dict[str, object],
    output_format: str,
) -> str:
    rows = []
    for filename in filenames:
        metadata = metadata_by_filename.get(filename, {})
        quality = audio_quality_by_filename.get(filename, {})
        rows.append(
            {
                "library_position": library_position_by_filename.get(filename, 0),
                "filename": filename,
                "path": str((folder / filename).resolve()),
                "title": metadata.get("title", ""),
                "artist": metadata.get("artist", ""),
                "album": metadata.get("album", ""),
                "album_artist": metadata.get("album_artist", ""),
                "genre": metadata.get("genre", ""),
                "year": metadata.get("year", ""),
                "track_number": metadata.get("track_number", ""),
                "duration": float(duration_by_filename.get(filename, 0.0) or 0.0),
                "bitrate_kbps": quality.get("bitrate_kbps", ""),
                "format": quality.get("format", ""),
                "low_bitrate": bool(quality.get("low_bitrate", False)),
                "possibly_corrupt": bool(quality.get("possibly_corrupt", False)),
                "issues": issues_by_filename.get(filename, []),
            }
        )

    if output_format == ".csv":
        return _build_report_csv(rows)

    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "folder": str(folder.resolve()),
        "summary": summary,
        "track_count": len(rows),
        "tracks": rows,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _build_report_csv(rows: list[dict[str, object]]) -> str:
    output = io.StringIO()
    fieldnames = [
        "library_position",
        "filename",
        "path",
        "title",
        "artist",
        "album",
        "album_artist",
        "genre",
        "year",
        "track_number",
        "duration",
        "bitrate_kbps",
        "format",
        "low_bitrate",
        "possibly_corrupt",
        "issues",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        csv_row = dict(row)
        csv_row["issues"] = ";".join(str(issue) for issue in row.get("issues", []))
        writer.writerow(csv_row)
    return output.getvalue()


def _display_title(filename: str, metadata: dict[str, str]) -> str:
    title = str(metadata.get("title", "") or Path(filename).stem).strip()
    artist = str(metadata.get("artist", "") or "").strip()
    return f"{artist} - {title}" if artist and artist.lower() not in title.lower() else title
