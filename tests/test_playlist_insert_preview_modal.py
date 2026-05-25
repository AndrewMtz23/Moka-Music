import unittest
from dataclasses import dataclass

from app.views.modals.playlist_insert_preview_modal import playlist_preview_rows


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


if __name__ == "__main__":
    unittest.main()
