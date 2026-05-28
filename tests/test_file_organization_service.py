import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.file_organization_service import (
    build_template_plan,
    execute_file_plan,
    filename_from_template,
    smart_playlist_filenames,
    validate_playlist,
)


@dataclass
class CachedTrack:
    metadata: dict[str, str]
    audio_quality: dict[str, object] | None = None
    duration: float = 0.0


class FakeController:
    def __init__(self, folder: Path):
        self.carpeta = str(folder)
        self.archivos = []
        self.tracks = {}

    def get_track_info(self, filename):
        return self.tracks.get(filename)

    def rename_file(self, old_name, new_name):
        index = self.archivos.index(old_name)
        self.archivos[index] = new_name

    def issue_keys_for_file(self, filename):
        return ["missing_cover"] if filename == "coverless.mp3" else []


class FileOrganizationServiceTests(unittest.TestCase):
    def test_filename_from_template_sanitizes_metadata_and_keeps_extension(self):
        result = filename_from_template(
            "old.mp3",
            {"track_number": "7", "artist": "A/B", "title": "C:D"},
            "{track_number:03d} - {artist} - {title}",
        )

        self.assertEqual(result, "007 - A_B - C_D.mp3")

    def test_build_template_plan_supports_folder_templates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(Path(temp_dir))
            controller.archivos = ["song.mp3"]
            controller.tracks["song.mp3"] = CachedTrack({"artist": "Artist", "album": "Album", "title": "Song", "track_number": "1"})

            plan = build_template_plan(controller, ["song.mp3"], "{artist}/{album}/{track_number:02d} - {title}")

            self.assertEqual(plan[0].new_name, "Artist/Album/01 - Song.mp3")

    def test_execute_file_plan_moves_file_and_updates_controller(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "song.mp3").write_bytes(b"fake")
            controller = FakeController(folder)
            controller.archivos = ["song.mp3"]
            controller.tracks["song.mp3"] = CachedTrack({"artist": "Artist", "album": "Album", "title": "Song"})
            plan = build_template_plan(controller, ["song.mp3"], "{artist}/{title}")

            result = execute_file_plan(controller, plan)

            self.assertEqual(result.moved, 1)
            self.assertTrue((folder / "Artist" / "Song.mp3").exists())
            self.assertEqual(controller.archivos, ["Artist/Song.mp3"])

    def test_validate_playlist_reports_duplicate_and_missing_track_numbers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "one.mp3").write_bytes(b"fake")
            (folder / "two.mp3").write_bytes(b"fake")
            controller = FakeController(folder)
            controller.archivos = ["one.mp3", "two.mp3"]
            controller.tracks["one.mp3"] = CachedTrack({"track_number": "1"})
            controller.tracks["two.mp3"] = CachedTrack({"track_number": "1"})

            issues = validate_playlist(controller, controller.archivos)

            self.assertIn("duplicate_track_number", {issue["issue"] for issue in issues})

    def test_smart_playlist_filters_low_bitrate_and_missing_cover(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(Path(temp_dir))
            controller.archivos = ["low.mp3", "coverless.mp3", "ok.mp3"]
            controller.tracks["low.mp3"] = CachedTrack({}, {"low_bitrate": True})
            controller.tracks["coverless.mp3"] = CachedTrack({}, {})
            controller.tracks["ok.mp3"] = CachedTrack({}, {})

            self.assertEqual(smart_playlist_filenames(controller, "low_bitrate"), ["low.mp3"])
            self.assertEqual(smart_playlist_filenames(controller, "missing_cover"), ["coverless.mp3"])

    def test_smart_playlist_filters_artist_and_genre(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(Path(temp_dir))
            controller.archivos = ["moka.mp3", "other.mp3", "rock.mp3"]
            controller.tracks["moka.mp3"] = CachedTrack({"artist": "MOKA"})
            controller.tracks["other.mp3"] = CachedTrack({"artist": "Otro Artista", "genre": "Pop"})
            controller.tracks["rock.mp3"] = CachedTrack({"artist": "Banda", "genre": "Rock Latino"})

            self.assertEqual(smart_playlist_filenames(controller, "artist:moka"), ["moka.mp3"])
            self.assertEqual(smart_playlist_filenames(controller, "genre:rock"), ["rock.mp3"])

    def test_smart_playlist_duration_stops_when_target_is_reached(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(Path(temp_dir))
            controller.archivos = ["one.mp3", "two.mp3", "three.mp3"]
            controller.tracks["one.mp3"] = CachedTrack({}, duration=120)
            controller.tracks["two.mp3"] = CachedTrack({}, duration=180)
            controller.tracks["three.mp3"] = CachedTrack({}, duration=240)

            self.assertEqual(smart_playlist_filenames(controller, "duration:5"), ["one.mp3", "two.mp3"])

    def test_smart_playlist_rejects_invalid_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(Path(temp_dir))
            controller.archivos = ["one.mp3"]
            controller.tracks["one.mp3"] = CachedTrack({}, duration=120)

            with self.assertRaises(ValueError):
                smart_playlist_filenames(controller, "duration:abc")


if __name__ == "__main__":
    unittest.main()
