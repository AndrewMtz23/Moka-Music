import errno
import math
import shutil
import struct
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import mutagen

from app.models.audio_edit_project import (
    AudioEditClip,
    AudioEditEffect,
    AudioEditEffectKind,
    AudioEditMarker,
    AudioEditMode,
    AudioEditProcessing,
    AudioEditProject,
    AudioEditTrack,
)
from app.services.audio_edit_service import (
    AudioEditCancelled,
    AudioEditError,
    apply_crossfade,
    build_render_command,
    build_retained_clips,
    export_audio_project,
    move_sequence_clip,
    overlapping_clip_pairs,
    remove_clip_interval,
    render_audio_project,
    sequence_clips,
    split_clip,
    trim_clip,
    validate_clip_bounds,
)


class AudioEditServiceTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("song.mp3")

    def test_trim_can_restore_with_verified_source_duration(self):
        clip = AudioEditClip(self.source, 2, 8, fade_in=1, fade_out=1)
        restored = trim_clip(clip, 0, 10, source_duration=10)
        self.assertEqual((restored.source_start, restored.source_end), (0, 10))
        self.assertEqual((restored.fade_in, restored.fade_out, restored.id), (1, 1, clip.id))
        rounded = trim_clip(clip, -1e-14, 10 + 1e-14, source_duration=10)
        self.assertEqual((rounded.source_start, rounded.source_end), (0, 10))
        with self.assertRaises(AudioEditError):
            trim_clip(clip, -0.001, 10, source_duration=10)
        with self.assertRaises(AudioEditError):
            trim_clip(clip, 0, 10)
        for duration in (0, -1, float("nan"), float("inf"), "bad"):
            with self.subTest(duration=duration), self.assertRaises(AudioEditError):
                trim_clip(clip, 0, 10, source_duration=duration)
        with self.assertRaises(AudioEditError):
            trim_clip(clip, 0, 11, source_duration=10)

    @patch("pathlib.Path.is_file", return_value=True)
    def test_preview_region_trims_final_mix_and_validates_limits(self, _is_file):
        project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (AudioEditClip(self.source, 0, 10),)),))
        command = build_render_command(project, Path("preview.wav"), preview_region=(2, 5))
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn(
            "[outa]apad=whole_dur=10.000000000,atrim=start=2.000000000:end=5.000000000,asetpts=PTS-STARTPTS[region]",
            graph,
        )
        self.assertEqual(command[command.index("-map") + 1], "[region]")
        for region in ((-1, 2), (3, 2), (2, 11), (0, float("nan"))):
            with self.subTest(region=region), self.assertRaises(AudioEditError):
                build_render_command(project, Path("preview.wav"), preview_region=region)
        full = build_render_command(project, Path("export.wav"))
        self.assertEqual(full[full.index("-map") + 1], "[outa]")

    def test_clip_rejects_invalid_times_and_fades(self):
        for values in (
            {"source_start": -1, "source_end": 5},
            {"source_start": 5, "source_end": 5},
            {"source_start": 0, "source_end": 5, "timeline_start": -1},
            {"source_start": 0, "source_end": 5, "fade_in": 3, "fade_out": 3},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                AudioEditClip(source_path=self.source, **values)

    def test_clip_rejects_crossfade_longer_than_its_source_range(self):
        with self.assertRaisesRegex(ValueError, "crossfade"):
            AudioEditClip(self.source, 0, 3, crossfade_in=4)

    def test_clip_normalizes_and_validates_gain_and_pan(self):
        clip = AudioEditClip(self.source, 0, 3, gain_db="-6", pan="0.5")

        self.assertEqual((clip.gain_db, clip.pan), (-6.0, 0.5))
        for values in (
            {"gain_db": float("nan")},
            {"gain_db": float("inf")},
            {"gain_db": -60.1},
            {"gain_db": 12.1},
            {"pan": float("nan")},
            {"pan": -1.01},
            {"pan": 1.01},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                AudioEditClip(self.source, 0, 3, **values)

    def test_audio_effects_validate_parameters_and_clip_chain(self):
        delay = AudioEditEffect(AudioEditEffectKind.DELAY, wet="0.5", delay_ms="250", feedback="0.4")
        reverb = AudioEditEffect("reverb", room_size="0.8")
        clip = AudioEditClip(self.source, 0, 3, effects=(delay, reverb))

        self.assertEqual(delay.wet, 0.5)
        self.assertEqual(reverb.kind, AudioEditEffectKind.REVERB)
        self.assertEqual(clip.effects, (delay, reverb))

        for values in (
            {"wet": float("nan")},
            {"wet": -0.1},
            {"wet": 1.1},
            {"delay_ms": 39},
            {"delay_ms": 1501},
            {"feedback": 0.81},
            {"room_size": 0.09},
            {"kind": "chorus"},
        ):
            arguments = {"kind": AudioEditEffectKind.DELAY, **values}
            with self.subTest(values=values), self.assertRaises(ValueError):
                AudioEditEffect(**arguments)

        with self.assertRaisesRegex(ValueError, "8 effects"):
            AudioEditClip(self.source, 0, 3, effects=tuple(AudioEditEffect("delay") for _ in range(9)))
        repeated = AudioEditEffect("delay", id="same")
        repeated_again = AudioEditEffect("reverb", id="same")
        with self.assertRaisesRegex(ValueError, "unique"):
            AudioEditClip(self.source, 0, 3, effects=(repeated, repeated_again))

    def test_audio_processing_validates_eq_and_compressor_parameters(self):
        neutral = AudioEditProcessing()
        self.assertTrue(neutral.is_neutral)
        self.assertTrue(AudioEditProcessing(bypassed=True).is_neutral)
        enabled = AudioEditProcessing(compressor_enabled=True)
        self.assertFalse(enabled.is_neutral)

        invalid_values = (
            {"low_gain_db": float("nan")},
            {"low_gain_db": -12.1},
            {"mid_gain_db": 12.1},
            {"high_gain_db": float("inf")},
            {"compressor_threshold_db": -61},
            {"compressor_threshold_db": 1},
            {"compressor_ratio": 0.9},
            {"compressor_ratio": 20.1},
            {"compressor_attack_ms": 0.09},
            {"compressor_attack_ms": 1000.1},
            {"compressor_release_ms": 0.9},
            {"compressor_release_ms": 1000.1},
            {"compressor_makeup_db": -0.1},
            {"compressor_makeup_db": 12.1},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ValueError):
                AudioEditProcessing(**values)

    def test_models_normalize_paths_and_compute_project_duration(self):
        clip = AudioEditClip(self.source, 0, 10, timeline_start=5, id="clip")
        track = AudioEditTrack(id="track", name="Track", clips=(clip,))
        project = AudioEditProject(mode=AudioEditMode.MULTITRACK, tracks=(track,), markers=(AudioEditMarker(4),))

        self.assertEqual(clip.source_path, self.source)
        self.assertEqual(project.duration, 15)

    def test_project_rejects_duplicate_track_ids(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            AudioEditProject(
                tracks=(
                    AudioEditTrack(id="same", name="First"),
                    AudioEditTrack(id="same", name="Second"),
                )
            )

    def test_build_retained_clips_removes_internal_interval_and_compacts_sequence(self):
        clips = build_retained_clips(self.source, 180, [(50, 55)])

        self.assertEqual(
            [(clip.source_start, clip.source_end, clip.timeline_start) for clip in clips],
            [(0, 50, 0), (55, 180, 50)],
        )
        self.assertEqual(sum(clip.duration for clip in clips), 175)

    def test_build_retained_clips_merges_overlapping_and_adjacent_removed_intervals(self):
        clips = build_retained_clips(self.source, 30, [(10, 15), (14, 20), (20, 22)])

        self.assertEqual(
            [(clip.source_start, clip.source_end) for clip in clips],
            [(0, 10), (22, 30)],
        )

    def test_build_retained_clips_rejects_invalid_interval_and_empty_result(self):
        for intervals in ([(0, 0)], [(-1, 2)], [(4, 31)], [(0, 30)]):
            with self.subTest(intervals=intervals), self.assertRaises(AudioEditError):
                build_retained_clips(self.source, 30, intervals)

    def test_validate_clip_bounds_rejects_source_end_after_duration(self):
        clip = AudioEditClip(self.source, 5, 11)

        with self.assertRaisesRegex(AudioEditError, "source duration"):
            validate_clip_bounds(clip, 10)

    def test_sequence_clips_places_clips_contiguously_in_input_order(self):
        first = AudioEditClip(self.source, 0, 10, timeline_start=90, id="first")
        second = AudioEditClip(Path("other.mp3"), 5, 15, timeline_start=0, id="second")

        result = sequence_clips([first, second])

        self.assertEqual([clip.id for clip in result], ["first", "second"])
        self.assertEqual([clip.timeline_start for clip in result], [0, 10])

    def test_sequence_clips_overlaps_only_the_declared_crossfade_interval(self):
        first = AudioEditClip(self.source, 0, 10, id="first")
        second = AudioEditClip(Path("other.mp3"), 0, 8, crossfade_in=2, id="second")
        third = AudioEditClip(Path("third.mp3"), 0, 4, crossfade_in=1, id="third")

        result = sequence_clips((first, second, third))

        self.assertEqual([clip.timeline_start for clip in result], [0, 8, 15])
        self.assertEqual(result[-1].timeline_end, 19)

    def test_sequence_clips_rejects_crossfade_on_first_clip_and_on_faded_edges(self):
        first_transition = AudioEditClip(self.source, 0, 5, crossfade_in=1, id="first")
        with self.assertRaisesRegex(AudioEditError, "first"):
            sequence_clips((first_transition,))

        first = AudioEditClip(self.source, 0, 5, fade_out=0.5, id="first")
        second = AudioEditClip(Path("other.mp3"), 0, 5, crossfade_in=1, id="second")
        with self.assertRaisesRegex(AudioEditError, "fade-out"):
            sequence_clips((first, second))

    def test_sequence_clips_rejects_empty_arrangement(self):
        with self.assertRaisesRegex(AudioEditError, "at least one"):
            sequence_clips([])

    def test_split_clip_keeps_source_ranges_contiguous_and_preserves_outer_fades(self):
        clip = AudioEditClip(
            self.source,
            10,
            30,
            timeline_start=4,
            fade_in=2,
            fade_out=3,
            id="original",
            gain_db=-6,
            pan=0.5,
        )

        left, right = split_clip(clip, 18)

        self.assertEqual((left.source_start, left.source_end, left.timeline_start), (10, 18, 4))
        self.assertEqual((right.source_start, right.source_end, right.timeline_start), (18, 30, 12))
        self.assertEqual((left.fade_in, left.fade_out), (2, 0))
        self.assertEqual((right.fade_in, right.fade_out), (0, 3))
        self.assertEqual((left.gain_db, left.pan), (-6, 0.5))
        self.assertEqual((right.gain_db, right.pan), (-6, 0.5))

    def test_split_clip_rejects_boundary_split(self):
        clip = AudioEditClip(self.source, 10, 30)

        with self.assertRaisesRegex(AudioEditError, "inside"):
            split_clip(clip, 10)

    def test_trim_clip_restricts_range_and_clamps_fades(self):
        clip = AudioEditClip(self.source, 0, 30, fade_in=8, fade_out=8, id="clip")

        trimmed = trim_clip(clip, 5, 15)

        self.assertEqual((trimmed.source_start, trimmed.source_end), (5, 15))
        self.assertEqual((trimmed.fade_in, trimmed.fade_out), (8, 2))
        self.assertEqual(clip.source_start, 0)
        self.assertEqual(clip.source_end, 30)

    def test_trim_clip_rejects_ranges_outside_selected_clip(self):
        clip = AudioEditClip(self.source, 10, 30)

        with self.assertRaisesRegex(AudioEditError, "inside"):
            trim_clip(clip, 0, 20)
        with self.assertRaisesRegex(AudioEditError, "inside"):
            trim_clip(clip, 10, 31)

    def test_remove_clip_interval_keeps_audio_before_and_after_gap(self):
        clip = AudioEditClip(self.source, 10, 40, timeline_start=7, id="clip")

        left, right = remove_clip_interval(clip, 20, 25)
        sequenced = sequence_clips((left, right))

        self.assertEqual((left.source_start, left.source_end), (10, 20))
        self.assertEqual((right.source_start, right.source_end), (25, 40))
        self.assertEqual([item.timeline_start for item in sequenced], [0, 10])
        self.assertEqual(sum(item.duration for item in sequenced), 25)

    def test_remove_clip_interval_rejects_empty_or_boundary_ranges(self):
        clip = AudioEditClip(self.source, 10, 40)

        for interval in ((10, 20), (30, 40), (15, 15), (9, 20), (20, 41)):
            with self.subTest(interval=interval), self.assertRaises(AudioEditError):
                remove_clip_interval(clip, *interval)

    def test_move_sequence_clip_reorders_and_compacts(self):
        clips = (
            AudioEditClip(self.source, 0, 3, id="a"),
            AudioEditClip(self.source, 3, 7, id="b"),
            AudioEditClip(self.source, 7, 10, id="c"),
        )

        result = move_sequence_clip(clips, "a", 2)

        self.assertEqual([clip.id for clip in result], ["b", "c", "a"])
        self.assertEqual([clip.timeline_start for clip in result], [0, 4, 7])

    def test_move_sequence_clip_clears_a_crossfade_when_its_neighbor_changes(self):
        clips = (
            AudioEditClip(self.source, 0, 3, id="a"),
            AudioEditClip(self.source, 3, 7, timeline_start=2, crossfade_in=1, id="b"),
            AudioEditClip(self.source, 7, 10, timeline_start=9, id="c"),
        )

        result = move_sequence_clip(clips, "b", 2)

        self.assertEqual([clip.id for clip in result], ["a", "c", "b"])
        self.assertEqual([clip.crossfade_in for clip in result], [0, 0, 0])

    def test_overlapping_clip_pairs_detects_timeline_intersection(self):
        track = AudioEditTrack(
            id="track",
            name="Track",
            clips=(
                AudioEditClip(self.source, 0, 10, timeline_start=0, id="a"),
                AudioEditClip(self.source, 10, 20, timeline_start=8, id="b"),
                AudioEditClip(self.source, 20, 30, timeline_start=17, id="c"),
            ),
        )

        self.assertEqual(overlapping_clip_pairs(track), (("a", "b"), ("b", "c")))

    def test_apply_crossfade_sets_duration_and_shifts_following_clips(self):
        first = AudioEditClip(self.source, 0, 10, id="first")
        second = AudioEditClip(Path("second.mp3"), 0, 8, timeline_start=10, id="second")
        third = AudioEditClip(Path("third.mp3"), 0, 5, timeline_start=18, id="third")
        track = AudioEditTrack("track", "Track", (first, second, third))

        updated = apply_crossfade(track, "first", "second", 2)

        self.assertEqual(updated.clips[1].crossfade_in, 2)
        self.assertEqual(updated.clips[1].timeline_start, 8)
        self.assertEqual(updated.clips[2].timeline_start, 16)
        restored = apply_crossfade(updated, "first", "second", 0)
        self.assertEqual(restored.clips[1].timeline_start, 10)
        self.assertEqual(restored.clips[2].timeline_start, 18)

    def test_apply_crossfade_rejects_incompatible_fades_duration_and_nonadjacent_pairs(self):
        first = AudioEditClip(self.source, 0, 10, fade_out=1, id="first")
        second = AudioEditClip(Path("second.mp3"), 0, 8, timeline_start=10, fade_in=1, id="second")
        third = AudioEditClip(Path("third.mp3"), 0, 5, timeline_start=18, id="third")
        track = AudioEditTrack("track", "Track", (first, second, third))

        for pair, duration in ((("first", "second"), 2), (("first", "third"), 1), (("first", "second"), 11)):
            with self.subTest(pair=pair, duration=duration), self.assertRaises(AudioEditError):
                apply_crossfade(track, *pair, duration)

    def test_build_render_command_uses_acrossfade_instead_of_concat_for_sequence(self):
        first_path = self._touch_source("first.mp3")
        second_path = self._touch_source("second.mp3")
        project = AudioEditProject(
            mode=AudioEditMode.SEQUENCE,
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (
                        AudioEditClip(first_path, 0, 4, id="first"),
                        AudioEditClip(second_path, 0, 3, timeline_start=3, crossfade_in=1, id="second"),
                    ),
                ),
            ),
        )

        command = build_render_command(project, self.source_folder / "result.wav")
        graph = command[command.index("-filter_complex") + 1]

        self.assertIn("acrossfade=d=1.000000000:c1=qsin:c2=qsin[outa]", graph)
        self.assertNotIn("concat=n=2", graph)

    def test_build_render_command_crossfades_multitrack_clips_before_track_mix(self):
        first_path = self._touch_source("first.mp3")
        second_path = self._touch_source("second.mp3")
        overlay_path = self._touch_source("overlay.mp3")
        project = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(
                AudioEditTrack(
                    "first",
                    "First",
                    (
                        AudioEditClip(first_path, 0, 4, id="first"),
                        AudioEditClip(second_path, 0, 3, timeline_start=3, crossfade_in=1, id="second"),
                    ),
                ),
                AudioEditTrack(
                    "overlay",
                    "Overlay",
                    (AudioEditClip(overlay_path, 0, 1, timeline_start=1, id="overlay"),),
                ),
            ),
        )

        command = build_render_command(project, self.source_folder / "mix.wav")
        graph = command[command.index("-filter_complex") + 1]

        self.assertIn("acrossfade=d=1.000000000:c1=qsin:c2=qsin", graph)
        self.assertIn("amix=inputs=2:duration=longest", graph)
        self.assertIn("adelay=delays=1000|1000:all=1", graph)

    def test_build_render_command_concatenates_sequence_clips_and_applies_fades(self):
        first_path = self._touch_source("first.mp3")
        second_path = self._touch_source("second.mp3")
        project = AudioEditProject(
            mode=AudioEditMode.SEQUENCE,
            tracks=(
                AudioEditTrack(
                    id="sequence",
                    name="Sequence",
                    clips=(
                        AudioEditClip(first_path, 1, 4, fade_in=0.25, id="first"),
                        AudioEditClip(second_path, 0, 3, fade_out=0.5, id="second"),
                    ),
                ),
            ),
        )

        command = build_render_command(project, self.source_folder / "result.wav")
        filter_graph = command[command.index("-filter_complex") + 1]

        self.assertIn("concat=n=2:v=0:a=1[outa]", filter_graph)
        self.assertIn("afade=t=in:st=0:d=0.250000000", filter_graph)
        self.assertIn("afade=t=out:st=2.500000000:d=0.500000000", filter_graph)
        self.assertEqual(command[-1], str(self.source_folder / "result.wav"))

    def test_build_render_command_mixes_multitrack_clips_with_delay_and_gain(self):
        first_path = self._touch_source("first.mp3")
        second_path = self._touch_source("second.mp3")
        project = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(
                AudioEditTrack(
                    "first",
                    "First",
                    clips=(AudioEditClip(first_path, 0, 3, timeline_start=0, id="one"),),
                    volume=0.5,
                ),
                AudioEditTrack(
                    "second",
                    "Second",
                    clips=(AudioEditClip(second_path, 1, 4, timeline_start=2.25, id="two"),),
                ),
            ),
        )

        command = build_render_command(project, self.source_folder / "mix.mp3")
        graph = command[command.index("-filter_complex") + 1]

        self.assertIn("volume=0.500000", graph)
        self.assertIn("adelay=delays=2250|2250:all=1", graph)
        self.assertIn("amix=inputs=2:duration=longest", graph)

    def test_build_render_command_applies_per_clip_gain_and_pan_before_mixing(self):
        first_path = self._touch_source("first.mp3")
        second_path = self._touch_source("second.mp3")
        project = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(
                AudioEditTrack(
                    "first",
                    "First",
                    (AudioEditClip(first_path, 0, 3, gain_db=-6, pan=-0.5, id="one"),),
                    volume=0.5,
                ),
                AudioEditTrack(
                    "second",
                    "Second",
                    (AudioEditClip(second_path, 0, 3, timeline_start=1, gain_db=3, pan=0.75, id="two"),),
                ),
            ),
        )

        command = build_render_command(project, self.source_folder / "mix.wav")
        graph = command[command.index("-filter_complex") + 1]

        first_chain = graph.index("volume=-6.000000dB")
        first_pan = graph.index("pan=stereo|c0=1.000000*c0|c1=0.500000*c1")
        first_track_gain = graph.index("volume=0.500000")
        second_chain = graph.index("volume=3.000000dB")
        second_pan = graph.index("pan=stereo|c0=0.250000*c0|c1=1.000000*c1")
        mix = graph.index("amix=inputs=2:duration=longest")
        self.assertLess(first_chain, first_pan)
        self.assertLess(first_pan, first_track_gain)
        self.assertLess(first_track_gain, mix)
        self.assertLess(second_chain, second_pan)
        self.assertLess(second_pan, mix)

    def test_build_render_command_adds_ordered_eq_compressor_and_safety_limiter(self):
        source_path = self._touch_source("processed.mp3")
        processing = AudioEditProcessing(
            low_gain_db=3,
            mid_gain_db=-2,
            high_gain_db=4,
            compressor_enabled=True,
            compressor_threshold_db=-18,
            compressor_ratio=4,
            compressor_attack_ms=10,
            compressor_release_ms=200,
            compressor_makeup_db=2,
        )
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(source_path, 0, 3, processing=processing, id="processed"),),
                ),
            )
        )

        with patch(
            "app.services.audio_edit_service._get_available_audio_filters",
            return_value={"lowshelf", "equalizer", "highshelf", "acompressor", "alimiter"},
        ):
            command = build_render_command(project, self.source_folder / "processed.wav")

        graph = command[command.index("-filter_complex") + 1]
        ordered_filters = (
            "lowshelf=f=120:g=3.000000",
            "equalizer=f=1000:width_type=q:width=1:g=-2.000000",
            "highshelf=f=8000:g=4.000000",
            "acompressor=threshold=0.125893:ratio=4.000000:attack=10.000000:release=200.000000:makeup=1.258925",
            "alimiter=limit=0.977237:level=0",
        )
        positions = [graph.index(item) for item in ordered_filters]
        self.assertEqual(positions, sorted(positions))

    def test_build_render_command_skips_neutral_and_bypassed_processing(self):
        source_path = self._touch_source("neutral_processing.mp3")
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(source_path, 0, 1, processing=AudioEditProcessing(bypassed=True), id="bypassed"),),
                ),
            )
        )

        command = build_render_command(project, self.source_folder / "neutral_processing.wav")

        graph = command[command.index("-filter_complex") + 1]
        self.assertNotIn("lowshelf=", graph)
        self.assertNotIn("equalizer=", graph)
        self.assertNotIn("highshelf=", graph)
        self.assertNotIn("acompressor=", graph)
        self.assertNotIn("alimiter=", graph)

    def test_build_render_command_keeps_fx_order_bypass_and_safety_limiter(self):
        source_path = self._touch_source("effects.mp3")
        delay = AudioEditEffect("delay", wet=0.4, delay_ms=250, feedback=0.3, id="delay")
        bypassed_reverb = AudioEditEffect("reverb", enabled=False, id="bypassed")
        reverb = AudioEditEffect("reverb", wet=0.2, feedback=0.5, room_size=0.5, id="reverb")
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(source_path, 0, 3, effects=(delay, bypassed_reverb, reverb), id="clip"),),
                    volume=0.5,
                ),
            )
        )

        with patch("app.services.audio_edit_service._get_available_audio_filters", return_value={"aecho", "alimiter"}):
            command = build_render_command(project, self.source_folder / "effects.wav")

        graph = command[command.index("-filter_complex") + 1]
        delay_filter = "aecho=in_gain=0.600000:out_gain=0.400000:delays=250.000:decays=0.300000"
        reverb_filter = "aecho=in_gain=0.800000:out_gain=0.200000:delays=16|36|54|76|99:"
        self.assertIn(delay_filter, graph)
        self.assertIn(reverb_filter, graph)
        self.assertNotIn("delays=350.000", graph)
        self.assertLess(graph.index(delay_filter), graph.index(reverb_filter))
        self.assertLess(graph.index(reverb_filter), graph.index("alimiter="))
        self.assertLess(graph.index("alimiter="), graph.index("volume=0.500000"))

    def test_build_render_command_reports_unavailable_fx_filter(self):
        source_path = self._touch_source("no_aecho.mp3")
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(source_path, 0, 1, effects=(AudioEditEffect("delay"),), id="clip"),),
                ),
            )
        )

        with (
            patch("app.services.audio_edit_service._get_available_audio_filters", return_value={"alimiter"}),
            self.assertRaisesRegex(AudioEditError, "aecho"),
        ):
            build_render_command(project, self.source_folder / "no_aecho.wav")

    def test_build_render_command_reports_missing_processing_filter(self):
        source_path = self._touch_source("missing_filter.mp3")
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (
                        AudioEditClip(
                            source_path,
                            0,
                            1,
                            processing=AudioEditProcessing(low_gain_db=3),
                            id="processed",
                        ),
                    ),
                ),
            )
        )

        with (
            patch("app.services.audio_edit_service._get_available_audio_filters", return_value={"equalizer"}),
            self.assertRaisesRegex(AudioEditError, "lowshelf"),
        ):
            build_render_command(project, self.source_folder / "missing_filter.wav")

    def test_build_render_command_uses_320_kbps_for_mp3_exports(self):
        source_path = self._touch_source("source.mp3")
        project = AudioEditProject(
            tracks=(AudioEditTrack("sequence", "Sequence", (AudioEditClip(source_path, 0, 1, id="clip"),)),)
        )

        command = build_render_command(project, self.source_folder / "result.mp3")

        bitrate_index = command.index("-b:a")
        self.assertEqual(command[bitrate_index + 1], "320k")

    def test_build_render_command_excludes_muted_and_non_solo_tracks(self):
        first_path = self._touch_source("first.mp3")
        second_path = self._touch_source("second.mp3")
        third_path = self._touch_source("third.mp3")
        project = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(
                AudioEditTrack("first", "First", (AudioEditClip(first_path, 0, 3, id="one"),)),
                AudioEditTrack(
                    "second",
                    "Second",
                    (AudioEditClip(second_path, 0, 3, gain_db=6, pan=1, id="two"),),
                    muted=True,
                ),
                AudioEditTrack(
                    "third",
                    "Third",
                    (AudioEditClip(third_path, 0, 3, gain_db=-3, pan=0.5, id="three"),),
                    solo=True,
                ),
            ),
        )

        command = build_render_command(project, self.source_folder / "mix.wav")

        self.assertEqual(command.count("-i"), 1)
        self.assertIn(str(third_path), command)
        self.assertNotIn(str(first_path), command)
        self.assertNotIn(str(second_path), command)
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("volume=-3.000000dB", graph)
        self.assertIn("pan=stereo|c0=0.500000*c0|c1=1.000000*c1", graph)
        self.assertNotIn("volume=6.000000dB", graph)

    def test_export_audio_project_uses_unique_names_and_does_not_replace_sources(self):
        source_path = self._touch_source("Song.wav")
        project = AudioEditProject(
            tracks=(AudioEditTrack("sequence", "Sequence", (AudioEditClip(source_path, 0, 1, id="clip"),)),)
        )
        original = source_path.read_bytes()

        def fake_render(_project, output, **_kwargs):
            Path(output).write_bytes(b"rendered")
            return Path(output)

        with patch("app.services.audio_edit_service.render_audio_project", side_effect=fake_render):
            first = export_audio_project(project, self.source_folder, "Song: Edited", ".wav")
            second = export_audio_project(project, self.source_folder, "Song: Edited", ".wav")

        self.assertEqual(first.name, "Song_ Edited.wav")
        self.assertEqual(second.name, "Song_ Edited (2).wav")
        self.assertEqual(source_path.read_bytes(), original)
        self.assertEqual(first.read_bytes(), b"rendered")
        self.assertEqual(second.read_bytes(), b"rendered")
        self.assertEqual(list(self.source_folder.glob(".mokamusic-render-*")), [])

    def test_export_audio_project_cleans_temp_when_render_is_cancelled(self):
        source_path = self._touch_source("source.mp3")
        project = AudioEditProject(
            tracks=(AudioEditTrack("sequence", "Sequence", (AudioEditClip(source_path, 0, 1, id="clip"),)),)
        )

        with (
            patch(
                "app.services.audio_edit_service.render_audio_project",
                side_effect=AudioEditCancelled("cancelled"),
            ),
            self.assertRaises(AudioEditCancelled),
        ):
            export_audio_project(project, self.source_folder, "Cancelled", ".mp3")

        self.assertEqual(list(self.source_folder.glob(".mokamusic-render-*")), [])

    def test_export_audio_project_falls_back_to_exclusive_copy_when_links_are_unavailable(self):
        source_path = self._touch_source("source.wav")
        project = AudioEditProject(
            tracks=(AudioEditTrack("sequence", "Sequence", (AudioEditClip(source_path, 0, 1, id="clip"),)),)
        )

        def fake_render(_project, output, **_kwargs):
            Path(output).write_bytes(b"rendered")
            return Path(output)

        with (
            patch("app.services.audio_edit_service.render_audio_project", side_effect=fake_render),
            patch("app.services.audio_edit_service.os.link", side_effect=OSError(errno.EPERM, "links unavailable")),
        ):
            result = export_audio_project(project, self.source_folder, "Rendered", ".wav")

        self.assertEqual(result.read_bytes(), b"rendered")
        self.assertEqual(list(self.source_folder.glob(".mokamusic-render-*")), [])

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for render integration test")
    def test_render_audio_project_creates_a_playable_wav(self):
        source_path = self.source_folder / "tone.wav"
        self._write_test_wave(source_path)
        project = AudioEditProject(
            tracks=(AudioEditTrack("sequence", "Sequence", (AudioEditClip(source_path, 0, 1, id="clip"),)),)
        )
        output_path = self.source_folder / "rendered.wav"

        result = render_audio_project(project, output_path)

        audio = mutagen.File(str(result))
        self.assertIsNotNone(audio)
        self.assertAlmostEqual(audio.info.length, 1.0, delta=0.1)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for render integration test")
    def test_render_audio_project_mixes_multipista_tracks_and_exports_320_kbps_mp3(self):
        first_path = self.source_folder / "first.wav"
        second_path = self.source_folder / "second.wav"
        self._write_test_wave(first_path, frequency=440)
        self._write_test_wave(second_path, frequency=660)
        project = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(
                AudioEditTrack("first", "First", (AudioEditClip(first_path, 0, 1, id="first_clip"),)),
                AudioEditTrack(
                    "second",
                    "Second",
                    (AudioEditClip(second_path, 0, 1, timeline_start=0.25, id="second_clip"),),
                    volume=0.5,
                ),
            ),
        )
        output_path = self.source_folder / "mix.mp3"

        result = render_audio_project(project, output_path)

        audio = mutagen.File(str(result))
        self.assertIsNotNone(audio)
        self.assertAlmostEqual(audio.info.length, 1.25, delta=0.1)
        self.assertEqual(audio.info.bitrate, 320000)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for clip mix render test")
    def test_render_applies_clip_gain_and_pan_to_mono_and_stereo_sources(self):
        mono_path = self.source_folder / "mono.wav"
        stereo_path = self.source_folder / "stereo.wav"
        self._write_test_wave(mono_path)
        self._write_stereo_test_wave(stereo_path)
        neutral_output = self.source_folder / "neutral.wav"
        mono_pan_output = self.source_folder / "mono_pan.wav"
        stereo_pan_output = self.source_folder / "stereo_pan.wav"

        gain_project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(mono_path, 0, 1, gain_db=-6, id="gain"),),
                    volume=0.5,
                ),
            )
        )
        neutral_project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(mono_path, 0, 1, id="neutral"),),
                    volume=0.5,
                ),
            )
        )
        mono_pan_project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(mono_path, 0, 1, pan=-1, id="mono_pan"),),
                ),
            )
        )
        stereo_pan_project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(stereo_path, 0, 1, pan=1, id="stereo_pan"),),
                ),
            )
        )

        render_audio_project(neutral_project, neutral_output)
        gain_output = export_audio_project(gain_project, self.source_folder, "gain_export", ".wav")
        render_audio_project(mono_pan_project, mono_pan_output)
        render_audio_project(stereo_pan_project, stereo_pan_output)

        gain_ratio = self._wave_channel_rms(gain_output, 0) / self._wave_channel_rms(neutral_output, 0)
        self.assertAlmostEqual(gain_ratio, 10 ** (-6 / 20), delta=0.02)
        self.assertGreater(self._wave_channel_rms(mono_pan_output, 0), 0.1)
        self.assertLess(self._wave_channel_rms(mono_pan_output, 1), 0.001)
        self.assertLess(self._wave_channel_rms(stereo_pan_output, 0), 0.001)
        self.assertGreater(self._wave_channel_rms(stereo_pan_output, 1), 0.1)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for processing integration test")
    def test_render_processes_eq_and_compression_without_clipping(self):
        source_path = self.source_folder / "processing_source.wav"
        silence_path = self.source_folder / "processing_silence.wav"
        self._write_test_wave(source_path)
        self._write_silence_test_wave(silence_path)
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (
                        AudioEditClip(
                            source_path,
                            0,
                            1,
                            processing=AudioEditProcessing(
                                low_gain_db=12,
                                mid_gain_db=12,
                                high_gain_db=12,
                                compressor_enabled=True,
                                compressor_threshold_db=-24,
                                compressor_ratio=4,
                                compressor_makeup_db=12,
                            ),
                            id="processed",
                        ),
                    ),
                ),
            )
        )
        silence_project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (
                        AudioEditClip(
                            silence_path,
                            0,
                            1,
                            processing=AudioEditProcessing(compressor_enabled=True),
                            id="silent",
                        ),
                    ),
                ),
            )
        )
        result = export_audio_project(project, self.source_folder, "processing_result", ".wav")
        silent_result = render_audio_project(silence_project, self.source_folder / "processing_silence_result.wav")

        audio = mutagen.File(str(result))
        self.assertIsNotNone(audio)
        self.assertAlmostEqual(audio.info.length, 1, delta=0.1)
        self.assertGreater(self._wave_rms(result, 0, 1), 0.1)
        self.assertLessEqual(self._wave_peak(result), 0.99)
        self.assertEqual(self._wave_peak(silent_result), 0)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for FX render integration test")
    def test_render_applies_delay_fx_to_audio_and_keeps_source_unchanged(self):
        source_path = self.source_folder / "impulse.wav"
        self._write_impulse_test_wave(source_path)
        original_bytes = source_path.read_bytes()
        effects = (
            AudioEditEffect("delay", wet=0.5, delay_ms=250, feedback=0.4),
            AudioEditEffect("reverb", wet=0.3, feedback=0.5, room_size=0.6),
        )
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(source_path, 0, 1, effects=effects, id="delay_clip"),),
                ),
            )
        )
        result = export_audio_project(project, self.source_folder, "delayed_impulse", ".wav")

        audio = mutagen.File(str(result))
        self.assertIsNotNone(audio)
        self.assertAlmostEqual(audio.info.length, 1, delta=0.1)
        self.assertGreater(self._wave_peak_in_range(result, 0.32, 0.08), 0.01)
        self.assertEqual(source_path.read_bytes(), original_bytes)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for crossfade render test")
    def test_render_audio_project_uses_crossfade_duration_in_sequence_and_multitrack(self):
        first_path = self.source_folder / "crossfade_first.wav"
        second_path = self.source_folder / "crossfade_second.wav"
        self._write_test_wave(first_path)
        self._write_test_wave(second_path, frequency=660)
        clips = (
            AudioEditClip(first_path, 0, 1, id="first"),
            AudioEditClip(second_path, 0, 1, timeline_start=0.75, crossfade_in=0.25, id="second"),
        )
        sequence = AudioEditProject(
            mode=AudioEditMode.SEQUENCE,
            tracks=(AudioEditTrack("sequence", "Sequence", clips),),
        )
        multitrack = AudioEditProject(
            mode=AudioEditMode.MULTITRACK,
            tracks=(AudioEditTrack("track", "Track", clips),),
        )

        sequence_result = export_audio_project(sequence, self.source_folder, "crossfade_sequence", ".wav")
        multitrack_result = render_audio_project(multitrack, self.source_folder / "crossfade_multitrack.wav")

        sequence_audio = mutagen.File(str(sequence_result))
        multitrack_audio = mutagen.File(str(multitrack_result))
        self.assertAlmostEqual(sequence_audio.info.length, 1.75, delta=0.1)
        self.assertAlmostEqual(multitrack_audio.info.length, 1.75, delta=0.1)
        before = self._wave_rms(sequence_result, 0.65, 0.07)
        during = self._wave_rms(sequence_result, 0.85, 0.07)
        after = self._wave_rms(sequence_result, 1.03, 0.07)
        self.assertGreater(during, min(before, after) * 0.85)

    def test_render_audio_project_removes_partial_crossfade_output_on_cancellation(self):
        source_path = self._touch_source("source.wav")
        second_path = self._touch_source("second.wav")
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (
                        AudioEditClip(source_path, 0, 1, id="first"),
                        AudioEditClip(second_path, 0, 1, timeline_start=0.75, crossfade_in=0.25, id="second"),
                    ),
                ),
            )
        )
        output_path = self.source_folder / "partial.wav"

        def fail_render(*_args, **_kwargs):
            output_path.write_bytes(b"partial")
            raise AudioEditCancelled("cancelled")

        with (
            patch("app.services.audio_edit_service._validate_project_sources"),
            patch("app.services.audio_edit_service.shutil.which", return_value="ffmpeg"),
            patch("app.services.audio_edit_service._run_render_process", side_effect=fail_render),
            self.assertRaises(AudioEditCancelled),
        ):
            render_audio_project(project, output_path)

        self.assertFalse(output_path.exists())

    def test_render_audio_project_removes_partial_fx_output_on_cancellation(self):
        source_path = self._touch_source("cancel_fx.wav")
        project = AudioEditProject(
            tracks=(
                AudioEditTrack(
                    "sequence",
                    "Sequence",
                    (AudioEditClip(source_path, 0, 1, effects=(AudioEditEffect("delay"),), id="clip"),),
                ),
            )
        )
        output_path = self.source_folder / "partial_fx.wav"

        def fail_render(*_args, **_kwargs):
            output_path.write_bytes(b"partial")
            raise AudioEditCancelled("cancelled")

        with (
            patch("app.services.audio_edit_service._validate_project_sources"),
            patch("app.services.audio_edit_service.shutil.which", return_value="ffmpeg"),
            patch("app.services.audio_edit_service._get_available_audio_filters", return_value={"aecho", "alimiter"}),
            patch("app.services.audio_edit_service._run_render_process", side_effect=fail_render),
            self.assertRaises(AudioEditCancelled),
        ):
            render_audio_project(project, output_path)

        self.assertFalse(output_path.exists())

    @property
    def source_folder(self) -> Path:
        if not hasattr(self, "_source_temp"):
            self._source_temp = TemporaryDirectory()
            self.addCleanup(self._source_temp.cleanup)
        return Path(self._source_temp.name)

    def _touch_source(self, name: str) -> Path:
        path = self.source_folder / name
        path.write_bytes(b"source")
        return path

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for region integration test")
    def test_region_render_matches_full_mix_slice_with_crossfade(self):
        source = self.source_folder / "region-source.wav"
        self._write_test_wave(source)
        original = source.read_bytes()
        clips = sequence_clips(
            (AudioEditClip(source, 0, 1, fade_in=0.2), AudioEditClip(source, 0, 1, crossfade_in=0.5))
        )
        project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", clips),))
        full = render_audio_project(project, self.source_folder / "full.wav")
        region = render_audio_project(project, self.source_folder / "region.wav", preview_region=(0.25, 1.25))
        with wave.open(str(full), "rb") as audio:
            rate = audio.getframerate()
            audio.setpos(round(0.25 * rate))
            expected = audio.readframes(rate)
        with wave.open(str(region), "rb") as audio:
            self.assertEqual(audio.getnframes(), rate)
            self.assertEqual(audio.readframes(rate), expected)
        self.assertEqual(source.read_bytes(), original)

    def _write_test_wave(self, path: Path, *, frequency: int = 440) -> None:
        sample_rate = 44100
        with wave.open(str(path), "wb") as source:
            source.setnchannels(1)
            source.setsampwidth(2)
            source.setframerate(sample_rate)
            samples = (
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * frequency * index / sample_rate)))
                for index in range(sample_rate)
            )
            source.writeframes(b"".join(samples))

    def _write_stereo_test_wave(self, path: Path) -> None:
        sample_rate = 44100
        with wave.open(str(path), "wb") as source:
            source.setnchannels(2)
            source.setsampwidth(2)
            source.setframerate(sample_rate)
            samples = (
                struct.pack(
                    "<hh",
                    int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate)),
                    int(6000 * math.sin(2 * math.pi * 660 * index / sample_rate)),
                )
                for index in range(sample_rate)
            )
            source.writeframes(b"".join(samples))

    def _write_silence_test_wave(self, path: Path) -> None:
        with wave.open(str(path), "wb") as source:
            source.setnchannels(1)
            source.setsampwidth(2)
            source.setframerate(44100)
            source.writeframes(b"\x00\x00" * 44100)

    def _write_impulse_test_wave(self, path: Path) -> None:
        samples = [0] * 44100
        samples[4410] = 20000
        with wave.open(str(path), "wb") as source:
            source.setnchannels(1)
            source.setsampwidth(2)
            source.setframerate(44100)
            source.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    def _wave_rms(self, path: Path, start: float, duration: float) -> float:
        return self._wave_channel_rms(path, 0, start, duration)

    def _wave_peak(self, path: Path) -> float:
        with wave.open(str(path), "rb") as rendered:
            samples = rendered.readframes(rendered.getnframes())
            sample_width = rendered.getsampwidth()
        if sample_width != 2:
            raise AssertionError(f"Expected 16-bit PCM WAV, got {sample_width * 8} bits")
        values = [abs(sample[0]) for sample in struct.iter_unpack("<h", samples)]
        return max(values) / 32768

    def _wave_peak_in_range(self, path: Path, start: float, duration: float) -> float:
        with wave.open(str(path), "rb") as rendered:
            sample_rate = rendered.getframerate()
            channel_count = rendered.getnchannels()
            rendered.setpos(round(start * sample_rate))
            samples = rendered.readframes(round(duration * sample_rate))
        sample_format = "<" + "h" * channel_count
        values = [abs(value) for sample in struct.iter_unpack(sample_format, samples) for value in sample]
        return max(values, default=0) / 32768

    def _wave_channel_rms(self, path: Path, channel: int, start: float = 0, duration: float = 1) -> float:
        with wave.open(str(path), "rb") as rendered:
            sample_rate = rendered.getframerate()
            channel_count = rendered.getnchannels()
            rendered.setpos(round(start * sample_rate))
            samples = rendered.readframes(round(duration * sample_rate))
        sample_format = "<" + "h" * channel_count
        values = [sample[channel] for sample in struct.iter_unpack(sample_format, samples)]
        return math.sqrt(sum(value * value for value in values) / len(values)) / 32768


if __name__ == "__main__":
    unittest.main()
