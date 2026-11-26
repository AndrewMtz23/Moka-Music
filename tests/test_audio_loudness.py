import math
import shutil
import struct
import tempfile
import threading
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from app.models.audio_edit_project import AudioEditClip, AudioEditProject, AudioEditTrack
from app.services.audio_edit_service import AudioEditCancelled, AudioEditError, render_audio_project, split_clip
from app.services.audio_loudness_service import analyze_clip_loudness, recommend_level
from app.services.audio_project_storage import load_editor_project, save_editor_project


class LoudnessTests(unittest.TestCase):
    def test_cancel_during_analysis_kills_and_reaps_process(self):
        cancel = threading.Event()
        process = Mock()
        process.poll.return_value = None

        def start(*args, **kwargs):
            cancel.set()
            return process

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            source.touch()
            with (
                patch("app.services.audio_loudness_service.shutil.which", return_value="ffmpeg"),
                patch("app.services.audio_loudness_service.subprocess.Popen", side_effect=start),
            ):
                with self.assertRaises(AudioEditCancelled):
                    analyze_clip_loudness(AudioEditClip(source, 0, 3), cancel_event=cancel)
        process.kill.assert_called_once()
        process.communicate.assert_called_once()

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_real_silence_is_not_boosted(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "silence.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\0" * 24000)
            with self.assertRaisesRegex(AudioEditError, "silent"):
                analyze_clip_loudness(AudioEditClip(source, 0, 3))

    def test_split_preserves_leveling(self):
        clip = AudioEditClip("source.wav", 0, 4, leveling_gain_db=14)
        self.assertEqual([item.leveling_gain_db for item in split_clip(clip, 2)], [14, 14])

    def test_recommendation_limits_peaks_and_rejects_silence(self):
        self.assertAlmostEqual(recommend_level(-30, -20).gain_db, 14)
        self.assertAlmostEqual(recommend_level(-30, -4).gain_db, 2.9)
        self.assertLess(recommend_level(-10, -1).gain_db, 0)
        with self.assertRaises(AudioEditError):
            recommend_level(float("-inf"), float("-inf"))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_real_analysis_export_and_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                wav.writeframes(
                    b"".join(
                        struct.pack("<h", round(300 * math.sin(i * 2 * math.pi * 440 / 44100)))
                        for i in range(44100 * 3)
                    )
                )
            original = source.read_bytes()
            clip = AudioEditClip(source, 0, 3)
            result = analyze_clip_loudness(clip)
            self.assertGreater(result.gain_db, 10)
            leveled = replace(clip, leveling_gain_db=result.gain_db)
            project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (leveled,)),))
            save_editor_project(root / "project.json", project, [source])
            self.assertEqual(load_editor_project(root / "project.json")[0], project)
            output = render_audio_project(project, root / "leveled.wav")
            preview = render_audio_project(project, root / "preview.wav", preview_region=(0.5, 1.5))
            with wave.open(str(output), "rb") as full, wave.open(str(preview), "rb") as short:
                full.setpos(round(full.getframerate() * 0.5))
                self.assertEqual(full.readframes(full.getframerate()), short.readframes(short.getnframes()))
            measured = analyze_clip_loudness(AudioEditClip(output, 0, 3))
            self.assertAlmostEqual(measured.integrated_lufs, -16, delta=0.2)
            self.assertLessEqual(measured.true_peak_db, -1)
            self.assertEqual(source.read_bytes(), original)
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(AudioEditCancelled):
                analyze_clip_loudness(clip, cancel_event=cancel)

    def test_leveling_gain_rejects_invalid_values(self):
        for gain in (float("nan"), float("inf"), 61, -61):
            with self.assertRaises(ValueError):
                AudioEditClip("source.wav", 0, 1, leveling_gain_db=gain)
