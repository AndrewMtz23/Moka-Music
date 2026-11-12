import threading
import time
import unittest
from pathlib import Path

from app.services.youtube_download_service import YouTubeDownloadProgress, YouTubeDownloadResult
from app.ui.workflows.youtube_download_workflow import YouTubeDownloadUiPort, YouTubeDownloadWorkflow


class FakeRoot:
    def __init__(self):
        self.callbacks = []

    def after(self, _delay, callback):
        self.callbacks.append(callback)

    def run_until(self, completed):
        deadline = time.monotonic() + 2
        while not completed.is_set() and time.monotonic() < deadline:
            if self.callbacks:
                self.callbacks.pop(0)()
            else:
                time.sleep(0.005)
        if not completed.is_set():
            raise AssertionError("The workflow did not complete")


class FakeProgress:
    def __init__(self):
        self.cancelled = False
        self.updates = []
        self.closed = False

    def update(self, completed, total=None, detail=""):
        self.updates.append((completed, total, detail))
        return not self.cancelled

    def close(self):
        self.closed = True


class YouTubeDownloadWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.root = FakeRoot()
        self.progress = FakeProgress()
        self.finished = threading.Event()
        self.calls = []
        self.completed_downloads = []
        self.options = {
            "url": "https://youtu.be/video01",
            "destination": "C:/Music/Incoming",
            "authorized": True,
        }

    def create_workflow(self, download):
        def finish(kind, title, message):
            self.calls.append((kind, title, message, threading.get_ident()))
            self.finished.set()

        ui = YouTubeDownloadUiPort(
            translate=lambda key, **kwargs: key if not kwargs else f"{key}:{kwargs}",
            request_options=lambda destination: (
                {**self.options, "destination": destination} if self.options is not None else None
            ),
            begin_progress=lambda **_kwargs: self.progress,
            show_warning=lambda title, message: finish("warning", title, message),
            show_info=lambda title, message: finish("info", title, message),
            show_error=lambda title, message: finish("error", title, message),
            schedule=self.root.after,
            download_complete=self.completed_downloads.append,
        )
        return YouTubeDownloadWorkflow(ui=ui, download=download)

    def test_download_runs_off_ui_thread_and_progress_is_applied_on_ui_thread(self):
        main_thread = threading.get_ident()
        worker_threads = []

        def download(url, destination, *, progress_callback):
            worker_threads.append(threading.get_ident())
            self.assertEqual(url, "https://youtu.be/video01")
            self.assertEqual(destination, "C:/Music/Incoming")
            progress_callback(YouTubeDownloadProgress(stage="downloading", percent=42.5))
            progress_callback(YouTubeDownloadProgress(stage="converting"))
            return YouTubeDownloadResult(title="Song", path=Path("C:/Music/Incoming/Song.mp3"))

        workflow = self.create_workflow(download)
        workflow.start("C:/Music/Incoming")
        self.root.run_until(self.finished)

        self.assertNotEqual(worker_threads[0], main_thread)
        self.assertTrue(self.progress.closed)
        self.assertEqual(self.progress.updates[0], (42, 100, "youtube_download.downloading_percent:{'percent': 42.5}"))
        self.assertEqual(self.progress.updates[1], (42, 100, "youtube_download.converting"))
        self.assertEqual(self.calls[0][0], "info")
        self.assertEqual(self.calls[0][3], main_thread)
        self.assertEqual(len(self.completed_downloads), 1)

    def test_cancelled_dialog_does_not_start_download(self):
        self.options = None
        workflow = self.create_workflow(lambda *_args, **_kwargs: self.fail("download must not start"))

        workflow.start("C:/Music/Incoming")

        self.assertFalse(self.calls)
        self.assertFalse(self.progress.closed)

    def test_missing_authorization_does_not_start_download(self):
        self.options["authorized"] = False
        workflow = self.create_workflow(lambda *_args, **_kwargs: self.fail("download must not start"))

        workflow.start("C:/Music/Incoming")

        self.assertEqual(self.calls[0][0], "warning")

    def test_invalid_url_is_reported_without_starting_download(self):
        self.options["url"] = "https://example.com/audio"
        workflow = self.create_workflow(lambda *_args, **_kwargs: self.fail("download must not start"))

        workflow.start("C:/Music/Incoming")

        self.assertEqual(self.calls[0][0], "error")
        self.assertIn("youtube_download.invalid_url", self.calls[0][2])

    def test_missing_incoming_library_folder_does_not_open_modal_or_start_download(self):
        workflow = self.create_workflow(lambda *_args, **_kwargs: self.fail("download must not start"))

        workflow.start("")

        self.assertEqual(self.calls[0][0], "warning")
        self.assertIn("youtube_download.incoming_folder_required", self.calls[0][2])
        self.assertFalse(self.progress.updates)

    def test_worker_error_is_reported_to_the_ui(self):
        def fail(*_args, **_kwargs):
            raise RuntimeError("network disconnected")

        workflow = self.create_workflow(fail)
        with self.assertLogs("app.ui.workflows.youtube_download_workflow", level="ERROR"):
            workflow.start("C:/Music/Incoming")
            self.root.run_until(self.finished)

        self.assertEqual(self.calls[0][0], "error")
        self.assertIn("network disconnected", self.calls[0][2])


if __name__ == "__main__":
    unittest.main()
