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


def download_youtube_audio(
    url: str,
    output_directory: str | Path,
    *,
    progress_callback: ProgressCallback | None = None,
) -> YouTubeDownloadResult:
    valid_url = validate_youtube_url(url)
    destination = Path(output_directory)
    if shutil.which("ffmpeg") is None:
        raise FFmpegUnavailableError("FFmpeg was not found on PATH")

    if not destination.is_dir():
        raise YouTubeDownloadError(f"Download destination is not a folder: {destination}")

    with tempfile.TemporaryDirectory(prefix=".mokamusic-ytdlp-", dir=destination) as temporary_directory:
        temp_path = Path(temporary_directory)
        options = _build_options(temp_path, progress_callback)
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(valid_url, download=True)
        except DownloadError as exc:
            raise YouTubeDownloadError(str(exc)) from exc
        except OSError as exc:
            raise YouTubeDownloadError(f"Download or conversion failed: {exc}") from exc

        if not info:
            raise YouTubeDownloadError("yt-dlp did not return video information")

        source = _find_converted_mp3(temp_path, info)
        target = _move_to_unique_destination(source, destination)
        _report(progress_callback, YouTubeDownloadProgress(stage="complete", percent=100.0))
        return YouTubeDownloadResult(title=str(info.get("title") or source.stem), path=target)


def _build_options(output_directory: Path, progress_callback: ProgressCallback | None) -> dict[str, object]:
    return {
        "format": "bestaudio/best",
        "outtmpl": {"default": str(output_directory / "%(title)s.%(ext)s")},
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
        "windowsfilenames": True,
        "overwrites": False,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_download_hook(progress_callback)],
        "postprocessor_hooks": [_postprocessor_hook(progress_callback)],
    }


def _download_hook(progress_callback: ProgressCallback | None) -> Callable[[dict[str, object]], None]:
    def report(data: dict[str, object]) -> None:
        status = data.get("status")
        if status == "downloading":
            downloaded = data.get("downloaded_bytes")
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            percent = round(float(downloaded) * 100 / float(total), 1) if downloaded is not None and total else None
            _report(progress_callback, YouTubeDownloadProgress(stage="downloading", percent=percent))
        elif status == "finished":
            _report(progress_callback, YouTubeDownloadProgress(stage="downloading", percent=100.0))

    return report


def _postprocessor_hook(progress_callback: ProgressCallback | None) -> Callable[[dict[str, object]], None]:
    def report(data: dict[str, object]) -> None:
        status = data.get("status")
        if status in {"started", "processing"}:
            _report(progress_callback, YouTubeDownloadProgress(stage="converting"))
        elif status == "finished":
            _report(progress_callback, YouTubeDownloadProgress(stage="converting", percent=100.0))

    return report


def _report(
    callback: ProgressCallback | None,
    progress: YouTubeDownloadProgress,
) -> None:
    if callback is not None and callback(progress) is False and progress.stage != "complete":
        raise YouTubeDownloadCancelled("Download cancelled")
