import unittest

from app.controllers.selection_controller import SelectionController


class FakeController:
    def __init__(self, folder="music"):
        self.carpeta = folder


class FakeTree:
    def __init__(self, items):
        self.items = items

    def selection(self):
        return list(self.items.keys())

    def item(self, item_id):
        return self.items[item_id]


def filename_from_item(item):
    for tag in item.get("tags", ()):
        if tag not in {"odd_row", "even_row", "placeholder"}:
            return tag
    return ""


class SelectionControllerTests(unittest.TestCase):
    def test_panel_lookup_by_search_and_library(self):
        controller = FakeController()
        tree = object()
        search_var = object()
        panel = {"controller": controller, "tree": tree, "search_var": search_var}
        selector = SelectionController(filename_from_item)

        self.assertIs(selector.panel_for_search([panel], search_var), panel)
        self.assertIs(selector.panel_for_library([panel], controller, tree), panel)

    def test_controller_and_tree_mapping(self):
        main_controller = FakeController()
        incoming_controller = FakeController()
        main_tree = object()
        incoming_tree = object()
        selector = SelectionController(filename_from_item)

        self.assertIs(
            selector.controller_for_tree(
                main_tree,
                main_controller=main_controller,
                main_tree=main_tree,
                incoming_controller=incoming_controller,
                incoming_tree=incoming_tree,
            ),
            main_controller,
        )
        self.assertIs(
            selector.tree_for_controller(
                incoming_controller,
                main_controller=main_controller,
                main_tree=main_tree,
                incoming_controller=incoming_controller,
                incoming_tree=incoming_tree,
            ),
            incoming_tree,
        )

    def test_selected_filenames_by_controller_deduplicates_visual_rows(self):
        controller = FakeController()
        tree = FakeTree(
            {
                "1": {"tags": ("odd_row", "a.mp3")},
                "2": {"tags": ("even_row", "a.mp3")},
                "3": {"tags": ("placeholder",)},
                "4": {"tags": ("b.mp3",)},
            }
        )
        selector = SelectionController(filename_from_item)

        selections = selector.selected_filenames_by_controller([(controller, tree)])

        self.assertEqual(selections, [(controller, tree, ["a.mp3", "b.mp3"])])


if __name__ == "__main__":
    unittest.main()
