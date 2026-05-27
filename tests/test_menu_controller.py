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
            get_recent_folders=lambda: [{"folder": "C:/Music/Main", "target": "main"}],
            open_recent_folder=record("recent"),
            clear_recent_folders=record("clear_recent"),
            export_playlist=record("export_playlist"),
            export_library_view_json=record("export_library_view_json"),
            export_selected=record("export_selected"),
            export_library_report=record("export_library_report"),
            import_metadata_json=record("import_metadata_json"),
            select_cover=record("cover"),
            exit_app=record("exit"),
            change_theme=record("theme"),
            show_theme_settings=record("theme_settings"),
            save_current_theme=record("save_theme"),
            manage_custom_themes=record("manage_themes"),
            import_theme=record("import_theme"),
            export_theme=record("export_theme"),
            toggle_fullscreen=record("fullscreen"),
            select_all=record("select_all"),
            deselect_all=record("deselect_all"),
            invert_selection=record("invert_selection"),
            show_quality_report=record("quality"),
            show_library_stats=record("stats"),
            show_library_comparison=record("compare"),
            show_playback_history=record("playback_history"),
            complete_metadata_online=record("complete_online"),
            find_missing_covers=record("missing_covers"),
            normalize_metadata=record("normalize_metadata"),
            search_replace_metadata=record("search_replace_metadata"),
            convert_audio=record("convert_audio"),
            show_backup_history=record("history"),
            undo_last_metadata_change=record("undo"),
            undo=record("global_undo"),
            redo=record("global_redo"),
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

    def test_theme_menu_opens_appearance_settings(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        theme_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.theme")
        self.assertEqual(
            [command.get("label") for command in theme_menu.commands if "label" in command],
            [
                "menu.customize_theme",
                "menu.save_theme_as",
                "menu.manage_themes",
                "menu.import_theme",
                "menu.export_theme",
                "menu.fullscreen",
            ],
        )

    def test_file_menu_includes_recent_folders_submenu(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        file_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.file")
        recent_cascade = next(cascade for cascade in file_menu.cascades if cascade["label"] == "menu.open_recent")
        recent_menu = recent_cascade["menu"]

        self.assertEqual(recent_menu.commands[0]["label"], "panel.main_library: Main")
        self.assertEqual(recent_menu.commands[-1]["label"], "menu.clear_recent_folders")

    def test_file_menu_includes_phase_two_export_and_import_actions(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        file_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.file")
        labels = [command.get("label") for command in file_menu.commands if "label" in command]

        self.assertIn("menu.export_selected", labels)
        self.assertIn("menu.export_library_report", labels)
        self.assertIn("menu.import_metadata_json", labels)

    def test_edit_menu_includes_selection_actions(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        edit_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.edit")
        labels = [command.get("label") for command in edit_menu.commands if "label" in command]

        self.assertEqual(
            labels[:3],
            ["menu.select_all", "menu.deselect_all", "menu.invert_selection"],
        )

    def test_tools_menu_includes_metadata_submenu(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        tools_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.tools")
        metadata_cascade = next(cascade for cascade in tools_menu.cascades if cascade["label"] == "menu.metadata_tools")
        labels = [command.get("label") for command in metadata_cascade["menu"].commands if "label" in command]

        self.assertEqual(
            labels,
            [
                "menu.complete_metadata_online",
                "menu.find_missing_covers",
                "menu.normalize_metadata",
                "menu.search_replace_metadata",
            ],
        )


if __name__ == "__main__":
    unittest.main()
