from __future__ import annotations

import math
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

import mutagen

from ..models.audio_edit_project import (
    AudioEditClip,
    AudioEditEffect,
    AudioEditEffectKind,
    AudioEditMode,
    AudioEditProcessing,
    AudioEditProject,
    AudioEditTrack,
)
from ..models.audio_export_settings import AudioExportSettings


class AudioEditError(ValueError):
    pass


class AudioEditCancelled(AudioEditError):
    pass


def validate_clip_bounds(clip: AudioEditClip, source_duration: float) -> None:
    try:
        duration = float(source_duration)
    except (TypeError, ValueError) as exc:
        raise AudioEditError("Source duration must be a positive finite number") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise AudioEditError("Source duration must be a positive finite number")
    if clip.source_end > duration:
        raise AudioEditError(f"Clip end exceeds source duration: {clip.source_end} > {duration}")


def build_retained_clips(
    source_path: str | Path,
    source_duration: float,
    removed_intervals: Iterable[tuple[float, float]],
) -> tuple[AudioEditClip, ...]:
    try:
        duration = float(source_duration)
    except (TypeError, ValueError) as exc:
        raise AudioEditError("Source duration must be a positive finite number") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise AudioEditError("Source duration must be a positive finite number")

    intervals: list[tuple[float, float]] = []
    for start_value, end_value in removed_intervals:
        try:
            start, end = float(start_value), float(end_value)
        except (TypeError, ValueError) as exc:
            raise AudioEditError("Removed interval boundaries must be finite numbers") from exc
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or end > duration:
            raise AudioEditError(f"Invalid removed interval: {start_value}–{end_value}")
        intervals.append((start, end))

    intervals.sort()
    merged: list[tuple[float, float]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    source = Path(source_path)
    retained: list[AudioEditClip] = []
    source_cursor = 0.0
    timeline_cursor = 0.0
    for start, end in merged:
        if start > source_cursor:
            clip = AudioEditClip(
                source_path=source,
                source_start=source_cursor,
                source_end=start,
                timeline_start=timeline_cursor,
            )
            retained.append(clip)
            timeline_cursor += clip.duration
        source_cursor = max(source_cursor, end)

    if source_cursor < duration:
        retained.append(
            AudioEditClip(
                source_path=source,
                source_start=source_cursor,
                source_end=duration,
                timeline_start=timeline_cursor,
            )
        )

    if not retained:
        raise AudioEditError("Removing these intervals would leave no audio")
    return tuple(retained)


def sequence_clips(clips: Iterable[AudioEditClip]) -> tuple[AudioEditClip, ...]:
    ordered = tuple(clips)
    if not ordered:
        raise AudioEditError("A sequence must contain at least one clip")
    if len({clip.id for clip in ordered}) != len(ordered):
        raise AudioEditError("Clip ids must be unique in a sequence")

    timeline_cursor = 0.0
    sequenced: list[AudioEditClip] = []
    for index, clip in enumerate(ordered):
        if clip.crossfade_in and index == 0:
            raise AudioEditError("The first sequence clip cannot have an incoming crossfade")
        if clip.crossfade_in and clip.fade_in:
            raise AudioEditError("An incoming crossfade cannot be combined with a clip fade-in")
        if clip.crossfade_in and sequenced[-1].fade_out:
            raise AudioEditError("An incoming crossfade cannot be combined with the previous clip fade-out")
        if clip.crossfade_in and clip.crossfade_in > sequenced[-1].duration:
            raise AudioEditError("Crossfade duration exceeds the previous clip duration")
        sequenced_clip = replace(clip, timeline_start=timeline_cursor - clip.crossfade_in)
        sequenced.append(sequenced_clip)
        timeline_cursor = sequenced_clip.timeline_end
    return tuple(sequenced)


def apply_crossfade(
    track: AudioEditTrack,
    first_clip_id: str,
    second_clip_id: str,
    duration: float,
) -> AudioEditTrack:
    try:
        crossfade_duration = float(duration)
    except (TypeError, ValueError) as exc:
        raise AudioEditError("Crossfade duration must be a finite number") from exc
    if not math.isfinite(crossfade_duration) or crossfade_duration < 0:
        raise AudioEditError("Crossfade duration must be a non-negative finite number")

    ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
    first_index = next((index for index, clip in enumerate(ordered) if clip.id == first_clip_id), None)
    second_index = next((index for index, clip in enumerate(ordered) if clip.id == second_clip_id), None)
    if first_index is None or second_index is None or second_index != first_index + 1:
        raise AudioEditError("Select two adjacent clips on the same track for a crossfade")
    first, second = ordered[first_index], ordered[second_index]
    if crossfade_duration > min(first.duration, second.duration):
        raise AudioEditError("Crossfade duration cannot exceed either clip duration")
    if crossfade_duration and (first.fade_out or second.fade_in):
        raise AudioEditError("Remove the adjacent fade-out and fade-in before applying a crossfade")

    target_start = first.timeline_end - crossfade_duration
    shift = target_start - second.timeline_start
    updated = list(ordered)
    updated[second_index] = replace(second, timeline_start=target_start, crossfade_in=crossfade_duration)
    for index in range(second_index + 1, len(updated)):
        clip = updated[index]
        updated[index] = replace(clip, timeline_start=max(0.0, clip.timeline_start + shift))

    if crossfade_duration:
        overlap_start = target_start
        overlap_end = first.timeline_end
        pair_ids = {first.id, second.id}
        if any(
            clip.id not in pair_ids and clip.timeline_start < overlap_end and overlap_start < clip.timeline_end
            for clip in updated
        ):
            raise AudioEditError("Crossfade interval overlaps another clip on the same track")

    updated_by_id = {clip.id: clip for clip in updated}
    updated_track = replace(track, clips=tuple(updated_by_id[clip.id] for clip in track.clips))
    validate_track_crossfades(updated_track)
    return updated_track


def clear_crossfades_with_changed_neighbors(
    original_clips: Iterable[AudioEditClip],
    updated_clips: Iterable[AudioEditClip],
    *,
    preserve_order: bool = False,
) -> tuple[AudioEditClip, ...]:
    original = list(original_clips)
    updated = list(updated_clips)
    if not preserve_order:
        original.sort(key=lambda clip: (clip.timeline_start, clip.id))
    updated_order = updated if preserve_order else sorted(updated, key=lambda clip: (clip.timeline_start, clip.id))
    original_predecessors = {clip.id: original[index - 1].id if index else None for index, clip in enumerate(original)}
    updated_by_id = {
        clip.id: (
            replace(clip, crossfade_in=0.0)
            if clip.crossfade_in
            and original_predecessors.get(clip.id) != (updated_order[index - 1].id if index else None)
            else clip
        )
        for index, clip in enumerate(updated_order)
    }
    return tuple(updated_by_id[clip.id] for clip in updated)


def split_clip(clip: AudioEditClip, source_position: float) -> tuple[AudioEditClip, AudioEditClip]:
    try:
        position = float(source_position)
    except (TypeError, ValueError) as exc:
        raise AudioEditError("Split position must be a finite number") from exc
    if not math.isfinite(position) or not clip.source_start < position < clip.source_end:
        raise AudioEditError("Split position must be inside the clip source range")

    left_duration = position - clip.source_start
    right_duration = clip.source_end - position
    left = replace(
        clip,
        source_end=position,
        fade_in=min(clip.fade_in, left_duration),
        fade_out=0.0,
        id=uuid4().hex,
    )
    right = replace(
        clip,
        source_start=position,
        timeline_start=clip.timeline_start + left_duration,
        fade_in=0.0,
        fade_out=min(clip.fade_out, right_duration),
        id=uuid4().hex,
        crossfade_in=0.0,
    )
    return left, right


def trim_clip(
    clip: AudioEditClip, source_start: float, source_end: float, *, source_duration: float | None = None
) -> AudioEditClip:
    try:
        start, end = float(source_start), float(source_end)
    except (TypeError, ValueError) as exc:
        raise AudioEditError("Trim boundaries must be finite numbers") from exc
    if not math.isfinite(start) or not math.isfinite(end):
        raise AudioEditError("Trim boundaries must be finite numbers")
    lower, upper = clip.source_start, clip.source_end
    if source_duration is not None:
        try:
            upper = float(source_duration)
        except (TypeError, ValueError) as exc:
            raise AudioEditError("Source duration must be a finite positive number") from exc
        if not math.isfinite(upper) or upper <= 0:
            raise AudioEditError("Source duration must be a finite positive number")
        lower = 0.0
    # Timeline-to-source arithmetic can overshoot an exact boundary by a few ULPs.
    if math.isclose(start, lower, rel_tol=0.0, abs_tol=1e-9):
        start = lower
    if math.isclose(end, upper, rel_tol=0.0, abs_tol=1e-9):
        end = upper
    if start < lower or end > upper or end <= start:
        raise AudioEditError("Trim range must be a positive interval inside the clip source range")

    fade_in = min(clip.fade_in, end - start)
    fade_out = min(clip.fade_out, end - start - fade_in)
    return replace(clip, source_start=start, source_end=end, fade_in=fade_in, fade_out=fade_out)


def remove_clip_interval(
    clip: AudioEditClip,
    source_start: float,
    source_end: float,
) -> tuple[AudioEditClip, AudioEditClip]:
    try:
        start, end = float(source_start), float(source_end)
    except (TypeError, ValueError) as exc:
        raise AudioEditError("Removed interval boundaries must be finite numbers") from exc
    if not math.isfinite(start) or not math.isfinite(end):
        raise AudioEditError("Removed interval boundaries must be finite numbers")
    if start < clip.source_start or end > clip.source_end or end <= start:
        raise AudioEditError("Removed interval must be a positive range inside the clip source range")
    if start == clip.source_start or end == clip.source_end:
        raise AudioEditError("Use trim controls to remove audio at a clip boundary")

    left = replace(
        clip,
        source_end=start,
        fade_out=0.0,
        id=uuid4().hex,
    )
    right = replace(
        clip,
        source_start=end,
        timeline_start=clip.timeline_start + (start - clip.source_start),
        fade_in=0.0,
        id=uuid4().hex,
        crossfade_in=0.0,
    )
    return left, right


def move_sequence_clip(
    clips: Iterable[AudioEditClip],
    clip_id: str,
    destination_index: int,
) -> tuple[AudioEditClip, ...]:
    ordered = list(clips)
    if not 0 <= destination_index < len(ordered):
        raise AudioEditError(f"Sequence index is out of range: {destination_index}")

    source_index = next((index for index, clip in enumerate(ordered) if clip.id == clip_id), None)
    if source_index is None:
        raise AudioEditError(f"Clip not found: {clip_id}")
    original = tuple(ordered)
    ordered.insert(destination_index, ordered.pop(source_index))
    return sequence_clips(clear_crossfades_with_changed_neighbors(original, ordered, preserve_order=True))


def overlapping_clip_pairs(track: AudioEditTrack) -> tuple[tuple[str, str], ...]:
    ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.timeline_end, clip.id))
    overlaps: list[tuple[str, str]] = []
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            if second.timeline_start >= first.timeline_end:
                break
            overlaps.append((first.id, second.id))
    return tuple(overlaps)


