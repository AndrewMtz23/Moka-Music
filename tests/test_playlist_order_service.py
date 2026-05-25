import unittest

from app.services.playlist_order_service import (
    insert_at_position,
    normalize_position,
    renumber_order,
    unique_filenames,
)


class PlaylistOrderServiceTests(unittest.TestCase):
    def test_normalize_position_clamps_to_bounds(self):
        self.assertEqual(normalize_position(-10, 5), 1)
        self.assertEqual(normalize_position(0, 5), 1)
        self.assertEqual(normalize_position(3, 5), 3)
        self.assertEqual(normalize_position(99, 5), 6)
        self.assertEqual(normalize_position("x", 5), 1)

    def test_unique_filenames_keeps_first_occurrence(self):
        self.assertEqual(
            unique_filenames(["a.mp3", "b.mp3", "a.mp3", "", "c.mp3"]),
            ["a.mp3", "b.mp3", "c.mp3"],
        )

    def test_insert_single_song_at_occupied_position_shifts_existing(self):
        order = ["001.mp3", "002.mp3", "003.mp3", "004.mp3"]

        result = insert_at_position(order, ["new.mp3"], 3)

        self.assertEqual(result, ["001.mp3", "002.mp3", "new.mp3", "003.mp3", "004.mp3"])

    def test_insert_multiple_songs_keeps_relative_order(self):
        order = ["001.mp3", "002.mp3", "003.mp3"]

        result = insert_at_position(order, ["new-a.mp3", "new-b.mp3"], 2)

        self.assertEqual(result, ["001.mp3", "new-a.mp3", "new-b.mp3", "002.mp3", "003.mp3"])

    def test_insert_at_start_and_end(self):
        order = ["002.mp3", "003.mp3"]

        self.assertEqual(insert_at_position(order, ["001.mp3"], 1), ["001.mp3", "002.mp3", "003.mp3"])
        self.assertEqual(insert_at_position(order, ["004.mp3"], 99), ["002.mp3", "003.mp3", "004.mp3"])

    def test_move_existing_song_without_duplication(self):
        order = ["001.mp3", "002.mp3", "003.mp3", "004.mp3"]

        result = insert_at_position(order, ["003.mp3"], 2)

        self.assertEqual(result, ["001.mp3", "003.mp3", "002.mp3", "004.mp3"])

    def test_move_multiple_existing_songs_as_block(self):
        order = ["001.mp3", "002.mp3", "003.mp3", "004.mp3", "005.mp3"]

        result = insert_at_position(order, ["004.mp3", "002.mp3"], 1)

        self.assertEqual(result, ["004.mp3", "002.mp3", "001.mp3", "003.mp3", "005.mp3"])

    def test_renumber_order_returns_track_numbers(self):
        self.assertEqual(
            renumber_order(["a.mp3", "b.mp3", "c.mp3"], start=100),
            {"a.mp3": 100, "b.mp3": 101, "c.mp3": 102},
        )
        self.assertEqual(renumber_order(["a.mp3"], start="x"), {"a.mp3": 1})


if __name__ == "__main__":
    unittest.main()
