from enum import Enum, auto


class SortMode(Enum):
    MANUAL = auto()
    FILENAME = auto()
    ARTIST = auto()
    ALBUM = auto()
    TRACK_NUMBER = auto()
    DURATION = auto()
    BITRATE = auto()
    DATE_ADDED = auto()
    LAST_PLAYED = auto()


class FilterMode(Enum):
    ALL = auto()
    MISSING_ARTIST = auto()
    MISSING_ALBUM = auto()
    MISSING_YEAR = auto()
    MISSING_TRACK = auto()
    MISSING_COVER = auto()
    DUPLICATES = auto()
    LOW_BITRATE = auto()
    BITRATE_128 = auto()
    BITRATE_256 = auto()
    BITRATE_320 = auto()
    POSSIBLY_CORRUPT = auto()
    UNPLAYED = auto()