def build_render_command(
    project: AudioEditProject,
    output_path: str | Path,
    *,
    bitrate: str = "320k",
    preview_region: tuple[float, float] | None = None,
    export_settings: AudioExportSettings | None = None,
) -> list[str]:
    if export_settings is not None and export_settings.format != _normalize_render_extension(Path(output_path).suffix):
        raise AudioEditError("Export settings do not match the output format")
    sample_rate = export_settings.sample_rate if export_settings else 44100
    clips_by_track = _active_clips_by_track(project)
    if not any(clips_by_track):
        raise AudioEditError("The arrangement has no audio to render")

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-n"]
    all_clips = [clip for clips in clips_by_track for clip in clips]
    for clip in all_clips:
        if not clip.source_path.is_file():
            raise AudioEditError(f"Audio source does not exist: {clip.source_path}")
        command.extend(["-i", str(clip.source_path)])

    filter_chains: list[str] = []
    labels_by_track: list[list[tuple[AudioEditClip, str]]] = []
    clip_index = 0
    for track, clips in zip(project.tracks, clips_by_track, strict=True):
        track_labels: list[tuple[AudioEditClip, str]] = []
        for clip in clips:
            if clip.crossfade_in:
                _validate_crossfade_link(track.clips, clip)
            label = f"clip{clip_index}"
            chain = (
                f"[{clip_index}:a:0]atrim=start={clip.source_start:.9f}:end={clip.source_end:.9f},"
                f"asetpts=PTS-STARTPTS,aresample={sample_rate},"
                "aformat=sample_fmts=fltp:channel_layouts=stereo"
            )
            if clip.gain_db != 0.0:
                chain += f",volume={clip.gain_db:.6f}dB"
            if clip.pan != 0.0:
                left_gain = 1.0 - max(clip.pan, 0.0)
                right_gain = 1.0 + min(clip.pan, 0.0)
                chain += f",pan=stereo|c0={left_gain:.6f}*c0|c1={right_gain:.6f}*c1"
            chain += _processing_filter_chain(clip.processing)
            active_effects = any(effect.enabled and effect.wet > 0 for effect in clip.effects)
            chain += _creative_effect_filter_chain(clip.effects)
            if _processing_filter_names(clip.processing) or active_effects:
                _require_audio_filters({"alimiter"})
                chain += f",alimiter=limit={10 ** (-0.2 / 20):.6f}:level=0"
            if active_effects:
                chain += f",atrim=duration={clip.duration:.9f}"
            if track.volume != 1.0:
                chain += f",volume={track.volume:.6f}"
            if clip.fade_in > 0:
                chain += f",afade=t=in:st=0:d={clip.fade_in:.9f}"
            if clip.fade_out > 0:
                fade_start = clip.duration - clip.fade_out
                chain += f",afade=t=out:st={fade_start:.9f}:d={clip.fade_out:.9f}"
            filter_chains.append(f"{chain}[{label}]")
            track_labels.append((clip, label))
            clip_index += 1
        labels_by_track.append(track_labels)

    if project.mode == AudioEditMode.SEQUENCE:
        if not labels_by_track[0]:
            raise AudioEditError("The sequence has no active audio")
        current_label = labels_by_track[0][0][1]
        for index, (clip, next_label) in enumerate(labels_by_track[0][1:], start=1):
            output_label = "outa" if index == len(labels_by_track[0]) - 1 else f"sequence{index}"
            if clip.crossfade_in > 0:
                filter_chains.append(
                    f"[{current_label}][{next_label}]acrossfade=d={clip.crossfade_in:.9f}:c1=qsin:c2=qsin[{output_label}]"
                )
            else:
                filter_chains.append(f"[{current_label}][{next_label}]concat=n=2:v=0:a=1[{output_label}]")
            current_label = output_label
        if len(labels_by_track[0]) == 1:
            filter_chains.append(f"[{current_label}]anull[outa]")
    else:
        segment_labels: list[str] = []
        segment_index = 0
        for clip_labels in labels_by_track:
            index = 0
            while index < len(clip_labels):
                group = [clip_labels[index]]
                index += 1
                while index < len(clip_labels) and clip_labels[index][0].crossfade_in > 0:
                    group.append(clip_labels[index])
                    index += 1
                current_label = group[0][1]
                for transition_index, (clip, next_label) in enumerate(group[1:], start=1):
                    output_label = f"track{segment_index}_fade{transition_index}"
                    filter_chains.append(
                        f"[{current_label}][{next_label}]acrossfade=d={clip.crossfade_in:.9f}:"
                        f"c1=qsin:c2=qsin[{output_label}]"
                    )
                    current_label = output_label
                delay_ms = round(group[0][0].timeline_start * 1000)
                segment_label = f"segment{segment_index}"
                if delay_ms:
                    chain = f"[{current_label}]adelay=delays={delay_ms}|{delay_ms}:all=1[{segment_label}]"
                else:
                    chain = f"[{current_label}]anull[{segment_label}]"
                filter_chains.append(chain)
                segment_labels.append(f"[{segment_label}]")
                segment_index += 1
        if len(segment_labels) == 1:
            filter_chains.append(f"{segment_labels[0]}anull[outa]")
        else:
            filter_chains.append(
                f"{''.join(segment_labels)}amix=inputs={len(segment_labels)}:"
                "duration=longest:dropout_transition=0:normalize=0[outa]"
            )
    output_label = "[outa]"
    if preview_region is not None:
        start, end = preview_region
        if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= project.duration:
            raise AudioEditError("Preview region must be inside the project")
        filter_chains.append(
            f"[outa]apad=whole_dur={project.duration:.9f},atrim=start={start:.9f}:end={end:.9f},"
            "asetpts=PTS-STARTPTS[region]"
        )
        output_label = "[region]"
    command.extend(["-filter_complex", ";".join(filter_chains), "-map", output_label])
    command.extend(_output_codec_arguments(Path(output_path), bitrate, export_settings))
    command.extend(["-progress", "pipe:1", "-f", _format_muxer(Path(output_path)), str(output_path)])
    return command


