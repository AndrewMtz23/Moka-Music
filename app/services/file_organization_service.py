from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil
from datetime import datetime

from .backup_service import BACKUP_DIR, safe_backup_folder_name
from .file_service import sanitize_filename
from .playback_history_service import normalize_history_path


DEFAULT_RENAME_TEMPLATE = "{track_number:03d} - {artist} - {title}"
DEFAULT_ORGANIZE_TEMPLATE = "{artist}/{album}/{track_number:02d} - {title}"
SMART_PLAYLIST_MODES = ("low_bitrate", "unplayed", "missing_cover", "artist", "genre", "duration")


@dataclass(frozen=True)
class FileOrganizationPlanItem:
    old_name: str
    new_name: str
    source: Path
    destination: Path


@dataclass
class FileOrganizationResult:
    moved: int
    errors: list[str]
    backup_path: Path | None = None


def build_template_plan(controller, filenames: list[str], template: str) -> list[FileOrganizationPlanItem]:
    folder = Path(controller.carpeta)
    used_paths = {Path(name).as_posix().lower() for name in controller.archivos}
    plan: list[FileOrganizationPlanItem] = []
    for filename in filenames:
        cached = controller.get_track_info(filename)
        metadata = dict(cached.metadata) if cached else {}
        new_name = filename_from_template(filename, metadata, template, used_paths)
        if new_name and new_name != filename:
            used_paths.discard(Path(filename).as_posix().lower())
            used_paths.add(Path(new_name).as_posix().lower())
            plan.append(
                FileOrganizationPlanItem(
                    old_name=filename,
                    new_name=new_name,
                    source=folder / filename,
                    destination=folder / new_name,
                )
            )
    return plan


def filename_from_template(
    filename: str,
    metadata: dict[str, str],
    template: str,
    used_paths: set[str] | None = None,
) -> str:
    source = Path(filename)
    values = template_values(filename, metadata)
    try:
        rendered = template.format(**values)
    except Exception:
        rendered = DEFAULT_RENAME_TEMPLATE.format(**values)
    rendered_path = sanitize_relative_path(rendered)
    if not rendered_path.suffix:
        rendered_path = rendered_path.with_suffix(source.suffix)
    candidate = rendered_path.as_posix()
    return unique_relative_path(candidate, used_paths or set())


def template_values(filename: str, metadata: dict[str, str]) -> dict[str, object]:
    stem = Path(filename).stem
    title = sanitize_filename(str(metadata.get("title", "") or stem).strip())
    artist = sanitize_filename(str(metadata.get("artist", "") or "Unknown Artist").strip())
    album = sanitize_filename(str(metadata.get("album", "") or "Unknown Album").strip())
    year = str(metadata.get("year", "") or "").strip()
    genre = str(metadata.get("genre", "") or "").strip()
    track_number = _int_value(metadata.get("track_number", ""), default=0)
    return {
        "title": title,
        "artist": artist,
        "album": album,
        "album_artist": sanitize_filename(str(metadata.get("album_artist", "") or artist).strip()),
        "year": sanitize_filename(year),
        "genre": sanitize_filename(genre),
        "track_number": track_number,
        "filename": stem,
    }


def sanitize_relative_path(value: str) -> Path:
    parts = [sanitize_filename(part).strip(". ") for part in str(value).replace("\\", "/").split("/")]
    clean_parts = [part or "Sin nombre" for part in parts if part not in {"", ".", ".."}]
    return Path(*clean_parts) if clean_parts else Path("Sin nombre")


def unique_relative_path(candidate: str, used_paths: set[str]) -> str:
    path = Path(candidate)
    next_path = path
    index = 2
    while next_path.as_posix().lower() in used_paths:
        next_path = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    return next_path.as_posix()


def execute_file_plan(controller, plan: list[FileOrganizationPlanItem], *, song_info=None) -> FileOrganizationResult:
    if not plan:
        return FileOrganizationResult(moved=0, errors=[])
    backup_path = write_file_plan_backup(controller.carpeta, plan)
    moved = 0
    errors: list[str] = []
    for item in plan:
        try:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item.source), str(item.destination))
            controller.rename_file(item.old_name, item.new_name)
            if song_info:
                song_info.invalidate(str(item.source))
                song_info.invalidate(str(item.destination))
            moved += 1
        except Exception as exc:
            errors.append(f"{item.old_name}: {exc}")
    return FileOrganizationResult(moved=moved, errors=errors, backup_path=backup_path)


