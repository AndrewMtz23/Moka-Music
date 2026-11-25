import io
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services.audio_waveform_service import (
    AudioWaveformCancelled,
    AudioWaveformError,
    build_waveform_command,
    extract_waveform,
)


def waveform_png(width=4, height=8):
    image = Image.new("RGB", (width, height), "black")
    for y in range(2, 6):
        image.putpixel((1, y), (64, 196, 255))
    for y in range(1, 7):
        image.putpixel((2, y), (64, 196, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class AudioWaveformServiceTests(unittest.TestCase):
    def test_build_waveform_command_bounds_image_dimensions_and_maps_audio(self):
        command = build_waveform_command("song.mp3", width=400, height=96)

        self.assertIn("[0:a:0]showwavespic=s=400x96:colors=0x40c4ff:scale=lin[v]", command)
        self.assertEqual(command[-1], "pipe:1")

    def test_build_waveform_command_rejects_nonpositive_dimensions(self):
        with self.assertRaises(ValueError):
            build_waveform_command("song.mp3", width=0, height=32)

    def test_build_waveform_command_rejects_unbounded_dimensions(self):
        with self.assertRaises(ValueError):
            build_waveform_command("song.mp3", width=5000, height=32)

    @patch("app.services.audio_waveform_service.shutil.which", return_value="ffmpeg")
    @patch(
        "app.services.audio_waveform_service.mutagen.File",
        return_value=SimpleNamespace(info=SimpleNamespace(length=12.5)),
    )
    @patch("app.services.audio_waveform_service.subprocess.Popen")
    def test_extract_waveform_returns_bounded_normalized_peaks(self, popen, _mutagen_file, _which):
        popen.return_value.poll.return_value = 0
        popen.return_value.communicate.return_value = (waveform_png(), b"")
        popen.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.mp3"
            source.write_bytes(b"audio")
            result = extract_waveform(source, width=4, height=8)

        self.assertEqual(result.duration, 12.5)
        self.assertEqual(len(result.peaks), 4)
        self.assertEqual(result.peaks[0], 0.0)
        self.assertGreater(result.peaks[1], 0.0)
        self.assertAlmostEqual(result.peaks[2], 5 / 7)
        self.assertEqual(result.peaks[3], 0.0)
        self.assertLessEqual(max(result.peaks), 1.0)

    def test_extract_waveform_rejects_missing_source(self):
        with self.assertRaisesRegex(AudioWaveformError, "does not exist"):
            extract_waveform("missing.mp3")

    def test_extract_waveform_honors_cancel_before_starting_ffmpeg(self):
        cancel_event = threading.Event()
        cancel_event.set()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.mp3"
            source.write_bytes(b"audio")
            with patch("app.services.audio_waveform_service.shutil.which") as which:
                with self.assertRaises(AudioWaveformCancelled):
                    extract_waveform(source, cancel_event=cancel_event)
            which.assert_not_called()

    @patch("app.services.audio_waveform_service.shutil.which", return_value=None)
    def test_extract_waveform_reports_missing_ffmpeg(self, _which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.mp3"
            source.write_bytes(b"audio")
            with self.assertRaisesRegex(AudioWaveformError, "FFmpeg"):
                extract_waveform(source)

    @patch("app.services.audio_waveform_service.shutil.which", return_value="ffmpeg")
    @patch(
        "app.services.audio_waveform_service.mutagen.File",
        return_value=SimpleNamespace(info=SimpleNamespace(length=12.5)),
    )
    @patch("app.services.audio_waveform_service.subprocess.Popen")
    def test_extract_waveform_reports_ffmpeg_failure(self, popen, _mutagen_file, _which):
        popen.return_value.poll.return_value = 1
        popen.return_value.communicate.return_value = (b"", b"decode failed")
        popen.return_value.returncode = 1
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.mp3"
            source.write_bytes(b"audio")
            with self.assertRaisesRegex(AudioWaveformError, "decode failed"):
                extract_waveform(source)

    @patch("app.services.audio_waveform_service.shutil.which", return_value="ffmpeg")
    @patch(
        "app.services.audio_waveform_service.mutagen.File",
        return_value=SimpleNamespace(info=SimpleNamespace(length=12.5)),
    )
    @patch("app.services.audio_waveform_service.subprocess.Popen")
    def test_extract_waveform_terminates_ffmpeg_when_cancelled(self, popen, _mutagen_file, _which):
        cancel_event = threading.Event()
        process = popen.return_value

        def wait_for_process(timeout=None):
            if process.communicate.call_count == 1:
                cancel_event.set()
                raise subprocess.TimeoutExpired("ffmpeg", timeout)
            return b"", b""

        process.communicate.side_effect = wait_for_process
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.mp3"
            source.write_bytes(b"audio")
            with self.assertRaises(AudioWaveformCancelled):
                extract_waveform(source, cancel_event=cancel_event)
        process.terminate.assert_called_once()
        self.assertEqual(process.communicate.call_count, 2)


if __name__ == "__main__":
    unittest.main()
