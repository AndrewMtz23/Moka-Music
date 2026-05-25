from dataclasses import dataclass
from enum import Enum, auto
from typing import Final


class ThemeMode(Enum):
    DARK = auto()
    LIGHT = auto()
    SYSTEM = auto()


@dataclass(frozen=True)
class ColorPalette:
    primary: str
    secondary: str
    background: str
    surface: str
    error: str
    text: str
    disabled: str


APP_NAME: Final[str] = "MokaMusic"
VERSION: Final[str] = "2.1.0"
COPYRIGHT: Final[str] = "Copyright 2026 MokaMusic"


THEMES: dict[ThemeMode, ColorPalette] = {
    ThemeMode.DARK: ColorPalette(
        primary="#6A5ACD",
        secondary="#2F7D32",
        background="#121212",
        surface="#1E1E1E",
        error="#CF6679",
        text="#FFFFFF",
        disabled="#888888",
    ),
    ThemeMode.LIGHT: ColorPalette(
        primary="#3F51B5",
        secondary="#2E7D32",
        background="#F5F5F5",
        surface="#FFFFFF",
        error="#B00020",
        text="#212121",
        disabled="#757575",
    ),
}


DEFAULT_VOLUME: Final[float] = 0.8
MAX_VOLUME: Final[float] = 1.0
MIN_VOLUME: Final[float] = 0.0
DEFAULT_POLL_INTERVAL: Final[float] = 0.5


class FileFormats:
    AUDIO = (".mp3", ".wav", ".ogg", ".flac")
    IMAGES = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
    COVERS = (".jpg", ".jpeg", ".png")


class UISettings:
    WINDOW_MIN_SIZE = (900, 640)
    WINDOW_DEFAULT_SIZE = (1280, 840)
    PREVIEW_IMAGE_SIZE = (150, 150)
    VOLUME_SLIDER_STEPS = 100
    MAX_FILENAME_DISPLAY = 50
    TOOLTIP_DELAY_MS = 500


class Icons:
    FOLDER = "[DIR]"
    MUSIC = "[MUSIC]"
    ADD = "[ADD]"
    PLAY = ">"
    PAUSE = "||"
    STOP = "[]"
    VOLUME = "[VOL]"
    WARNING = "[WARN]"
    ERROR = "[ERR]"
    SUCCESS = "[OK]"
    IMAGE = "[IMG]"
    EXIT = "[EXIT]"


class Messages:
    FILE_NOT_FOUND = "File not found: {}"
    UNSUPPORTED_FORMAT = "Unsupported format: {}"
    DUPLICATE_FILE = "The file already exists in the library: {}"
    METADATA_SAVED = "Metadata saved successfully"
    PLAYBACK_STARTED = "Playback started: {}"
    PLAYBACK_PAUSED = "Playback paused"
    TRACK_ENDED = "Track finished"


DEFAULT_METADATA = {
    "title": "",
    "artist": "",
    "album": "",
    "genre": "",
    "year": "",
    "track_number": "0",
}


LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
LOG_FILE: Final[str] = "mokamusic.log"

SUPPORTED_AUDIO_FORMATS = FileFormats.AUDIO
SUPPORTED_IMAGE_FORMATS = FileFormats.IMAGES
SUPPORTED_COVER_FORMATS = FileFormats.COVERS
MAX_FILENAME_DISPLAY = UISettings.MAX_FILENAME_DISPLAY
ICON_MUSIC = Icons.MUSIC
ICON_ADD = Icons.ADD
MSG_ADDED_SUCCESS = "Song added successfully"
MSG_DUPLICATE = "Song already exists: {}"
DEFAULT_COVER_ART = "assets/default_cover.png"
CONFIG_FILE_NAME = "mokamusic_config.json"
