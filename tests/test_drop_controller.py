import tempfile
import unittest
from pathlib import Path

from app.controllers.drop_controller import DropController


def fake_t(key: str, **kwargs) -> str:
    if kwargs:
        args = ",".join(f"{name}={value}" for name, value in sorted(kwargs.items()))
        return f"{key}({args})"
    return key


class FakeSongInfo:
    def get_metadata(self, filepath):
        return {"title": Path(filepath).stem}


class FakeController:
    def __init__(self, folder):
        self.carpeta = str(folder)
        self.archivos = []

    def register_file(self, filename):
        self.archivos.append(filename)


class DropControllerTests(unittest.TestCase):
    def test_parse_paths_uses_splitlist_and_strips_tk_braces(self):
        raw = "{C:/Music/one.mp3} {C:/Cover Art/cover.jpg}"

        paths = DropController().parse_paths(
            raw,
            splitlist=lambda _raw: ("{C:/Music/one.mp3}", "{C:/Cover Art/cover.jpg}"),
        )

        self.assertEqual(paths, ["C:/Music/one.mp3", "C:/Cover Art/cover.jpg"])

    def test_classify_paths_splits_folders_audio_and_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            library = folder / "library"
            library.mkdir()
            audio = folder / "song.m4a"
            audio.write_bytes(b"audio")
            image = folder / "cover.png"
            image.write_bytes(b"image")
            ignored = folder / "notes.txt"
            ignored.write_text("nope", encoding="utf-8")

            payload = DropController().classify_paths([str(library), str(audio), str(image), str(ignored)])

            self.assertEqual(payload.folders, [str(library)])
            self.assertEqual(payload.audio_files, [str(audio)])
            self.assertEqual(payload.image_files, [str(image)])

    def test_add_audio_files_copies_into_controller_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            source.write_bytes(b"audio")
            destination = root / "library"
            destination.mkdir()
            controller = FakeController(destination)

            result = DropController().add_audio_files(
                [str(source)],
                controller=controller,
                song_info=FakeSongInfo(),
                translator=fake_t,
            )

            self.assertEqual(result.added, 1)
            self.assertEqual(result.errors, [])
            self.assertTrue((destination / "source.mp3").exists())
            self.assertEqual(controller.archivos, ["source.mp3"])


if __name__ == "__main__":
    unittest.main()
