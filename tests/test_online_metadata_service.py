import unittest

from app.services.online_metadata_service import MusicBrainzClient, parse_musicbrainz_recordings


class OnlineMetadataServiceTests(unittest.TestCase):
    def test_parse_musicbrainz_recordings_extracts_metadata(self):
        payload = {
            "recordings": [
                {
                    "title": "Song",
                    "score": "98",
                    "artist-credit": [{"artist": {"name": "Artist"}}],
                    "releases": [{"title": "Album", "date": "2024-05-01"}],
                    "tags": [{"name": "rock", "count": 5}],
                }
            ]
        }

        results = parse_musicbrainz_recordings(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata()["title"], "Song")
        self.assertEqual(results[0].metadata()["artist"], "Artist")
        self.assertEqual(results[0].metadata()["album"], "Album")
        self.assertEqual(results[0].metadata()["year"], "2024")
        self.assertEqual(results[0].metadata()["genre"], "rock")
        self.assertEqual(results[0].score, 98)

    def test_search_returns_empty_without_query_metadata(self):
        self.assertEqual(MusicBrainzClient().search({}), [])


if __name__ == "__main__":
    unittest.main()
