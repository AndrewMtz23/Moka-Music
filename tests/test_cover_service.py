import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.services.cover_service import find_folder_cover, process_cover_image


class CoverServiceTests(unittest.TestCase):
    def test_find_folder_cover_prefers_known_cover_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio = folder / "song.mp3"
            audio.write_bytes(b"audio")
            Image.new("RGB", (100, 100), color="blue").save(folder / "random.png")
            Image.new("RGB", (10, 10), color="red").save(folder / "cover.jpg")

            self.assertEqual(find_folder_cover(audio), str(folder / "cover.jpg"))

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


if __name__ == "__main__":
    unittest.main()
