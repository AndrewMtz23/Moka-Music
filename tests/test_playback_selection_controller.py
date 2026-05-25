import unittest

from app.controllers.playback_selection_controller import PlaybackSelectionController


class FakeController:
    def __init__(self, folder="music"):
        self.carpeta = folder


class FakeTree:
    def __init__(self, items, selected=None):
        self.items = items
        self.selected = selected or []

    def selection(self):
        return tuple(self.selected)

    def get_children(self):
        return tuple(self.items.keys())

    def item(self, item_id):
        return self.items[item_id]


def filename_from_item(item):
    tags = item.get("tags", ())
    return tags[0] if tags else ""


class PlaybackSelectionControllerTests(unittest.TestCase):
    def test_selected_track_returns_filename_and_filepath(self):
        tree = FakeTree({"0": {"tags": ("song.mp3",)}}, selected=["0"])

        selected = PlaybackSelectionController(filename_from_item).selected_track(
            FakeController("library"),
            tree,
        )

        self.assertEqual(selected.item_id, "0")
        self.assertEqual(selected.filename, "song.mp3")
        self.assertEqual(selected.filepath, "library\\song.mp3")

    def test_relative_item_moves_with_bounds(self):
        tree = FakeTree(
            {"0": {"tags": ("a.mp3",)}, "1": {"tags": ("b.mp3",)}},
            selected=["0"],
        )
        controller = PlaybackSelectionController(filename_from_item)

        self.assertEqual(controller.relative_item(tree, offset=1, shuffle=False), "1")
        self.assertIsNone(controller.relative_item(tree, offset=-1, shuffle=False))

    def test_relative_item_uses_shuffle_for_next_track(self):
        tree = FakeTree(
            {
                "0": {"tags": ("a.mp3",)},
                "1": {"tags": ("b.mp3",)},
                "2": {"tags": ("c.mp3",)},
            },
            selected=["0"],
        )
        controller = PlaybackSelectionController(filename_from_item, chooser=lambda candidates: candidates[-1])

        self.assertEqual(controller.relative_item(tree, offset=1, shuffle=True), "2")


if __name__ == "__main__":
    unittest.main()