def _processing_filter_chain(processing: AudioEditProcessing) -> str:
    if processing.is_neutral:
        return ""
    filters: list[str] = []
    if processing.low_gain_db:
        filters.append(f"lowshelf=f=120:g={processing.low_gain_db:.6f}")
    if processing.mid_gain_db:
        filters.append(f"equalizer=f=1000:width_type=q:width=1:g={processing.mid_gain_db:.6f}")
    if processing.high_gain_db:
        filters.append(f"highshelf=f=8000:g={processing.high_gain_db:.6f}")
    if processing.compressor_enabled:
        threshold = 10 ** (processing.compressor_threshold_db / 20)
        makeup = 10 ** (processing.compressor_makeup_db / 20)
        filters.append(
            f"acompressor=threshold={threshold:.6f}:ratio={processing.compressor_ratio:.6f}:"
            f"attack={processing.compressor_attack_ms:.6f}:release={processing.compressor_release_ms:.6f}:"
            f"makeup={makeup:.6f}"
        )
    _require_audio_filters(set(_processing_filter_names(processing)))
    return "," + ",".join(filters) if filters else ""


def _processing_filter_names(processing: AudioEditProcessing) -> frozenset[str]:
    if processing.is_neutral:
        return frozenset()
    names = set()
    if processing.low_gain_db:
        names.add("lowshelf")
    if processing.mid_gain_db:
        names.add("equalizer")
    if processing.high_gain_db:
        names.add("highshelf")
    if processing.compressor_enabled:
        names.add("acompressor")
    return frozenset(names)


