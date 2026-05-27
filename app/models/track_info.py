from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrackInfo:
    filename: str
    filepath: str
    metadata: dict[str, str]
    duration: float
    cover_art: Optional[bytes]
    audio_quality: dict[str, object] = field(default_factory=dict)
