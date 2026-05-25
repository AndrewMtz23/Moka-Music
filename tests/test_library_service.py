import unittest

from app.models import FilterMode, SortMode, TrackInfo
from app.services.library_service import filter_files, natural_filename_key, quality_report, sort_files


def track(filename: str, metadata: dict[str, str], duration: float = 0.0) -> TrackInfo:
    return TrackInfo(filename, filename, metadata, duration, None)


class LibraryServiceTests(unittest.TestCase):
    def setUp(self):
        self.files = ["b.mp3", "a.mp3", "c.mp3", "d.mp3"]
        self.cache = {
            "b.mp3": track(
                "b.mp3",
                {
                    "title": "Same",
                    "artist": "Beta",
                    "album": "Two",
                    "year": "",
                    "track_number": "2",
                },
                40.0,
            ),
            "a.mp3": track(
                "a.mp3",
                {
                    "title": "Same",
                    "artist": "Beta",
                    "album": "One",
                    "year": "2025",
                    "track_number": "1",
                },
                20.0,
            ),
            "c.mp3": track(
                "c.mp3",
                {
                    "title": "Other",
                    "artist": "",
                    "album": "",
                    "year": "2024",
                    "track_number": "0",
                },
                10.0,
            ),
            "d.mp3": track(
                "d.mp3",
                {
                    "title": "Last",
                    "artist": "Delta",
                    "album": "Three",
                    "year": "2023",
                    "track_number": "10",
                },
                30.0,
            ),
        }

    def test_sort_files_uses_metadata_duration_and_manual_modes(self):
        self.assertEqual(
            sort_files(self.files, self.cache, SortMode.FILENAME, lambda _name: 0.0),
            ["a.mp3", "b.mp3", "c.mp3", "d.mp3"],
        )
        self.assertEqual(
            sort_files(self.files, self.cache, SortMode.ALBUM, lambda _name: 0.0),
            ["c.mp3", "a.mp3", "d.mp3", "b.mp3"],
        )
        self.assertEqual(
            sort_files(self.files, self.cache, SortMode.DURATION, lambda _name: 0.0),
            ["c.mp3", "a.mp3", "d.mp3", "b.mp3"],
        )
        self.assertEqual(
            sort_files(self.files, self.cache, SortMode.MANUAL, lambda _name: 0.0),
            self.files,
        )

    def test_sort_files_uses_natural_filename_order_for_numeric_prefixes(self):
        files = [
            "100 - C. Tangana - Los Tontos.mp3",
            "09 - The Strokes - Selfless.mp3",
            "10 - Enjambre - Necropolis.mp3",
            "11 - Otra.mp3",
        ]

        self.assertEqual(
            sort_files(files, {}, SortMode.FILENAME, lambda _name: 0.0),
            [
                "09 - The Strokes - Selfless.mp3",
                "10 - Enjambre - Necropolis.mp3",
                "11 - Otra.mp3",
                "100 - C. Tangana - Los Tontos.mp3",
            ],
        )
        self.assertLess(natural_filename_key("2 - a.mp3"), natural_filename_key("10 - a.mp3"))

    def test_filter_files_searches_metadata_and_special_filters(self):
        self.assertEqual(filter_files(self.files, self.cache, "last"), ["d.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.MISSING_ARTIST), ["c.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.MISSING_TRACK), ["c.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.DUPLICATES), ["b.mp3", "a.mp3"])
        self.assertEqual(
            filter_files(
                self.files,
                self.cache,
                mode=FilterMode.MISSING_COVER,
                has_cover_art=lambda filename: filename in {"a.mp3", "d.mp3"},
            ),
            ["b.mp3", "c.mp3"],
        )

    def test_quality_report_counts_missing_fields_and_duplicates(self):
        report = quality_report(self.files, self.cache)

        self.assertEqual(report["total"], 4)
        self.assertEqual(report["missing_artist"], 1)
        self.assertEqual(report["missing_album"], 1)
        self.assertEqual(report["missing_year"], 1)
        self.assertEqual(report["missing_track"], 1)
        self.assertEqual(report["duplicate_groups"], 1)
        self.assertEqual(report["duplicate_tracks"], 2)


if __name__ == "__main__":
    unittest.main()
