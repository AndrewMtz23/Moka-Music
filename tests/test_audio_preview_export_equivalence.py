"""Compare rendered audio, not only FFmpeg command construction."""

import math
import shutil
import struct
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models.audio_edit_project import (
    AudioEditClip,
    AudioEditEffect,
    AudioEditMode,
    AudioEditProject,
    AudioEditTrack,
)
from app.services.audio_edit_service import export_audio_project, render_audio_project


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
class PreviewExportEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "source.wav"
        rate = 44100
        # Cosine deliberately starts away from zero: an abrupt cut has a
        # measurable boundary step, so a fade cannot pass by testing silence.
        with wave.open(str(self.source), "wb") as audio:
            audio.setparams((2, 2, rate, 0, "NONE", "not compressed"))
            audio.writeframes(
                b"".join(
                    struct.pack(
                        "<hh",
                        int(6000 * math.cos(2 * math.pi * 440 * i / rate)),
                        int(4000 * math.cos(2 * math.pi * 660 * i / rate)),
                    )
                    for i in range(3 * rate)
                )
            )
        self.original = self.source.read_bytes()

    def pcm(self, path):
        with wave.open(str(path), "rb") as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()), (44100, 2, 2))
            return audio.readframes(audio.getnframes())

    def assert_regions_match(self, project, regions):
        output = export_audio_project(project, self.root, "export", ".wav")
        full = self.pcm(output)
        for index, (start, end) in enumerate(regions):
            with self.subTest(region=(start, end)):
                preview = render_audio_project(project, self.root / f"preview-{index}.wav", preview_region=(start, end))
                expected = full[round(start * 44100) * 4 : round(end * 44100) * 4]
                self.assertEqual(len(expected), round((end - start) * 44100) * 4)
                self.assertEqual(self.pcm(preview), expected)
        self.assertEqual(self.source.read_bytes(), self.original)
        return full

    def test_short_fades_reduce_boundary_steps_without_changing_middle(self):
        clip = AudioEditClip(self.source, 0.5, 1.5, fade_in=0.01, fade_out=0.01)
        project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (clip,)),))
        faded = self.assert_regions_match(project, ((0, 0.1), (0.9, 1)))
        dry_project = replace(
            project, tracks=(replace(project.tracks[0], clips=(replace(clip, fade_in=0, fade_out=0),)),)
        )
        dry = self.pcm(render_audio_project(dry_project, self.root / "dry.wav"))
        self.assertEqual(len(faded), len(dry))
        self.assertEqual(faded[882 * 4 : -882 * 4], dry[882 * 4 : -882 * 4])
        for offset in (0, len(faded) - 4):
            self.assertGreater(max(abs(v) for v in struct.unpack_from("<hh", dry, offset)), 1000)
            self.assertLess(max(abs(v) for v in struct.unpack_from("<hh", faded, offset)), 32)

    def test_crossfade_audition_matches_export_across_transition(self):
        clips = (
            AudioEditClip(self.source, 0, 1),
            AudioEditClip(self.source, 1, 2, timeline_start=0.75, crossfade_in=0.25),
        )
        project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", clips),))
        self.assert_regions_match(project, ((0.7, 1.1), (1.5, 1.75)))

    def test_multitrack_audition_keeps_neighboring_audio_gain_pan_and_mute(self):
        project = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(
                AudioEditTrack("a", "First", (AudioEditClip(self.source, 0, 1, fade_out=0.01, pan=-0.5),)),
                AudioEditTrack(
                    "b", "Neighbor", (AudioEditClip(self.source, 1, 2, timeline_start=0.25, gain_db=-6),), volume=0.5
                ),
                AudioEditTrack("c", "Muted", (AudioEditClip(self.source, 0, 1),), muted=True),
            ),
        )
        self.assert_regions_match(project, ((0, 0.1), (0.95, 1.05), (1.15, 1.25)))

    def test_effect_history_is_preserved_in_late_audition(self):
        effects = (AudioEditEffect("delay", wet=0.3, delay_ms=250, feedback=0.4),)
        clip = AudioEditClip(self.source, 0.5, 2.5, effects=effects, fade_out=0.01)
        project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (clip,)),))
        self.assert_regions_match(project, ((0.3, 0.6), (1.9, 2)))
