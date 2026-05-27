import json
import tempfile
import unittest
from pathlib import Path

from app.controllers.config_controller import AppConfig, ConfigController


class ConfigControllerTests(unittest.TestCase):
    def test_load_returns_defaults_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = ConfigController(Path(temp_dir) / "missing.json")

            config = controller.load(default_language="en")

            self.assertEqual(config.theme, "light")
            self.assertEqual(config.language, "en")
            self.assertEqual(config.volume, 0.8)
            self.assertFalse(config.repeat)
            self.assertFalse(config.onboarding_seen)

    def test_load_normalizes_invalid_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "font_scale": 9,
                        "density": "huge",
                        "accent_color": "tomato",
                        "custom_themes": [
                            {
                                "id": "custom_moka",
                                "name": "Moka",
                                "base_theme": "forest",
                                "font_scale": "1.15",
                                "density": "compact",
                                "accent_color": "#336699",
                            },
                            {"id": "", "name": "skip"},
                        ],
                        "language": "zz",
                        "volume": 9,
                        "repeat": 1,
                        "shuffle": 0,
                        "onboarding_seen": 1,
                        "recent_folders": [
                            {"folder": "C:/Music/Main", "target": "main"},
                            {"folder": "C:/Music/Incoming", "target": "incoming"},
                            {"folder": "", "target": "main"},
                            "bad",
                        ],
                        "cleanup_presets": "bad",
                        "playback_history": [{"filename": "song.mp3"}],
                    }
                ),
                encoding="utf-8",
            )

            config = ConfigController(path).load(default_language="es")

            self.assertEqual(config.theme, "dark")
            self.assertEqual(config.font_scale, 1.3)
            self.assertEqual(config.density, "normal")
            self.assertEqual(config.accent_color, "")
            self.assertEqual(
                config.custom_themes,
                [
                    {
                        "id": "custom_moka",
                        "name": "Moka",
                        "base_theme": "forest",
                        "font_scale": 1.15,
                        "density": "compact",
                        "accent_color": "#336699",
                    }
                ],
            )
            self.assertEqual(config.language, "es")
            self.assertEqual(config.volume, 1.0)
            self.assertTrue(config.repeat)
            self.assertFalse(config.shuffle)
            self.assertTrue(config.onboarding_seen)
            self.assertEqual(
                config.recent_folders,
                [
                    {"folder": "C:/Music/Main", "target": "main"},
                    {"folder": "C:/Music/Incoming", "target": "incoming"},
                ],
            )
            self.assertEqual(config.cleanup_presets, [])
            self.assertEqual(config.playback_history, [{"filename": "song.mp3"}])

    def test_load_preserves_theme_presets_and_falls_back_for_unknown_theme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps({"theme": "forest"}), encoding="utf-8")

            self.assertEqual(ConfigController(path).load().theme, "forest")

            path.write_text(json.dumps({"theme": "not-a-theme"}), encoding="utf-8")

            self.assertEqual(ConfigController(path).load().theme, "light")

            path.write_text(
                json.dumps(
                    {
                        "theme": "custom_moka",
                        "custom_themes": [{"id": "custom_moka", "name": "Moka"}],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(ConfigController(path).load().theme, "custom_moka")

    def test_save_writes_app_config_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            controller = ConfigController(path)

            self.assertTrue(
                controller.save(
                    AppConfig(
                        theme="oled_black",
                        font_scale=1.15,
                        density="comfortable",
                        accent_color="#336699",
                        custom_themes=[{"id": "custom_moka", "name": "Moka", "base_theme": "dark"}],
                        language="en",
                        volume=0.25,
                        repeat=True,
                        onboarding_seen=True,
                        main_folder="main",
                        recent_folders=[{"folder": "C:/Music/Main", "target": "main"}],
                        playback_history=[{"filename": "song.mp3", "play_count": 1}],
                    )
                )
            )

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["theme"], "oled_black")
            self.assertEqual(payload["font_scale"], 1.15)
            self.assertEqual(payload["density"], "comfortable")
            self.assertEqual(payload["accent_color"], "#336699")
            self.assertEqual(payload["custom_themes"], [{"id": "custom_moka", "name": "Moka", "base_theme": "dark"}])
            self.assertEqual(payload["language"], "en")
            self.assertEqual(payload["volume"], 0.25)
            self.assertTrue(payload["repeat"])
            self.assertTrue(payload["onboarding_seen"])
            self.assertEqual(payload["main_folder"], "main")
            self.assertEqual(payload["recent_folders"], [{"folder": "C:/Music/Main", "target": "main"}])
            self.assertEqual(payload["playback_history"], [{"filename": "song.mp3", "play_count": 1}])


if __name__ == "__main__":
    unittest.main()
