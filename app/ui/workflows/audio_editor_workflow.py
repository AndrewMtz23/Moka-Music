from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class AudioEditorUiPort:
    translate: Callable[..., str]
    show_warning: Callable[[str, str], object]
    open_editor: Callable[[list[Path]], None]
    has_saved_project: Callable[[], bool] = lambda: False


@dataclass(frozen=True)
class AudioEditorLibraryPort:
    selected_audio_paths: Callable[[], list[Path]]


class AudioEditorWorkflow:
    def __init__(self, *, library: AudioEditorLibraryPort, ui: AudioEditorUiPort) -> None:
        self.library = library
        self.ui = ui

    def open(self) -> None:
        paths = self.library.selected_audio_paths()
        if not paths and not self.ui.has_saved_project():
            self.ui.show_warning(
                self.ui.translate("audio_editor.title"),
                self.ui.translate("audio_editor.select_tracks_first"),
            )
            return
        self.ui.open_editor(paths)
