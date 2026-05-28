import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.audio_conversion_service import build_conversion_items, build_ffmpeg_command, convert_audio_files, preset_by_id


class AudioConversionServiceTests(unittest.TestCase):
    def test_build_conversion_items_uses_unique_destinations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "song.mp3").touch()

            items = build_conversion_items(["/music/song.wav", "/other/song.flac"], folder, "mp3")

            self.assertEqual(items[0].destination.name, "song (2).mp3")
            self.assertEqual(items[1].destination.name, "song (3).mp3")

    def test_build_ffmpeg_command_sets_codec_for_mp3(self):
        command = build_ffmpeg_command(Path("in.wav"), Path("out.mp3"), overwrite=True, bitrate="320k")

        self.assertIn("-y", command)
        self.assertIn("libmp3lame", command)
        self.assertIn("320k", command)
        self.assertEqual(command[-1], "out.mp3")

    def test_build_conversion_items_can_preserve_folder_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "library"
            source = root / "artist" / "album" / "song.wav"
            source.parent.mkdir(parents=True)
            source.touch()

            items = build_conversion_items(
                [source],
                Path(temp_dir) / "converted",
                ".mp3",
                bitrate="256k",
                preserve_structure=True,
                source_root=root,
            )

            self.assertEqual(items[0].destination, Path(temp_dir) / "converted" / "artist" / "album" / "song.mp3")
            self.assertEqual(items[0].bitrate, "256k")

    def test_preserve_folder_structure_allows_same_name_in_different_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "library"
            one = root / "one" / "song.wav"
            two = root / "two" / "song.wav"
            one.parent.mkdir(parents=True)
            two.parent.mkdir(parents=True)
            one.touch()
            two.touch()

            items = build_conversion_items(
                [one, two],
                Path(temp_dir) / "converted",
                ".mp3",
                preserve_structure=True,
                source_root=root,
            )

            self.assertEqual(items[0].destination.name, "song.mp3")
            self.assertEqual(items[1].destination.name, "song.mp3")
            self.assertNotEqual(items[0].destination.parent, items[1].destination.parent)

    def test_preset_by_id_returns_conversion_preset(self):
        preset = preset_by_id("mp3_128")

        self.assertEqual(preset.extension, ".mp3")
        self.assertEqual(preset.bitrate, "128k")

    @patch("app.services.audio_conversion_service.ffmpeg_available", return_value=True)
    @patch("app.services.audio_conversion_service.subprocess.run")
    def test_convert_audio_files_reports_success(self, run, _available):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "in.wav"
            destination = Path(temp_dir) / "out.mp3"
            source.touch()

            result = convert_audio_files(build_conversion_items([source], temp_dir, ".mp3"))

            self.assertEqual(result.converted, 1)
            self.assertEqual(result.errors, [])
            self.assertTrue(run.called)


if __name__ == "__main__":
    unittest.main()
