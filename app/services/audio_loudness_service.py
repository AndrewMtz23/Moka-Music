"""Measure the processed clip; recommend linear gain without compressing dynamics."""

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, replace

from ..models.audio_edit_project import AudioEditProject, AudioEditTrack
from .audio_edit_service import AudioEditCancelled, AudioEditError, build_render_command


@dataclass(frozen=True)
class LoudnessRecommendation:
    integrated_lufs: float
    true_peak_db: float
    gain_db: float


def recommend_level(integrated, peak):
    if not all(math.isfinite(value) for value in (integrated, peak)):
        raise AudioEditError("No measurable loudness: audio may be silent or too short")
    # 0.1 dB margin for measurement rounding. Do not boost beyond measured peak headroom.
    gain = min(-16 - integrated, -1.1 - peak, 60.0)
    if gain < -60:
        raise AudioEditError("Required attenuation exceeds the supported range")
    return LoudnessRecommendation(integrated, peak, gain)


def analyze_clip_loudness(clip, *, track_volume=1.0, cancel_event=None):
    def check_cancel():
        if cancel_event is not None and cancel_event.is_set():
            raise AudioEditCancelled("Loudness analysis cancelled")

    check_cancel()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioEditError("FFmpeg was not found on PATH")
    isolated = replace(clip, timeline_start=0, crossfade_in=0, leveling_gain_db=0)
    project = AudioEditProject(tracks=(AudioEditTrack("analysis", "Analysis", (isolated,), volume=track_volume),))
    command = build_render_command(project, "analysis.wav")
    command[0] = ffmpeg
    command[command.index("-loglevel") + 1] = "info"
    graph_index = command.index("-filter_complex") + 1
    command[graph_index] += ";[outa]loudnorm=I=-16:TP=-1:print_format=json[measured]"
    map_index = command.index("-map") + 1
    command[map_index] = "[measured]"
    command = command[: map_index + 1] + ["-f", "null", "-"]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise AudioEditError(f"Could not start FFmpeg: {exc}") from exc
    try:
        while True:
            check_cancel()
            try:
                _, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
        check_cancel()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    if process.returncode:
        raise AudioEditError(stderr[-2000:] or "FFmpeg loudness analysis failed")
    try:
        data = json.loads(stderr[stderr.rfind("{") : stderr.rfind("}") + 1])
        integrated, peak = float(data["input_i"]), float(data["input_tp"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AudioEditError("FFmpeg did not return valid loudness measurements") from exc
    return recommend_level(integrated, peak)
