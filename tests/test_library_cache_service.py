import tempfile
import unittest
from pathlib import Path

from app.services.library_cache_service import LibraryCache
from app.services.track_scan_service import TrackScanResult


class LibraryCacheServiceTests(unittest.TestCase):
    def test_save_and_read_valid_track(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            result = TrackScanResult(
                filename="song.mp3",
                filepath=str(audio),
                metadata={"title": "Song", "artist": "Artist"},
                duration=12.5,
                audio_quality={"bitrate_kbps": 320},
                has_cover_art=True,
            )

            cache.save_track(result)
            cached = cache.get_valid_track(audio)

        self.assertIsNotNone(cached)
        self.assertEqual(cached.metadata["title"], "Song")
        self.assertEqual(cached.duration, 12.5)
        self.assertEqual(cached.audio_quality["bitrate_kbps"], 320)
        self.assertTrue(cached.has_cover_art)

    def test_cache_miss_when_file_size_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            cache.save_track(
                TrackScanResult(
                    filename="song.mp3",
                    filepath=str(audio),
                    metadata={"title": "Song"},
                    duration=1.0,
                    audio_quality={},
                )
            )

            audio.write_bytes(b"audio changed")

            self.assertIsNone(cache.get_valid_track(audio))

    def test_invalidate_path_removes_track(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            cache.save_track(
                TrackScanResult(
                    filename="song.mp3",
                    filepath=str(audio),
                    metadata={"title": "Song"},
                    duration=1.0,
                    audio_quality={},
                )
            )

            cache.invalidate_path(audio)

            self.assertIsNone(cache.get_valid_track(audio))

    def test_corrupt_database_falls_back_to_cache_miss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            db_path = root / "cache.sqlite"
            db_path.write_text("not sqlite", encoding="utf-8")

            self.assertIsNone(LibraryCache(db_path).get_valid_track(audio))


if __name__ == "__main__":
    unittest.main()
