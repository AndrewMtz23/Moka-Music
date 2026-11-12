from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Protocol

from ...services.youtube_download_service import (
    InvalidYouTubeUrlError,
    YouTubeDownloadCancelled,
    YouTubeDownloadProgress,
    YouTubeDownloadResult,
    download_youtube_audio,
    validate_youtube_url,
)


class DownloadProgressPort(Protocol):
    cancelled: bool

    def update(self, completed: int, total: int | None = None, detail: str = "") -> bool: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class YouTubeDownloadUiPort:
    translate: Callable[..., str]
    request_options: Callable[[str], dict[str, object] | None]
    begin_progress: Callable[..., DownloadProgressPort]
    show_warning: Callable[[str, str], object]
    show_info: Callable[[str, str], object]
    show_error: Callable[[str, str], object]
    schedule: Callable[[int, Callable[[], None]], object]
    download_complete: Callable[[YouTubeDownloadResult], None]


class YouTubeDownloadWorkflow:
    def __init__(
        self,
        *,
        ui: YouTubeDownloadUiPort,
        download: Callable[..., YouTubeDownloadResult] = download_youtube_audio,
    ) -> None:
        self.ui = ui
        self.download = download
        self.logger = logging.getLogger(__name__)
