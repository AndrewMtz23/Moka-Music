import tempfile
import unittest
from pathlib import Path

from app.controllers.library_ui_controller import LibraryUiController
from app.controllers.metadata_controller import MetadataController
from app.i18n import I18n
from app.models import FilterMode, SortMode, TrackInfo


class FakeTree:
    def __init__(self):
        self.items = []
        self.tags = {}
        self.x_position = None
        self.y_position = None

    def delete(self, *args):
        self.items = []

    def get_children(self):
        return tuple(str(index) for index in range(len(self.items)))

    def insert(self, _parent, _index, text="", values=(), tags=()):
        self.items.append({"text": text, "values": values, "tags": tags})

    def item(self, item_id):
        return self.items[int(item_id)]

    def tag_configure(self, tag, **kwargs):
        self.tags[tag] = kwargs

    def xview_moveto(self, value):
        self.x_position = value

    def yview_moveto(self, value):
        self.y_position = value


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


class FakeLabel:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


def filename_from_item(item):
    tags = item.get("tags", ())
    if tags and tags[0] != "placeholder":
        return tags[0]
    return ""


def theme_colors():
    return {
        "surface": "#111111",
        "surface_alt": "#222222",
        "text": "#eeeeee",
        "text_secondary": "#999999",
        "highlight": "#ffffff",
        "highlight_text": "#000000",
    }


class LibraryUiControllerTests(unittest.TestCase):
    def make_controller(self):
        return LibraryUiController(
            translator=I18n("es").t,
            theme_colors=theme_colors,
            filename_from_item=filename_from_item,
            short_name=lambda filename: Path(filename).stem,
        )

    def test_update_treeview_uses_metadata_for_display_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = MetadataController()
            controller.carpeta = temp_dir
            controller.archivos = ["song.mp3"]
            controller._metadata_cache = {
                "song.mp3": TrackInfo(
                    "song.mp3",
                    str(Path(temp_dir) / "song.mp3"),
                    {"title": "Tema", "artist": "Artista"},
                    0.0,
                    None,
                )
            }
            tree = FakeTree()

            self.make_controller().update_treeview(
                tree=tree,
                files=["song.mp3"],
                controller=controller,
                panel=None,
            )

            self.assertEqual(tree.items[0]["text"], "Artista - Tema")
            self.assertEqual(tree.items[0]["tags"], ("song.mp3", "odd_row"))
            self.assertEqual(tree.x_position, 0)
            self.assertEqual(tree.y_position, 0)

    def test_refresh_tree_applies_search_and_updates_result_label(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = MetadataController()
            controller.carpeta = temp_dir
            controller.archivos = ["visible.mp3", "hidden.mp3"]
            tree = FakeTree()
            panel = {
                "controller": controller,
                "tree": tree,
                "search_var": FakeVar("visible"),
                "filter_var": FakeVar(I18n("es").t("filter.all")),
                "filter_mode": FilterMode.ALL,
                "result_label": FakeLabel(),
            }

            files = self.make_controller().refresh_library_tree(
                controller=controller,
                tree=tree,
                panel=panel,
                filter_mode_from_text=lambda _value: FilterMode.ALL,
            )

            self.assertEqual(files, ["visible.mp3"])
            self.assertEqual(tree.items[0]["tags"][0], "visible.mp3")
            self.assertEqual(panel["result_label"].options["text"], "1 de 2")

    def test_sort_files_uses_injected_mapping(self):
        controller = MetadataController()

        self.make_controller().sort_files(
            controller=controller,
            sort_option="Por album",
            sort_mode_from_text=lambda _value: SortMode.ALBUM,
        )

        self.assertEqual(controller._sort_mode, SortMode.ALBUM)

    def test_can_reorder_only_full_unfiltered_view(self):
        controller = MetadataController()
        controller.archivos = ["one.mp3", "two.mp3"]
        tree = FakeTree()
        ui_controller = self.make_controller()
        ui_controller.update_treeview(tree=tree, files=controller.archivos, controller=controller, panel=None)

        panel = {
            "search_var": FakeVar(""),
            "filter_mode": FilterMode.ALL,
        }
        self.assertTrue(ui_controller.can_reorder_current_view(controller=controller, tree=tree, panel=panel))

        filtered_panel = {
            "search_var": FakeVar("one"),
            "filter_mode": FilterMode.ALL,
        }
        self.assertFalse(
            ui_controller.can_reorder_current_view(controller=controller, tree=tree, panel=filtered_panel)
        )


if __name__ == "__main__":
    unittest.main()
