import unittest

from app.services.playback_history_service import playback_history_summary, played_paths, record_playback


class PlaybackHistoryServiceTests(unittest.TestCase):
    def test_record_playback_creates_and_updates_track_entries(self):
        history = record_playback(
            [],
            filepath="/music/song.mp3",
            filename="song.mp3",
            metadata={"artist": "Artist", "title": "Song"},
            played_at="2026-05-26T10:00:00+00:00",
        )
        history = record_playback(
            history,
            filepath="/music/song.mp3",
            filename="song.mp3",
            metadata={"artist": "Artist", "title": "Song"},
            played_at="2026-05-26T10:05:00+00:00",
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["play_count"], 2)
        self.assertEqual(history[0]["last_played"], "2026-05-26T10:05:00+00:00")
        self.assertTrue(played_paths(history))

    def test_playback_history_summary_counts_unique_tracks_and_plays(self):
        summary = playback_history_summary(
            [
                {"filename": "a.mp3", "play_count": 3, "last_played": "b"},
                {"filename": "b.mp3", "play_count": 2, "last_played": "a"},
            ]
        )

        self.assertEqual(summary["unique_tracks"], 2)
        self.assertEqual(summary["total_plays"], 5)
        self.assertEqual(len(summary["top_tracks"]), 2)


if __name__ == "__main__":
    unittest.main()
