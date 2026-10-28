import unittest

from app.services.track_number_service import plan_gap_closure


class TrackNumberServiceTests(unittest.TestCase):
    def test_invalid_or_unknown_removed_number_changes_nothing(self):
        tracks = [("zero", 0, False), ("one", 1, False)]
        self.assertEqual(plan_gap_closure(tracks, None), [])
        self.assertEqual(plan_gap_closure(tracks, -1), [])

    def test_existing_duplicate_means_no_hole_was_created(self):
        self.assertEqual(plan_gap_closure([("ten", 10, False), ("eleven", 11, False)], 10), [])

    def test_manual_block_is_reserved_and_visual_order_does_not_matter(self):
        tracks = [("thirteen", 13, False), ("twelve", 12, True), ("eleven", 11, True), ("fourteen", 14, False)]
        self.assertEqual(plan_gap_closure(tracks, 10), [("thirteen", 10), ("fourteen", 13)])
