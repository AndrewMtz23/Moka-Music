import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from .audio_player import audio_player
from ...constants import DEFAULT_POLL_INTERVAL


class PlayerState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()
    BUFFERING = auto()


@dataclass
class PlaybackStatus:
    state: PlayerState
    position: float
    duration: float
    volume: float
    current_track: Optional[str]


class AudioMonitorThread(threading.Thread):
    def __init__(
        self,
        on_state_change: Optional[Callable[[PlaybackStatus], None]] = None,
        on_track_end: Optional[Callable[[], None]] = None,
        on_position_change: Optional[Callable[[float], None]] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        super().__init__(daemon=True)
        self.logger = logging.getLogger(__name__)
        self._running = True
        self._poll_interval = poll_interval
        self._on_state_change = on_state_change
        self._on_track_end = on_track_end
        self._on_position_change = on_position_change
        self._last_state = PlayerState.STOPPED
        self._last_position = 0.0
        self._last_track = None

    def stop(self) -> None:
        self._running = False
        self.join(timeout=1.0)

    def _get_current_status(self) -> PlaybackStatus:
        return PlaybackStatus(
            state=self._determine_player_state(),
            position=audio_player.get_position(),
            duration=audio_player.duration,
            volume=audio_player.volume,
            current_track=audio_player.get_current_track(),
        )

    def _determine_player_state(self) -> PlayerState:
        if not audio_player.get_current_track():
            return PlayerState.STOPPED
        if audio_player.is_paused:
            return PlayerState.PAUSED
        if audio_player.is_playing():
            return PlayerState.PLAYING
        return PlayerState.STOPPED

    def run(self) -> None:
        while self._running:
            current_status = self._get_current_status()

            if current_status.state != self._last_state:
                self._handle_state_change(current_status)
                self._last_state = current_status.state

            if (
                self._last_state == PlayerState.PLAYING
                and current_status.state == PlayerState.STOPPED
                and self._last_track == current_status.current_track
            ):
                self._handle_track_end()

            if current_status.state == PlayerState.PLAYING and abs(current_status.position - self._last_position) > 0.1:
                self._handle_position_change(current_status.position)
                self._last_position = current_status.position

            self._last_track = current_status.current_track
            time.sleep(self._poll_interval)

    def _handle_state_change(self, status: PlaybackStatus) -> None:
        if not self._on_state_change:
            return
        try:
            self._on_state_change(status)
        except Exception as exc:
            self.logger.error("Error in on_state_change callback: %s", exc)

    def _handle_track_end(self) -> None:
        if not self._on_track_end:
            return
        try:
            self._on_track_end()
        except Exception as exc:
            self.logger.error("Error in on_track_end callback: %s", exc)

    def _handle_position_change(self, position: float) -> None:
        if not self._on_position_change:
            return
        try:
            self._on_position_change(position)
        except Exception as exc:
            self.logger.error("Error in on_position_change callback: %s", exc)
