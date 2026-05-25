import unittest

from app.utils.text_cleanup import (
    build_quick_cleanup_metadata,
    remove_feature_text,
    remove_parenthetical_text,
    title_from_filename,
)


class TextCleanupTests(unittest.TestCase):
    def test_remove_feature_text_handles_title_and_artist_patterns(self):
        self.assertEqual(remove_feature_text("Song (feat. Guest)"), "Song")
        self.assertEqual(remove_feature_text("Artist ft Guest"), "Artist")
        self.assertEqual(remove_feature_text("Artist x Guest"), "Artist")

    def test_remove_parenthetical_text_removes_parentheses_and_brackets(self):
        self.assertEqual(remove_parenthetical_text("Track (Video Oficial) [Explicit]"), "Track")

    def test_title_from_filename_returns_stem(self):
        self.assertEqual(title_from_filename("Artist - Song.mp3"), "Artist - Song")

    def test_build_quick_cleanup_metadata_composes_known_actions(self):
        metadata = {
            "title": "Track (Video Oficial) feat Guest",
            "artist": "Artist feat Guest",
        }

        self.assertEqual(
            build_quick_cleanup_metadata("remove_feat", "fallback.mp3", metadata),
            {"title": "Track (Video Oficial)", "artist": "Artist"},
        )
        self.assertEqual(
            build_quick_cleanup_metadata("remove_parentheses", "fallback.mp3", metadata),
            {"title": "Track feat Guest"},
        )
        self.assertEqual(
            build_quick_cleanup_metadata("copy_artist", "fallback.mp3", metadata),
            {"album_artist": "Artist feat Guest"},
        )


if __name__ == "__main__":
    unittest.main()
