import unittest
from dataclasses import dataclass

from app.views.modals.playlist_insert_preview_modal import (
    playlist_preview_issues,
    playlist_preview_rows,
    request_playlist_insert_preview,
)


@dataclass(frozen=True)
class FakeItem:
    old_name: str
    old_position: int | None
    new_position: int
    track_number: int
    new_name: str


@dataclass(frozen=True)
class FakePlan:
    items: list[FakeItem]


class FakeTrack:
    def __init__(self, metadata):
        self.metadata = metadata


class FakeController:
    def __init__(self, metadata_by_name):
        self.metadata_by_name = metadata_by_name

    def get_track_info(self, filename):
        return FakeTrack(self.metadata_by_name.get(filename, {}))


class PlaylistInsertPreviewModalTests(unittest.TestCase):
    def test_playlist_preview_rows_formats_plan_items(self):
        plan = FakePlan(
            [
                FakeItem("old.mp3", 100, 101, 101, "101 - A - Song.mp3"),
                FakeItem("new.mp3", None, 100, 100, "100 - B - New.mp3"),
            ]
        )

        self.assertEqual(
            playlist_preview_rows(plan),
            [
                ("old.mp3", "100", "101", "101", "101 - A - Song.mp3"),
                ("new.mp3", "", "100", "100", "100 - B - New.mp3"),
            ],
        )

    def test_request_preview_function_is_available_for_editable_modal(self):
        self.assertTrue(callable(request_playlist_insert_preview))

    def test_playlist_preview_issues_reports_missing_fields_and_duplicates(self):
        controller = FakeController(
            {
                "plain.mp3": {"title": "", "artist": ""},
                "artist - song.mp3": {"title": "Song", "artist": ""},
            }
        )
        plan = FakePlan(
            [
                FakeItem("plain.mp3", 1, 1, 1, "001 - Plain.mp3"),
                FakeItem("artist - song.mp3", 2, 2, 2, "001 - Plain.mp3"),
            ]
        )
        object.__setattr__(plan.items[0], "controller", controller)
        object.__setattr__(plan.items[1], "controller", controller)

        issues = playlist_preview_issues(plan)

        self.assertIn("plain.mp3: missing_title", issues)
        self.assertIn("plain.mp3: missing_artist", issues)
        self.assertIn("001 - Plain.mp3: duplicate_name", issues)


if __name__ == "__main__":
    unittest.main()
