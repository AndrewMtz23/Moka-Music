from __future__ import annotations

import logging
import math
import queue
import shutil
import tempfile
import threading
import tkinter as tk
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable, Iterable
from uuid import uuid4

from ..models.audio_edit_project import (
    AudioEditClip,
    AudioEditMarker,
    AudioEditMode,
    AudioEditProject,
    AudioEditTrack,
)
from ..models.audio_export_settings import AudioExportSettings
from ..services.audio_edit_service import (
    AudioEditCancelled,
    AudioEditError,
    apply_crossfade,
    clear_crossfades_with_changed_neighbors,
    export_audio_project,
    move_sequence_clip,
    remove_clip_interval,
    render_audio_project,
    sequence_clips,
    split_clip,
    trim_clip,
    validate_track_crossfades,
)
from ..services.audio_waveform_service import AudioWaveform, AudioWaveformError, extract_waveform
from ..utils import themed_messagebox as messagebox
from .audio_editor_layout import EditorLayoutMixin
from .audio_editor_loop import EditorLoopMixin
from .audio_editor_projects import EditorProjectsMixin
from .audio_editor_quick_trim import EditorQuickTrimMixin
from .audio_editor_relink import EditorRelinkMixin, SourceHistoryState
from .audio_editor_source_drag import SourceDragMixin
from .audio_effect_chain_dialog import edit_audio_effect_chain
from .audio_export_dialog import choose_audio_export
from .audio_processing_dialog import edit_audio_processing
from .audio_timeline_interaction import sequence_drop_index


@dataclass(frozen=True)
class _ClipboardEntry:
    clip: AudioEditClip
    track_offset: int
    time_offset: float


