import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..constants import CONFIG_FILE_NAME
from ..i18n import normalize_language


@dataclass
class AppConfig:
    theme: str = "light"
    language: str = "es"
    volume: float = 0.8
    repeat: bool = False
    shuffle: bool = False
    main_folder: str = ""
    incoming_folder: str = ""
    cleanup_presets: list[dict[str, object]] = field(default_factory=list)


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
        return AppConfig(
            theme=str(raw_config.get("theme", "light") or "light"),
            language=normalize_language(str(raw_config.get("language", default_language) or default_language)),
            volume=self._coerce_volume(raw_config.get("volume", 0.8)),
            repeat=bool(raw_config.get("repeat", False)),
            shuffle=bool(raw_config.get("shuffle", False)),
            main_folder=str(raw_config.get("main_folder", "") or ""),
            incoming_folder=str(raw_config.get("incoming_folder", "") or ""),
            cleanup_presets=raw_config.get("cleanup_presets", []) if isinstance(raw_config.get("cleanup_presets", []), list) else [],
        )

    def _coerce_volume(self, value) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.8
