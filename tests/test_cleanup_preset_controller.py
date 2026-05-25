import unittest

from app.controllers.cleanup_preset_controller import CleanupPresetController


class FakeMenu:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class CleanupPresetControllerTests(unittest.TestCase):
    def test_refresh_menu_sets_names_and_selects_first_when_needed(self):
        controller = CleanupPresetController()
        menu = FakeMenu()
        variable = FakeVar("missing")

        controller.refresh_menu(
            [{"name": "Uno", "actions": ["remove_feat"]}],
            menu,
            variable,
        )

        self.assertEqual(menu.options["values"], ["Uno"])
        self.assertEqual(variable.get(), "Uno")

    def test_selected_upsert_and_delete_preset(self):
        controller = CleanupPresetController()
        presets = [{"name": "Uno", "actions": ["remove_feat"]}]

        self.assertEqual(controller.selected_preset(presets, "Uno"), presets[0])
        self.assertEqual(controller.preset_index_by_name(presets, "uno"), 0)

        created = controller.upsert_preset(
            presets,
            name="Dos",
            actions=["copy_artist"],
            replace_existing=False,
        )
        self.assertFalse(created.replaced)
        self.assertEqual(len(created.presets), 2)

        replaced = controller.upsert_preset(
            created.presets,
            name="Uno",
            actions=["title_only"],
            replace_existing=True,
        )
        self.assertTrue(replaced.replaced)
        self.assertEqual(replaced.presets[0]["actions"], ["title_only"])

        deleted = controller.delete_preset(replaced.presets, "Uno")
        self.assertEqual(deleted, [{"name": "Dos", "actions": ["copy_artist"]}])


if __name__ == "__main__":
    unittest.main()
