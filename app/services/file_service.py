import logging
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from ..constants import FileFormats, UISettings
from ..i18n import I18n
from ..models import ActionResult
from .song_info_service import SongInfo


logger = logging.getLogger(__name__)


def sanitize_filename(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        value = value.replace(char, "_")
    return value.strip()


def is_supported_audio_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in FileFormats.AUDIO


def is_supported_image_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in FileFormats.IMAGES


def list_audio_files(folder: str | Path) -> list[str]:
    try:
        path = Path(folder)
        return [
            item.relative_to(path).as_posix()
            for item in sorted(path.rglob("*"))
            if item.is_file() and is_supported_audio_file(item)
        ]
    except Exception as exc:
        logger.error("Error listing audio files: %s", exc)
        return []


def shorten_filename(value: str | Path, max_len: int = UISettings.MAX_FILENAME_DISPLAY) -> str:
    name = Path(value).name
    if len(name) <= max_len:
        return name
    stem, suffix = os.path.splitext(name)
    max_stem_len = max_len - len(suffix) - 3
    return f"{stem[:max_stem_len]}...{suffix}"


def parse_dropped_audio_files(raw_data: str) -> list[str]:
    entries = raw_data.split() if isinstance(raw_data, str) else []
    valid_files: list[str] = []
    for entry in entries:
        normalized = entry.strip("{}")
        if is_supported_audio_file(normalized):
            valid_files.append(normalized)
    return valid_files


def add_song_to_library(
    source_file: str,
    destination_controller,
    *,
    song_info: Optional[SongInfo] = None,
    translator: Optional[Callable[..., str]] = None,
) -> ActionResult:
    t = translator or I18n().t
    inspector = song_info or SongInfo()

    if not destination_controller.carpeta:
        return ActionResult.fail(t("add.select_destination"))

    source_path = Path(source_file)
    if not source_path.exists():
        return ActionResult.fail(t("add.file_missing", path=source_file))
    if source_path.suffix.lower() not in FileFormats.AUDIO:
        return ActionResult.fail(t("add.unsupported_format", suffix=source_path.suffix))

    destination_dir = Path(destination_controller.carpeta)
    destination_path = destination_dir / source_path.name

    if destination_path.name in destination_controller.archivos:
        return ActionResult.fail(t("add.song_exists", name=destination_path.name))

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != destination_path.resolve():
            shutil.copy2(source_path, destination_path)
        destination_controller.register_file(destination_path.name)
        metadata = inspector.get_metadata(str(destination_path)) or {}
        return ActionResult.ok(
            t("add.song_added", name=destination_path.name),
            data={"filename": destination_path.name, "metadata": metadata},
        )
    except Exception as exc:
        logger.error("Error adding song %s: %s", source_file, exc)
        return ActionResult.fail(t("add.could_not_add", error=exc))


def move_song_between_libraries(
    origin_controller,
    destination_controller,
    filename: str,
    *,
    translator: Optional[Callable[..., str]] = None,
) -> ActionResult:
    t = translator or I18n().t

    if not filename or filename not in origin_controller.archivos:
        return ActionResult.fail(t("action.song_missing_origin"))
    if not destination_controller.carpeta:
        return ActionResult.fail(t("action.no_destination"))
    if filename in destination_controller.archivos:
        return ActionResult.fail(t("action.song_exists_destination", name=filename))

    source_path = os.path.join(origin_controller.carpeta, filename)
    destination_path = os.path.join(destination_controller.carpeta, filename)

    if not os.path.exists(source_path):
        return ActionResult.fail(t("action.file_no_longer_exists", path=source_path))

    try:
        shutil.move(source_path, destination_path)
        origin_controller.remove_file(filename)
        destination_controller.register_file(filename)
        return ActionResult.ok(t("action.song_moved"), data={"filename": filename})
    except Exception as exc:
        logger.error("Error moving %s: %s", filename, exc)
        return ActionResult.fail(t("action.could_not_move", error=exc))


def delete_song(
    controller,
    filename: str,
    *,
    move_to_trash: bool = True,
    translator: Optional[Callable[..., str]] = None,
) -> ActionResult:
    t = translator or I18n().t

    if not filename or filename not in controller.archivos:
        return ActionResult.fail(t("action.song_missing"))

    filepath = os.path.join(controller.carpeta, filename)
    if not os.path.exists(filepath):
        return ActionResult.fail(t("action.file_no_longer_exists", path=filepath))

    try:
        if move_to_trash:
            try:
                import send2trash

                send2trash.send2trash(filepath)
            except Exception:
                os.unlink(filepath)
        else:
            os.unlink(filepath)
        controller.remove_file(filename)
        return ActionResult.ok(t("action.song_deleted"))
    except Exception as exc:
        logger.error("Error deleting %s: %s", filename, exc)
        return ActionResult.fail(t("action.could_not_delete", error=exc))


def rename_song(
    controller,
    current_name: str,
    new_name: str,
    *,
    translator: Optional[Callable[..., str]] = None,
) -> ActionResult:
    t = translator or I18n().t

    if not current_name or current_name not in controller.archivos:
        return ActionResult.fail(t("action.song_missing"))

    clean_name = sanitize_filename(new_name.strip())
    if not clean_name:
        return ActionResult.fail(t("action.empty_name"))

    _, extension = os.path.splitext(current_name)
    full_new_name = f"{clean_name}{extension}"

    if full_new_name in controller.archivos:
        return ActionResult.fail(t("action.name_exists", name=full_new_name))

    source_path = os.path.join(controller.carpeta, current_name)
    destination_path = os.path.join(controller.carpeta, full_new_name)

    try:
        os.rename(source_path, destination_path)
        controller.rename_file(current_name, full_new_name)
        return ActionResult.ok(
            t("action.song_renamed"),
            data={"filename": full_new_name, "filepath": destination_path},
        )
    except Exception as exc:
        logger.error("Error renaming %s to %s: %s", current_name, full_new_name, exc)
        return ActionResult.fail(t("action.could_not_rename", error=exc))
