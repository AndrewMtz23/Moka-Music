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

    def test_load_normalizes_invalid_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "language": "zz",
                        "volume": 9,
                        "repeat": 1,
                        "shuffle": 0,
                        "cleanup_presets": "bad",
                    }
                ),
                encoding="utf-8",
            )

            config = ConfigController(path).load(default_language="es")

            self.assertEqual(config.theme, "dark")
            self.assertEqual(config.language, "es")
            self.assertEqual(config.volume, 1.0)
            self.assertTrue(config.repeat)
            self.assertFalse(config.shuffle)
            self.assertEqual(config.cleanup_presets, [])

    def test_save_writes_app_config_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            controller = ConfigController(path)

            self.assertTrue(
                controller.save(
                    AppConfig(
                        theme="dark",
                        language="en",
                        volume=0.25,
                        repeat=True,
                        main_folder="main",
                    )
                )
            )

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["theme"], "dark")
            self.assertEqual(payload["language"], "en")
            self.assertEqual(payload["volume"], 0.25)
            self.assertTrue(payload["repeat"])
            self.assertEqual(payload["main_folder"], "main")


if __name__ == "__main__":
    unittest.main()