def _creative_effect_filter_chain(effects: tuple[AudioEditEffect, ...]) -> str:
    active_effects = tuple(effect for effect in effects if effect.enabled and effect.wet > 0)
    if not active_effects:
        return ""
    filter_names: set[str] = set()
    filters: list[str] = []
    for effect in active_effects:
        filter_names.add("aecho")
        dry_gain = 1.0 - effect.wet
        if effect.kind == AudioEditEffectKind.DELAY:
            filters.append(
                f"aecho=in_gain={dry_gain:.6f}:out_gain={effect.wet:.6f}:"
                f"delays={effect.delay_ms:.3f}:decays={effect.feedback:.6f}"
            )
        else:
            room_scale = 0.5 + effect.room_size * 1.5
            reflection_delays = tuple(round(delay * room_scale) for delay in (13, 29, 43, 61, 79))
            reflection_decays = tuple(effect.feedback * decay for decay in (1, 0.82, 0.68, 0.55, 0.44))
            filters.append(
                f"aecho=in_gain={dry_gain:.6f}:out_gain={effect.wet:.6f}:"
                f"delays={'|'.join(map(str, reflection_delays))}:"
                f"decays={'|'.join(f'{decay:.6f}' for decay in reflection_decays)}"
            )
    _require_audio_filters(filter_names)
    return "," + ",".join(filters) if filters else ""


