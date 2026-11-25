"""Relocate project audio references after validating replacement audio."""

import math
import threading
import tkinter as tk
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import filedialog, ttk
from uuid import uuid4

from ..models.audio_edit_project import AudioEditProject
from ..services.audio_waveform_service import AudioWaveform, extract_waveform
from ..utils.window_chrome import theme_window_caption


@dataclass(frozen=True)
class SourceHistoryState:
    project: AudioEditProject
    sources: tuple[Path, ...]
    source: Path
    target: Path
    change_source_list: bool

    def inverse(self, project, sources):
        return replace(self, project=project, sources=tuple(sources), source=self.target, target=self.source)


class EditorRelinkMixin:
    def _missing_source_paths(self):
        paths = dict.fromkeys(
            [*self._paths, *(clip.source_path for track in self._project.tracks for clip in track.clips)]
        )
        return [path for path in paths if not path.is_file() or path in self._failed_paths]

    def _browse_relink_source(self, old=None):
        if self._render_busy or self._pending_relink is not None:
            return
        if old is None:
            missing = self._missing_source_paths()
            if not missing:
                self._status_var.set(self.translate("audio_editor.relink_none"))
                return
            if len(missing) > 1:
                self._show_missing_sources(missing)
                return
            old = missing[0]
        selected = filedialog.askopenfilename(
            parent=self,
            title=self.translate("audio_editor.relink_choose", name=old.name),
            filetypes=[
                (self.translate("audio_editor.audio_files"), "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma"),
                (self.translate("audio_editor.all_files"), "*.*"),
            ],
        )
        if selected:
            self._start_source_relink(old, Path(selected).resolve())

    def _show_missing_sources(self, paths):
        window = tk.Toplevel(self)
        window.title(self.translate("audio_editor.relink_source"))
        window.configure(background=self.colors["background"])
        x = max(0, self.winfo_rootx() + (self.winfo_width() - 680) // 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - 300) // 2)
        window.geometry(f"680x300+{x}+{y}")
        window.transient(self)
        theme_window_caption(window, self.colors)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        ttk.Label(window, text=self.translate("audio_editor.relink_hint"), style="Editor.Muted.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=12
        )
        listing = tk.Listbox(
            window,
            exportselection=False,
            background=self.colors["surface"],
            foreground=self.colors["text"],
            selectbackground=self.colors["highlight"],
        )
        listing.grid(row=1, column=0, sticky="nsew", padx=(16, 0))
        scroll = ttk.Scrollbar(window, command=listing.yview)
        scroll.grid(row=1, column=1, sticky="ns", padx=(0, 16))
        listing.configure(yscrollcommand=scroll.set)
        horizontal = ttk.Scrollbar(window, orient="horizontal", command=listing.xview)
        horizontal.grid(row=2, column=0, sticky="ew", padx=(16, 0))
        listing.configure(xscrollcommand=horizontal.set)
        for path in paths:
            listing.insert(tk.END, str(path))
        listing.selection_set(0)

        def choose(_event=None):
            selected = listing.curselection()
            if selected:
                old = paths[selected[0]]
                window.destroy()
                self._browse_relink_source(old)

        ttk.Button(
            window, text=self.translate("audio_editor.relink_source"), command=choose, style="Editor.Primary.TButton"
        ).grid(row=3, column=0, sticky="e", padx=16, pady=12)
        window.bind("<Escape>", lambda _event: window.destroy())
        listing.bind("<Return>", choose)
        listing.bind("<Double-Button-1>", choose)
        window.grab_set()
        listing.focus_set()

    def _start_source_relink(self, old, new):
        if self._render_busy or self._pending_relink is not None:
            return
        token = uuid4().hex
        self._pending_relink = token
        results, cancel = self._results, self._cancel_event
        self._status_var.set(self.translate("audio_editor.relink_checking", name=new.name))

        def worker():
            try:
                waveform = extract_waveform(new, width=1200, height=96, cancel_event=cancel)
            except Exception as exc:
                results.put(("relink", old, (token, new, exc)))
            else:
                results.put(("relink", old, (token, new, waveform)))

        self._relink_thread = threading.Thread(target=worker, daemon=True)
        try:
            self._relink_thread.start()
        except RuntimeError as exc:
            self._pending_relink = None
            self._status_var.set(self.translate("audio_editor.relink_failed", error=exc))

    def _finish_source_relink(self):
        if self._render_busy or self._relink_ready is None:
            return
        old, (token, new, result) = self._relink_ready
        self._relink_ready = None
        if token != self._pending_relink:
            return
        self._pending_relink = None
        if isinstance(result, Exception):
            self._status_var.set(self.translate("audio_editor.relink_failed", error=result))
            return
        self._apply_source_relink(old, new, result)

    def _apply_source_relink(self, old, new, waveform):
        referenced = [clip for track in self._project.tracks for clip in track.clips if clip.source_path == old]
        if self._render_busy or (not referenced and old not in self._paths):
            return False
        if not new.is_file() or not isinstance(waveform, AudioWaveform) or not math.isfinite(waveform.duration):
            self._status_var.set(
                self.translate("audio_editor.relink_failed", error=self.translate("audio_editor.error"))
            )
            return False
        required = max((clip.source_end for clip in referenced), default=0)
        if waveform.duration <= 0 or waveform.duration + 1e-9 < required:
            self._status_var.set(
                self.translate(
                    "audio_editor.relink_short", required=f"{required:.2f}", actual=f"{waveform.duration:.2f}"
                )
            )
            return False
        updated = replace(
            self._project,
            tracks=tuple(
                replace(
                    track,
                    clips=tuple(
                        replace(clip, source_path=new) if clip.source_path == old else clip for clip in track.clips
                    ),
                )
                for track in self._project.tracks
            ),
        )
        self._cancel_editor_drag()
        self._remember_state(source_relink=(new, old))
        self._paths = list(dict.fromkeys(new if path == old else path for path in self._paths))
        self._waveforms[new] = waveform
        self._failed_paths.discard(new)
        self._auto_add_paths.discard(old)
        notice = getattr(self, "_missing_sources_notice", None)
        self._load_errors = [error for error in self._load_errors if old.name not in error and error != notice]
        self._restore_project_state(updated)
        self._refresh_source_list()
        self._status_var.set(self.translate("audio_editor.relink_done", name=new.name))
        return True

    def _restore_history_state(self, state):
        if isinstance(state, SourceHistoryState):
            if state.change_source_list and state.source in self._paths and state.target in state.sources:
                paths = []
                keep_source = state.source in state.sources
                for path in self._paths:
                    if path != state.source:
                        paths.append(path)
                    elif keep_source:
                        # Undo a merge without resurrecting unrelated removed rows.
                        if state.sources.index(state.target) < state.sources.index(state.source):
                            paths.extend((state.target, state.source))
                        else:
                            paths.extend((state.source, state.target))
                    else:
                        paths.append(state.target)
                self._paths = list(dict.fromkeys(paths))
            self._restore_project_state(state.project)
            self._refresh_source_list()
        else:
            self._restore_project_state(state)
