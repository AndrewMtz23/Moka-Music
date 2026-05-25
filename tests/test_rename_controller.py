import tempfile
import unittest
from pathlib import Path

from app.controllers.rename_controller import RenameController, RenamePlanItem
from app.models import TrackInfo


class FakeSongInfo:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, path):
        self.invalidated.append(path)


class FakeController:
    def __init__(self, folder, files, metadata):
        self.carpeta = str(folder)
        self.archivos = list(files)
        self.metadata = metadata

    def get_track_info(self, filename):
        return TrackInfo(filename, str(Path(self.carpeta) / filename), self.metadata.get(filename, {}), 0.0, None)

    def rename_file(self, old_name, new_name):
        index = self.archivos.index(old_name)
        self.archivos[index] = new_name


class RenameControllerTests(unittest.TestCase):
    def test_build_plan_uses_metadata_and_avoids_duplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(
                temp_dir,
                ["old.mp3", "taken.mp3"],
                {
                    "old.mp3": {
                        "track_number": "1",
                        "artist": "Artist",
                        "title": "Title",
                    }
                },
            )

            plan = RenameController().build_plan([(controller, "tree", ["old.mp3"])])

            self.assertEqual(len(plan), 1)
            self.assertEqual(plan[0].old_name, "old.mp3")
            self.assertEqual(plan[0].new_name, "01. Artist - Title.mp3")

    def test_build_plan_skips_unchanged_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(temp_dir, ["same.mp3"], {"same.mp3": {"title": "same"}})

            plan = RenameController().build_plan([(controller, "tree", ["same.mp3"])])

            self.assertEqual(plan, [])

    def test_execute_plan_renames_files_and_updates_preview_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "old.mp3").write_bytes(b"audio")
            controller = FakeController(folder, ["old.mp3"], {})
            song_info = FakeSongInfo()
            plan = [RenamePlanItem(controller, "tree", "old.mp3", "new.mp3")]

            result = RenameController().execute_plan(
                plan,
                song_info=song_info,
                preview_controller=controller,
                preview_filename="old.mp3",
            )

            self.assertEqual(result.renamed, 1)
            self.assertEqual(result.errors, [])
            self.assertFalse((folder / "old.mp3").exists())
            self.assertTrue((folder / "new.mp3").exists())
            self.assertEqual(controller.archivos, ["new.mp3"])
            self.assertEqual(result.preview_filename, "new.mp3")
            self.assertEqual(result.changed_pairs, {(id(controller), id("tree"))})
            self.assertEqual(
                song_info.invalidated,
                [str(folder / "old.mp3"), str(folder / "new.mp3")],
            )


if __name__ == "__main__":
    unittest.main()
