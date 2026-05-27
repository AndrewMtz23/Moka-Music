from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CUSTOM_THEME_KEYS = {"id", "name", "base_theme", "font_scale", "density", "accent_color"}
BASE_THEME_IDS = {"light", "dark", "moka_classic", "midnight_blue", "forest", "rose", "high_contrast", "oled_black"}
VALID_DENSITIES = {"compact", "normal", "comfortable"}


def is_valid_hex_color(color: str) -> bool:
    if not isinstance(color, str):
        return False
    if len(color) != 7 or not color.startswith("#"):
        return False
    return all(character in "0123456789abcdefABCDEF" for character in color[1:])


def custom_theme_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_")
    return f"custom_{slug or 'tema'}"


def normalize_custom_theme(raw_theme: dict[str, Any], *, fallback_name: str = "Tema") -> dict[str, object] | None:
    if not isinstance(raw_theme, dict):
        return None
    name = str(raw_theme.get("name", "") or fallback_name).strip()
    theme_id = str(raw_theme.get("id", "") or custom_theme_id(name)).strip()
    if not name or not theme_id:
        return None
    base_theme = str(raw_theme.get("base_theme", "light") or "light")
    if base_theme not in BASE_THEME_IDS:
        base_theme = "light"
    density = str(raw_theme.get("density", "normal") or "normal")
    if density not in VALID_DENSITIES:
        density = "normal"
    try:
        font_scale = max(0.85, min(1.3, float(raw_theme.get("font_scale", 1.0))))
    except (TypeError, ValueError):
        font_scale = 1.0
    accent_color = str(raw_theme.get("accent_color", "") or "").strip().lower()
    if not is_valid_hex_color(accent_color):
        accent_color = ""
    return {
        "id": theme_id,
        "name": name,
        "base_theme": base_theme,
        "font_scale": font_scale,
        "density": density,
        "accent_color": accent_color,
    }


def dedupe_theme_id(theme_id: str, existing_themes: list[dict[str, object]]) -> str:
    existing_ids = {str(theme.get("id", "") or "") for theme in existing_themes}
    if theme_id not in existing_ids:
        return theme_id
    index = 2
    while f"{theme_id}_{index}" in existing_ids:
        index += 1
    return f"{theme_id}_{index}"


def export_custom_theme(theme: dict[str, object], output_path: str | Path) -> Path:
    normalized = normalize_custom_theme(theme)
    if normalized is None:
        raise ValueError("Invalid custom theme")
    destination = Path(output_path)
    if destination.suffix.lower() != ".json":
        destination = destination.with_suffix(".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def import_custom_theme(input_path: str | Path, existing_themes: list[dict[str, object]]) -> dict[str, object]:
    raw_theme = json.loads(Path(input_path).read_text(encoding="utf-8"))
    normalized = normalize_custom_theme(raw_theme)
    if normalized is None:
        raise ValueError("Invalid custom theme")
    normalized["id"] = dedupe_theme_id(str(normalized["id"]), existing_themes)
    return normalized


def public_theme_payload(theme: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in theme.items() if key in CUSTOM_THEME_KEYS}
