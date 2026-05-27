import unittest

from app.models import TrackInfo
from app.services.metadata_tools_service import (
    build_normalize_plan,
    build_search_replace_plan,
    normalize_metadata_text,
    normalize_metadata_values,
)


class FakeController:
    def __init__(self, metadata):
        self.metadata = metadata

    def get_track_info(self, filename):
        return TrackInfo(filename, filename, self.metadata[filename], 0.0, None, {})


class MetadataToolsServiceTests(unittest.TestCase):
    def test_normalize_metadata_text_cleans_spaces_and_case(self):
        self.assertEqual(normalize_metadata_text("  hello__WORLD  ", title_case=True), "Hello World")
        self.assertEqual(normalize_metadata_text("A–B"), "A - B")

    def test_normalize_metadata_values_returns_changed_fields(self):
        updates = normalize_metadata_values({"title": "  hello   world ", "year": "2020"})

        self.assertEqual(updates["title"], "Hello World")
        self.assertNotIn("year", updates)

    def test_build_normalize_plan(self):
        controller = FakeController({"song.mp3": {"title": " hello   world "}})

        plan = build_normalize_plan([(controller, object(), ["song.mp3"])])

        self.assertEqual(plan[0].updates, {"title": "Hello World"})

    def test_build_search_replace_plan(self):
        controller = FakeController({"song.mp3": {"artist": "Moka Music"}})

        plan = build_search_replace_plan(
            [(controller, object(), ["song.mp3"])],
            field="artist",
            search_text="music",
            replacement="Records",
        )

        self.assertEqual(plan[0].updates, {"artist": "Moka Records"})


if __name__ == "__main__":
    unittest.main()
