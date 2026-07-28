import unittest
from unittest.mock import patch

from app.controllers.menu_controller import MenuCallbacks, MenuController


class FakeRoot:
    def __init__(self):
        self.config_calls = []
        self.children = []

    def config(self, **kwargs):
        self.config_calls.append(kwargs)

    def pack_slaves(self):
        return self.children

    def option_get(self, *_args):
        return ""


class FakeMenu:
    def __init__(self, _parent, tearoff=None, **kwargs):
        self.tearoff = tearoff
        self.kwargs = kwargs
        self.commands = []
        self.cascades = []

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_separator(self):
        self.commands.append({"separator": True})

    def add_cascade(self, **kwargs):
        self.cascades.append(kwargs)

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)


class FakeFrame:
    def __init__(self, parent, **kwargs):
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls = []
        self.destroyed = False
        if hasattr(parent, "children"):
            parent.children.append(self)

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def destroy(self):
        self.destroyed = True


class FakeMenubutton:
    def __init__(self, parent, **kwargs):
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls = []

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)


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
            analyze_audio_quality=record("analyze_audio_quality"),
            detect_advanced_duplicates=record("advanced_duplicates"),
            validate_audio_files=record("validate_audio_files"),
            convert_audio=record("convert_audio"),
            rename_files_by_template=record("rename_template"),
            organize_files_by_folders=record("organize_files"),
            validate_playlist=record("validate_playlist"),
            generate_smart_playlist=record("smart_playlist"),
            show_backup_history=record("history"),
            undo_last_metadata_change=record("undo"),
            undo=record("global_undo"),
            redo=record("global_redo"),
            change_language=record("language"),
            get_current_language=lambda: "es",
            detect_system_language=record("detect_language"),
            report_missing_translations=record("missing_translations"),
            show_quick_guide=record("quick_guide"),
            show_shortcuts=record("shortcuts"),
            view_logs=record("logs"),
            open_backup_folder=record("backup_folder"),
            show_system_diagnostics=record("diagnostics"),
            show_about=record("about"),
        ), calls

    def test_install_sets_menu_on_root(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with (
            patch("app.controllers.menu_controller.tk.Menu", FakeMenu),
            patch("app.controllers.menu_controller.tk.Frame", FakeFrame),
            patch("app.controllers.menu_controller.tk.Menubutton", FakeMenubutton),
        ):
            MenuController(root, fake_t, callbacks).install()

        self.assertEqual(len(root.config_calls), 1)
        self.assertEqual(root.config_calls[0]["menu"], "")
        self.assertTrue(root.children[0].pack_calls)

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

    def test_tools_menu_includes_audio_submenu(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        tools_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.tools")
        audio_cascade = next(cascade for cascade in tools_menu.cascades if cascade["label"] == "menu.audio_tools")
        labels = [command.get("label") for command in audio_cascade["menu"].commands if "label" in command]

        self.assertEqual(
            labels,
            [
                "menu.analyze_audio_quality",
                "menu.detect_advanced_duplicates",
                "menu.validate_audio_files",
                "menu.convert_audio",
            ],
        )

    def test_tools_menu_includes_organization_submenu(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        tools_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.tools")
        organization_cascade = next(
            cascade for cascade in tools_menu.cascades if cascade["label"] == "menu.organization_tools"
        )
        labels = [command.get("label") for command in organization_cascade["menu"].commands if "label" in command]

        self.assertEqual(
            labels,
            [
                "menu.rename_by_template",
                "menu.organize_files",
                "menu.validate_playlist",
                "menu.generate_smart_playlist",
            ],
        )

    def test_menu_uses_theme_colors_when_provided(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()
        colors = {
            "surface": "#111111",
            "text": "#eeeeee",
            "primary": "#ff00ff",
            "button_text": "#000000",
            "disabled": "#777777",
        }

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks, colors).build()

        self.assertEqual(menu.kwargs["background"], "#111111")
        self.assertEqual(menu.kwargs["foreground"], "#eeeeee")
        self.assertEqual(menu.kwargs["activebackground"], "#ff00ff")

    def test_language_menu_marks_active_language_and_includes_tools(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        language_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.language")
        labels = [command.get("label") for command in language_menu.commands if "label" in command]

        self.assertEqual(labels[:2], ["✓ menu.language_es", "menu.language_en"])
        self.assertIn("menu.detect_system_language", labels)
        self.assertIn("menu.report_missing_translations", labels)

    def test_help_menu_includes_support_actions(self):
        root = FakeRoot()
        callbacks, _calls = self.callbacks()

        with patch("app.controllers.menu_controller.tk.Menu", FakeMenu):
            menu = MenuController(root, fake_t, callbacks).build()

        help_menu = next(cascade["menu"] for cascade in menu.cascades if cascade["label"] == "menu.help")
        labels = [command.get("label") for command in help_menu.commands if "label" in command]

        self.assertEqual(
            labels,
            [
                "menu.quick_guide",
                "menu.shortcuts",
                "menu.view_logs",
                "menu.open_backup_folder",
                "menu.system_diagnostics",
                "menu.about",
            ],
        )


if __name__ == "__main__":
    unittest.main()
