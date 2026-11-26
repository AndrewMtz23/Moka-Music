from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import uuid4

MIN_CLIP_GAIN_DB = -60.0
MAX_CLIP_GAIN_DB = 12.0
MIN_EQ_GAIN_DB = -12.0
MAX_EQ_GAIN_DB = 12.0


@dataclass(frozen=True)
class AudioEditProcessing:
    low_gain_db: float = 0.0
    mid_gain_db: float = 0.0
    high_gain_db: float = 0.0
    compressor_enabled: bool = False
    compressor_threshold_db: float = -18.0
    compressor_ratio: float = 2.0
    compressor_attack_ms: float = 20.0
    compressor_release_ms: float = 250.0
    compressor_makeup_db: float = 0.0
    bypassed: bool = False

    def __post_init__(self) -> None:
        numeric_ranges = {
            "low_gain_db": (MIN_EQ_GAIN_DB, MAX_EQ_GAIN_DB),
            "mid_gain_db": (MIN_EQ_GAIN_DB, MAX_EQ_GAIN_DB),
            "high_gain_db": (MIN_EQ_GAIN_DB, MAX_EQ_GAIN_DB),
            "compressor_threshold_db": (-60.0, 0.0),
            "compressor_ratio": (1.0, 20.0),
            "compressor_attack_ms": (0.1, 1000.0),
            "compressor_release_ms": (1.0, 1000.0),
            "compressor_makeup_db": (0.0, 12.0),
        }
        for field_name, (minimum, maximum) in numeric_ranges.items():
            value = getattr(self, field_name)
            try:
                normalized = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be between {minimum:g} and {maximum:g}") from exc
            if not math.isfinite(normalized) or not minimum <= normalized <= maximum:
                raise ValueError(f"{field_name} must be between {minimum:g} and {maximum:g}")
            object.__setattr__(self, field_name, normalized)
        if not isinstance(self.compressor_enabled, bool) or not isinstance(self.bypassed, bool):
            raise ValueError("Processing enable and bypass values must be boolean")

    @property
    def is_neutral(self) -> bool:
        return self.bypassed or (
            self.low_gain_db == 0 and self.mid_gain_db == 0 and self.high_gain_db == 0 and not self.compressor_enabled
        )


class AudioEditMode(str, Enum):
    SEQUENCE = "sequence"
    MULTITRACK = "multitrack"


class AudioEditEffectKind(str, Enum):
    REVERB = "reverb"
    DELAY = "delay"


@dataclass(frozen=True)
class AudioEditEffect:
    kind: AudioEditEffectKind
    wet: float = 0.25
    delay_ms: float = 350.0
    feedback: float = 0.35
    room_size: float = 0.5
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        try:
            kind = AudioEditEffectKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported audio effect: {self.kind}") from exc
        object.__setattr__(self, "kind", kind)
        for field_name, minimum, maximum in (
            ("wet", 0.0, 1.0),
            ("delay_ms", 40.0, 1500.0),
            ("feedback", 0.0, 0.8),
            ("room_size", 0.1, 1.0),
        ):
            try:
                value = float(getattr(self, field_name))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Effect {field_name} must be between {minimum:g} and {maximum:g}") from exc
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"Effect {field_name} must be between {minimum:g} and {maximum:g}")
            object.__setattr__(self, field_name, value)
        if not self.id or not isinstance(self.enabled, bool):
            raise ValueError("Effect id must not be empty and enabled must be boolean")


