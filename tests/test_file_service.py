import tempfile
import unittest
from pathlib import Path

from app.controllers.metadata_controller import MetadataController
from app.services.file_service import (
    add_song_to_library,
    delete_song,
    is_supported_audio_file,
    is_supported_image_file,
    list_audio_files,
    move_song_between_libraries,
    parse_dropped_audio_files,
    rename_song,
    sanitize_filename,
    shorten_filename,
)


def fake_t(key: str, **kwargs) -> str:
    if kwargs:
        args = ",".join(f"{name}={value}" for name, value in sorted(kwargs.items()))
        return f"{key}({args})"
    return key


class FakeSongInfo:
    def get_metadata(self, filepath: str):
        return {"title": Path(filepath).stem}


class FileServiceTests(unittest.TestCase):
    def test_sanitize_filename_replaces_invalid_chars(self):
        self.assertEqual(sanitize_filename(' a<b>c:"d"/e\\f|g?h* '), "a_b_c__d__e_f_g_h_")

    def test_file_helpers_filter_and_format_supported_files(self):
        self.assertTrue(is_supported_audio_file("song.mp3"))
        self.assertTrue(is_supported_image_file("cover.png"))
        self.assertFalse(is_supported_audio_file("notes.txt"))

        self.assertEqual(shorten_filename("very-long-track-name.mp3", max_len=12), "very-....mp3")
        self.assertEqual(parse_dropped_audio_files("{C:/Music/a.mp3} C:/Music/b.txt C:/Music/c.flac"), ["C:/Music/a.mp3", "C:/Music/c.flac"])

    def test_list_audio_files_returns_sorted_supported_filenames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "b.wav").write_bytes(b"fake")
            (folder / "a.mp3").write_bytes(b"fake")
            (folder / "Artist").mkdir()
            (folder / "Artist" / "c.flac").write_bytes(b"fake")
            (folder / "cover.jpg").write_bytes(b"fake")

            self.assertEqual(list_audio_files(folder), ["a.mp3", "Artist/c.flac", "b.wav"])

    def test_add_song_to_library_copies_file_and_registers_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            source.write_bytes(b"fake")
            destination = root / "library"
            destination.mkdir()

            controller = MetadataController()
            controller.carpeta = str(destination)

            result = add_song_to_library(
                str(source),
                controller,
                song_info=FakeSongInfo(),
                translator=fake_t,
            )

            self.assertTrue(result.success)
            self.assertTrue((destination / "source.mp3").exists())
            self.assertIn("source.mp3", controller.archivos)
            self.assertEqual(result.data["metadata"], {"title": "source"})

    def test_move_song_between_libraries_updates_both_controllers(self):
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

            result = move_song_between_libraries(origin, destination, "track.mp3", translator=fake_t)

            self.assertTrue(result.success)
            self.assertFalse((source_dir / "track.mp3").exists())
            self.assertTrue((dest_dir / "track.mp3").exists())
            self.assertNotIn("track.mp3", origin.archivos)
            self.assertIn("track.mp3", destination.archivos)

    def test_rename_and_delete_song_update_controller(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "old.mp3").write_bytes(b"fake")

            controller = MetadataController()
            controller.carpeta = str(folder)
            controller.archivos = ["old.mp3"]

            rename_result = rename_song(controller, "old.mp3", "new:name", translator=fake_t)

            self.assertTrue(rename_result.success)
            self.assertTrue((folder / "new_name.mp3").exists())
            self.assertIn("new_name.mp3", controller.archivos)

            delete_result = delete_song(controller, "new_name.mp3", move_to_trash=False, translator=fake_t)

            self.assertTrue(delete_result.success)
            self.assertFalse((folder / "new_name.mp3").exists())
            self.assertNotIn("new_name.mp3", controller.archivos)


if __name__ == "__main__":
    unittest.main()
