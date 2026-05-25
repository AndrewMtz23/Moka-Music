import tempfile
import unittest
from pathlib import Path

from app.controllers.add_music_controller import agregar_a_lista
from app.controllers.metadata_controller import MetadataController
from app.services.song_info_service import SongInfo
from app.ui_helpers.file_dialogs import FileHandler


class FakeTree:
    def __init__(self):
        self.items = []

    def delete(self, *args):
        self.items = []

    def get_children(self):
        return list(range(len(self.items)))

    def insert(self, _parent, _index, values=None, tags=None):
        self.items.append({"values": values, "tags": tags})


class AddSongTests(unittest.TestCase):
    def test_add_song_copies_file_into_destination_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            dest_dir = Path(temp_dir) / "dest"
            source_dir.mkdir()
            dest_dir.mkdir()

            source_file = source_dir / "track.mp3"
            source_file.write_bytes(b"fake-audio")

            controller = MetadataController()
            controller.carpeta = str(dest_dir)
            tree = FakeTree()

            result = agregar_a_lista(
                str(source_file),
                controller,
                tree,
                file_handler=FileHandler(),
                song_info=SongInfo(),
            )

            self.assertTrue(result.success)
            self.assertTrue((dest_dir / "track.mp3").exists())
            self.assertIn("track.mp3", controller.archivos)
            self.assertEqual(len(tree.items), 0)