def _require_audio_filters(filter_names: set[str]) -> None:
    if not filter_names:
        return
    available = _get_available_audio_filters()
    missing = sorted(filter_names - available)
    if missing:
        raise AudioEditError(
            "The installed FFmpeg does not provide required audio filter(s): "
            f"{', '.join(missing)}. Install a full FFmpeg build and try again."
        )


@lru_cache(maxsize=4)
def _get_available_audio_filters() -> frozenset[str]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioEditError("FFmpeg was not found on PATH")
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioEditError(f"Could not inspect FFmpeg audio filters: {exc}") from exc
    return frozenset(
        fields[1] for line in result.stdout.splitlines() if len(fields := line.split()) >= 3 and "->" in fields[2]
    )


def _validate_crossfade_link(clips: tuple[AudioEditClip, ...], clip: AudioEditClip) -> None:
    ordered = sorted(clips, key=lambda item: (item.timeline_start, item.id))
    index = next((index for index, item in enumerate(ordered) if item.id == clip.id), None)
    if index is None or index == 0:
        raise AudioEditError("An incoming crossfade requires a preceding clip on the same track")
    previous = ordered[index - 1]
    if clip.fade_in or previous.fade_out:
        raise AudioEditError("Crossfade cannot overlap a clip fade-in or fade-out")
    if clip.crossfade_in > min(previous.duration, clip.duration):
        raise AudioEditError("Crossfade duration cannot exceed either clip duration")
    expected_start = previous.timeline_end - clip.crossfade_in
    if not math.isclose(clip.timeline_start, expected_start, abs_tol=1e-6):
        raise AudioEditError("Crossfade clips must overlap by exactly the configured duration")
    if any(
        other.id not in {previous.id, clip.id}
        and other.timeline_start < previous.timeline_end
        and expected_start < other.timeline_end
        for other in ordered
    ):
        raise AudioEditError("Crossfade interval overlaps another clip on the same track")


