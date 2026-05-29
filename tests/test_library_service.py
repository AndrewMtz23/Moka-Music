import unittest

from app.models import FilterMode, SortMode, TrackInfo
from app.services.library_service import (
    BITRATE_128_MAX_KBPS,
    BITRATE_256_MAX_KBPS,
    BITRATE_256_MIN_KBPS,
    BITRATE_320_MIN_KBPS,
    filter_files,
    natural_filename_key,
    quality_report,
    sort_files,
)
from app.services.playback_history_service import normalize_history_path


def track(filename: str, metadata: dict[str, str], duration: float = 0.0, quality=None) -> TrackInfo:
    return TrackInfo(filename, filename, metadata, duration, None, quality or {})


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
                {"bitrate_kbps": 96, "low_bitrate": True},
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
                {"bitrate_kbps": 255},
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
                {"bitrate_kbps": 320},
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
                {"possibly_corrupt": True},
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
            sort_files(self.files, self.cache, SortMode.BITRATE, lambda _name: 0.0),
            ["b.mp3", "a.mp3", "c.mp3", "d.mp3"],
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
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.MISSING_TRACK), [])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.DUPLICATES), ["b.mp3", "a.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.LOW_BITRATE), ["b.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.BITRATE_128), ["b.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.BITRATE_256), ["a.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.BITRATE_320), ["c.mp3"])
        self.assertEqual(filter_files(self.files, self.cache, mode=FilterMode.POSSIBLY_CORRUPT), ["d.mp3"])
        self.assertEqual(
            filter_files(
                self.files,
                self.cache,
                mode=FilterMode.MISSING_COVER,
                has_cover_art=lambda filename: filename in {"a.mp3", "d.mp3"},
            ),
            ["b.mp3", "c.mp3"],
        )
        self.assertEqual(
            filter_files(
                self.files,
                self.cache,
                mode=FilterMode.UNPLAYED,
                played_paths={normalize_history_path("a.mp3"), normalize_history_path("d.mp3")},
            ),
            ["b.mp3", "c.mp3"],
        )

    def test_bitrate_filters_use_tolerant_ranges(self):
        files = ["low.mp3", "mid_start.mp3", "mid_end.mp3", "high.mp3", "unknown.mp3", "invalid.mp3"]
        cache = {
            "low.mp3": track("low.mp3", {}, quality={"bitrate_kbps": BITRATE_128_MAX_KBPS}),
            "mid_start.mp3": track("mid_start.mp3", {}, quality={"bitrate_kbps": BITRATE_256_MIN_KBPS}),
            "mid_end.mp3": track("mid_end.mp3", {}, quality={"bitrate_kbps": BITRATE_256_MAX_KBPS}),
            "high.mp3": track("high.mp3", {}, quality={"bitrate_kbps": BITRATE_320_MIN_KBPS}),
            "unknown.mp3": track("unknown.mp3", {}, quality={"bitrate_kbps": 0}),
            "invalid.mp3": track("invalid.mp3", {}, quality={"bitrate_kbps": "not-a-number"}),
        }

        self.assertEqual(filter_files(files, cache, mode=FilterMode.BITRATE_128), ["low.mp3"])
        self.assertEqual(filter_files(files, cache, mode=FilterMode.BITRATE_256), ["mid_start.mp3", "mid_end.mp3"])
        self.assertEqual(filter_files(files, cache, mode=FilterMode.BITRATE_320), ["high.mp3"])

    def test_sort_files_can_use_last_played_history(self):
        self.assertEqual(
            sort_files(
                self.files,
                self.cache,
                SortMode.LAST_PLAYED,
                lambda _name: 0.0,
                lambda name: {"a.mp3": "2026-05-26T10:00:00", "d.mp3": "2026-05-26T11:00:00"}.get(name, ""),
            ),
            ["d.mp3", "a.mp3", "c.mp3", "b.mp3"],
        )

    def test_quality_report_counts_missing_fields_and_duplicates(self):
        report = quality_report(self.files, self.cache)

        self.assertEqual(report["total"], 4)
        self.assertEqual(report["missing_artist"], 1)
        self.assertEqual(report["missing_album"], 1)
        self.assertEqual(report["missing_year"], 1)
        self.assertEqual(report["missing_track"], 0)
        self.assertEqual(report["duplicate_groups"], 1)
        self.assertEqual(report["duplicate_tracks"], 2)
        self.assertEqual(report["low_bitrate"], 1)
        self.assertEqual(report["possibly_corrupt"], 1)

    def test_sort_files_by_track_number_treats_zero_as_valid(self):
        files = ["missing.mp3", "two.mp3", "zero.mp3", "bad.mp3"]
        cache = {
            "zero.mp3": track("zero.mp3", {"track_number": "0"}),
            "two.mp3": track("two.mp3", {"track_number": "2"}),
            "bad.mp3": track("bad.mp3", {"track_number": "x"}),
            "missing.mp3": track("missing.mp3", {}),
        }

        self.assertEqual(
            sort_files(files, cache, SortMode.TRACK_NUMBER, lambda _name: 0.0),
            ["zero.mp3", "two.mp3", "bad.mp3", "missing.mp3"],
        )

    def test_duplicate_filter_uses_fuzzy_matching(self):
        files = ["one.mp3", "two.mp3"]
        cache = {
            "one.mp3": track("one.mp3", {"title": "The Song", "artist": "Artist"}),
            "two.mp3": track("two.mp3", {"title": "The Song Remastered", "artist": "Artist"}),
        }

        self.assertEqual(filter_files(files, cache, mode=FilterMode.DUPLICATES), files)

    def test_duplicate_filter_includes_repeated_track_numbers(self):
        files = ["first.mp3", "second.mp3", "third.mp3"]
        cache = {
            "first.mp3": track("first.mp3", {"title": "A", "artist": "A", "track_number": "7"}),
            "second.mp3": track("second.mp3", {"title": "B", "artist": "B", "track_number": "7"}),
            "third.mp3": track("third.mp3", {"title": "C", "artist": "C", "track_number": "8"}),
        }

        self.assertEqual(filter_files(files, cache, mode=FilterMode.DUPLICATES), ["first.mp3", "second.mp3"])


if __name__ == "__main__":
    unittest.main()
