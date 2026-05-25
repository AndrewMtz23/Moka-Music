import unittest
from unittest.mock import patch

from app.controllers.menu_controller import MenuCallbacks, MenuController


class FakeRoot:
    def __init__(self):
        self.config_calls = []

    def config(self, **kwargs):
        self.config_calls.append(kwargs)


class FakeMenu:
    def __init__(self, _parent, tearoff=None):
        self.tearoff = tearoff
        self.commands = []
        self.cascades = []

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_separator(self):
        self.commands.append({"separator": True})

    def add_cascade(self, **kwargs):
        self.cascades.append(kwargs)


def fake_t(key: str, **_kwargs) -> str:
    return key


class MenuControllerTests(unittest.TestCase):
    def callbacks(self):
        calls = []

        def record(name):
            return lambda *args: calls.append((name, args))

        return MenuCallbacks(
            open_main_folder=record("main"),
            open_incoming_folder=record("incoming"),
            select_cover=record("cover"),
            exit_app=record("exit"),
            change_theme=record("theme"),
            show_quality_report=record("quality"),
            show_backup_history=record("history"),
            undo_last_metadata_change=record("undo"),
            change_language=record("language"),
            show_about=record("about"),
        ), calls

    def test_install_sets_menu_on_root(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            MenuController(root, fake_t, callbacks).install()

        self.assertEqual(len(root.config_calls), 1)
        self.assertIn("menu", root.config_calls[0])


if __name__ == "__main__":
    unittest.main()
