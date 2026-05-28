from __future__ import annotations

import locale
from pathlib import Path

from ..i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, TRANSLATIONS
from .audio_conversion_service import ffmpeg_available
from .backup_service import BACKUP_DIR


def detect_system_language() -> str:
    language, _encoding = locale.getlocale()
    if not language:
        return DEFAULT_LANGUAGE
    normalized = language.lower()
    if normalized.startswith("es"):
        return "es"
    if normalized.startswith("en"):
        return "en"
    return DEFAULT_LANGUAGE


def active_language_label(label: str, language: str, current_language: str) -> str:
    return f"✓ {label}" if language == current_language else label


def missing_translation_report() -> dict[str, list[str]]:
    all_keys = set()
    for translations in TRANSLATIONS.values():
        all_keys.update(translations.keys())
    return {
        language: sorted(all_keys - set(TRANSLATIONS.get(language, {}).keys()))
        for language in SUPPORTED_LANGUAGES
    }


def format_missing_translation_report(report: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for language in SUPPORTED_LANGUAGES:
        missing = report.get(language, [])
        if missing:
            lines.append(f"{language}: {len(missing)}")
            lines.extend(f"- {key}" for key in missing[:25])
            if len(missing) > 25:
                lines.append(f"... +{len(missing) - 25}")
        else:
            lines.append(f"{language}: 0")
    return "\n".join(lines)


def diagnostic_lines(*, log_file: str | Path, main_folder: str = "", incoming_folder: str = "") -> list[str]:
    log_path = Path(log_file)
    backup_path = BACKUP_DIR
    return [
        f"ffmpeg: {'OK' if ffmpeg_available() else 'NO'}",
        f"log: {'OK' if log_path.exists() else 'NO'} ({log_path})",
        f"backups: {'OK' if backup_path.exists() else 'NO'} ({backup_path})",
        f"main_folder: {'OK' if main_folder and Path(main_folder).exists() else 'NO'} ({main_folder or '-'})",
        f"incoming_folder: {'OK' if incoming_folder and Path(incoming_folder).exists() else 'NO'} ({incoming_folder or '-'})",
    ]
