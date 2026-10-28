"""Repeatable cache/UI benchmark using temporary files, never user audio."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controllers.library_ui_controller import LibraryUiController
from app.controllers.metadata_controller import MetadataController
from app.i18n import I18n
from app.services.library_cache_service import LibraryCache
from app.services.track_scan_service import TrackScanResult
from app.ui_helpers.widgets import LibraryListbox


def main() -> None:
    measurements = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        folder = Path(temp_dir)
        cache = LibraryCache(folder / "cache.sqlite")
        for index in range(850):
            path = folder / f"{index:04d}.mp3"
            path.write_bytes(b"benchmark")
            cache.save_track(
                TrackScanResult(
                    path.name,
                    str(path),
                    {
                        "title": f"Song {index}",
                        "artist": "Artist",
                        "album": "Album",
                        "year": "2026",
                        "track_number": str(index),
                    },
                    180.0,
                    {},
                    True,
                )
            )
        controller = MetadataController(library_cache=cache)
        start = time.perf_counter()
        controller.cargar_archivos_mp3(str(folder))
        measurements["cached_load_seconds"] = time.perf_counter() - start
        root = tk.Tk()
        root.withdraw()
        try:
            tree = LibraryListbox(root)
            ui = LibraryUiController(
                translator=I18n().t,
                theme_colors=lambda: {
                    "surface": "#ffffff",
                    "surface_alt": "#eeeeee",
                    "text": "#111111",
                    "text_secondary": "#888888",
                    "highlight": "#000000",
                    "highlight_text": "#ffffff",
                    "warning": "#999900",
                    "error": "#ff0000",
                },
                filename_from_item=lambda item: item["tags"][0],
                short_name=lambda filename: filename,
            )
            for label in ("initial_render", "unchanged_refresh", "single_edit"):
                if label == "single_edit":
                    controller.get_track_info("0210.mp3").metadata["title"] = "Edited title"
                start = time.perf_counter()
                ui.update_treeview(tree=tree, files=controller.archivos, controller=controller, panel=None)
                root.update_idletasks()
                measurements[f"{label}_seconds"] = time.perf_counter() - start
        finally:
            root.destroy()
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    main()
