import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.services.youtube_download_service import (
    FFmpegUnavailableError,
    InvalidYouTubeUrlError,
    YouTubeDownloadError,
    YouTubeDownloadProgress,
    _build_options,
    download_youtube_audio,
    validate_youtube_url,
)


class YouTubeDownloadServiceTests(unittest.TestCase):
    def test_validate_accepts_supported_video_urls(self):
        urls = (
            "https://www.youtube.com/watch?v=video_01",
            "https://youtu.be/video-02",
            "https://m.youtube.com/shorts/video03",
            "https://music.youtube.com/watch?v=video04",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(validate_youtube_url(url), url)

    def test_validate_rejects_non_youtube_and_non_video_urls(self):
        for url in ("https://example.com/watch?v=abc", "https://youtube.com/", "not a URL"):
            with self.subTest(url=url):
                with self.assertRaises(InvalidYouTubeUrlError):
                    validate_youtube_url(url)

    def test_options_use_best_audio_mp3_320_and_windows_safe_names(self):
        options = _build_options(Path("C:/Downloads/temp"), None)

        self.assertEqual(options["format"], "bestaudio/best")
        self.assertEqual(
            options["postprocessors"],
            [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
        )
        self.assertTrue(options["windowsfilenames"])
        self.assertFalse(options["overwrites"])
        self.assertTrue(options["noplaylist"])

    def test_yt_dlp_sanitizes_reserved_characters_in_windows_filename(self):
        with YoutubeDL(_build_options(Path("C:/Downloads/temp"), None)) as downloader:
            filename = Path(downloader.prepare_filename({"title": 'A:B ? <C> | "D"*', "ext": "webm", "id": "abc"})).name

        self.assertFalse(any(character in filename for character in '<>:"/\\|?*'))

    @patch("app.services.youtube_download_service.shutil.which", return_value=None)
    def test_missing_ffmpeg_is_reported(self, _which):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FFmpegUnavailableError):
                download_youtube_audio("https://youtu.be/video01", temp_dir)

    @patch("app.services.youtube_download_service.shutil.which", return_value="ffmpeg")
    def test_missing_destination_is_reported(self, _which):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "incoming"
            with self.assertRaisesRegex(YouTubeDownloadError, "not a folder"):
                download_youtube_audio("https://youtu.be/video01", missing)

    @patch("app.services.youtube_download_service.shutil.which", return_value="ffmpeg")
    @patch("app.services.youtube_download_service.YoutubeDL")
    def test_download_moves_mp3_to_destination_without_overwriting(self, youtube_dl, _which):
        def extract_info(url, *, download):
            self.assertEqual(url, "https://youtu.be/video01")
            self.assertTrue(download)
            output = Path(youtube_dl.call_args.args[0]["outtmpl"]["default"].replace("%(title)s.%(ext)s", "Song.mp3"))
            output.write_bytes(b"mp3 data")
            return {"title": "Song", "filepath": str(output)}

        context = youtube_dl.return_value.__enter__.return_value
        context.extract_info.side_effect = extract_info

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            (destination / "Song.mp3").write_bytes(b"existing file")

            result = download_youtube_audio(
                "https://youtu.be/video01",
                destination,
                progress_callback=lambda event: event.stage != "complete",
            )

            self.assertEqual(result.title, "Song")
            self.assertEqual(result.path.name, "Song (2).mp3")
            self.assertEqual(result.path.read_bytes(), b"mp3 data")
            self.assertEqual((destination / "Song.mp3").read_bytes(), b"existing file")
            options = youtube_dl.call_args.args[0]
            self.assertEqual(options["format"], "bestaudio/best")
            self.assertTrue(options["windowsfilenames"])

    @patch("app.services.youtube_download_service.shutil.which", return_value="ffmpeg")
    @patch("app.services.youtube_download_service.YoutubeDL")
    def test_download_reports_percent_and_conversion_stage(self, youtube_dl, _which):
        events: list[YouTubeDownloadProgress] = []

        def extract_info(_url, *, download):
            options = youtube_dl.call_args.args[0]
            output = Path(options["outtmpl"]["default"].replace("%(title)s.%(ext)s", "Song.mp3"))
            output.write_bytes(b"mp3 data")
            options["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 25, "total_bytes": 100})
            options["postprocessor_hooks"][0]({"status": "started"})
            return {"title": "Song", "filepath": str(output)}

        youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = extract_info

        with tempfile.TemporaryDirectory() as temp_dir:
            download_youtube_audio(
                "https://youtu.be/video01",
                temp_dir,
                progress_callback=lambda event: events.append(event),
            )

        self.assertIn(YouTubeDownloadProgress(stage="downloading", percent=25.0), events)
        self.assertIn(YouTubeDownloadProgress(stage="converting"), events)
        self.assertEqual(events[-1], YouTubeDownloadProgress(stage="complete", percent=100.0))

    def test_progress_hook_uses_estimated_size_and_reports_unknown_percentage(self):
        events = []
        options = _build_options(Path("C:/Downloads/temp"), events.append)

        options["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 0, "total_bytes_estimate": 80})
        options["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 12})

        self.assertEqual(events[0], YouTubeDownloadProgress(stage="downloading", percent=0.0))
        self.assertEqual(events[1], YouTubeDownloadProgress(stage="downloading"))

    @patch("app.services.youtube_download_service.shutil.which", return_value="ffmpeg")
    @patch("app.services.youtube_download_service.YoutubeDL")
    def test_download_error_is_reported_and_temporary_files_are_removed(self, youtube_dl, _which):
        def fail(_url, *, download):
            options = youtube_dl.call_args.args[0]
            partial = Path(options["outtmpl"]["default"].replace("%(title)s.%(ext)s", "partial.part"))
            partial.write_bytes(b"partial")
            raise DownloadError("Video unavailable")

        youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = fail

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(YouTubeDownloadError, "Video unavailable"):
                download_youtube_audio("https://youtu.be/video01", temp_dir)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    @patch("app.services.youtube_download_service.shutil.which", return_value="ffmpeg")
    @patch("app.services.youtube_download_service.YoutubeDL")
    def test_connection_errors_are_preserved_for_the_ui(self, youtube_dl, _which):
        youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = DownloadError("Connection refused")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(YouTubeDownloadError, "Connection refused"):
                download_youtube_audio("https://youtu.be/video01", temp_dir)


if __name__ == "__main__":
    unittest.main()
