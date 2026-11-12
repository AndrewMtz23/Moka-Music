from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


class YouTubeDownloadError(RuntimeError):
    pass


class InvalidYouTubeUrlError(ValueError):
    pass


class FFmpegUnavailableError(YouTubeDownloadError):
    pass


class YouTubeDownloadCancelled(YouTubeDownloadError):
    pass


@dataclass(frozen=True)
class YouTubeDownloadProgress:
    stage: str
    percent: float | None = None


@dataclass(frozen=True)
class YouTubeDownloadResult:
    title: str
    path: Path


ProgressCallback = Callable[[YouTubeDownloadProgress], bool | None]


def validate_youtube_url(url: str) -> str:
    candidate = url.strip()
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise InvalidYouTubeUrlError("Invalid YouTube URL") from exc

    host = (parsed.hostname or "").casefold().rstrip(".")
    is_youtube_host = host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    if parsed.scheme not in {"http", "https"} or not is_youtube_host or parsed.username or parsed.password:
        raise InvalidYouTubeUrlError("Enter a valid YouTube video URL")

    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    if host == "youtu.be":
        video_id = path_parts[0] if path_parts else ""
    elif parsed.path.rstrip("/") == "/watch":
        video_id = query.get("v", [""])[0]
    elif len(path_parts) >= 2 and path_parts[0] in {"embed", "live", "shorts", "v"}:
        video_id = path_parts[1]
    else:
        video_id = ""

    if not video_id or not all(character.isalnum() or character in "_-" for character in video_id):
        raise InvalidYouTubeUrlError("Enter a valid YouTube video URL")
    return candidate
