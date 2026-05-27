import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..constants import CONFIG_FILE_NAME
from ..i18n import normalize_language


VALID_THEME_IDS = {
    "light",
    "dark",
    "system",
    "moka_classic",
    "midnight_blue",
    "forest",
    "rose",
    "high_contrast",
    "oled_black",
}

VALID_DENSITIES = {"compact", "normal", "comfortable"}
HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass
class AppConfig:
    theme: str = "light"
    font_scale: float = 1.0
    density: str = "normal"
    accent_color: str = ""
    custom_themes: list[dict[str, object]] = field(default_factory=list)
    language: str = "es"
    volume: float = 0.8
    repeat: bool = False
    shuffle: bool = False
    onboarding_seen: bool = False
    main_folder: str = ""
    incoming_folder: str = ""
    recent_folders: list[dict[str, str]] = field(default_factory=list)
    cleanup_presets: list[dict[str, object]] = field(default_factory=list)
    playback_history: list[dict[str, object]] = field(default_factory=list)


class ConfigController:
    def __init__(self, config_path: str | Path = CONFIG_FILE_NAME) -> None:
        self.path = Path(config_path)
        self.logger = logging.getLogger(__name__)

    def load(self, *, default_language: str = "es") -> AppConfig:
        if not self.path.exists():
            return AppConfig(language=normalize_language(default_language))
        try:
            raw_config = json.loads(self.path.read_text(encoding="utf-8"))
            return self._from_mapping(raw_config, default_language=default_language)
        except Exception as exc:
            self.logger.warning("Could not load config: %s", exc)
            return AppConfig(language=normalize_language(default_language))

    def save(self, config: AppConfig) -> bool:
        try:
            self.path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
            return True
        except Exception as exc:
            self.logger.warning("Could not save config: %s", exc)
            return False

    def _from_mapping(self, raw_config: Any, *, default_language: str) -> AppConfig:
        if not isinstance(raw_config, dict):
            return AppConfig(language=normalize_language(default_language))
        custom_themes = self._coerce_custom_themes(raw_config.get("custom_themes", []))
        return AppConfig(
            theme=self._coerce_theme(raw_config.get("theme", "light"), custom_themes),
            font_scale=self._coerce_font_scale(raw_config.get("font_scale", 1.0)),
            density=self._coerce_density(raw_config.get("density", "normal")),
            accent_color=self._coerce_accent_color(raw_config.get("accent_color", "")),
            custom_themes=custom_themes,
            language=normalize_language(str(raw_config.get("language", default_language) or default_language)),
            volume=self._coerce_volume(raw_config.get("volume", 0.8)),
            repeat=bool(raw_config.get("repeat", False)),
            shuffle=bool(raw_config.get("shuffle", False)),
            onboarding_seen=bool(raw_config.get("onboarding_seen", False)),
            main_folder=str(raw_config.get("main_folder", "") or ""),
            incoming_folder=str(raw_config.get("incoming_folder", "") or ""),
            recent_folders=self._coerce_recent_folders(raw_config.get("recent_folders", [])),
            cleanup_presets=raw_config.get("cleanup_presets", []) if isinstance(raw_config.get("cleanup_presets", []), list) else [],
            playback_history=raw_config.get("playback_history", []) if isinstance(raw_config.get("playback_history", []), list) else [],
        )

    def _coerce_volume(self, value) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.8

    def _coerce_theme(self, value, custom_themes: list[dict[str, object]] | None = None) -> str:
        theme = str(value or "light")
        custom_ids = {str(item.get("id", "")) for item in custom_themes or []}
        return theme if theme in VALID_THEME_IDS or theme in custom_ids else "light"

    def _coerce_font_scale(self, value) -> float:
        try:
            return max(0.85, min(1.3, float(value)))
        except (TypeError, ValueError):
            return 1.0

    def _coerce_density(self, value) -> str:
        density = str(value or "normal")
        return density if density in VALID_DENSITIES else "normal"

    def _coerce_accent_color(self, value) -> str:
        color = str(value or "").strip()
        return color.lower() if HEX_COLOR_PATTERN.fullmatch(color) else ""

    def _coerce_recent_folders(self, value) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        recent_folders: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            folder = str(item.get("folder", "") or "").strip()
            target = str(item.get("target", "main") or "main")
            if not folder:
                continue
            recent_folders.append({"folder": folder, "target": target if target in {"main", "incoming"} else "main"})
        return recent_folders[:10]

    def _coerce_custom_themes(self, value) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        themes: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            theme_id = str(item.get("id", "") or "").strip()
            name = str(item.get("name", "") or "").strip()
            if not theme_id or not name or theme_id in seen_ids:
                continue
            base_theme = self._coerce_theme(item.get("base_theme", "light"))
            themes.append(
                {
                    "id": theme_id,
                    "name": name,
                    "base_theme": base_theme,
                    "font_scale": self._coerce_font_scale(item.get("font_scale", 1.0)),
                    "density": self._coerce_density(item.get("density", "normal")),
                    "accent_color": self._coerce_accent_color(item.get("accent_color", "")),
                }
            )
            seen_ids.add(theme_id)
        return themes[:25]
