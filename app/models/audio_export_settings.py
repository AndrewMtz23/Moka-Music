"""Validated output preferences; independent of project edits and preview audio."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioExportSettings:
    format: str = ".mp3"
    sample_rate: int = 44100
    bitrate_kbps: int = 320
    bit_depth: int = 16
    ogg_quality: int = 5

    @staticmethod
    def sample_rates(format):
        return (44100, 48000, 96000) if format in (".wav", ".flac") else (44100, 48000)

    def __post_init__(self):
        if self.format not in (".mp3", ".wav", ".flac", ".ogg"):
            raise ValueError("Unsupported export format")
        if self.sample_rate not in self.sample_rates(self.format):
            raise ValueError("Unsupported sample rate for this format")
        if self.bitrate_kbps not in (128, 192, 256, 320):
            raise ValueError("Unsupported MP3 bitrate")
        if self.bit_depth not in (16, 24):
            raise ValueError("Unsupported bit depth")
        if self.ogg_quality not in (3, 5, 7, 9):
            raise ValueError("Unsupported OGG quality")
