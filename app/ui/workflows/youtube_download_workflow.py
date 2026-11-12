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

    def start(self, destination: str) -> None:
        if not destination.strip():
            self.ui.show_warning(
                self.ui.translate("youtube_download.title"),
                self.ui.translate("youtube_download.incoming_folder_required"),
            )
            return

        options = self.ui.request_options(destination)
        if not options:
            return
        if not bool(options.get("authorized")):
            self.ui.show_warning(
                self.ui.translate("youtube_download.title"),
                self.ui.translate("youtube_download.authorization_required"),
            )
            return

        try:
            url = validate_youtube_url(str(options.get("url", "")))
        except InvalidYouTubeUrlError as exc:
            self.ui.show_error(
                self.ui.translate("youtube_download.title"),
                self.ui.translate("youtube_download.invalid_url", error=exc),
            )
            return

        requested_destination = str(options.get("destination", "")).strip()
        if requested_destination != destination:
            self.ui.show_error(
                self.ui.translate("youtube_download.title"),
                self.ui.translate("youtube_download.destination_changed"),
            )
            return
        progress = self.ui.begin_progress(
            title=self.ui.translate("youtube_download.title"),
            message=self.ui.translate("youtube_download.progress"),
            total=100,
        )
        events: queue.Queue[tuple[str, object]] = queue.Queue()
        cancelled = threading.Event()

        def report(event: YouTubeDownloadProgress) -> bool:
            if cancelled.is_set():
                return False
            events.put(("progress", event))
            return True

        def worker() -> None:
            try:
                result = self.download(url, destination, progress_callback=report)
            except YouTubeDownloadCancelled as exc:
                events.put(("cancelled", exc))
            except Exception as exc:
                self.logger.exception("YouTube audio download failed")
                events.put(("error", exc))
            else:
                events.put(("success", result))

        try:
            threading.Thread(target=worker, daemon=True).start()
        except RuntimeError as exc:
            progress.close()
            self.logger.exception("Could not start YouTube download worker")
            self.ui.show_error(
                self.ui.translate("youtube_download.title"),
                self.ui.translate("youtube_download.failed", error=exc),
            )
            return

        self._poll_events(events, cancelled, progress, completed=0)

    def _poll_events(
        self,
        events: queue.Queue[tuple[str, object]],
        cancelled: threading.Event,
        progress: DownloadProgressPort,
        completed: int,
    ) -> None:
        if progress.cancelled:
            cancelled.set()

        while True:
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                self.ui.schedule(
                    100,
                    lambda completed=completed: self._poll_events(events, cancelled, progress, completed),
                )
                return

            if kind == "progress":
                event = payload
                if not isinstance(event, YouTubeDownloadProgress) or progress.cancelled:
                    continue
                if event.percent is not None:
                    completed = int(event.percent)
                detail = self._progress_detail(event)
                progress.update(completed, 100, detail)
                continue

            progress.close()
            title = self.ui.translate("youtube_download.title")
            if kind == "success":
                result = payload
                if not isinstance(result, YouTubeDownloadResult):
                    self.ui.show_error(
                        title,
                        self.ui.translate(
                            "youtube_download.failed",
                            error="The download service returned an invalid result",
                        ),
                    )
                    return
                self.ui.show_info(
                    title,
                    self.ui.translate("youtube_download.done", path=result.path),
                )
                self.ui.download_complete(result)
                return
            if kind == "cancelled":
                self.ui.show_info(title, self.ui.translate("youtube_download.cancelled"))
                return
            self.ui.show_error(
                title,
                self.ui.translate("youtube_download.failed", error=payload),
            )
            return

    def _progress_detail(self, event: YouTubeDownloadProgress) -> str:
        if event.stage == "downloading":
            if event.percent is None:
                return self.ui.translate("youtube_download.downloading")
            return self.ui.translate("youtube_download.downloading_percent", percent=event.percent)
        if event.stage == "converting":
            return self.ui.translate("youtube_download.converting")
        return self.ui.translate("youtube_download.progress")
