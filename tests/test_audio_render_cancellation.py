import io
import threading
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from app.models.audio_edit_project import AudioEditClip, AudioEditProject, AudioEditTrack
from app.services.audio_edit_service import AudioEditCancelled, export_audio_project


class RenderCompletionCancellationTests(unittest.TestCase):
    def test_cancel_at_process_exit_does_not_publish_export(self):
        for with_progress in (False, True):
            with self.subTest(with_progress=with_progress):
                self._export_at_process_exit(cancel=True, with_progress=with_progress)

    def test_successful_process_exit_still_publishes_export(self):
        self._export_at_process_exit(cancel=False, with_progress=True)

    def _export_at_process_exit(self, *, cancel, with_progress):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.wav"
            with wave.open(str(source), "wb") as audio:
                audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                audio.writeframes(b"\0\0" * 8000)
            original = source.read_bytes()
            project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (AudioEditClip(source, 0, 1),)),))
            cancelled = threading.Event()
            progress = []

            def report(percent, _message):
                progress.append(percent)
                return True

            def start_process(command, **_kwargs):
                # Control the external process boundary to reproduce the race
                # without timing-dependent sleeps; keep render/export cleanup real.
                Path(command[-1]).write_bytes(original)

                def poll():
                    if cancel:
                        cancelled.set()
                    return 0

                return SimpleNamespace(stdout=io.StringIO(""), stderr=io.StringIO(""), poll=poll, returncode=0)

            with (
                patch("app.services.audio_edit_service.subprocess.Popen", side_effect=start_process),
                patch("app.services.audio_edit_service.shutil.which", return_value="ffmpeg"),
            ):
                kwargs = {"cancel_event": cancelled, "progress_callback": report if with_progress else None}
                if cancel:
                    with self.assertRaises(AudioEditCancelled):
                        export_audio_project(project, root, "trimmed", ".wav", **kwargs)
                    self.assertEqual(list(root.iterdir()), [source])
                    self.assertNotIn(100, progress)
                else:
                    result = export_audio_project(project, root, "trimmed", ".wav", **kwargs)
                    self.assertEqual(result.read_bytes(), original)
                    self.assertEqual(progress, [100])
                    self.assertEqual(set(root.iterdir()), {source, result})
            self.assertEqual(source.read_bytes(), original)
