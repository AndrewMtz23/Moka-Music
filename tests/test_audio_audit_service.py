import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.audio_audit_service import build_audio_quality_rows, detect_advanced_duplicates, validate_audio_files


@dataclass
class CachedTrack:
    metadata: dict[str, str]
    duration: float
    audio_quality: dict[str, object]


class FakeController:
    def __init__(self, folder: Path, tracks: dict[str, CachedTrack]):
        self.carpeta = str(folder)
        self.tracks = tracks

    def get_track_info(self, filename: str):
        return self.tracks.get(filename)


class AudioAuditServiceTests(unittest.TestCase):
    def test_build_audio_quality_rows_includes_cached_quality(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(
                Path(temp_dir),
                {
                    "song.mp3": CachedTrack(
                        metadata={"title": "Song", "artist": "Artist"},
                        duration=123.4,
                        audio_quality={"bitrate_kbps": 128, "format": "MP3", "low_bitrate": True},
                    )
                },
            )

            rows = build_audio_quality_rows([(controller, None, ["song.mp3"])])

            self.assertEqual(rows[0]["title"], "Song")
            self.assertEqual(rows[0]["bitrate_kbps"], 128)
            self.assertTrue(rows[0]["low_bitrate"])

    def test_detect_advanced_duplicates_matches_metadata_and_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(
                Path(temp_dir),
                {
                    "one.mp3": CachedTrack({"title": "Same Song", "artist": "MOKA"}, 180.0, {}),
                    "two.mp3": CachedTrack({"title": "Same Song", "artist": "MOKA"}, 181.5, {}),
                    "three.mp3": CachedTrack({"title": "Other", "artist": "MOKA"}, 180.0, {}),
                },
            )

            rows = detect_advanced_duplicates([(controller, None, ["one.mp3", "two.mp3", "three.mp3"])])

            self.assertEqual(len(rows), 1)
            self.assertIn("one.mp3", rows[0]["filename"])
            self.assertIn("duplicate_duration_delta", rows[0]["issue"])

    def test_validate_audio_files_reports_missing_and_bad_quality(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            controller = FakeController(
                folder,
                {
                    "missing.mp3": CachedTrack(
                        {"title": "Missing"},
                        0.0,
                        {"bitrate_kbps": 0, "possibly_corrupt": True},
                    )
                },
            )

            rows = validate_audio_files([(controller, None, ["missing.mp3"])])

            self.assertEqual(len(rows), 1)
            self.assertIn("missing_file", rows[0]["issues"])
            self.assertIn("possibly_corrupt", rows[0]["issues"])


if __name__ == "__main__":
    unittest.main()
