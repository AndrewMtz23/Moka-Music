import unittest

from app.models import TrackInfo
from app.services.library_compare_service import compare_libraries


def track(filename: str, metadata: dict[str, str]) -> TrackInfo:
    return TrackInfo(filename, filename, metadata, 0.0, None, {})


class LibraryCompareServiceTests(unittest.TestCase):
    def test_compare_libraries_marks_new_and_cross_duplicates(self):
        main_files = ["main_song.mp3", "main_other.mp3"]
        incoming_files = ["same_song.mp3", "fresh.mp3"]
        main_cache = {
            "main_song.mp3": track("main_song.mp3", {"artist": "Artist", "title": "The Song"}),
            "main_other.mp3": track("main_other.mp3", {"artist": "Other", "title": "Track"}),
        }
        incoming_cache = {
            "same_song.mp3": track("same_song.mp3", {"artist": "Artist", "title": "The Song Remastered"}),
            "fresh.mp3": track("fresh.mp3", {"artist": "Fresh", "title": "New Track"}),
        }

        comparison = compare_libraries(main_files, main_cache, incoming_files, incoming_cache)

        self.assertEqual(comparison["total_incoming"], 2)
        self.assertEqual(comparison["duplicates"], 1)
        self.assertEqual(comparison["new_tracks"], 1)
        rows = comparison["rows"]
        self.assertEqual(rows[0].status, "duplicate")
        self.assertEqual(rows[0].matched_filename, "main_song.mp3")
        self.assertEqual(rows[1].status, "new")
        self.assertEqual(rows[1].matched_filename, "")


if __name__ == "__main__":
    unittest.main()
