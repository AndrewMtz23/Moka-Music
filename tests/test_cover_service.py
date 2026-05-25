import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.services.cover_service import COVER_FILENAME, find_folder_cover, process_cover_image, replace_folder_cover


class CoverServiceTests(unittest.TestCase):
    def test_find_folder_cover_prefers_known_cover_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio = folder / "song.mp3"
            audio.write_bytes(b"audio")
            Image.new("RGB", (100, 100), color="blue").save(folder / "random.png")
            Image.new("RGB", (10, 10), color="red").save(folder / "cover.jpg")
            Image.new("RGB", (10, 10), color="green").save(folder / "PORTADA.jpg")

            self.assertEqual(find_folder_cover(audio), str(folder / "PORTADA.jpg"))

    def test_find_folder_cover_falls_back_to_largest_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio = folder / "song.mp3"
            audio.write_bytes(b"audio")
            Image.new("RGB", (5, 5), color="red").save(folder / "small.jpg")
            Image.new("RGB", (100, 100), color="blue").save(folder / "large.jpg")

            self.assertEqual(find_folder_cover(audio), str(folder / "large.jpg"))

    def test_process_cover_image_returns_jpeg_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "cover.png"
            Image.new("RGBA", (20, 20), color=(255, 0, 0, 255)).save(image_path)

            image_data = process_cover_image(image_path)

            self.assertIsInstance(image_data, bytes)
            self.assertTrue(image_data.startswith(b"\xff\xd8"))

    def test_replace_folder_cover_writes_portada_and_removes_previous_portada_variants(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            source = folder / "new.png"
            old = folder / "PORTADA.png"
            Image.new("RGB", (20, 20), color="red").save(source)
            Image.new("RGB", (10, 10), color="blue").save(old)

            result = replace_folder_cover(source, folder)

            self.assertEqual(result, str(folder / COVER_FILENAME))
            self.assertTrue((folder / COVER_FILENAME).exists())
            self.assertFalse(old.exists())


if __name__ == "__main__":
    unittest.main()