class AudioEditorDashboard(
    EditorQuickTrimMixin,
    EditorRelinkMixin,
    EditorLoopMixin,
    EditorProjectsMixin,
    SourceDragMixin,
    EditorLayoutMixin,
    tk.Toplevel,
):
    def __init__(
        self,
        parent,
        *,
        source_paths: Iterable[str | Path],
        translate: Callable[..., str],
        colors: dict[str, str],
        playback_snapshot: object | None = None,
        play_loop_preview: Callable[[Path], None] | None = None,
        play_preview: Callable[[Path], None] | None = None,
        pause_preview: Callable[[], None] | None = None,
        resume_preview: Callable[[], None] | None = None,
        stop_preview: Callable[[], None] | None = None,
        preview_is_playing: Callable[[], bool] | None = None,
        restore_playback: Callable[[object | None], None] | None = None,
        playback_position: Callable[[], float] | None = None,
        export_completed: Callable[[Path], None] | None = None,
        initial_export_folder: str | Path | None = None,
        project_path: str | Path | None = None,
    ):
        super().__init__(parent)
        self._session_path = Path(project_path) if project_path else None
        self._project_path = None
        self._saved_document_state = None
        self._project_load_failed = False
        self.parent = parent
        self.translate = translate
        self.colors = colors
        self.logger = logging.getLogger(__name__)
        self._cancel_event = threading.Event()
        self._render_cancel = threading.Event()
        self._results: queue.Queue[tuple[str, Path, AudioWaveform | Exception | None]] = queue.Queue()
        self._render_results: queue.Queue[tuple[str, object]] = queue.Queue()
        self._poll_id: str | None = None
        self._render_poll_id: str | None = None
        self._temp_dir = Path(tempfile.mkdtemp(prefix="mokamusic-audio-editor-"))
        self._closing = False
        self._pending_relink = None
        self._relink_ready = None
        self._render_busy = False
        self._render_thread: threading.Thread | None = None
        self._preview_path: Path | None = None
        self._preview_project_snapshot: AudioEditProject | None = None
        self._preview_region_snapshot = None
        self._audition_region = None
        self._preview_is_audition = False
        self._loop_var = tk.BooleanVar(value=False)
        self._play_loop_preview = play_loop_preview
        self._preview_active = False
        self._preview_paused = False
        self._playback_snapshot = playback_snapshot
        self._playback_modified = False
        self._play_preview = play_preview
        self._pause_preview = pause_preview
        self._resume_preview = resume_preview
        self._stop_preview = stop_preview
        self._preview_is_playing = preview_is_playing
        self._restore_playback = restore_playback
        self._playback_position = playback_position
        self._export_completed = export_completed
        self._initial_export_folder = Path(initial_export_folder) if initial_export_folder else None
        self._undo_stack: list[AudioEditProject | SourceHistoryState] = []
        self._redo_stack: list[AudioEditProject | SourceHistoryState] = []
        self._clipboard: tuple[_ClipboardEntry, ...] = ()
        self._updating_track_controls = False
        self._paths: list[Path] = []
        self._waveforms: dict[Path, AudioWaveform] = {}
        self._failed_paths: set[Path] = set()
        self._load_errors: list[str] = []
        self._clips: list[AudioEditClip] = []
        self._tracks: list[AudioEditTrack] = []
        self._markers: list[AudioEditMarker] = []
        self._mode = AudioEditMode.SEQUENCE
        self._sequence_track_volume = 1.0
        self._selected_track_id: str | None = None
        self._export_settings = AudioExportSettings()
        self._export_format_var = tk.StringVar(value=".mp3")
        self._track_volume_var = tk.DoubleVar(value=100)
        self._clip_gain_var = tk.StringVar(value="0")
        self._clip_pan_var = tk.StringVar(value="0")
        self._workers_active = 0
        initial_paths = [Path(path).resolve() for path in source_paths if Path(path).is_file()]
        self._auto_add_paths = set(initial_paths)
        self._project = AudioEditProject()

        self.title(self.translate("audio_editor.title"))
        self.geometry("1180x690")
        self.minsize(860, 520)
        self.configure(background=colors["background"])
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.resizable(True, True)
        self._build_ui()
        self._bind_editor_shortcuts()
        self._init_source_drag()
        self._render_control_states: dict[tk.Widget, str] = {}
        self._collect_render_controls(self)
        self._refresh_project()
        self._saved_document_state = self._project_state()
        if not self._restore_editor_session():
            self._add_source_paths(initial_paths)
        self._update_project_title()
        self._poll_id = self.after(80, self._poll_results)
        self._render_poll_id = self.after(80, self._poll_render_results)
        self._playback_poll_id = self.after(150, self._refresh_playback_display)

    def _bind_editor_shortcuts(self) -> None:
        shortcuts = {
            "<Control-s>": self._save_editor_project,
            "<Control-Shift-S>": self._save_project_as,
            "<Control-n>": self._new_editor_project,
            "<Control-o>": self._open_editor_project,
            "<space>": self._toggle_preview,
            "<s>": self._split_at_cursor,
            "<F4>": self._toggle_inspector,
            "<Control-0>": self._fit_project,
            "<Delete>": self._remove_selected_clip,
            "<Control-c>": self._copy_selected_clips,
            "<Control-x>": self._cut_selected_clips,
            "<Control-v>": self._paste_clips,
            "<Control-d>": self._duplicate_selected_clips,
            "<Control-z>": self._undo,
            "<Control-y>": self._redo,
            "<Control-Shift-Z>": self._redo,
        }
        for sequence, action in shortcuts.items():
            self.bind(sequence, lambda event, callback=action: self._run_shortcut(event, callback))
        # Scope cursor keys to the timeline: entries, lists and resize grips
        # retain their normal keyboard behavior.
        for sequence, direction, step in (
            ("<Left>", "backward", 0.1),
            ("<Right>", "forward", 0.1),
            ("<Shift-Left>", "backward", 0.01),
            ("<Shift-Right>", "forward", 0.01),
            ("<Home>", "start", 0),
            ("<End>", "end", 0),
        ):
            self.timeline.canvas.bind(
                sequence,
                lambda event, direction=direction, step=step: self._run_shortcut(
                    event, lambda: self._navigate_cursor(direction, step=step)
                ),
            )

    def _run_shortcut(self, _event, action: Callable[[], None]) -> str | None:
        if action in (
            self._save_editor_project,
            self._save_project_as,
            self._new_editor_project,
            self._open_editor_project,
        ):
            action()
            return "break"
        focus = self.focus_get()
        input_controls = (
            tk.Entry,
            tk.Text,
            tk.Listbox,
            tk.Spinbox,
            ttk.Button,
            ttk.Checkbutton,
            ttk.Combobox,
            ttk.Entry,
            ttk.Scale,
            ttk.Spinbox,
            ttk.Treeview,
        )
        if focus is not None and isinstance(focus, input_controls):
            return None
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return "break"
        action()
        return "break"

    def _build_ui(self) -> None:
        self._build_editor_layout()

    def _browse_sources(self) -> None:
        selected = filedialog.askopenfilenames(
            parent=self,
            title=self.translate("audio_editor.choose_audio"),
            filetypes=[
                (self.translate("audio_editor.audio_files"), "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma"),
                (self.translate("audio_editor.all_files"), "*.*"),
            ],
        )
        self._add_source_paths(selected)

    def _add_source_paths(self, paths: Iterable[str | Path]) -> None:
        new_paths = [
            Path(path).resolve() for path in paths if Path(path).is_file() and Path(path).resolve() not in self._paths
        ]
        if not new_paths:
            return
        self._paths.extend(new_paths)
        self._refresh_source_list()
        self._status_var.set(self.translate("audio_editor.loading_count", count=len(new_paths)))
        self._workers_active += 1

        results = self._results
        cancel_event = self._cancel_event

        def load_waveforms() -> None:
            for path in new_paths:
                if cancel_event.is_set():
                    break
                try:
                    waveform = extract_waveform(path, width=1200, height=96, cancel_event=cancel_event)
                except AudioWaveformError as exc:
                    results.put(("error", path, exc))
                except Exception as exc:
                    self.logger.exception("Unexpected error extracting waveform for %s", path)
                    results.put(("error", path, exc))
                else:
                    results.put(("loaded", path, waveform))
            results.put(("batch_done", Path(), None))

        try:
            threading.Thread(target=load_waveforms, daemon=True).start()
        except RuntimeError as exc:
            self._workers_active -= 1
            self.logger.exception("Could not start audio waveform worker")
            self._status_var.set(self.translate("audio_editor.worker_failed", error=exc))

    def _refresh_source_list(self) -> None:
        self.source_list.delete(0, tk.END)
        for path in self._paths:
            if not path.is_file():
                state = self.translate("audio_editor.source_missing")
            elif path in self._waveforms:
                state = self.translate("audio_editor.ready")
            elif path in self._failed_paths:
                state = self.translate("audio_editor.error")
            else:
                state = self.translate("audio_editor.loading")
            self.source_list.insert(tk.END, f"{path.name}  ·  {state}")
        self._update_project_title()

    def _poll_results(self) -> None:
        if not self.winfo_exists():
            return
        loaded_count = 0
        source_list_changed = False
        while True:
            try:
                kind, path, payload = self._results.get_nowait()
            except queue.Empty:
                break
            if kind == "relink":
                self._relink_ready = (path, payload)
            elif kind == "loaded" and isinstance(payload, AudioWaveform):
                self._waveforms[path] = payload
                loaded_count += 1
                source_list_changed = True
                if path in self._auto_add_paths:
                    self._append_clip(path, payload)
            elif kind == "error" and isinstance(payload, Exception):
                self._failed_paths.add(path)
                self._load_errors.append(f"{path.name}: {payload}")
                source_list_changed = True
                self.logger.warning("Could not load waveform for %s: %s", path, payload)
            elif kind == "batch_done":
                self._workers_active = max(0, self._workers_active - 1)
        if source_list_changed:
            self._refresh_source_list()
        if loaded_count:
            self._refresh_project()
        if self._load_errors and source_list_changed:
            self._status_var.set(self.translate("audio_editor.load_errors", errors="; ".join(self._load_errors)))
        elif not self._workers_active and source_list_changed:
            self._status_var.set(self.translate("audio_editor.ready_status", count=len(self._waveforms)))
        self._finish_source_relink()
        self._poll_id = self.after(80, self._poll_results)

    def _add_selected_source(self) -> None:
        selected_indices = self.source_list.curselection()
        if not selected_indices:
            self._status_var.set(self.translate("audio_editor.select_source"))
            return
        for index in selected_indices:
            path = self._paths[index]
            waveform = self._waveforms.get(path)
            if waveform is None:
                self._status_var.set(self.translate("audio_editor.source_loading", name=path.name))
                continue
            self._append_clip(path, waveform)
        self._refresh_project()

    def _add_selected_as_track(self) -> None:
        selected_indices = self.source_list.curselection()
        if not selected_indices:
            self._status_var.set(self.translate("audio_editor.select_source"))
            return
        if self._mode != AudioEditMode.MULTITRACK:
            self._switch_mode(AudioEditMode.MULTITRACK)
        added = False
        for index in selected_indices:
            path = self._paths[index]
            waveform = self._waveforms.get(path)
            if waveform is None:
                self._status_var.set(self.translate("audio_editor.source_loading", name=path.name))
                continue
            self._append_clip(path, waveform, as_new_track=True)
            added = True
        if added:
            self._refresh_project()

    def _append_clip(self, path: Path, waveform: AudioWaveform, *, as_new_track: bool = False) -> None:
        if self._render_busy:
            return
        self._refresh_project()
        self._remember_state()
        clip = AudioEditClip(source_path=path, source_start=0, source_end=waveform.duration)
        if self._mode == AudioEditMode.SEQUENCE:
            timeline_start = self._clips[-1].timeline_end if self._clips else 0.0
            self._clips = list(sequence_clips((*self._clips, replace(clip, timeline_start=timeline_start))))
        elif as_new_track or not self._selected_track_id:
            clip = replace(clip, timeline_start=self.timeline.playhead_position)
            track = AudioEditTrack(id=uuid4().hex, name=path.stem, clips=(clip,))
            self._tracks.append(track)
            self._selected_track_id = track.id
        else:
            track_index = next(
                (index for index, track in enumerate(self._tracks) if track.id == self._selected_track_id),
                None,
            )
            if track_index is None:
                return
            track = self._tracks[track_index]
            clip = replace(clip, timeline_start=self.timeline.playhead_position)
            self._tracks[track_index] = replace(track, clips=(*track.clips, clip))
        self.timeline.select_single_clip(clip.id)
        self._refresh_project()

    def _selected_clip_location(self) -> tuple[int, int] | None:
        for track_index, track in enumerate(self._project.tracks):
            for clip_index, clip in enumerate(track.clips):
                if clip.id == self.timeline.selected_clip_id:
                    return track_index, clip_index
        return None

    def _read_range(self) -> tuple[float, float]:
        return _parse_time_value(self._range_start_var.get()), _parse_time_value(self._range_end_var.get())

    def _apply_clip_edit(self, operation: Callable[[AudioEditClip], object]) -> None:
        location = self._selected_clip_location()
        if location is None:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        track_index, clip_index = location
        track = self._project.tracks[track_index]
        clip = track.clips[clip_index]
        try:
            result = operation(clip)
        except AudioEditError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        except ValueError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        replacements = list(result) if isinstance(result, tuple) else [result]
        if not replacements:
            self._status_var.set(self.translate("audio_editor.edit_error", error="No audio remains"))
            return
        clips = list(track.clips[:clip_index] + tuple(replacements) + track.clips[clip_index + 1 :])
        try:
            if self._mode == AudioEditMode.SEQUENCE:
                updated_clips = sequence_clips(clips)
            else:
                updated_track = replace(track, clips=tuple(clips))
                validate_track_crossfades(updated_track)
        except AudioEditError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        self._remember_state()
        if self._mode == AudioEditMode.SEQUENCE:
            self._clips = list(updated_clips)
        else:
            self._tracks[track_index] = updated_track
        self.timeline.select_single_clip(replacements[0].id)
        self._invalidate_preview()
        self._refresh_project()
        self._selection_changed(self.timeline.selected_clip_id)

    def _trim_clip_on_timeline(self, clip_id: str, edge: str, position: float) -> None:
        if self._render_busy or edge not in {"left", "right"}:
            return
        clip = next((clip for track in self._project.tracks for clip in track.clips if clip.id == clip_id), None)
        if clip is None:
            return
        boundary = clip.timeline_start if edge == "left" else clip.timeline_end
        if abs(position - boundary) < 1e-9:
            return
        self.timeline.select_single_clip(clip_id)

        waveform = self._waveforms.get(clip.source_path)
        source_duration = waveform.duration if waveform is not None else None

        def operation(current):
            offset = position - current.timeline_start
            if edge == "left":
                result = trim_clip(
                    current, current.source_start + offset, current.source_end, source_duration=source_duration
                )
                if self._mode == AudioEditMode.MULTITRACK:
                    result = replace(result, timeline_start=position)
                return result
            return trim_clip(
                current, current.source_start, current.source_start + offset, source_duration=source_duration
            )

        self._apply_clip_edit(operation)

    def _trim_selected_clip(self) -> None:
        if self._render_busy:
            return
        try:
            source_start, source_end = self._read_range()
        except ValueError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        if len(self.timeline.selected_clip_ids) > 1:
            self._apply_selected_clip_edits(
                lambda clip: trim_clip(clip, clip.source_start + source_start, clip.source_start + source_end)
            )
            return
        location = self._selected_clip_location()
        if location is None:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        track_index, clip_index = location
        clip = self._project.tracks[track_index].clips[clip_index]
        # The inspector displays milliseconds. Preserve the exact source value
        # when that field is unchanged, rather than trimming to its rounded text.
        if source_start == float(f"{clip.source_start:.3f}"):
            source_start = clip.source_start
        if source_end == float(f"{clip.source_end:.3f}"):
            source_end = clip.source_end
        if (source_start, source_end) == (clip.source_start, clip.source_end):
            return
        waveform = self._waveforms.get(clip.source_path)
        self._apply_clip_edit(
            lambda current: trim_clip(
                current,
                source_start,
                source_end,
                source_duration=waveform.duration if waveform is not None else None,
            )
        )

    def _remove_selected_range(self) -> None:
        try:
            source_start, source_end = self._read_range()
        except ValueError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        if len(self.timeline.selected_clip_ids) > 1:
            self._apply_selected_clip_edits(
                lambda clip: remove_clip_interval(
                    clip,
                    clip.source_start + source_start,
                    clip.source_start + source_end,
                )
            )
            return
        self._apply_clip_edit(lambda clip: remove_clip_interval(clip, source_start, source_end))

    def _split_at_cursor(self) -> None:
        location = self._selected_clip_location()
        if location is None:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        if len(self.timeline.selected_clip_ids) > 1:
            primary_clip = self._project.tracks[location[0]].clips[location[1]]
            if self._mode == AudioEditMode.SEQUENCE:
                split_offset = self.timeline.playhead_position - primary_clip.timeline_start

                def operation(clip: AudioEditClip) -> tuple[AudioEditClip, AudioEditClip]:
                    return split_clip(clip, clip.source_start + split_offset)

            else:

                def operation(clip: AudioEditClip) -> tuple[AudioEditClip, AudioEditClip]:
                    return split_clip(
                        clip,
                        clip.source_start + self.timeline.playhead_position - clip.timeline_start,
                    )

            self._apply_selected_clip_edits(operation)
            return
        track_index, clip_index = location
        clip = self._project.tracks[track_index].clips[clip_index]
        source_position = clip.source_start + self.timeline.playhead_position - clip.timeline_start
        self._apply_clip_edit(lambda _clip: split_clip(clip, source_position))

    def _remove_selected_clip(self) -> None:
        if len(self.timeline.selected_clip_ids) > 1:
            self._remove_clips_by_id(self.timeline.selected_clip_ids)
            return
        location = self._selected_clip_location()
        if location is None:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        self._remove_clip_at_location(*location)

    def _remove_clip_by_id(self, clip_id: str) -> None:
        if clip_id in self.timeline.selected_clip_ids and len(self.timeline.selected_clip_ids) > 1:
            self._remove_clips_by_id(self.timeline.selected_clip_ids)
            return
        location = next(
            (
                (track_index, clip_index)
                for track_index, track in enumerate(self._project.tracks)
                for clip_index, clip in enumerate(track.clips)
                if clip.id == clip_id
            ),
            None,
        )
        if location is None:
            return
        self._remove_clip_at_location(*location)

    def _remove_clip_at_location(self, track_index: int, clip_index: int) -> None:
        clip = self._project.tracks[track_index].clips[clip_index]
        self._remove_clips_by_id([clip.id])

    def _remove_clips_by_id(self, clip_ids: Iterable[str]) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        selected_ids = set(clip_ids)
        if not selected_ids:
            return
        all_clips = [clip for track in self._project.tracks for clip in track.clips]
        selected_ids.intersection_update(clip.id for clip in all_clips)
        if not selected_ids:
            return
        self._remember_state()
        if self._mode == AudioEditMode.SEQUENCE:
            remaining = clear_crossfades_with_changed_neighbors(
                self._clips,
                (clip for clip in self._clips if clip.id not in selected_ids),
            )
            self._clips = list(sequence_clips(remaining)) if remaining else []
        else:
            updated_tracks = []
            for track in self._tracks:
                remaining = clear_crossfades_with_changed_neighbors(
                    track.clips,
                    (clip for clip in track.clips if clip.id not in selected_ids),
                )
                updated_tracks.append(replace(track, clips=remaining))
            self._tracks = updated_tracks
        remaining_clips = [
            clip for track in self._project.tracks for clip in track.clips if clip.id not in selected_ids
        ]
        self.timeline.select_single_clip(remaining_clips[0].id if remaining_clips else None)
        self._invalidate_preview()
        self._refresh_project()
        self._selection_changed(self.timeline.selected_clip_id)

    def _selected_clip_entries(self) -> list[tuple[int, int, AudioEditClip]]:
        selected_ids = set(self.timeline.selected_clip_ids)
        return [
            (track_index, clip_index, clip)
            for track_index, track in enumerate(self._project.tracks)
            for clip_index, clip in enumerate(track.clips)
            if clip.id in selected_ids
        ]

    def _copy_selected_clips(self) -> None:
        selected = self._selected_clip_entries()
        if not selected:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        primary_id = self.timeline.selected_clip_id
        primary = next((entry for entry in selected if entry[2].id == primary_id), selected[0])
        first_position = min(entry[2].timeline_start for entry in selected)
        selected_ids = {entry[2].id for entry in selected}
        clipboard_clips: dict[str, AudioEditClip] = {}
        for entry in selected:
            track_index, clip = entry[0], entry[2]
            track_clips = sorted(
                self._project.tracks[track_index].clips,
                key=lambda item: (item.timeline_start, item.id),
            )
            clip_index = next(index for index, item in enumerate(track_clips) if item.id == clip.id)
            if clip.crossfade_in and (clip_index == 0 or track_clips[clip_index - 1].id not in selected_ids):
                clip = replace(clip, crossfade_in=0.0)
            clipboard_clips[clip.id] = clip
        self._clipboard = tuple(
            _ClipboardEntry(
                clip=clipboard_clips[entry[2].id],
                track_offset=entry[0] - primary[0],
                time_offset=entry[2].timeline_start - first_position,
            )
            for entry in sorted(selected, key=lambda item: (item[2].timeline_start, item[0], item[1]))
        )
        self._status_var.set(self.translate("audio_editor.copied_clips", count=len(selected)))

    def _cut_selected_clips(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        if not self._selected_clip_entries():
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        self._copy_selected_clips()
        if self._clipboard:
            self._remove_clips_by_id(entry.clip.id for entry in self._clipboard)

    def _paste_clips(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        if not self._clipboard:
            self._status_var.set(self.translate("audio_editor.clipboard_empty"))
            return
        if self._mode == AudioEditMode.SEQUENCE:
            position = self.timeline.snap_position(
                self.timeline.playhead_position,
                include_playhead=False,
            )
            insertion_index = sum(clip.timeline_end <= position for clip in self._clips)
            pasted = [self._copy_clip_at(entry.clip, 0) for entry in self._clipboard]
            updated = [*self._clips[:insertion_index], *pasted, *self._clips[insertion_index:]]
            updated = list(clear_crossfades_with_changed_neighbors(self._clips, updated, preserve_order=True))
            pasted_crossfades = {
                clip.id: entry.clip.crossfade_in
                for clip, entry in zip(pasted, self._clipboard, strict=True)
                if entry.clip.crossfade_in
            }
            updated = [
                replace(clip, crossfade_in=pasted_crossfades[clip.id]) if clip.id in pasted_crossfades else clip
                for clip in updated
            ]
            try:
                updated_sequence = sequence_clips(updated)
            except AudioEditError as exc:
                self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
                return
            self._remember_state()
            self._clips = list(updated_sequence)
            pasted_ids = [clip.id for clip in pasted]
        else:
            target_track_index = next(
                (index for index, track in enumerate(self._tracks) if track.id == self._selected_track_id),
                0,
            )
            updated_tracks = list(self._tracks)
            if not self._tracks:
                updated_tracks = [AudioEditTrack(uuid4().hex, self.translate("audio_editor.track", number=1))]
                target_track_index = 0
            position = self.timeline.snap_position(
                self.timeline.playhead_position,
                include_playhead=False,
            )
            pasted = [self._copy_clip_at(entry.clip, position + entry.time_offset) for entry in self._clipboard]
            target_track = updated_tracks[target_track_index]
            updated_tracks[target_track_index] = replace(target_track, clips=(*target_track.clips, *pasted))
            try:
                validate_track_crossfades(updated_tracks[target_track_index])
            except AudioEditError as exc:
                self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
                return
            self._remember_state()
            self._tracks = updated_tracks
            self._selected_track_id = updated_tracks[target_track_index].id
            pasted_ids = [clip.id for clip in pasted]
        self._invalidate_preview()
        self._refresh_project()
        self.timeline.set_selection(pasted_ids, primary_id=pasted_ids[0])
        self._selection_changed(self.timeline.selected_clip_id)

    def _duplicate_selected_clips(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        selected = self._selected_clip_entries()
        if not selected:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        self._copy_selected_clips()
        if self._mode == AudioEditMode.SEQUENCE:
            self.timeline.set_playhead_position(max(clip.timeline_end for _, _, clip in selected))
            self._paste_clips()
            return

        primary_id = self.timeline.selected_clip_id
        primary = next((entry for entry in selected if entry[2].id == primary_id), selected[0])
        duplicate_start = max(clip.timeline_end for _, _, clip in selected)
        destination_indices = {entry.track_offset + primary[0] for entry in self._clipboard}
        if any(not 0 <= index < len(self._tracks) for index in destination_indices):
            self._status_var.set(self.translate("audio_editor.invalid_group_track_destination"))
            return
        duplicates = [
            (
                entry.track_offset + primary[0],
                self._copy_clip_at(entry.clip, duplicate_start + entry.time_offset),
            )
            for entry in self._clipboard
        ]
        track_clips = [list(track.clips) for track in self._tracks]
        for track_index, clip in duplicates:
            track_clips[track_index].append(clip)
        updated_tracks = [
            replace(track, clips=tuple(clips)) for track, clips in zip(self._tracks, track_clips, strict=True)
        ]
        try:
            for track in updated_tracks:
                validate_track_crossfades(track)
        except AudioEditError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        self._remember_state()
        self._tracks = updated_tracks
        self._invalidate_preview()
        self._refresh_project()
        duplicated_ids = [clip.id for _, clip in duplicates]
        self.timeline.set_selection(duplicated_ids, primary_id=duplicated_ids[0])
        self._selection_changed(self.timeline.selected_clip_id)

    @staticmethod
    def _copy_clip_at(clip: AudioEditClip, timeline_start: float) -> AudioEditClip:
        return replace(clip, id=uuid4().hex, timeline_start=max(0.0, timeline_start))

    def _apply_selected_clip_edits(self, operation: Callable[[AudioEditClip], object]) -> None:
        selected_ids = set(self.timeline.selected_clip_ids)
        if not selected_ids:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        primary_id = self.timeline.selected_clip_id
        updated_tracks: list[AudioEditTrack] = []
        updated_selection: list[str] = []
        try:
            for track in self._project.tracks:
                updated_clips: list[AudioEditClip] = []
                for clip in track.clips:
                    if clip.id not in selected_ids:
                        updated_clips.append(clip)
                        continue
                    result = operation(clip)
                    replacements = result if isinstance(result, tuple) else (result,)
                    if not replacements:
                        raise AudioEditError("The operation would remove all selected audio")
                    updated_clips.extend(replacements)
                    updated_selection.extend(replacement.id for replacement in replacements)
                updated_tracks.append(replace(track, clips=tuple(updated_clips)))
        except (AudioEditError, ValueError) as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        if not updated_selection:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        updated_sequence: tuple[AudioEditClip, ...] = ()
        if self._mode == AudioEditMode.SEQUENCE:
            try:
                updated_sequence = sequence_clips(updated_tracks[0].clips)
            except AudioEditError as exc:
                self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
                return
        else:
            try:
                for track in updated_tracks:
                    validate_track_crossfades(track)
            except AudioEditError as exc:
                self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
                return
        self._remember_state()
        if self._mode == AudioEditMode.SEQUENCE:
            self._clips = list(updated_sequence)
        else:
            self._tracks = updated_tracks
        selected_primary = next(
            (clip_id for clip_id in updated_selection if clip_id == primary_id),
            updated_selection[0],
        )
        self._invalidate_preview()
        self._refresh_project()
        self.timeline.set_selection(updated_selection, primary_id=selected_primary)
        self.timeline.redraw()
        self._selection_changed(self.timeline.selected_clip_id)

    def _move_selected_clip(self, offset: int) -> None:
        if self._mode != AudioEditMode.SEQUENCE:
            self._status_var.set(self.translate("audio_editor.move_with_cursor_hint"))
            return
        location = self._selected_clip_location()
        if location is None:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        _track_index, index = location
        try:
            moved_clips = move_sequence_clip(self._clips, self._clips[index].id, index + offset)
        except AudioEditError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        if moved_clips == tuple(self._clips):
            return
        self._remember_state()
        self._clips = list(moved_clips)
        self._invalidate_preview()
        self._refresh_project()
        self._selection_changed(self.timeline.selected_clip_id)

    def _move_selected_clip_to_cursor(self) -> None:
        selected_ids = set(self.timeline.selected_clip_ids)
        if not selected_ids:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        if self._mode == AudioEditMode.SEQUENCE:
            selected = [clip for clip in self._clips if clip.id in selected_ids]
            if len(selected) == 1:
                self._status_var.set(self.translate("audio_editor.move_with_arrows_hint"))
                return
            remaining = [clip for clip in self._clips if clip.id not in selected_ids]
            insertion_position = self.timeline.snap_position(
                self.timeline.playhead_position,
                exclude_clip_ids=selected_ids,
            )
            insertion_index = sum(clip.timeline_end <= insertion_position for clip in remaining)
            moved = clear_crossfades_with_changed_neighbors(
                self._clips,
                remaining[:insertion_index] + selected + remaining[insertion_index:],
                preserve_order=True,
            )
            if moved == self._clips:
                return
            self._remember_state()
            self._clips = list(sequence_clips(moved))
            self._invalidate_preview()
            self._refresh_project()
            return
        primary_location = self._selected_clip_location()
        if primary_location is None:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        primary_clip = self._project.tracks[primary_location[0]].clips[primary_location[1]]
        selected_clips = [clip for track in self._tracks for clip in track.clips if clip.id in selected_ids]
        target_start = self.timeline.snap_clip_start(
            primary_clip.id,
            self.timeline.playhead_position,
            group_ids=selected_ids,
            include_playhead=False,
        )
        delta = target_start - primary_clip.timeline_start
        delta = max(delta, -min(clip.timeline_start for clip in selected_clips))
        if delta == 0:
            return
        self._remember_state()
        self._tracks = [
            replace(
                track,
                clips=tuple(
                    replace(clip, timeline_start=clip.timeline_start + delta) if clip.id in selected_ids else clip
                    for clip in track.clips
                ),
            )
            for track in self._tracks
        ]
        self._invalidate_preview()
        self._refresh_project()

    def _reorder_sequence_drag(self, clip_id, position):
        selected_ids = set(self.timeline.selected_clip_ids) if clip_id in self.timeline.selected_clip_ids else {clip_id}
        selected = [clip for clip in self._clips if clip.id in selected_ids]
        if not selected:
            return
        remaining = [clip for clip in self._clips if clip.id not in selected_ids]
        index = sequence_drop_index(self._clips, selected_ids, position)
        reordered = remaining[:index] + selected + remaining[index:]
        if reordered == self._clips:
            return
        reordered = clear_crossfades_with_changed_neighbors(self._clips, reordered, preserve_order=True)
        self._remember_state()
        self._clips = list(sequence_clips(reordered))
        self._invalidate_preview()
        self._refresh_project()
        self.timeline.set_selection(list(selected_ids), primary_id=clip_id)
        self._selection_changed(clip_id)

    def _drop_source_paths(self, paths, track_index, position):
        if self._render_busy or not paths or any(path not in self._waveforms for path in paths):
            return
        clips = [AudioEditClip(path, 0, self._waveforms[path].duration) for path in paths]
        if self._mode == AudioEditMode.SEQUENCE:
            if track_index != 0:
                return
            index = sequence_drop_index(self._clips, set(), position)
            updated = self._clips[:index] + clips + self._clips[index:]
            updated = clear_crossfades_with_changed_neighbors(self._clips, updated, preserve_order=True)
            updated = list(sequence_clips(updated))
        else:
            if not 0 <= track_index <= len(self._tracks):
                return
            start = max(0, position)
            positioned = []
            for clip in clips:
                positioned.append(replace(clip, timeline_start=start))
                start += clip.duration
            tracks = list(self._tracks)
            if track_index == len(tracks):
                tracks.append(AudioEditTrack(uuid4().hex, paths[0].stem))
            tracks[track_index] = replace(tracks[track_index], clips=tracks[track_index].clips + tuple(positioned))
            try:
                validate_track_crossfades(tracks[track_index])
            except AudioEditError as exc:
                self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
                return
        self._remember_state()
        if self._mode == AudioEditMode.SEQUENCE:
            self._clips = updated
        else:
            self._tracks = tracks
            self._selected_track_id = tracks[track_index].id
        self._invalidate_preview()
        self._refresh_project()
        self.timeline.set_selection([clip.id for clip in clips], primary_id=clips[0].id)
        self._selection_changed(clips[0].id)

    def _move_clip_on_timeline(self, clip_id: str, target_track_index: int, position: float) -> None:
        if self._render_busy:
            return
        if self._mode == AudioEditMode.SEQUENCE:
            self._reorder_sequence_drag(clip_id, position)
            return
        location = next(
            (
                (track_index, clip_index)
                for track_index, track in enumerate(self._tracks)
                for clip_index, clip in enumerate(track.clips)
                if clip.id == clip_id
            ),
            None,
        )
        if location is None or not 0 <= target_track_index < len(self._tracks):
            return
        primary_track_index, primary_clip_index = location
        primary_clip = self._tracks[primary_track_index].clips[primary_clip_index]
        selected_ids = set(self.timeline.selected_clip_ids)
        if clip_id not in selected_ids:
            selected_ids = {clip_id}
        selected = [
            (track_index, clip)
            for track_index, track in enumerate(self._tracks)
            for clip in track.clips
            if clip.id in selected_ids
        ]
        for track in self._tracks:
            ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
            for index, clip in enumerate(ordered[1:], start=1):
                if clip.crossfade_in and bool({ordered[index - 1].id, clip.id} & selected_ids):
                    if not {ordered[index - 1].id, clip.id} <= selected_ids:
                        self._status_var.set(self.translate("audio_editor.crossfade_move_group"))
                        return
        track_delta = target_track_index - primary_track_index
        if any(not 0 <= track_index + track_delta < len(self._tracks) for track_index, _ in selected):
            self._status_var.set(self.translate("audio_editor.invalid_group_track_destination"))
            return
        target_start = self.timeline.snap_clip_start(
            clip_id,
            position,
            group_ids=selected_ids,
            include_playhead=False,
        )
        time_delta = target_start - primary_clip.timeline_start
        time_delta = max(time_delta, -min(clip.timeline_start for _, clip in selected))
        if track_delta == 0 and time_delta == 0:
            return
        if track_delta == 0:
            selected_ids_to_clips = {
                clip.id: replace(clip, timeline_start=clip.timeline_start + time_delta) for _, clip in selected
            }
            updated_tracks = [
                replace(
                    track,
                    clips=tuple(selected_ids_to_clips.get(clip.id, clip) for clip in track.clips),
                )
                for track in self._tracks
            ]
        else:
            updated_tracks = [[clip for clip in track.clips if clip.id not in selected_ids] for track in self._tracks]
            for source_track_index, clip in selected:
                updated_tracks[source_track_index + track_delta].append(
                    replace(clip, timeline_start=clip.timeline_start + time_delta)
                )
            updated_tracks = [
                replace(track, clips=tuple(clips)) for track, clips in zip(self._tracks, updated_tracks, strict=True)
            ]
        try:
            for track in updated_tracks:
                validate_track_crossfades(track)
        except AudioEditError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        self._remember_state()
        self._tracks = updated_tracks
        self._selected_track_id = self._tracks[target_track_index].id
        self._invalidate_preview()
        self._refresh_project()
        self.timeline.set_selection(list(selected_ids), primary_id=clip_id)
        self._selection_changed(clip_id)

    def _fade_clip_on_timeline(self, clip_id: str, side: str, duration: float) -> None:
        if self._render_busy or side not in {"in", "out"}:
            return
        clip = next((clip for track in self._project.tracks for clip in track.clips if clip.id == clip_id), None)
        if clip is None or abs(getattr(clip, f"fade_{side}") - duration) < 1e-9:
            return
        self.timeline.select_single_clip(clip_id)
        self._apply_clip_edit(lambda current: replace(current, **{f"fade_{side}": duration}))

    def _apply_fades(self) -> None:
        try:
            fade_in = _parse_time_value(self._fade_in_var.get()) if self._fade_in_var.get().strip() else None
            fade_out = _parse_time_value(self._fade_out_var.get()) if self._fade_out_var.get().strip() else None
        except ValueError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return

        selected_ids = set(self.timeline.selected_clip_ids)
        for track in self._project.tracks:
            ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
            for index, clip in enumerate(ordered):
                if clip.id not in selected_ids:
                    continue
                if (clip.crossfade_in and fade_in) or (
                    index + 1 < len(ordered) and ordered[index + 1].crossfade_in and fade_out
                ):
                    self._status_var.set(self.translate("audio_editor.crossfade_fade_conflict"))
                    return

        def operation(clip: AudioEditClip) -> AudioEditClip:
            return replace(
                clip,
                fade_in=clip.fade_in if fade_in is None else fade_in,
                fade_out=clip.fade_out if fade_out is None else fade_out,
            )

        if len(self.timeline.selected_clip_ids) > 1:
            self._apply_selected_clip_edits(operation)
        else:
            self._apply_clip_edit(operation)

    def _apply_clip_mix(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        selected = self._selected_clip_entries()
        if not selected:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        try:
            updates = {}
            if self._clip_gain_var.get().strip():
                updates["gain_db"] = float(self._clip_gain_var.get())
            if self._clip_pan_var.get().strip():
                updates["pan"] = float(self._clip_pan_var.get()) / 100.0
            updated = [replace(clip, **updates) for _, _, clip in selected]
        except (TypeError, ValueError) as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        if all(
            (clip.gain_db, clip.pan) == (new_clip.gain_db, new_clip.pan)
            for (_, _, clip), new_clip in zip(selected, updated, strict=True)
        ):
            return
        self._apply_selected_clip_edits(lambda clip: replace(clip, **updates))
        self._status_var.set(
            self.translate(
                "audio_editor.clip_mix_applied",
                count=len(selected),
                gain=self._clip_gain_var.get() or "—",
                pan=f"{self._clip_pan_var.get()}",
            )
        )

    def _edit_clip_processing(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        selected = self._selected_clip_entries()
        if not selected:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        result = edit_audio_processing(self, selected[0][2].processing, self.translate)
        if result is None:
            return
        selected_ids = {clip.id for _, _, clip in selected}
        if all(clip.processing == result for _, _, clip in selected):
            return
        self._apply_selected_clip_edits(
            lambda clip: replace(clip, processing=result) if clip.id in selected_ids else clip
        )
        self._status_var.set(
            self.translate(
                "audio_editor.processing_applied",
                count=len(selected),
                bypass=self.translate("audio_editor.processing_bypass_active")
                if result.bypassed
                else self.translate("audio_editor.processing_bypass_inactive"),
            )
        )

    def _edit_clip_effects(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        selected = self._selected_clip_entries()
        if not selected:
            self._status_var.set(self.translate("audio_editor.select_clip_first"))
            return
        result = edit_audio_effect_chain(self, selected[0][2].effects, self.translate)
        if result is None:
            return
        selected_ids = {clip.id for _, _, clip in selected}
        if all(clip.effects == result for _, _, clip in selected):
            return
        self._apply_selected_clip_edits(lambda clip: replace(clip, effects=result) if clip.id in selected_ids else clip)
        self._status_var.set(self.translate("audio_editor.fx_applied", count=len(selected), effects=len(result)))

    def _apply_crossfade(
        self,
        first_clip_id: str | None = None,
        second_clip_id: str | None = None,
        duration: float | None = None,
    ) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        if first_clip_id is None or second_clip_id is None:
            selected = self._selected_clip_entries()
            if len(selected) != 2 or selected[0][0] != selected[1][0]:
                self._status_var.set(self.translate("audio_editor.select_adjacent_clips"))
                return
            selected.sort(key=lambda entry: (entry[2].timeline_start, entry[2].id))
            first_clip_id, second_clip_id = selected[0][2].id, selected[1][2].id
        if duration is None:
            try:
                duration = _parse_time_value(self._crossfade_duration_var.get())
            except ValueError as exc:
                self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
                return
        track_index = next(
            (
                index
                for index, track in enumerate(self._project.tracks)
                if any(clip.id == first_clip_id for clip in track.clips)
                and any(clip.id == second_clip_id for clip in track.clips)
            ),
            None,
        )
        if track_index is None:
            self._status_var.set(self.translate("audio_editor.select_adjacent_clips"))
            return
        try:
            updated_track = apply_crossfade(
                self._project.tracks[track_index],
                first_clip_id,
                second_clip_id,
                duration,
            )
        except AudioEditError as exc:
            self._status_var.set(self.translate("audio_editor.edit_error", error=exc))
            return
        if updated_track == self._project.tracks[track_index]:
            return
        self._remember_state()
        if self._mode == AudioEditMode.SEQUENCE:
            self._clips = list(updated_track.clips)
        else:
            self._tracks[track_index] = updated_track
        self._crossfade_duration_var.set(f"{duration:.3f}")
        self._invalidate_preview()
        self._refresh_project()
        self.timeline.set_selection([first_clip_id, second_clip_id], primary_id=second_clip_id)
        self._selection_changed(second_clip_id)
        self._status_var.set(self.translate("audio_editor.crossfade_applied", duration=f"{duration:.3f}"))

    def _cursor_moved(self, position: float) -> None:
        centiseconds = round(position * 100)
        minutes, remainder = divmod(centiseconds, 6000)
        seconds, fraction = divmod(remainder, 100)
        self._status_var.set(
            self.translate("audio_editor.cursor_position", position=f"{minutes:02d}:{seconds:02d}.{fraction:02d}")
        )

    def _refresh_project(self) -> None:
        if self._mode == AudioEditMode.SEQUENCE:
            tracks = (
                AudioEditTrack(
                    id="sequence",
                    name=self.translate("audio_editor.sequence"),
                    clips=tuple(self._clips),
                    volume=self._sequence_track_volume,
                ),
            )
        else:
            tracks = tuple(self._tracks)
        self._project = AudioEditProject(
            mode=self._mode,
            tracks=tracks,
            markers=tuple(sorted(self._markers, key=lambda marker: marker.position)),
        )
        self.timeline.set_project(self._project, self._waveforms)
        self._duration_var.set(
            self.translate(
                "audio_editor.sequence_duration",
                duration=self._format_duration(self._project.duration),
            )
        )
        self._selection_changed(self.timeline.selected_clip_id)
        self._update_project_title()

    def _add_marker(self, position: float) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        self._remember_state()
        marker = AudioEditMarker(position=position, label=f"M{len(self._markers) + 1}")
        self._markers.append(marker)
        self._invalidate_preview()
        self._refresh_project()
        self._status_var.set(
            self.translate(
                "audio_editor.marker_added",
                marker=marker.label,
                position=self._format_duration(position),
            )
        )

    def _remove_marker(self, marker_id: str) -> None:
        if self._render_busy:
            return
        marker = next((item for item in self._markers if item.id == marker_id), None)
        if marker is None:
            return
        self._remember_state()
        self._markers = [item for item in self._markers if item.id != marker_id]
        self._invalidate_preview()
        self._refresh_project()
        self._status_var.set(self.translate("audio_editor.marker_removed", marker=marker.label))

    def _selection_changed(self, clip_id: str | None) -> None:
        if clip_id is None:
            self._refresh_track_controls()
            self._sync_property_selection()
            return
        location = self._selected_clip_location()
        if location is None:
            return
        track_index, clip_index = location
        track = self._project.tracks[track_index]
        clip = track.clips[clip_index]
        self._selected_track_id = track.id if self._mode == AudioEditMode.MULTITRACK else None
        selected_clips = [
            item
            for project_track in self._project.tracks
            for item in project_track.clips
            if item.id in self.timeline.selected_clip_ids
        ]
        if len(selected_clips) > 1:
            self._range_start_var.set("0")
            self._range_end_var.set(f"{min(item.duration for item in selected_clips):.3f}")
            selected_clips.sort(key=lambda item: (item.timeline_start, item.id))
            second_clip = selected_clips[1] if len(selected_clips) == 2 else None
            self._crossfade_duration_var.set(f"{second_clip.crossfade_in if second_clip else 0.0:.3f}")
        else:
            self._range_start_var.set(f"{clip.source_start:.3f}")
            self._range_end_var.set(f"{clip.source_end:.3f}")
            self._crossfade_duration_var.set(f"{clip.crossfade_in:.3f}")
        self._fade_in_var.set(f"{clip.fade_in:.3f}")
        self._fade_out_var.set(f"{clip.fade_out:.3f}")
        self._clip_gain_var.set(f"{clip.gain_db:g}")
        self._clip_pan_var.set(f"{clip.pan * 100:g}")
        if len(selected_clips) > 1:
            self._status_var.set(self.translate("audio_editor.selected_clips", count=len(selected_clips)))
        else:
            self._status_var.set(
                self.translate(
                    "audio_editor.selected_clip",
                    name=clip.source_path.name,
                    duration=self._format_duration(clip.duration),
                )
            )
        self._refresh_track_controls()
        self._sync_property_selection()

    def _refresh_track_controls(self) -> None:
        self._updating_track_controls = True
        track = next((item for item in self._project.tracks if item.id == self._selected_track_id), None)
        if track is None and self._mode == AudioEditMode.SEQUENCE and self._project.tracks:
            track = self._project.tracks[0]
        self._track_volume_var.set(track.volume * 100 if track else 100)
        self._updating_track_controls = False

    def _set_selected_track_volume(self, _event=None) -> None:
        if self._updating_track_controls or self._render_busy:
            return
        track_index = next(
            (index for index, item in enumerate(self._tracks) if item.id == self._selected_track_id),
            None,
        )
        if self._mode == AudioEditMode.SEQUENCE and self._project.tracks:
            current = self._project.tracks[0]
            try:
                volume = max(0.0, min(1.0, float(self._track_volume_var.get()) / 100))
            except (TypeError, ValueError):
                return
            if volume == current.volume:
                return
            self._remember_state()
            self._sequence_track_volume = volume
        elif track_index is not None:
            track = self._tracks[track_index]
            try:
                volume = max(0.0, min(1.0, float(self._track_volume_var.get()) / 100))
            except (TypeError, ValueError):
                return
            if volume == track.volume:
                return
            self._remember_state()
            self._tracks[track_index] = replace(track, volume=volume)
        else:
            return
        self._invalidate_preview()
        self._refresh_project()

    def _toggle_selected_track_mute(self) -> None:
        self._update_selected_track(muted=None)

    def _toggle_selected_track_solo(self) -> None:
        self._update_selected_track(solo=None)

    def _update_selected_track(self, *, muted: bool | None = None, solo: bool | None = None) -> None:
        track_index = next(
            (index for index, track in enumerate(self._tracks) if track.id == self._selected_track_id),
            None,
        )
        if self._mode == AudioEditMode.SEQUENCE:
            self._status_var.set(self.translate("audio_editor.track_controls_multitrack_only"))
            return
        if track_index is None:
            self._status_var.set(self.translate("audio_editor.select_track_first"))
            return
        track = self._tracks[track_index]
        changes: dict[str, bool] = {}
        if muted is None:
            changes["muted"] = not track.muted
        if solo is None:
            changes["solo"] = not track.solo
        self._remember_state()
        self._tracks[track_index] = replace(track, **changes)
        self._invalidate_preview()
        self._refresh_project()

    def _remember_state(self, *, source_relink=None) -> None:
        if self._render_busy:
            raise AudioEditError("Wait for the current render operation to finish")
        self._undo_stack.append(
            SourceHistoryState(self._project, tuple(self._paths), *source_relink, source_relink[1] in self._paths)
            if source_relink
            else self._project
        )
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self) -> None:
        if not self._undo_stack:
            self._status_var.set(self.translate("audio_editor.nothing_to_undo"))
            return
        state = self._undo_stack.pop()
        self._redo_stack.append(
            state.inverse(self._project, self._paths) if isinstance(state, SourceHistoryState) else self._project
        )
        self._restore_history_state(state)

    def _redo(self) -> None:
        if not self._redo_stack:
            self._status_var.set(self.translate("audio_editor.nothing_to_redo"))
            return
        state = self._redo_stack.pop()
        self._undo_stack.append(
            state.inverse(self._project, self._paths) if isinstance(state, SourceHistoryState) else self._project
        )
        self._restore_history_state(state)

    def _restore_project_state(self, project: AudioEditProject) -> None:
        self._mode = project.mode
        self._markers = list(project.markers)
        if self._mode == AudioEditMode.SEQUENCE:
            self._clips = list(project.tracks[0].clips) if project.tracks else []
            self._tracks = []
            self._selected_track_id = None
            self._sequence_track_volume = project.tracks[0].volume if project.tracks else 1.0
        else:
            self._tracks = list(project.tracks)
            self._clips = []
            self._selected_track_id = self._tracks[0].id if self._tracks else None
        self._mode_var.set(
            self.translate(
                "audio_editor.mode_multitrack"
                if self._mode == AudioEditMode.MULTITRACK
                else "audio_editor.mode_sequence"
            )
        )
        self._invalidate_preview()
        self._refresh_project()

    def _switch_mode(self, next_mode: AudioEditMode) -> None:
        if next_mode == self._mode:
            return
        self._remember_state()
        if next_mode == AudioEditMode.MULTITRACK:
            self._tracks = (
                [
                    AudioEditTrack(
                        id=uuid4().hex,
                        name=self.translate("audio_editor.track", number=1),
                        clips=tuple(self._clips),
                        volume=self._sequence_track_volume,
                    )
                ]
                if self._clips
                else []
            )
            self._selected_track_id = self._tracks[0].id if self._tracks else None
        else:
            clips = sorted(
                (clip for track in self._tracks for clip in track.clips),
                key=lambda clip: (clip.timeline_start, clip.id),
            )
            self._clips = list(sequence_clips(clips)) if clips else []
            if self._tracks:
                self._sequence_track_volume = self._tracks[0].volume
            self._tracks = []
            self._selected_track_id = None
        self._mode = next_mode
        self._mode_var.set(
            self.translate(
                "audio_editor.mode_multitrack"
                if next_mode == AudioEditMode.MULTITRACK
                else "audio_editor.mode_sequence"
            )
        )
        self._invalidate_preview()
        self._refresh_project()

    def _on_mode_selected(self, _event=None) -> None:
        next_mode = (
            AudioEditMode.MULTITRACK
            if self._mode_var.get() == self.translate("audio_editor.mode_multitrack")
            else AudioEditMode.SEQUENCE
        )
        self._switch_mode(next_mode)

    def _invalidate_preview(self) -> None:
        self._audition_region = None
        self._preview_is_audition = False
        if self._preview_active:
            self._stop_active_preview(restore=True)
        if self._preview_path is not None:
            self._delete_preview_file(self._preview_path)
            self._preview_path = None
            self._preview_project_snapshot = None
            self._preview_region_snapshot = None

    def _collect_render_controls(self, parent: tk.Misc) -> None:
        for widget in parent.winfo_children():
            if isinstance(
                widget,
                (ttk.Button, ttk.Combobox, ttk.Entry, ttk.Spinbox, ttk.Scale, tk.Listbox, tk.Canvas),
            ):
                if widget is not self._cancel_button:
                    self._render_control_states[widget] = str(widget.cget("state"))
            elif isinstance(widget, ttk.Checkbutton):
                self._render_control_states[widget] = str(widget.cget("state"))
            self._collect_render_controls(widget)

    def _refresh_zoom_label(self) -> None:
        self._zoom_label.configure(text=f"{self.timeline.pixels_per_second / 60:.0%}")

    def _toggle_snap(self) -> None:
        self.timeline.snap_enabled = self._snap_var.get()

    def _zoom(self, factor: float) -> None:
        self.timeline.zoom(factor)
        self._refresh_zoom_label()

    def _toggle_preview(self) -> None:
        if self._preview_active:
            if self._preview_paused:
                self._resume()
            else:
                self._pause()
            return
        if self._audition_region is not None:
            self._invalidate_preview()
        self._start_preview()

    def _start_preview(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        if not any(track.clips for track in self._project.tracks):
            self._status_var.set(self.translate("audio_editor.nothing_to_preview"))
            return
        if self._play_preview is None:
            self._status_var.set(self.translate("audio_editor.preview_unavailable"))
            return
        if (
            self._preview_path is not None
            and self._preview_path.is_file()
            and self._preview_region_snapshot == self._requested_preview_region()
            and self._preview_project_snapshot == self._project
        ):
            try:
                self._play_preview_file(self._preview_path)
            except Exception as exc:
                self._restore_previous_playback()
                self.logger.exception("Could not start audio preview")
                self._status_var.set(self.translate("audio_editor.preview_failed", error=exc))
                return
            self._preview_active = True
            self._preview_paused = False
            self._update_transport_controls()
            self._status_var.set(self.translate("audio_editor.preview_playing"))
            return
        self._start_render("preview")

    def _pause(self) -> None:
        if not self._preview_active or self._pause_preview is None:
            self._status_var.set(self.translate("audio_editor.preview_not_playing"))
            return
        try:
            self._pause_preview()
        except Exception as exc:
            self.logger.exception("Could not pause audio preview")
            self._status_var.set(self.translate("audio_editor.preview_failed", error=exc))
            return
        self._preview_paused = True
        self._update_transport_controls()
        self._status_var.set(self.translate("audio_editor.preview_paused"))

    def _resume(self) -> None:
        if not self._preview_active or self._resume_preview is None:
            self._status_var.set(self.translate("audio_editor.preview_not_playing"))
            return
        try:
            self._resume_preview()
        except Exception as exc:
            self.logger.exception("Could not resume audio preview")
            self._status_var.set(self.translate("audio_editor.preview_failed", error=exc))
            return
        self._preview_paused = False
        self._update_transport_controls()
        self._status_var.set(self.translate("audio_editor.preview_playing"))

    def _stop(self) -> None:
        if not self._preview_active:
            self._status_var.set(self.translate("audio_editor.preview_not_playing"))
            return
        self._stop_active_preview(restore=True)
        self._playback_time_var.set("00:00")
        self._status_var.set(self.translate("audio_editor.preview_stopped"))

    def _stop_active_preview(self, *, restore: bool) -> None:
        try:
            if self._stop_preview is not None:
                self._stop_preview()
        except Exception as exc:
            self.logger.exception("Could not stop audio preview")
            if not self._closing:
                self._status_var.set(self.translate("audio_editor.preview_failed", error=exc))
        finally:
            self._preview_active = False
            self._preview_paused = False
            self._update_transport_controls()
        if restore and self._restore_playback is not None:
            self._restore_previous_playback()

    def _restore_previous_playback(self) -> None:
        if not self._playback_modified:
            return
        if self._restore_playback is not None:
            try:
                self._restore_playback(self._playback_snapshot)
            except Exception as exc:
                self.logger.exception("Could not restore the previous playback state")
                if not self._closing:
                    self._status_var.set(self.translate("audio_editor.playback_restore_failed", error=exc))
        self._playback_modified = False

    def _choose_export(self) -> None:
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        if not any(track.clips for track in self._project.tracks):
            self._status_var.set(self.translate("audio_editor.nothing_to_export"))
            return
        initial_dir = getattr(self, "_initial_export_folder", None)
        if initial_dir is None or not Path(initial_dir).is_dir():
            initial_dir = next(
                (clip.source_path.parent for track in self._project.tracks for clip in track.clips),
                Path.home(),
            )
        default_name = next(
            (clip.source_path.stem for track in self._project.tracks for clip in track.clips),
            self.translate("audio_editor.default_export_name"),
        )
        format = self._export_format_var.get()
        settings = replace(
            self._export_settings,
            format=format,
            sample_rate=self._export_settings.sample_rate
            if self._export_settings.sample_rate in AudioExportSettings.sample_rates(format)
            else 44100,
        )
        result = choose_audio_export(
            self, translate=self.translate, colors=self.colors, folder=initial_dir, name=default_name, settings=settings
        )
        if result is None:
            return
        output_folder, base_name, settings = result
        self._export_settings = settings
        self._export_format_var.set(settings.format)
        self._initial_export_folder = output_folder
        self._start_render(
            "export",
            output_folder=output_folder,
            base_name=base_name,
            extension=settings.format,
            export_settings=settings,
        )

    def _start_render(
        self,
        kind: str,
        *,
        output_folder: Path | None = None,
        base_name: str = "",
        extension: str = ".mp3",
        export_settings: AudioExportSettings | None = None,
    ) -> None:
        if self._render_busy:
            return
        project = self._project
        preview_region = self._requested_preview_region() if kind == "preview" else None
        is_audition = kind == "preview" and self._audition_region is not None
        self._cancel_editor_drag()
        self._render_cancel.clear()
        self._render_busy = True
        self._set_render_controls_busy(True)
        self._cancel_button.configure(state="normal")
        self._status_var.set(self.translate("audio_editor.render_starting"))

        if kind == "preview":
            output_path = self._temp_dir / f"preview-{uuid4().hex}.wav"
        elif output_folder is not None:
            output_path = None
        else:
            self._render_busy = False
            self._set_render_controls_busy(False)
            self._cancel_button.configure(state="disabled")
            self._status_var.set(self.translate("audio_editor.export_failed", error="Export folder is missing"))
            return

        def report_progress(percent: int, phase: str) -> bool:
            self._render_results.put(("progress", (percent, phase)))
            return not self._render_cancel.is_set()

        def render_worker() -> None:
            try:
                if kind == "preview":
                    if output_path is None:
                        raise AudioEditError("Preview output path was not initialized")
                    result_path = render_audio_project(
                        project,
                        output_path,
                        cancel_event=self._render_cancel,
                        progress_callback=report_progress,
                        **({"preview_region": preview_region} if preview_region is not None else {}),
                    )
                else:
                    if output_folder is None:
                        raise AudioEditError("Export folder is missing")
                    result_path = export_audio_project(
                        project,
                        output_folder,
                        base_name,
                        extension,
                        **({"export_settings": export_settings} if export_settings is not None else {}),
                        cancel_event=self._render_cancel,
                        progress_callback=report_progress,
                    )
            except AudioEditCancelled as exc:
                self._render_results.put(("cancelled", str(exc)))
            except Exception as exc:
                self.logger.exception("Audio editor %s render failed", kind)
                self._render_results.put(("error", (kind, exc)))
            else:
                self._render_results.put(("complete", (kind, result_path, project, preview_region, is_audition)))
            finally:
                if self._closing:
                    if kind == "preview" and output_path is not None:
                        self._delete_preview_file(output_path)
                    self._cleanup_temp_directory()

        self._render_thread = threading.Thread(target=render_worker, daemon=True)
        try:
            self._render_thread.start()
        except RuntimeError as exc:
            self._render_busy = False
            self._set_render_controls_busy(False)
            self._cancel_button.configure(state="disabled")
            self.logger.exception("Could not start audio render worker")
            self._status_var.set(self.translate("audio_editor.worker_failed", error=exc))

    def _poll_render_results(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        while True:
            try:
                kind, payload = self._render_results.get_nowait()
            except queue.Empty:
                break
            if kind == "progress" and isinstance(payload, tuple):
                percent, phase = payload
                self._status_var.set(self.translate("audio_editor.render_progress", percent=percent, phase=phase))
            elif kind == "cancelled":
                self._audition_region = None
                self._finish_render()
                self._status_var.set(self.translate("audio_editor.render_cancelled"))
            elif kind == "error" and isinstance(payload, tuple):
                render_kind, error = payload
                self._audition_region = None
                self._finish_render()
                key = "audio_editor.preview_failed" if render_kind == "preview" else "audio_editor.export_failed"
                self._status_var.set(self.translate(key, error=error))
                messagebox.showerror(self.translate("dialog.error"), self.translate(key, error=error), parent=self)
            elif kind == "complete" and isinstance(payload, tuple):
                render_kind, path, project = payload[:3]
                preview_region = payload[3] if len(payload) > 3 else None
                self._finish_render()
                if render_kind == "preview":
                    if self._render_cancel.is_set():
                        self._delete_preview_file(path)
                        self._audition_region = None
                        self._status_var.set(self.translate("audio_editor.render_cancelled"))
                        continue
                    self._preview_path = path
                    self._preview_project_snapshot = project
                    self._preview_region_snapshot = preview_region
                    self._preview_is_audition = bool(payload[4]) if len(payload) > 4 else False
                    try:
                        if self._play_preview is None:
                            raise AudioEditError("Audio preview is unavailable")
                        self._play_preview_file(path)
                    except Exception as exc:
                        self._restore_previous_playback()
                        self.logger.exception("Could not play rendered audio preview")
                        self._status_var.set(self.translate("audio_editor.preview_failed", error=exc))
                        messagebox.showerror(
                            self.translate("dialog.error"),
                            self.translate("audio_editor.preview_failed", error=exc),
                            parent=self,
                        )
                    else:
                        self._preview_active = True
                        self._preview_paused = False
                        self._update_transport_controls()
                        self._status_var.set(self.translate("audio_editor.preview_playing"))
                else:
                    self._status_var.set(self.translate("audio_editor.export_complete", path=path))
                    if self._export_completed is not None:
                        try:
                            self._export_completed(path)
                        except Exception as exc:
                            self.logger.exception("Audio export completed but library refresh failed")
                            self._status_var.set(
                                self.translate("audio_editor.export_refresh_failed", path=path, error=exc)
                            )
                            messagebox.showerror(
                                self.translate("dialog.error"),
                                self.translate("audio_editor.export_refresh_failed", path=path, error=exc),
                                parent=self,
                            )
        self._render_poll_id = self.after(80, self._poll_render_results)

    def _finish_render(self) -> None:
        self._render_busy = False
        self._set_render_controls_busy(False)
        self._cancel_button.configure(state="disabled")

    def _set_render_controls_busy(self, busy: bool) -> None:
        for widget, previous_state in tuple(self._render_control_states.items()):
            if not widget.winfo_exists():
                continue
            widget.configure(state="disabled" if busy else previous_state)
        self._update_transport_controls()
        self._sync_property_selection()
        if busy:
            self._cancel_button.grid()
        else:
            self._cancel_button.grid_remove()

    def _refresh_playback_display(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        if self._preview_active and self._playback_position is not None:
            try:
                if not self._preview_paused and self._preview_is_playing is not None and not self._preview_is_playing():
                    self._stop_active_preview(restore=True)
                    self._status_var.set(self.translate("audio_editor.preview_stopped"))
                    self._playback_time_var.set("00:00")
                    self._playback_poll_id = self.after(150, self._refresh_playback_display)
                    return
                position = max(0.0, float(self._playback_position()))
                if self._preview_region_snapshot is not None:
                    start, end = self._preview_region_snapshot
                    position = (
                        min(end, start + position) if self._preview_is_audition else start + position % (end - start)
                    )
                self._playback_time_var.set(self._format_duration(position))
                self.timeline.set_playhead_position(position)
            except Exception as exc:
                self.logger.exception("Could not read preview playback position")
                self._status_var.set(self.translate("audio_editor.playback_position_failed", error=exc))
        self._playback_poll_id = self.after(150, self._refresh_playback_display)

    def _update_transport_controls(self) -> None:
        if not hasattr(self, "_play_pause_button"):
            return
        paused_or_stopped = not self._preview_active or self._preview_paused
        self._play_pause_button.configure(
            text="▶" if paused_or_stopped else "⏸",
            state="normal" if not self._render_busy else "disabled",
        )
        self._stop_button.configure(
            state="normal" if self._preview_active and not self._render_busy else "disabled",
        )

    def _delete_preview_file(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            self.logger.warning("Could not remove temporary audio preview: %s", path, exc_info=True)

    def _cleanup_temp_directory(self) -> None:
        try:
            shutil.rmtree(self._temp_dir, ignore_errors=False)
        except FileNotFoundError:
            pass
        except OSError:
            self.logger.warning("Could not remove audio editor temporary directory: %s", self._temp_dir, exc_info=True)

    def close(self) -> None:
        if self._panel_layout_id is not None:
            self.after_cancel(self._panel_layout_id)
            self._panel_layout_id = None
        if self._closing:
            return
        if not self._prepare_project_close():
            return
        self._cancel_editor_drag()
        self._closing = True
        self._cancel_event.set()
        self._render_cancel.set()
        if self._preview_active:
            self._stop_active_preview(restore=True)
        else:
            self._restore_previous_playback()
        for poll_id in (self._poll_id, self._render_poll_id, self._playback_poll_id):
            if poll_id is not None:
                try:
                    self.after_cancel(poll_id)
                except tk.TclError:
                    pass
        if self._render_thread is None or not self._render_thread.is_alive():
            self._cleanup_temp_directory()
        self.destroy()

    def _translate(self, key: str) -> str:
        return self.translate(key)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = int(seconds)
        return f"{total // 60:02d}:{total % 60:02d}"


def _parse_time_value(value: str) -> float:
    parts = value.strip().split(":")
    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            minutes, remainder = (float(part) for part in parts)
            if minutes < 0 or not 0 <= remainder < 60:
                raise ValueError
            seconds = minutes * 60 + remainder
        else:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Enter seconds or a time in MM:SS format") from exc
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Time must be a non-negative finite value")
    return seconds
