import unittest

from app.models import ActionResult
from app.utils.ui_formatting import (
    backup_action_label,
    filename_from_metadata,
    filename_from_tree_item,
    format_action_error,
    format_metadata_summary,
    metadata_label_key,
)


def fake_t(key: str, **kwargs) -> str:
    if kwargs:
        suffix = ",".join(f"{name}={value}" for name, value in sorted(kwargs.items()))
        return f"{key}({suffix})"
    return key


class UiFormattingTests(unittest.TestCase):
    def test_filename_from_tree_item_ignores_visual_tags(self):
        item = {"tags": ("odd_row", "song.mp3", "selected")}

        self.assertEqual(filename_from_tree_item(item), "song.mp3")
        self.assertEqual(filename_from_tree_item({"tags": ("placeholder",)}), "")

    def test_filename_from_metadata_uses_track_artist_title_and_avoids_duplicates(self):
        metadata = {"title": "Song", "artist": "Artist", "track_number": "3"}

        result = filename_from_metadata(
            "old.mp3",
            metadata,
            {"03. Artist - Song.mp3"},
            lambda value: value,
        )

        self.assertEqual(result, "03. Artist - Song (2).mp3")

    def test_backup_action_and_metadata_labels_are_translatable(self):
        self.assertEqual(metadata_label_key("album_artist"), "metadata.album_artist")
        self.assertEqual(backup_action_label({"quick_action": "remove_feat"}, fake_t), "quick_actions.remove_feat")
        self.assertEqual(
            backup_action_label({"quick_preset": "Mi preset"}, fake_t),
            "backup.action_preset(name=Mi preset)",
        )
        self.assertEqual(backup_action_label({"__cover__": "cover.jpg"}, fake_t), "backup.action_cover")

    def test_format_metadata_summary_and_action_errors(self):
        summary = format_metadata_summary({"title": "Track", "artist": "A"}, fake_t)
        self.assertIn("- preview.title_field: Track", summary)
        self.assertIn("- preview.artist: A", summary)

        result = ActionResult.fail("No jalo", errors=[str(index) for index in range(10)])
        detail = format_action_error(result, fake_t, limit=3)

        self.assertIn("No jalo", detail)
        self.assertIn("0\n1\n2", detail)
        self.assertIn("message.more_errors(count=7)", detail)


if __name__ == "__main__":
    unittest.main()
