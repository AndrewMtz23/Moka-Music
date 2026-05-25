import unittest

from app.controllers.ui_text_controller import UiTextController
from app.models import FilterMode, SortMode


def fake_t(key: str, **kwargs) -> str:
    return key


class FakeWidget:
    def __init__(self):
        self.options = {}
        self.headings = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def heading(self, column, **kwargs):
        self.headings[column] = kwargs


class FakeVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class FakeController:
    def __init__(self):
        self._sort_mode = SortMode.ALBUM


class UiTextControllerTests(unittest.TestCase):
    def test_refresh_text_widgets_uses_registered_keys(self):
        widget = FakeWidget()

        UiTextController(fake_t).refresh_text_widgets({"artist_label": widget})

        self.assertEqual(widget.options["text"], "metadata.artist")

    def test_refresh_tree_headings(self):
        tree = FakeWidget()

        UiTextController(fake_t).refresh_tree_headings(tree)

        self.assertEqual(tree.headings["#0"], {"text": "tree.song_name"})
        self.assertEqual(tree.headings["path"], {"text": "tree.file_path"})

    def test_refresh_sort_widgets_updates_values_and_current_text(self):
        menu = FakeWidget()
        var = FakeVar()

        UiTextController(fake_t).refresh_sort_widgets(
            [(menu, var, FakeController())],
            sort_options=["name", "album"],
            sort_text_for_mode=lambda mode: f"mode:{mode.name}",
        )

        self.assertEqual(menu.options["values"], ["name", "album"])
        self.assertEqual(var.value, "mode:ALBUM")

    def test_refresh_library_panels_updates_filter_and_calls_refresh_hooks(self):
        filter_menu = FakeWidget()
        filter_var = FakeVar()
        calls = []
        panel = {
            "filter_menu": filter_menu,
            "filter_var": filter_var,
            "filter_mode": FilterMode.MISSING_ARTIST,
            "tree": "tree",
            "controller": "controller",
        }

        UiTextController(fake_t).refresh_library_panels(
            [panel],
            filter_options=["all", "missing"],
            filter_text_for_mode=lambda mode: f"filter:{mode.name}",
            refresh_search_placeholder=lambda panel: calls.append(("placeholder", panel)),
            apply_tree_colors=lambda tree: calls.append(("colors", tree)),
            refresh_library_tree=lambda controller, tree: calls.append(("refresh", controller, tree)),
        )

        self.assertEqual(filter_menu.options["values"], ["all", "missing"])
        self.assertEqual(filter_var.value, "filter:MISSING_ARTIST")
        self.assertEqual(calls[0][0], "placeholder")
        self.assertEqual(calls[1], ("colors", "tree"))
        self.assertEqual(calls[2], ("refresh", "controller", "tree"))


if __name__ == "__main__":
    unittest.main()
