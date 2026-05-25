from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackInfo:
    filename: str
    filepath: str
    metadata: dict[str, str]
    duration: float
    cover_art: Optional[bytes]
