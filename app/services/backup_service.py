import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


BACKUP_DIR = Path("backups")


def safe_backup_folder_name(folder_path: str) -> str:
    folder_name = Path(folder_path).name or "library"
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in folder_name)


def encode_cover_art(cover_art: Optional[bytes]) -> Optional[str]:
    return base64.b64encode(cover_art).decode("ascii") if cover_art else None


def decode_cover_art(value) -> Optional[bytes]:
    if not value:
        return None
    return base64.b64decode(str(value).encode("ascii"))


def build_track_backup(
    *,
    filename: str,
    filepath: str,
    metadata: dict[str, str],
    cover_art: Optional[bytes],
) -> dict[str, object]:
    return {
        "filename": filename,
        "filepath": filepath,
        "metadata": dict(metadata),
        "cover_art_b64": encode_cover_art(cover_art),
    }


def write_metadata_backup(
    *,
    library_folder: str,
    applied_metadata: dict[str, str],
    tracks: list[dict[str, object]],
    backup_dir: Path = BACKUP_DIR,
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{safe_backup_folder_name(library_folder)}_{timestamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "library_folder": library_folder,
        "applied_metadata": applied_metadata,
        "track_count": len(tracks),
        "tracks": tracks,
    }
    backup_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return backup_path


def read_backup_payload(backup_path: str | Path) -> dict[str, object]:
    path = Path(backup_path)
    return json.loads(path.read_text(encoding="utf-8"))


def iter_backup_payloads(backup_dir: Path = BACKUP_DIR) -> list[tuple[Path, dict[str, object]]]:
    if not backup_dir.exists():
        return []
    payloads: list[tuple[Path, dict[str, object]]] = []
    for path in sorted(backup_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payloads.append((path, read_backup_payload(path)))
        except (OSError, json.JSONDecodeError):
            continue
    return payloads
