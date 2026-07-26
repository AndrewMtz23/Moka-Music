import unittest

from mutagen.mp4 import MP4Cover

from app.services.song_info_service import SongInfo


class FakeAudio:
    def __init__(self, tags):
        self.tags = tags


class SongInfoServiceTests(unittest.TestCase):
    def test_extract_generic_cover_reads_mp4_covr_art(self):
        cover_data = b"jpeg-cover"
        audio = FakeAudio({"covr": [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]})

        self.assertEqual(SongInfo()._extract_generic_cover(audio), cover_data)


if __name__ == "__main__":
    unittest.main()
