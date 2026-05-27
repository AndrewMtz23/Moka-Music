import json
import tempfile
import unittest
from pathlib import Path

from app.services.custom_theme_service import (
    custom_theme_id,
    dedupe_theme_id,
    export_custom_theme,
    import_custom_theme,
    normalize_custom_theme,
)


class CustomThemeServiceTests(unittest.TestCase):
    def test_normalizes_custom_theme(self):
        theme = normalize_custom_theme(
            {
                "name": "Mi Moka",
                "base_theme": "forest",
                "font_scale": 2,
                "density": "huge",
                "accent_color": "#336699",
            }
        )

        self.assertEqual(theme["id"], "custom_mi_moka")
        self.assertEqual(theme["base_theme"], "forest")
        self.assertEqual(theme["font_scale"], 1.3)
        self.assertEqual(theme["density"], "normal")
        self.assertEqual(theme["accent_color"], "#336699")

    def test_dedupes_theme_ids(self):
        self.assertEqual(
            dedupe_theme_id("custom_moka", [{"id": "custom_moka"}]),
            "custom_moka_2",
        )

    def test_import_and_export_custom_theme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            source = folder / "theme.json"
            destination = folder / "exported.json"
            source.write_text(
                json.dumps({"id": "custom_moka", "name": "Moka", "base_theme": "dark"}),
                encoding="utf-8",
            )

            theme = import_custom_theme(source, [{"id": "custom_moka"}])
            export_custom_theme(theme, destination)

            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(theme["id"], "custom_moka_2")
            self.assertEqual(payload["name"], "Moka")

    def test_custom_theme_id_falls_back(self):
        self.assertEqual(custom_theme_id(""), "custom_tema")


if __name__ == "__main__":
    unittest.main()
