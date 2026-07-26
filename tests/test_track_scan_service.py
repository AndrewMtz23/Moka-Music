import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mutagen.mp4 import MP4Cover

from app.services.track_scan_service import scan_track


class FakeEasyAudio:
    def __init__(self, values):
        self.values = values

    def get(self, key, fallback):
        return self.values.get(key, fallback)


class FakeInfo:
    length = 123.4
    bitrate = 320000
    sample_rate = 44100
    channels = 2


class FakeFullAudio:
    info = FakeInfo()
    mime = ["audio/mp4"]

    def __init__(self, tags=None):
        self.tags = tags or {}


class TrackScanServiceTests(unittest.TestCase):
    def test_scan_track_combines_metadata_quality_duration_and_cover(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "song.m4a"
            path.write_bytes(b"fake")
            cover_data = b"cover"
            easy_audio = FakeEasyAudio(
                {
                    "title": ["Title"],
                    "artist": ["Artist"],
                    "albumartist": ["Album Artist"],
                    "album": ["Album"],
                    "date": ["2026"],
                    "tracknumber": ["7"],
                    "genre": ["Rock"],
                    "comment": ["Comment"],
                }
            )
            full_audio = FakeFullAudio({"covr": [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]})

            def fake_mutagen_file(_filepath, easy=False):
                return easy_audio if easy else full_audio

            with patch("app.services.track_scan_service.mutagen.File", side_effect=fake_mutagen_file):
                result = scan_track(path)

        self.assertEqual(result.filename, "song.m4a")
        self.assertEqual(result.metadata["title"], "Title")
        self.assertEqual(result.metadata["artist"], "Artist")
        self.assertEqual(result.metadata["album_artist"], "Album Artist")
        self.assertEqual(result.metadata["track_number"], "7")
        self.assertEqual(result.duration, 123.4)
        self.assertEqual(result.audio_quality["bitrate_kbps"], 320)
        self.assertEqual(result.audio_quality["sample_rate"], 44100)
        self.assertEqual(result.audio_quality["channels"], "stereo")
        self.assertTrue(result.has_cover_art)
        self.assertEqual(result.error, "")

    def test_scan_track_returns_safe_defaults_for_unreadable_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.mp3"
            path.write_bytes(b"fake")

            with patch("app.services.track_scan_service.mutagen.File", side_effect=Exception("bad header")):
                result = scan_track(path)

        self.assertEqual(result.metadata["title"], "broken")
        self.assertEqual(result.duration, 0.0)
        self.assertTrue(result.audio_quality["possibly_corrupt"])
        self.assertFalse(result.has_cover_art)
        self.assertIn("bad header", result.error)

    def test_scan_track_rejects_unsupported_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("nope", encoding="utf-8")

            result = scan_track(path)

        self.assertEqual(result.metadata["title"], "notes")
        self.assertTrue(result.audio_quality["possibly_corrupt"])
        self.assertFalse(result.has_cover_art)


if __name__ == "__main__":
    unittest.main()
