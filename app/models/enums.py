from enum import Enum, auto


class SortMode(Enum):
    MANUAL = auto()
    FILENAME = auto()
    ARTIST = auto()
    ALBUM = auto()
    TRACK_NUMBER = auto()
    DURATION = auto()
    DATE_ADDED = auto()


class FilterMode(Enum):
    ALL = auto()
    MISSING_ARTIST = auto()
    MISSING_ALBUM = auto()
    MISSING_YEAR = auto()
    MISSING_TRACK = auto()
    MISSING_COVER = auto()
    DUPLICATES = auto()
