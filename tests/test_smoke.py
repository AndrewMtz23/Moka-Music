import importlib
import unittest
from pathlib import Path


class SmokeTests(unittest.TestCase):
    def test_main_module_imports(self):
        module = importlib.import_module("main")
        self.assertTrue(hasattr(module, "main"))

    def test_ui_module_imports(self):
        module = importlib.import_module("app.ui")
        self.assertTrue(hasattr(module, "iniciar_app"))
        self.assertEqual(Path(module.__file__).name, "__init__.py")
        self.assertEqual(Path(module.__file__).parent.name, "ui")
