import tempfile
import unittest
from pathlib import Path

from app.controllers.metadata_controller import MetadataController
from app.controllers.song_actions_controller import SongActions


class FakeTree:
    def __init__(self):
        self.items = []

    def delete(self, *args):
        self.items = []

    def insert(self, _parent, _index, values=None, tags=None):
        self.items.append({"values": values, "tags": tags})

    def get_children(self):
        return list(range(len(self.items)))


class FakePreview:
    def __init__(self):
        self.cleared = False
        self.updated = None

    def clear_preview(self):
        self.cleared = True

    def update_preview(self, metadata):
        self.updated = metadata


class SongActionsTests(unittest.TestCase):
    def test_move_song_updates_both_controllers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            dest_dir = root / "dest"
            source_dir.mkdir()
            dest_dir.mkdir()
            (source_dir / "track.mp3").write_bytes(b"fake")

            origin = MetadataController()
            origin.carpeta = str(source_dir)
            origin.archivos = ["track.mp3"]

            destination = MetadataController()
            destination.carpeta = str(dest_dir)
            destination.archivos = []

            actions = SongActions()
            result = actions.mover_cancion(
                origin,
                destination,
                "track.mp3",
                FakeTree(),
                FakeTree(),
                FakePreview(),
            )

            self.assertTrue(result.success)
            self.assertFalse((source_dir / "track.mp3").exists())
            self.assertTrue((dest_dir / "track.mp3").exists())
            self.assertNotIn("track.mp3", origin.archivos)
            self.assertIn("track.mp3", destination.archivos)

    def test_move_song_does_not_render_trees_directly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            dest_dir = root / "dest"
            source_dir.mkdir()
            dest_dir.mkdir()
            (source_dir / "track.mp3").write_bytes(b"fake")

            origin = MetadataController()
            origin.carpeta = str(source_dir)
            origin.archivos = ["track.mp3"]

            destination = MetadataController()
            destination.carpeta = str(dest_dir)
            destination.archivos = []

            origin_tree = FakeTree()
            destination_tree = FakeTree()
            actions = SongActions()

            result = actions.mover_cancion(
                origin,
                destination,
                "track.mp3",
                origin_tree,
                destination_tree,
                FakePreview(),
            )

            self.assertTrue(result.success)
            self.assertEqual(origin_tree.items, [])
            self.assertEqual(destination_tree.items, [])

    def test_rename_song_changes_filename_on_disk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "old.mp3").write_bytes(b"fake")

            controller = MetadataController()
            controller.carpeta = str(folder)
            controller.archivos = ["old.mp3"]

            actions = SongActions()
            result = actions.renombrar_cancion(
                controller,
                "old.mp3",
                "new_name",
                FakeTree(),
                FakePreview(),
            )

            self.assertTrue(result.success)
            self.assertTrue((folder / "new_name.mp3").exists())
            self.assertIn("new_name.mp3", controller.archivos)
