import json
import tempfile
import unittest
from pathlib import Path

from app.services.playlist_export_service import export_library_report, export_library_view_json, export_playlist


class PlaylistExportServiceTests(unittest.TestCase):
    def test_exports_m3u8_with_extinf_and_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = folder / "playlist.m3u8"

            export_playlist(
                folder=folder,
                filenames=["song.mp3"],
                output_path=output,
                metadata_by_filename={"song.mp3": {"title": "Song", "artist": "Artist", "duration": "12"}},
            )

            content = output.read_text(encoding="utf-8")
            self.assertIn("#EXTM3U", content)
            self.assertIn("#EXTINF:12,Artist - Song", content)
            self.assertIn(str((folder / "song.mp3").resolve()), content)

    def test_exports_pls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = folder / "playlist.pls"

            export_playlist(folder=folder, filenames=["song.mp3"], output_path=output)

            content = output.read_text(encoding="utf-8")
            self.assertIn("[playlist]", content)
            self.assertIn("File1=", content)
            self.assertIn("NumberOfEntries=1", content)

    def test_exports_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = folder / "playlist.json"

            export_playlist(
                folder=folder,
                filenames=["song.mp3"],
                output_path=output,
                metadata_by_filename={"song.mp3": {"title": "Song", "duration": "3"}},
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["track_count"], 1)
            self.assertEqual(payload["tracks"][0]["metadata"]["title"], "Song")

    def test_exports_library_view_json_with_filter_and_quality(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = folder / "view.json"

            export_library_view_json(
                folder=folder,
                output_path=output,
                filenames=["song.mp3"],
                metadata_by_filename={"song.mp3": {"title": "Song", "track_number": "92"}},
                audio_quality_by_filename={"song.mp3": {"bitrate_kbps": 128}},
                duration_by_filename={"song.mp3": 10.5},
                library_position_by_filename={"song.mp3": 92},
                filter_info={"label": "128 kbps o menos", "mode": "BITRATE_128", "search": ""},
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["filter"]["mode"], "BITRATE_128")
            self.assertEqual(payload["track_count"], 1)
            self.assertEqual(payload["tracks"][0]["visible_position"], 1)
            self.assertEqual(payload["tracks"][0]["library_position"], 92)
            self.assertEqual(payload["tracks"][0]["track_number"], "92")
            self.assertEqual(payload["tracks"][0]["audio_quality"]["bitrate_kbps"], 128)

    def test_exports_library_report_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = folder / "report.json"

            export_library_report(
                folder=folder,
                output_path=output,
                filenames=["song.mp3"],
                metadata_by_filename={"song.mp3": {"title": "Song", "artist": "Artist"}},
                audio_quality_by_filename={"song.mp3": {"bitrate_kbps": 128, "low_bitrate": True}},
                duration_by_filename={"song.mp3": 9.5},
                library_position_by_filename={"song.mp3": 3},
                issues_by_filename={"song.mp3": ["low_bitrate"]},
                summary={"total": 1},
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total"], 1)
            self.assertEqual(payload["tracks"][0]["library_position"], 3)
            self.assertEqual(payload["tracks"][0]["issues"], ["low_bitrate"])

    def test_exports_library_report_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = folder / "report.csv"

            export_library_report(
                folder=folder,
                output_path=output,
                filenames=["song.mp3"],
                metadata_by_filename={"song.mp3": {"title": "Song"}},
                issues_by_filename={"song.mp3": ["missing_artist", "low_bitrate"]},
            )

            content = output.read_text(encoding="utf-8")
            self.assertIn("filename", content)
            self.assertIn("song.mp3", content)
            self.assertIn("missing_artist;low_bitrate", content)


if __name__ == "__main__":
    unittest.main()
