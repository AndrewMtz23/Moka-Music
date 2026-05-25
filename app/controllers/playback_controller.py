from dataclasses import dataclass
from typing import Optional

from ..services.playback.audio_player import audio_player as default_audio_player


@dataclass
class PlaybackState:
    current_file: Optional[str]
    duration: float
    position: float
    is_playing: bool
    volume: float
    available: bool


class PlaybackController:
    def __init__(self, player=default_audio_player) -> None:
        self.player = player
        self.current_file: Optional[str] = None
        self.duration = 0.0
        self.last_position = 0.0

    @property
    def available(self) -> bool:
        return bool(self.player.available)

    @property
    def volume(self) -> float:
        return float(self.player.volume or 0.0)

    def load(self, filepath: str) -> PlaybackState:
        self.player.load(filepath)
        self.current_file = filepath
        self.duration = float(self.player.duration or 0.0)
        self.last_position = 0.0
        return self.state(position=0.0)

    def play(self) -> PlaybackState:
        if self.current_file:
            self.player.play()
        return self.state()

    def pause(self) -> PlaybackState:
        if self.current_file:
            self.last_position = self.player.get_position()
            self.player.pause()
        return self.state(position=self.last_position)

    def stop(self) -> PlaybackState:
        self.player.stop()
        self.last_position = 0.0
        return self.state(position=0.0)

    def restart(self) -> PlaybackState:
        if self.current_file:
            self.player.seek(0.0)
            self.last_position = 0.0
            self.player.play()
        return self.state(position=0.0)

    def seek_relative(self, seconds: float) -> PlaybackState:
        if not self.current_file:
            return self.state()
        was_playing = self.player.is_playing()
        position = self.player.seek(self.player.get_position() + seconds, resume=was_playing)
        self.last_position = position
        return self.state(position=position)

    def seek_absolute(self, position_seconds: float) -> PlaybackState:
        if not self.current_file:
            return self.state()
        position = self.player.seek(position_seconds, resume=self.player.is_playing())
        self.last_position = position
        return self.state(position=position)

    def toggle(self) -> PlaybackState:
        if self.player.is_playing():
            return self.pause()
        return self.play()

    def set_volume(self, volume: float) -> PlaybackState:
        self.player.set_volume(volume)
        return self.state()

    def poll_track_end(self) -> bool:
        return bool(self.player.poll_track_end())

    def mark_ended(self) -> PlaybackState:
        self.last_position = self.duration
        return self.state(position=self.duration)

    def state(self, *, position: float | None = None) -> PlaybackState:
        if position is None:
            position = self.player.get_position() if self.current_file else self.last_position
        self.last_position = max(0.0, float(position or 0.0))
        return PlaybackState(
            current_file=self.current_file,
            duration=float(self.duration or 0.0),
            position=self.last_position,
            is_playing=bool(self.player.is_playing()),
            volume=self.volume,
            available=self.available,
        )

    def cleanup(self) -> None:
        self.player.cleanup()
