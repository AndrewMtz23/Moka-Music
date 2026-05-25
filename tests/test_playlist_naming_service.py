import unittest

from app.services.playlist_naming_service import playlist_base_name, playlist_filename_from_metadata


class PlaylistNamingServiceTests(unittest.TestCase):
    def test_builds_playlist_filename_with_track_artist_and_title(self):
        result = playlist_filename_from_metadata(
            "old.mp3",
            {"track_number": "100", "artist": "Kinto Piso", "title": "Te demoras Llámame"},
            set(),
        )

        self.assertEqual(result, "100 - Kinto Piso - Te demoras Llámame.mp3")

    def test_uses_three_digits_for_small_track_numbers(self):
        self.assertEqual(
            playlist_filename_from_metadata("old.flac", {"track_number": "7", "artist": "A", "title": "B"}, set()),
            "007 - A - B.flac",
        )

    def test_infers_missing_artist_from_filename(self):
        self.assertEqual(
            playlist_filename_from_metadata("TBX - OYE MORENO.mp3", {"track_number": "2", "title": "OYE MORENO"}, set()),
            "002 - TBX - OYE MORENO.mp3",
        )

    def test_uses_filename_stem_when_title_is_missing(self):
        self.assertEqual(
            playlist_filename_from_metadata("Original Name.mp3", {"track_number": "4", "artist": "Artist"}, set()),
            "004 - Artist - Original Name.mp3",
        )

    def test_uses_filename_artist_and_title_when_metadata_is_missing(self):
        self.assertEqual(
            playlist_filename_from_metadata("Victor Mendivil - Mia.mp3", {"track_number": "1"}, set()),
            "001 - Victor Mendivil - Mia.mp3",
        )

    def test_resolves_name_collisions(self):
        result = playlist_filename_from_metadata(
            "old.mp3",
            {"track_number": "100", "artist": "Artist", "title": "Song"},
            {"100 - Artist - Song.mp3", "100 - Artist - Song (2).mp3"},
        )

        self.assertEqual(result, "100 - Artist - Song (3).mp3")

    def test_preserves_current_name_without_collision_suffix(self):
        result = playlist_filename_from_metadata(
            "100 - Artist - Song.mp3",
            {"track_number": "100", "artist": "Artist", "title": "Song"},
            {"100 - Artist - Song.mp3"},
        )

        self.assertEqual(result, "100 - Artist - Song.mp3")

    def test_sanitizes_invalid_filename_characters(self):
        self.assertEqual(
            playlist_base_name("bad.mp3", {"track_number": "1", "artist": "A/B", "title": "C:D"}),
            "001 - A_B - C_D",
        )

    def test_track_number_argument_overrides_metadata(self):
        self.assertEqual(
            playlist_filename_from_metadata(
                "old.mp3",
                {"track_number": "1", "artist": "Artist", "title": "Song"},
                set(),
                track_number=100,
            ),
            "100 - Artist - Song.mp3",
        )


if __name__ == "__main__":
    unittest.main()
