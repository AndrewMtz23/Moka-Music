import tempfile
import unittest
from pathlib import Path

from app.controllers.metadata_apply_controller import MetadataApplyController
from app.models import ActionResult


class FakeSongInfo:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, path):
        self.invalidated.append(path)


class FakeController:
    def __init__(self, folder, files=None, *, fail=False):
        self.carpeta = str(folder)
        self.archivos = ["a.mp3"] if files is None else files
        self.portada_path = "cover.jpg"
        self.fail = fail
        self.single_calls = []
        self.group_calls = []
        self.all_calls = []

    def aplicar_cambios_a_archivo(self, filename, metadata, cover_path=None):
        self.single_calls.append((filename, metadata, cover_path))
        if self.fail:
            return ActionResult.fail("failed", errors=[f"{filename}: error"])
        return ActionResult.ok("saved")

    def aplicar_cambios_a_archivos(self, filenames, metadata, cover_path=None):
        self.group_calls.append((filenames, metadata, cover_path))
        if self.fail:
            return 0, [f"{filenames[0]}: error"]
        return len(filenames), []

    def aplicar_cambios(self, metadata):
        self.all_calls.append(metadata)
        if self.fail:
            return 0, ["error"]
        return len(self.archivos), []


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeTree:
    def __init__(self, selection=None, items=None):
        self._selection = selection or []
        self._items = items or {}

    def selection(self):
        return self._selection

    def item(self, item_id):
        return self._items[item_id]


class MetadataApplyControllerTests(unittest.TestCase):
    def test_metadata_from_vars_ignores_empty_values(self):
        result = MetadataApplyController().metadata_from_vars(
            {
                "title": FakeVar("  Capos  "),
                "artist": FakeVar(""),
                "album": FakeVar("   "),
            }
        )

        self.assertEqual(result, {"title": "Capos"})

    def test_first_selected_target_returns_first_valid_song(self):
        controller_without_folder = FakeController("", files=["skip.mp3"])
        controller_without_folder.carpeta = ""
        valid_controller = FakeController("music", files=["song.mp3"])
        empty_tree = FakeTree(selection=["x"], items={"x": {"values": ["skip.mp3"]}})
        valid_tree = FakeTree(selection=["y"], items={"y": {"values": ["song.mp3"]}})

        result = MetadataApplyController().first_selected_target(
            [(empty_tree, controller_without_folder), (valid_tree, valid_controller)],
            lambda item: item["values"][0],
        )

        self.assertEqual(result, (valid_controller, valid_tree, "song.mp3"))

    def test_all_files_target_prefers_primary_library(self):
        primary = FakeController("main", files=["a.mp3"])
        incoming = FakeController("incoming", files=["b.mp3"])
        primary_tree = object()
        incoming_tree = object()

        result = MetadataApplyController().all_files_target(
            primary_controller=primary,
            primary_tree=primary_tree,
            incoming_controller=incoming,
            incoming_tree=incoming_tree,
        )

        self.assertEqual(result, (primary, primary_tree, ["a.mp3"]))

    def test_all_files_target_uses_incoming_when_primary_is_empty(self):
        primary = FakeController("main", files=[])
        incoming = FakeController("incoming", files=["b.mp3"])
        primary_tree = object()
        incoming_tree = object()

        result = MetadataApplyController().all_files_target(
            primary_controller=primary,
            primary_tree=primary_tree,
            incoming_controller=incoming,
            incoming_tree=incoming_tree,
        )

        self.assertEqual(result, (incoming, incoming_tree, ["b.mp3"]))

    def test_preview_target_requires_active_song(self):
        controller = FakeController("main", files=["a.mp3"])
        tree = object()

        self.assertIsNone(
            MetadataApplyController().preview_target(
                controller=None,
                filename="a.mp3",
                current_song={"title": "A"},
                tree_for_controller=lambda _controller: tree,
            )
        )

        result = MetadataApplyController().preview_target(
            controller=controller,
            filename="a.mp3",
            current_song={"title": "A"},
            tree_for_controller=lambda _controller: tree,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.controller, controller)
        self.assertEqual(result.tree, tree)
        self.assertEqual(result.filename, "a.mp3")
        self.assertEqual(result.current_song, {"title": "A"})

    def test_selected_count_sums_group_filenames(self):
        self.assertEqual(
            MetadataApplyController().selected_count(
                [
                    (object(), object(), ["a.mp3", "b.mp3"]),
                    (object(), object(), ["c.mp3"]),
                ]
            ),
            3,
        )

    def test_apply_single_invalidates_and_marks_changed_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(temp_dir)
            tree = object()
            song_info = FakeSongInfo()

            result = MetadataApplyController().apply_single(
                controller=controller,
                tree=tree,
                filename="a.mp3",
                metadata={"artist": "New"},
                cover_path="cover.jpg",
                song_info=song_info,
            )

            self.assertTrue(result.success)
            self.assertEqual(controller.single_calls, [("a.mp3", {"artist": "New"}, "cover.jpg")])
            self.assertEqual(song_info.invalidated, [str(Path(temp_dir) / "a.mp3")])
            self.assertEqual(result.changed_pairs, {(id(controller), id(tree))})

    def test_apply_groups_reports_preview_and_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(temp_dir, files=["a.mp3", "b.mp3"])
            tree = object()
            song_info = FakeSongInfo()

            result = MetadataApplyController().apply_groups(
                groups=[(controller, tree, ["a.mp3", "b.mp3"])],
                metadata={"album": "Album"},
                song_info=song_info,
                preview_controller=controller,
                preview_filename="b.mp3",
            )

            self.assertEqual(result.success_count, 2)
            self.assertEqual(result.errors, [])
            self.assertTrue(result.affected_preview)
            self.assertEqual(result.changed_pairs, {(id(controller), id(tree))})
            self.assertEqual(
                song_info.invalidated,
                [str(Path(temp_dir) / "a.mp3"), str(Path(temp_dir) / "b.mp3")],
            )

    def test_apply_all_invalidates_loaded_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(temp_dir, files=["a.mp3", "b.mp3"])
            song_info = FakeSongInfo()

            success_count, errors = MetadataApplyController().apply_all(
                controller=controller,
                metadata={"genre": "Rock"},
                song_info=song_info,
            )

            self.assertEqual(success_count, 2)
            self.assertEqual(errors, [])
            self.assertEqual(controller.all_calls, [{"genre": "Rock"}])
            self.assertEqual(
                song_info.invalidated,
                [str(Path(temp_dir) / "a.mp3"), str(Path(temp_dir) / "b.mp3")],
            )


if __name__ == "__main__":
    unittest.main()
