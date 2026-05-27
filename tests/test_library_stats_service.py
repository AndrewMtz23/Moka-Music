import unittest

from app.models import TrackInfo
from app.services.library_stats_service import build_library_stats, format_duration


def track(filename, metadata, duration=0):
    return TrackInfo(filename, filename, metadata, duration, None)


class LibraryStatsServiceTests(unittest.TestCase):
    def test_build_library_stats_counts_distribution_and_completion(self):
        files = ["one.mp3", "two.mp3", "three.mp3"]
        cache = {
            "one.mp3": track(
                "one.mp3",
                {"title": "One", "artist": "A", "album": "X", "genre": "Rock", "year": "2024", "track_number": "1"},
                60,
            ),
            "two.mp3": track(
                "two.mp3",
                {"title": "Two", "artist": "A", "album": "Y", "genre": "Pop", "year": "2024", "track_number": "2"},
                120,
            ),
            "three.mp3": track(
                "three.mp3",
                {"title": "Three", "artist": "", "album": "", "genre": "Rock", "year": "", "track_number": "0"},
                30,
            ),
        }

        stats = build_library_stats(files, cache)

        self.assertEqual(stats["total_tracks"], 3)
        self.assertEqual(stats["total_duration"], 210)
        self.assertEqual(stats["complete_metadata"], 2)
        self.assertEqual(stats["completion_percent"], 66.7)
        self.assertEqual(stats["genres"][0], ("Rock", 2))
        self.assertEqual(stats["top_artists"][0], ("A", 2))

    def test_format_duration(self):
        self.assertEqual(format_duration(65), "1:05")
        self.assertEqual(format_duration(3661), "1:01:01")


if __name__ == "__main__":
    unittest.main()
