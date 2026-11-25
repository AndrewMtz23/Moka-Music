import unittest

from app.views.audio_editor_dashboard import _parse_time_value
from app.views.audio_timeline import (
    canvas_x_to_seconds,
    canvas_y_to_track_index,
    resample_peaks,
    snap_to_nearest,
    time_tick_interval,
)


class AudioTimelineHelpersTests(unittest.TestCase):
    def test_resample_peaks_preserves_empty_and_single_pixel_cases(self):
        self.assertEqual(resample_peaks((), 10), ())
        self.assertEqual(resample_peaks((0.2, 0.8), 1), (0.8,))

    def test_resample_peaks_returns_requested_width_and_preserves_local_maxima(self):
        result = resample_peaks((0.0, 0.4, 0.1, 0.9, 0.2, 0.3), 3)

        self.assertEqual(len(result), 3)
        self.assertEqual(result, (0.4, 0.9, 0.3))

    def test_time_tick_interval_keeps_labels_readable_at_zoom_levels(self):
        self.assertEqual(time_tick_interval(120), 1)
        self.assertEqual(time_tick_interval(10), 10)
        self.assertEqual(time_tick_interval(0.1), 1200)

    def test_canvas_position_maps_to_nonnegative_timeline_seconds(self):
        self.assertEqual(canvas_x_to_seconds(84, 60), 0)
        self.assertEqual(canvas_x_to_seconds(144, 60), 1)
        self.assertEqual(canvas_x_to_seconds(0, 60), 0)

    def test_canvas_vertical_position_maps_to_track_and_ignores_gaps(self):
        self.assertEqual(canvas_y_to_track_index(48, 2), 0)
        self.assertEqual(canvas_y_to_track_index(181, 2), 0)
        self.assertIsNone(canvas_y_to_track_index(182, 2))
        self.assertEqual(canvas_y_to_track_index(190, 2), 1)
        self.assertIsNone(canvas_y_to_track_index(400, 2))

    def test_snap_to_nearest_uses_closest_candidate_within_tolerance(self):
        self.assertEqual(snap_to_nearest(10.08, (9.9, 10.1), tolerance=0.15), 10.1)
        self.assertEqual(snap_to_nearest(10.2, (10,), tolerance=0.15), 10.2)
        self.assertEqual(snap_to_nearest(10.01, (), tolerance=0.15), 10.01)

    def test_snap_to_nearest_keeps_position_when_all_candidates_are_outside_tolerance(self):
        self.assertEqual(snap_to_nearest(3.0, (2.8, 3.3), tolerance=0.1), 3.0)

    def test_parse_time_value_accepts_seconds_and_mm_ss(self):
        self.assertEqual(_parse_time_value("12.5"), 12.5)
        self.assertEqual(_parse_time_value("1:05.25"), 65.25)

    def test_parse_time_value_rejects_invalid_and_negative_values(self):
        for value in ("", "-1", "1:60", "1:2:3", "nan"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_time_value(value)


if __name__ == "__main__":
    unittest.main()
