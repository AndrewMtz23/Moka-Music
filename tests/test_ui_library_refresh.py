import logging
import tempfile
import unittest
from pathlib import Path

from app.controllers.metadata_controller import MetadataController
from app.i18n import I18n
from app.models import FilterMode, TrackInfo
from app.ui import MokaMusicApp


class FakeFileHandler:
    def obtener_nombre_corto(self, filename):
        return Path(filename).stem


class FakeStyleManager:
    def get_theme_colors(self):
        return {
            "surface": "#ffffff",
            "surface_alt": "#eeeeee",
            "text": "#111111",
            "text_secondary": "#666666",
            "highlight": "#111111",
            "highlight_text": "#ffffff",
            "warning": "#92400e",
            "error": "#b91c1c",
        }


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
        item_id = str(len(self.items))
        self.items.append({"text": text, "values": values, "tags": tags})
        return item_id

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

    def set(self, value):
        self.value = value


class FakeLabel:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


class UiLibraryRefreshTests(unittest.TestCase):
    def make_app(self, main_controller=None, incoming_controller=None, main_tree=None, incoming_tree=None):
        app = MokaMusicApp.__new__(MokaMusicApp)
        app.logger = logging.getLogger("tests.ui")
        app.i18n = I18n("es")
        app.t = app.i18n.t
        app.file_handler = FakeFileHandler()
        app.style_manager = FakeStyleManager()
        app.controller_principal = main_controller or MetadataController(translator=app.t)
        app.controller_nueva = incoming_controller or MetadataController(translator=app.t)
        app.tree_principal = main_tree or FakeTree()
        app.tree_nueva = incoming_tree or FakeTree()
        app._library_panels = []
        return app

    def make_panel(self, controller, tree, query="", filter_text=None):
        app = self.make_app(main_controller=controller, main_tree=tree)
        panel = {
            "controller": controller,
            "tree": tree,
            "search_var": FakeVar(query),
            "filter_var": FakeVar(filter_text or app.t("filter.all")),
            "filter_mode": FilterMode.ALL,
            "result_label": FakeLabel(),
        }
        app._library_panels.append(panel)
        return app, panel

    def test_refresh_main_library_renders_controller_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = MetadataController()
            controller.carpeta = temp_dir
            controller.archivos = ["B Song.mp3", "A Song.mp3"]
            controller._metadata_cache = {
                "B Song.mp3": TrackInfo(
                    "B Song.mp3",
                    str(Path(temp_dir) / "B Song.mp3"),
                    {"title": "B Song", "artist": "B", "album": "Album", "year": "2026", "track_number": "1"},
                    0.0,
                    None,
                ),
                "A Song.mp3": TrackInfo(
                    "A Song.mp3",
                    str(Path(temp_dir) / "A Song.mp3"),
                    {"title": "A Song", "artist": "A", "album": "Album", "year": "2026", "track_number": "2"},
                    0.0,
                    None,
                ),
            }
            controller._cover_cache = {"B Song.mp3": True, "A Song.mp3": True}
            tree = FakeTree()
            app, panel = self.make_panel(controller, tree)

            app._refresh_library_tree(controller, tree)

            self.assertEqual([item["text"] for item in tree.items], ["B Song", "A Song"])
            self.assertEqual(tree.items[0]["tags"][0], "B Song.mp3")
            self.assertEqual(panel["result_label"].options["text"], "2 de 2")

    def test_refresh_incoming_library_uses_its_own_controller_and_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            incoming = MetadataController()
            incoming.carpeta = temp_dir
            incoming.archivos = ["incoming.mp3"]
            tree = FakeTree()
            app = self.make_app(incoming_controller=incoming, incoming_tree=tree)
            panel = {
                "controller": incoming,
                "tree": tree,
                "search_var": FakeVar(""),
                "filter_var": FakeVar(app.t("filter.all")),
                "filter_mode": FilterMode.ALL,
                "result_label": FakeLabel(),
            }
            app._library_panels.append(panel)

            app._refresh_library_tree(incoming, tree)

            self.assertEqual(len(tree.items), 1)
            self.assertEqual(tree.items[0]["tags"][0], "incoming.mp3")
            self.assertEqual(app._controller_for_tree(tree), incoming)

    def test_refresh_applies_search_filter_before_rendering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = MetadataController()
            controller.carpeta = temp_dir
            controller.archivos = ["visible-track.mp3", "hidden-track.mp3"]
            controller._metadata_cache = {}
            tree = FakeTree()
            app, panel = self.make_panel(controller, tree, query="visible")

            app._refresh_library_tree(controller, tree)

            self.assertEqual(len(tree.items), 1)
            self.assertEqual(tree.items[0]["tags"][0], "visible-track.mp3")
            self.assertEqual(panel["result_label"].options["text"], "1 de 2")

    def test_empty_message_distinguishes_no_folder_no_audio_and_no_results(self):
        app = self.make_app()
        no_folder = MetadataController(translator=app.t)
        self.assertEqual(
            app._empty_library_message(no_folder),
            "Selecciona una carpeta para ver canciones.",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            no_audio = MetadataController(translator=app.t)
            no_audio.carpeta = temp_dir
            self.assertEqual(
                app._empty_library_message(no_audio),
                "La carpeta cargada no contiene archivos de audio compatibles.",
            )

            filtered = MetadataController(translator=app.t)
            filtered.carpeta = temp_dir
            filtered.archivos = ["song.mp3"]
            panel = {"search_var": FakeVar("zzz"), "filter_mode": FilterMode.ALL}
            self.assertEqual(
                app._empty_library_message(filtered, panel),
                "No hay canciones que coincidan con la busqueda o filtro actual.",
            )

    def test_cleanup_presets_are_normalized_to_known_actions(self):
        app = self.make_app()

        presets = app._normalize_cleanup_presets(
            [
                {"name": "Mi preset", "actions": ["remove_feat", "unknown", "copy_artist"]},
                {"name": "", "actions": ["remove_feat"]},
                {"name": "Vacio", "actions": []},
            ]
        )

        self.assertEqual(presets, [{"name": "Mi preset", "actions": ["remove_feat", "copy_artist"]}])

    def test_cleanup_plan_combines_actions_per_song(self):
        controller = MetadataController(translator=I18n("es").t)
        controller.carpeta = "music"
        controller.archivos = ["song.mp3"]
        controller._metadata_cache = {
            "song.mp3": TrackInfo(
                "song.mp3",
                "music/song.mp3",
                {
                    "title": "Tema (Video Oficial) feat Otro",
                    "artist": "Cantante feat Invitado",
                    "album_artist": "",
                },
                0.0,
                None,
            )
        }
        tree = FakeTree()
        app = self.make_app(main_controller=controller, main_tree=tree)

        plan = app._cleanup_controller().build_plan(
            [(controller, tree, ["song.mp3"])],
            ["remove_feat", "remove_parentheses", "copy_artist"],
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][3]["title"], "Tema")
        self.assertEqual(plan[0][3]["artist"], "Cantante")
        self.assertEqual(plan[0][3]["album_artist"], "Cantante")


if __name__ == "__main__":
    unittest.main()