def validate_track_crossfades(track: AudioEditTrack) -> None:
    for clip in track.clips:
        if clip.crossfade_in:
            _validate_crossfade_link(track.clips, clip)


def render_audio_project(
    project: AudioEditProject,
    output_path: str | Path,
    *,
    bitrate: str = "320k",
    preview_region: tuple[float, float] | None = None,
    export_settings: AudioExportSettings | None = None,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[int, str], bool] | None = None,
) -> Path:
    destination = Path(output_path)
    if destination.exists():
        raise AudioEditError(f"Render output already exists: {destination}")
    if not destination.parent.is_dir():
        raise AudioEditError(f"Render output folder does not exist: {destination.parent}")
    _validate_project_sources(project)
    if shutil.which("ffmpeg") is None:
        raise AudioEditError("FFmpeg was not found on PATH")
    command = build_render_command(
        project, destination, bitrate=bitrate, preview_region=preview_region, export_settings=export_settings
    )
    try:
        _run_render_process(
            command,
            preview_region[1] - preview_region[0] if preview_region else project.duration,
            cancel_event,
            progress_callback,
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AudioEditError("FFmpeg completed without producing an audio file")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def export_audio_project(
    project: AudioEditProject,
    output_folder: str | Path,
    base_name: str,
    extension: str,
    *,
    bitrate: str = "320k",
    export_settings: AudioExportSettings | None = None,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[int, str], bool] | None = None,
) -> Path:
    output_dir = Path(output_folder)
    if not output_dir.is_dir():
        raise AudioEditError(f"Export folder does not exist: {output_dir}")
    normalized_extension = _normalize_render_extension(extension)
    safe_name = _safe_output_name(base_name)
    if not safe_name:
        raise AudioEditError("Export file name must contain at least one valid character")

    temp_handle = tempfile.NamedTemporaryFile(
        prefix=".mokamusic-render-",
        suffix=normalized_extension,
        dir=output_dir,
        delete=False,
    )
    temporary_path = Path(temp_handle.name)
    temp_handle.close()
    temporary_path.unlink()
    try:
        render_audio_project(
            project,
            temporary_path,
            bitrate=bitrate,
            **({"export_settings": export_settings} if export_settings is not None else {}),
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        suffix = 1
        while True:
            numbered_name = safe_name if suffix == 1 else f"{safe_name} ({suffix})"
            destination = output_dir / f"{numbered_name}{normalized_extension}"
            if any(
                destination.resolve() == clip.source_path.resolve() for track in project.tracks for clip in track.clips
            ):
                suffix += 1
                continue
            try:
                os.link(temporary_path, destination)
            except FileExistsError:
                suffix += 1
                continue
            except OSError:
                try:
                    descriptor = os.open(
                        destination,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o666,
                    )
                except FileExistsError:
                    suffix += 1
                    continue
                except OSError as fallback_exc:
                    raise AudioEditError(
                        f"Could not publish export without overwriting an existing file: {fallback_exc}"
                    ) from fallback_exc
                try:
                    with os.fdopen(descriptor, "wb") as target:
                        with temporary_path.open("rb") as source:
                            shutil.copyfileobj(source, target)
                except OSError as copy_exc:
                    try:
                        destination.unlink(missing_ok=True)
                    except OSError as cleanup_exc:
                        raise AudioEditError(
                            f"Export copy failed ({copy_exc}) and partial output cleanup failed ({cleanup_exc})"
                        ) from copy_exc
                    raise AudioEditError(f"Could not copy the completed export: {copy_exc}") from copy_exc
            return destination
    finally:
        temporary_path.unlink(missing_ok=True)


def _active_clips_by_track(project: AudioEditProject) -> list[list[AudioEditClip]]:
    has_solo = any(track.solo and not track.muted for track in project.tracks)
    clips_by_track: list[list[AudioEditClip]] = []
    for track in project.tracks:
        if track.muted or (has_solo and not track.solo):
            clips_by_track.append([])
            continue
        clips = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
        clips_by_track.append(clips)
    return clips_by_track


def _validate_project_sources(project: AudioEditProject) -> None:
    for clips in _active_clips_by_track(project):
        for clip in clips:
            if not clip.source_path.is_file():
                raise AudioEditError(f"Audio source does not exist: {clip.source_path}")
            try:
                audio = mutagen.File(str(clip.source_path))
                duration = float(audio.info.length) if audio is not None and audio.info is not None else 0.0
            except (OSError, AttributeError, TypeError, ValueError) as exc:
                raise AudioEditError(f"Could not read audio source {clip.source_path}: {exc}") from exc
            validate_clip_bounds(clip, duration)


def _run_render_process(
    command: list[str],
    duration: float,
    cancel_event: threading.Event | None,
    progress_callback: Callable[[int, str], bool] | None,
) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise AudioEditCancelled("Audio render cancelled")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise AudioEditError(f"Could not start FFmpeg: {exc}") from exc

    output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    stderr_lines: list[str] = []

    def read_stdout() -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            output_queue.put(("stdout", line.strip()))

    def read_stderr() -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            stderr_lines.append(line.rstrip())

    stdout_reader = threading.Thread(target=read_stdout, daemon=True)
    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    stdout_reader.start()
    stderr_reader.start()
    last_percent = 0
    latest_output_time = 0.0
    cancelled = False
    while process.poll() is None:
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
        try:
            kind, line = output_queue.get(timeout=0.1)
        except queue.Empty:
            kind, line = "", ""
        if kind == "stdout":
            key, separator, value = line.partition("=")
            if separator and key == "out_time_ms":
                try:
                    latest_output_time = max(0.0, float(value) / 1_000_000)
                except ValueError:
                    continue
                percent = min(99, int(latest_output_time / max(duration, 0.001) * 100))
                if percent > last_percent:
                    last_percent = percent
                    if progress_callback is not None and not progress_callback(percent, "rendering"):
                        cancelled = True
        if cancelled:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            break
    stdout_reader.join()
    stderr_reader.join()
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    # Cancellation may arrive as the process exits, bypassing the loop body.
    if cancelled or (cancel_event is not None and cancel_event.is_set()):
        raise AudioEditCancelled("Audio render cancelled")
    if process.returncode != 0:
        detail = "\n".join(stderr_lines).strip()
        raise AudioEditError(detail or f"FFmpeg exited with {process.returncode}")
    if progress_callback is not None and not progress_callback(100, "complete"):
        raise AudioEditCancelled("Audio render cancelled")


def _output_codec_arguments(path: Path, bitrate: str, settings: AudioExportSettings | None = None) -> list[str]:
    suffix = _normalize_render_extension(path.suffix)
    if settings is not None:
        if suffix == ".mp3":
            codec = ["-codec:a", "libmp3lame", "-b:a", f"{settings.bitrate_kbps}k"]
        elif suffix == ".ogg":
            codec = ["-codec:a", "libvorbis", "-q:a", str(settings.ogg_quality)]
        elif suffix == ".flac":
            codec = [
                "-codec:a",
                "flac",
                "-sample_fmt",
                "s16" if settings.bit_depth == 16 else "s32",
                "-bits_per_raw_sample",
                str(settings.bit_depth),
            ]
        else:
            codec = ["-codec:a", "pcm_s16le" if settings.bit_depth == 16 else "pcm_s24le"]
        return [*codec, "-ar", str(settings.sample_rate)]
    if suffix == ".mp3":
        return ["-codec:a", "libmp3lame", "-b:a", bitrate]
    if suffix == ".ogg":
        return ["-codec:a", "libvorbis", "-q:a", "5"]
    if suffix == ".flac":
        return ["-codec:a", "flac"]
    return ["-codec:a", "pcm_s16le"]


def _format_muxer(path: Path) -> str:
    suffix = _normalize_render_extension(path.suffix)
    return {".mp3": "mp3", ".ogg": "ogg", ".flac": "flac", ".wav": "wav"}[suffix]


def _normalize_render_extension(extension: str) -> str:
    normalized = extension.strip().lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized not in {".mp3", ".wav", ".flac", ".ogg"}:
        raise AudioEditError(f"Unsupported audio export format: {extension}")
    return normalized


def _safe_output_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(". ")
    if cleaned.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        cleaned = f"_{cleaned}"
    return cleaned
