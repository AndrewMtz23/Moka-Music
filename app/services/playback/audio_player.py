import logging
import os
from pathlib import Path
from typing import Optional

from ...constants import DEFAULT_VOLUME, FileFormats
from ...utils.audio_utils import AudioUtils


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except Exception:  # pragma: no cover - import path varies by environment
    pygame = None


class AudioPlayer:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.current_track: Optional[str] = None
        self.duration = 0.0
        self.volume = DEFAULT_VOLUME
        self.is_paused = False
        self._available = False
        self._track_ended = False
        self._was_playing = False
        self._position_offset = 0.0
        self._setup_mixer()

    def _setup_mixer(self) -> None:
        if pygame is None:
            self.logger.warning("pygame is not available; audio playback disabled")
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            pygame.mixer.music.set_volume(self.volume)
            self._available = True
        except Exception as exc:
            self.logger.error("Unable to initialize pygame mixer: %s", exc)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def load(self, path: str) -> None:
        if not self._available:
            raise RuntimeError("Audio playback is not available in this environment.")

        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if path_obj.suffix.lower() not in FileFormats.AUDIO:
            raise ValueError(f"Unsupported format: {path_obj.suffix}")

        pygame.mixer.music.load(str(path_obj))
        self.current_track = str(path_obj)
        self.duration = AudioUtils.get_audio_duration(str(path_obj))
        self.is_paused = False
        self._track_ended = False
        self._was_playing = False
        self._position_offset = 0.0

    def play(self) -> None:
        if not self._available or not self.current_track:
            return
        if self.is_paused:
            pygame.mixer.music.unpause()
        else:
            try:
                pygame.mixer.music.play(start=self._position_offset)
            except TypeError:
                pygame.mixer.music.play()
            except Exception as exc:
                self.logger.warning("Unable to start at %.2fs: %s", self._position_offset, exc)
                self._position_offset = 0.0
                pygame.mixer.music.play()
        self.is_paused = False
        self._track_ended = False
        self._was_playing = True

    def pause(self) -> None:
        if not self._available:
            return
        pygame.mixer.music.pause()
        self.is_paused = True

    def stop(self) -> None:
        if not self._available:
            return
        pygame.mixer.music.stop()
        self.is_paused = False
        self._track_ended = False
        self._was_playing = False
        self._position_offset = 0.0

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))
        if self._available:
            pygame.mixer.music.set_volume(self.volume)

    def is_playing(self) -> bool:
        return bool(self._available and pygame.mixer.music.get_busy() and not self.is_paused)

    def get_position(self) -> float:
        if not self._available:
            return self._position_offset
        milliseconds = pygame.mixer.music.get_pos()
        if milliseconds < 0:
            return self._position_offset
        return min(self.duration or 0.0, self._position_offset + (milliseconds / 1000.0))

    def seek(self, position_seconds: float, *, resume: bool = True) -> float:
        if not self.current_track:
            return 0.0

        target = max(0.0, min(float(position_seconds), self.duration or float(position_seconds)))
        self._position_offset = target
        self._track_ended = False

        if not self._available:
            return target

        was_playing = self.is_playing()
        try:
            pygame.mixer.music.play(start=target)
            if not resume and not was_playing:
                pygame.mixer.music.pause()
                self.is_paused = True
                self._was_playing = False
            else:
                self.is_paused = False
                self._was_playing = True
        except TypeError:
            self.logger.warning("Seeking is not supported by this pygame version")
        except Exception as exc:
            self.logger.warning("Unable to seek to %.2fs: %s", target, exc)
        return target

    def get_current_track(self) -> Optional[str]:
        return self.current_track

    def poll_track_end(self) -> bool:
        if not self._available or not self.current_track:
            return False

        busy = pygame.mixer.music.get_busy()
        if self._was_playing and not busy and not self.is_paused:
            if not self._track_ended:
                self._track_ended = True
                self._was_playing = False
                return True
        elif busy:
            self._track_ended = False
            self._was_playing = True
        return False

    def cleanup(self) -> None:
        if not self._available:
            return
        try:
            self.stop()
            pygame.mixer.quit()
        except Exception as exc:
            self.logger.error("Error cleaning up audio player: %s", exc)


audio_player = AudioPlayer()