def write_file_plan_backup(library_folder: str, plan: list[FileOrganizationPlanItem]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"{safe_backup_folder_name(library_folder)}_files_{timestamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "library_folder": library_folder,
        "operation": "file_organization",
        "items": [
            {
                "old_name": item.old_name,
                "new_name": item.new_name,
                "source": str(item.source),
                "destination": str(item.destination),
            }
            for item in plan
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_playlist(controller, filenames: list[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_track_numbers: dict[int, str] = {}
    track_numbers: list[int] = []
    for filename in filenames:
        path = Path(controller.carpeta) / filename
        cached = controller.get_track_info(filename)
        metadata = dict(cached.metadata) if cached else {}
        normalized = filename.lower()
        if normalized in seen_names:
            issues.append({"filename": filename, "issue": "duplicate_file", "detail": filename})
        seen_names.add(normalized)
        if not path.exists():
            issues.append({"filename": filename, "issue": "missing_file", "detail": str(path)})
        track_number = _int_value(metadata.get("track_number", ""), default=-1)
        if track_number < 0:
            issues.append({"filename": filename, "issue": "missing_track_number", "detail": ""})
            continue
        if track_number in seen_track_numbers:
            issues.append({"filename": filename, "issue": "duplicate_track_number", "detail": str(track_number)})
        seen_track_numbers[track_number] = filename
        track_numbers.append(track_number)
    if track_numbers:
        expected = set(range(min(track_numbers), max(track_numbers) + 1))
        for missing in sorted(expected - set(track_numbers)):
            issues.append({"filename": "", "issue": "missing_track_gap", "detail": str(missing)})
    return issues


def smart_playlist_filenames(controller, mode: str) -> list[str]:
    criterion, value = parse_smart_playlist_mode(mode)
    if criterion not in SMART_PLAYLIST_MODES:
        raise ValueError(f"Unsupported smart playlist mode: {mode}")
    result: list[str] = []
    duration_limit = _duration_limit_seconds(value) if criterion == "duration" else 0.0
    duration_total = 0.0
    for filename in controller.archivos:
        cached = controller.get_track_info(filename)
        metadata = dict(cached.metadata) if cached else {}
        quality = dict(cached.audio_quality or {}) if cached else {}
        if criterion == "low_bitrate" and quality.get("low_bitrate"):
            result.append(filename)
        elif criterion == "missing_cover" and "missing_cover" in controller.issue_keys_for_file(filename):
            result.append(filename)
        elif criterion == "unplayed":
            path = str(Path(controller.carpeta) / filename)
            played_paths = getattr(controller, "_played_paths", set())
            if normalize_history_path(path) not in played_paths:
                result.append(filename)
        elif criterion == "artist" and _matches_text(metadata.get("artist", ""), value):
            result.append(filename)
        elif criterion == "genre" and _matches_text(metadata.get("genre", ""), value):
            result.append(filename)
        elif criterion == "duration":
            duration = float(getattr(cached, "duration", 0.0) or 0.0) if cached else 0.0
            if duration_total + duration <= duration_limit or not result:
                result.append(filename)
                duration_total += duration
            if duration_total >= duration_limit and result:
                break
    return result


def parse_smart_playlist_mode(mode: str) -> tuple[str, str]:
    raw = str(mode or "").strip()
    if ":" not in raw:
        return raw, ""
    criterion, value = raw.split(":", 1)
    return criterion.strip().lower(), value.strip()


def _matches_text(current: object, expected: str) -> bool:
    expected = expected.strip().lower()
    if not expected:
        return False
    return expected in str(current or "").lower()


def _duration_limit_seconds(value: str) -> float:
    try:
        minutes = float(str(value or "").strip())
    except ValueError:
        raise ValueError("Duration criteria must use minutes, for example duration:60")
    if minutes <= 0:
        raise ValueError("Duration criteria must be greater than zero minutes")
    return max(1.0, minutes) * 60.0


def _int_value(value: object, *, default: int) -> int:
    try:
        return int(str(value or "").split("/")[0].strip())
    except (TypeError, ValueError):
        return default