@dataclass(frozen=True)
class AudioEditClip:
    source_path: Path
    source_start: float
    source_end: float
    timeline_start: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    crossfade_in: float = 0.0
    gain_db: float = 0.0
    pan: float = 0.0
    processing: AudioEditProcessing = field(default_factory=AudioEditProcessing)
    effects: tuple[AudioEditEffect, ...] = ()
    leveling_gain_db: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_path", Path(self.source_path))
        for field_name in (
            "source_start",
            "source_end",
            "timeline_start",
            "fade_in",
            "fade_out",
            "crossfade_in",
            "gain_db",
            "pan",
            "leveling_gain_db",
        ):
            value = getattr(self, field_name)
            try:
                normalized = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be a finite number") from exc
            if not math.isfinite(normalized):
                raise ValueError(f"{field_name} must be a finite number")
            object.__setattr__(self, field_name, normalized)

        if not self.id:
            raise ValueError("Clip id must not be empty")
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise ValueError("Clip source range must have a positive duration")
        if self.timeline_start < 0:
            raise ValueError("Clip timeline start must not be negative")
        if self.fade_in < 0 or self.fade_out < 0:
            raise ValueError("Clip fades must not be negative")
        if self.fade_in + self.fade_out > self.duration:
            raise ValueError("Clip fades cannot exceed its duration")
        if self.crossfade_in < 0 or self.crossfade_in > self.duration:
            raise ValueError("Clip crossfade must be between zero and its duration")
        if not MIN_CLIP_GAIN_DB <= self.gain_db <= MAX_CLIP_GAIN_DB:
            raise ValueError(f"Clip gain must be between {MIN_CLIP_GAIN_DB:g} and {MAX_CLIP_GAIN_DB:g} dB")
        if not -1.0 <= self.pan <= 1.0:
            raise ValueError("Clip pan must be between -1 (left) and 1 (right)")
        if not -60 <= self.leveling_gain_db <= 60:
            raise ValueError("Leveling gain must be between -60 and 60 dB")
        if not isinstance(self.processing, AudioEditProcessing):
            raise ValueError("Clip processing must be an AudioEditProcessing value")
        effects = tuple(self.effects)
        if len(effects) > 8:
            raise ValueError("An audio clip cannot contain more than 8 effects")
        if not all(isinstance(effect, AudioEditEffect) for effect in effects):
            raise ValueError("Clip effects must be AudioEditEffect values")
        if len({effect.id for effect in effects}) != len(effects):
            raise ValueError("Effect ids must be unique within a clip")
        object.__setattr__(self, "effects", effects)

    @property
    def duration(self) -> float:
        return self.source_end - self.source_start

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.duration


@dataclass(frozen=True)
class AudioEditMarker:
    position: float
    label: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        try:
            position = float(self.position)
        except (TypeError, ValueError) as exc:
            raise ValueError("Marker position must be a finite number") from exc
        if not math.isfinite(position) or position < 0:
            raise ValueError("Marker position must be a non-negative finite number")
        if not self.id:
            raise ValueError("Marker id must not be empty")
        object.__setattr__(self, "position", position)


@dataclass(frozen=True)
class AudioEditTrack:
    id: str
    name: str
    clips: tuple[AudioEditClip, ...] = ()
    volume: float = 1.0
    muted: bool = False
    solo: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.name.strip():
            raise ValueError("Track id and name must not be empty")
        try:
            volume = float(self.volume)
        except (TypeError, ValueError) as exc:
            raise ValueError("Track volume must be between 0 and 1") from exc
        if not math.isfinite(volume) or not 0 <= volume <= 1:
            raise ValueError("Track volume must be between 0 and 1")
        clips = tuple(self.clips)
        if len({clip.id for clip in clips}) != len(clips):
            raise ValueError("Clip ids must be unique within a track")
        object.__setattr__(self, "clips", clips)
        object.__setattr__(self, "volume", volume)

    @property
    def duration(self) -> float:
        return max((clip.timeline_end for clip in self.clips), default=0.0)


@dataclass(frozen=True)
class AudioEditProject:
    mode: AudioEditMode = AudioEditMode.SEQUENCE
    tracks: tuple[AudioEditTrack, ...] = ()
    markers: tuple[AudioEditMarker, ...] = ()

    def __post_init__(self) -> None:
        try:
            mode = AudioEditMode(self.mode)
        except ValueError as exc:
            raise ValueError(f"Unsupported audio edit mode: {self.mode}") from exc
        tracks = tuple(self.tracks)
        markers = tuple(self.markers)
        if len({track.id for track in tracks}) != len(tracks):
            raise ValueError("Track ids must be unique")
        clip_ids = [clip.id for track in tracks for clip in track.clips]
        if len(set(clip_ids)) != len(clip_ids):
            raise ValueError("Clip ids must be unique within a project")
        if len({marker.id for marker in markers}) != len(markers):
            raise ValueError("Marker ids must be unique within a project")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "tracks", tracks)
        object.__setattr__(self, "markers", markers)

    @property
    def duration(self) -> float:
        return max((track.duration for track in self.tracks), default=0.0)
