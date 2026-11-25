import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services.audio_edit_service import _get_available_audio_filters, _run_render_process
from app.services.audio_waveform_service import extract_waveform


class EditorBackgroundProcessTests(unittest.TestCase):
    def assert_background_process(self, call):
        self.assertEqual(call.kwargs.get("creationflags"), getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_render_keeps_progress_pipes_without_opening_console(self):
        process = SimpleNamespace(stdout=io.StringIO(""), stderr=io.StringIO(""), poll=lambda: 0, returncode=0)
        with patch("app.services.audio_edit_service.subprocess.Popen", return_value=process) as popen:
            _run_render_process(["ffmpeg"], 1, None, None)
        self.assert_background_process(popen.call_args)
        self.assertEqual(popen.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(popen.call_args.kwargs["stderr"], subprocess.PIPE)

    def test_filter_inspection_does_not_open_console(self):
        _get_available_audio_filters.cache_clear()
        self.addCleanup(_get_available_audio_filters.cache_clear)
        with (
            patch("app.services.audio_edit_service.shutil.which", return_value="ffmpeg"),
            patch(
                "app.services.audio_edit_service.subprocess.run",
                return_value=SimpleNamespace(stdout=" T.. aecho A->A echo"),
            ) as run,
        ):
            self.assertIn("aecho", _get_available_audio_filters())
        self.assert_background_process(run.call_args)

    def test_waveform_does_not_open_console(self):
        png = io.BytesIO()
        Image.new("RGB", (4, 8)).save(png, format="PNG")
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("app.services.audio_waveform_service.shutil.which", return_value="ffmpeg"),
            patch(
                "app.services.audio_waveform_service.mutagen.File",
                return_value=SimpleNamespace(info=SimpleNamespace(length=1)),
            ),
            patch("app.services.audio_waveform_service.subprocess.Popen") as popen,
        ):
            source = Path(folder) / "source.wav"
            source.touch()
            popen.return_value.communicate.return_value = (png.getvalue(), b"")
            popen.return_value.returncode = 0
            self.assertEqual(extract_waveform(source, width=4, height=8).duration, 1)
        self.assert_background_process(popen.call_args)
