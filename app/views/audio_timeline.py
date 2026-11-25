from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from ..models.audio_edit_project import AudioEditClip, AudioEditProject
from ..services.audio_waveform_service import AudioWaveform
from .audio_timeline_fades import TimelineFadeMixin
from .audio_timeline_interaction import (
    _LANE_GAP,
    _LANE_HEIGHT,
    _LANE_TOP,
    _LEFT_GUTTER,
    _RULER_HEIGHT,
    TimelineInteractionMixin,
)
from .audio_timeline_region import TimelineRegionMixin

_SNAP_TOLERANCE_PIXELS = 10


def time_tick_interval(pixels_per_second: float) -> float:
    target_seconds = 90 / max(pixels_per_second, 0.001)
    choices = (0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600, 7200)
    return next((choice for choice in choices if choice >= target_seconds), choices[-1])


def resample_peaks(peaks: tuple[float, ...], width: int) -> tuple[float, ...]:
    if width <= 0 or not peaks:
        return ()
    if width == 1:
        return (max(peaks),)
    last_index = len(peaks) - 1
    return tuple(
        max(peaks[round(index * last_index / (width - 1)) : round((index + 1) * last_index / (width - 1)) + 1])
        for index in range(width)
    )


def canvas_x_to_seconds(canvas_x: float, pixels_per_second: float) -> float:
    if pixels_per_second <= 0:
        raise ValueError("Timeline zoom must be positive")
    return max(0.0, (canvas_x - _LEFT_GUTTER) / pixels_per_second)


def canvas_y_to_track_index(canvas_y: float, track_count: int) -> int | None:
    if canvas_y < _LANE_TOP or track_count <= 0:
        return None
    offset = canvas_y - _LANE_TOP
    track_index = int(offset // (_LANE_HEIGHT + _LANE_GAP))
    if track_index >= track_count or offset % (_LANE_HEIGHT + _LANE_GAP) >= _LANE_HEIGHT:
        return None
    return track_index


def snap_to_nearest(position: float, candidates: tuple[float, ...], tolerance: float) -> float:
    nearby = (candidate for candidate in candidates if abs(candidate - position) <= tolerance)
    return min(nearby, key=lambda candidate: (abs(candidate - position), candidate), default=position)


class AudioTimeline(TimelineRegionMixin, TimelineFadeMixin, TimelineInteractionMixin, ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        colors: dict[str, str],
        translate: Callable[..., str],
        on_selection_changed: Callable[[str | None], None] | None = None,
        on_marker_added: Callable[[float], None] | None = None,
        on_marker_removed: Callable[[str], None] | None = None,
        on_cursor_moved: Callable[[float], None] | None = None,
        on_play_from_position: Callable[[float], None] | None = None,
        on_region_changed: Callable[[tuple[float, float] | None], None] | None = None,
        on_fade_changed: Callable[[str, str, float], None] | None = None,
        on_clip_trimmed: Callable[[str, str, float], None] | None = None,
        on_clip_moved: Callable[[str, int, float], None] | None = None,
        on_transition_changed: Callable[[str, str, float], None] | None = None,
        on_remove_clip: Callable[[str], None] | None = None,
        context_actions: dict[str, Callable[[], None]] | None = None,
        context_enabled: Callable[[str], bool] | None = None,
    ):
        super().__init__(parent)
        self.colors = colors
        self.translate = translate
        self.on_selection_changed = on_selection_changed
        self.on_marker_added = on_marker_added
        self.on_marker_removed = on_marker_removed
        self.on_cursor_moved = on_cursor_moved
        self.on_play_from_position = on_play_from_position
        self.selection_region = None
        self._region_origin = None
        self.on_region_changed = on_region_changed
        self.on_fade_changed = on_fade_changed
        self.on_clip_trimmed = on_clip_trimmed
        self.on_clip_moved = on_clip_moved
        self.on_transition_changed = on_transition_changed
        self.on_remove_clip = on_remove_clip
        self.context_actions = context_actions or {}
        self.context_enabled = context_enabled or (lambda _action: True)
        self.project = AudioEditProject()
        self.waveforms: dict[Path, AudioWaveform] = {}
        self.pixels_per_second = 60.0
        self.selected_clip_id: str | None = None
        self.selected_clip_ids: list[str] = []
        self.playhead_position = 0.0
        self.snap_enabled = True
        self._drag_clip_id: str | None = None
        self._drag_origin: tuple[float, float] | None = None
        self._drag_transition: tuple[str, str, float, float] | None = None
        self.content_width = 1200

        self.canvas = tk.Canvas(
            self,
            background=colors["background"],
            highlightthickness=0,
            height=260,
            scrollregion=(0, 0, 1200, 260),
            takefocus=True,
        )
        self.horizontal_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self._scroll_horizontal)
        self.vertical_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.horizontal_scrollbar.set)
        self.canvas.configure(yscrollcommand=self.vertical_scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        self.horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self._select_at_pointer)
        self.canvas.bind("<Button-3>", self._show_clip_context_menu)
        self.canvas.bind("<ButtonRelease-1>", self._move_clip_at_pointer)
        self.canvas.bind("<Double-Button-1>", self._play_from_pointer)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_vertical_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_mousewheel)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self._init_gestures()

    def set_project(self, project: AudioEditProject, waveforms: dict[Path, AudioWaveform]) -> None:
        self.cancel_drag()
        self.project = project
        self.waveforms = waveforms
        self.set_preview_region(self.selection_region)
        existing_ids = {clip.id for track in project.tracks for clip in track.clips}
        self.set_selection([clip_id for clip_id in self.selected_clip_ids if clip_id in existing_ids])
        self.redraw()

    def set_selection(self, clip_ids: list[str], primary_id: str | None = None) -> None:
        existing_ids = {clip.id for track in self.project.tracks for clip in track.clips}
        self.selected_clip_ids = list(dict.fromkeys(clip_id for clip_id in clip_ids if clip_id in existing_ids))
        if primary_id in self.selected_clip_ids:
            self.selected_clip_id = primary_id
        elif self.selected_clip_id in self.selected_clip_ids:
            return
        else:
            self.selected_clip_id = self.selected_clip_ids[-1] if self.selected_clip_ids else None

    def select_single_clip(self, clip_id: str | None) -> None:
        self.set_selection([clip_id] if clip_id is not None else [], primary_id=clip_id)

    def zoom(self, factor: float, *, anchor_x: float | None = None) -> None:
        if not math.isfinite(factor) or factor <= 0:
            return
        scale = min(480.0, max(0.05, self.pixels_per_second * factor))
        if scale == self.pixels_per_second:
            return
        width = self.canvas.winfo_width()
        anchor = width / 2 if anchor_x is None else min(max(anchor_x, 0), width)
        # Keep the same timeline coordinate at the same viewport pixel.
        time = (self.canvas.canvasx(anchor) - _LEFT_GUTTER) / self.pixels_per_second
        self.cancel_drag()
        self.pixels_per_second = scale
        self.redraw()
        left = _LEFT_GUTTER + time * scale - anchor
        self.canvas.xview_moveto(max(0, left) / self.content_width)

    def snap_position(
        self,
        position: float,
        *,
        exclude_clip_ids: set[str] | None = None,
        include_playhead: bool = False,
    ) -> float:
        if not self.snap_enabled:
            return max(0.0, position)
        excluded = exclude_clip_ids or set()
        candidates = [marker.position for marker in self.project.markers]
        for track in self.project.tracks:
            for clip in track.clips:
                if clip.id not in excluded:
                    candidates.extend((clip.timeline_start, clip.timeline_end))
        if include_playhead:
            candidates.append(self.playhead_position)
        return max(
            0.0,
            snap_to_nearest(position, tuple(candidates), _SNAP_TOLERANCE_PIXELS / self.pixels_per_second),
        )

    def snap_clip_start(
        self,
        clip_id: str,
        position: float,
        *,
        group_ids: set[str] | None = None,
        include_playhead: bool = True,
    ) -> float:
        clip = next(
            (clip for track in self.project.tracks for clip in track.clips if clip.id == clip_id),
            None,
        )
        if clip is None or not self.snap_enabled:
            return max(0.0, position)
        excluded = group_ids or {clip_id}
        anchors = self._snap_anchors(excluded, include_playhead=include_playhead)
        candidates = tuple(
            candidate for anchor in anchors for candidate in (anchor, anchor - clip.duration) if candidate >= 0
        )
        return max(
            0.0,
            snap_to_nearest(position, candidates, _SNAP_TOLERANCE_PIXELS / self.pixels_per_second),
        )

    def _snap_anchors(self, exclude_clip_ids: set[str], *, include_playhead: bool) -> tuple[float, ...]:
        candidates = [marker.position for marker in self.project.markers]
        for track in self.project.tracks:
            for clip in track.clips:
                if clip.id not in exclude_clip_ids:
                    candidates.extend((clip.timeline_start, clip.timeline_end))
        if include_playhead:
            candidates.append(self.playhead_position)
        return tuple(candidates)

    def set_playhead_position(self, position: float) -> None:
        self.playhead_position = max(0.0, float(position))
        x = _LEFT_GUTTER + self.playhead_position * self.pixels_per_second
        height = max(
            self.canvas.winfo_height(), 260, _LANE_TOP + len(self.project.tracks) * (_LANE_HEIGHT + _LANE_GAP) + 10
        )
        if self.canvas.find_withtag("playhead"):
            self.canvas.coords("playhead", x, _RULER_HEIGHT, x, height)
        else:
            self.redraw()

    def redraw(self) -> None:
        self.canvas.delete("all")
        duration = self.project.duration
        width = max(self.canvas.winfo_width(), _LEFT_GUTTER + int(max(duration, 1) * self.pixels_per_second) + 60)
        self.content_width = width
        height = max(
            self.canvas.winfo_height(), 260, _LANE_TOP + len(self.project.tracks) * (_LANE_HEIGHT + _LANE_GAP) + 10
        )
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self._draw_ruler(width, height)
        self._draw_tracks()
        self._draw_transitions()
        self._draw_fades()
        self._draw_markers(height)
        self._draw_region_selection()
        self.canvas.create_line(
            _LEFT_GUTTER + self.playhead_position * self.pixels_per_second,
            _RULER_HEIGHT,
            _LEFT_GUTTER + self.playhead_position * self.pixels_per_second,
            height,
            fill=self.colors["error"],
            width=2,
            tags=("playhead",),
        )

    def _draw_ruler(self, width: int, height: int) -> None:
        self.canvas.create_rectangle(
            0,
            0,
            width,
            _RULER_HEIGHT,
            fill=self.colors["surface"],
            outline=self.colors["border"],
        )
        self.canvas.create_text(
            16,
            18,
            text=self._translate("audio_editor.time"),
            anchor="w",
            fill=self.colors["text_secondary"],
        )
        interval = time_tick_interval(self.pixels_per_second)
        duration = max(self.project.duration, 15)
        seconds = 0.0
        while seconds <= duration:
            x = _LEFT_GUTTER + seconds * self.pixels_per_second
            self.canvas.create_line(x, 22, x, height, fill=self.colors["border_soft"])
            self.canvas.create_text(
                x + 3,
                17,
                text=self._format_time(seconds),
                anchor="w",
                fill=self.colors["text_secondary"],
            )
            seconds += interval

    def _draw_tracks(self) -> None:
        for track_index, track in enumerate(self.project.tracks):
            lane_top = _LANE_TOP + track_index * (_LANE_HEIGHT + _LANE_GAP)
            lane_bottom = lane_top + _LANE_HEIGHT
            track_state = []
            if track.muted:
                track_state.append("M")
            if track.solo:
                track_state.append("S")
            label = track.name
            if track_state:
                label += f" [{' '.join(track_state)}]"
            self.canvas.create_text(
                10,
                lane_top + 20,
                text=label,
                anchor="w",
                width=_LEFT_GUTTER - 14,
                fill=self.colors["text"],
            )
            self.canvas.create_text(
                10,
                lane_top + 42,
                text=f"{track.volume:.0%}",
                anchor="w",
                fill=self.colors["text_secondary"],
            )
            self.canvas.create_rectangle(
                _LEFT_GUTTER,
                lane_top,
                self.content_width,
                lane_bottom,
                fill=self.colors["surface"],
                outline=self.colors["border_soft"],
            )
            for clip in track.clips:
                self._draw_clip(clip, lane_top, lane_bottom)

    def _draw_transitions(self) -> None:
        for track_index, track in enumerate(self.project.tracks):
            lane_top = _LANE_TOP + track_index * (_LANE_HEIGHT + _LANE_GAP)
            lane_bottom = lane_top + _LANE_HEIGHT
            ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
            for index, clip in enumerate(ordered[1:], start=1):
                if clip.crossfade_in <= 0:
                    continue
                previous = ordered[index - 1]
                start_x = _LEFT_GUTTER + clip.timeline_start * self.pixels_per_second
                end_x = _LEFT_GUTTER + previous.timeline_end * self.pixels_per_second
                transition_tag = f"transition:{previous.id}:{clip.id}"
                self.canvas.create_rectangle(
                    start_x,
                    lane_top + 8,
                    end_x,
                    lane_bottom - 8,
                    fill=self.colors["warning"],
                    stipple="gray50",
                    outline=self.colors["warning"],
                    width=2,
                    tags=("transition", transition_tag),
                )
                self.canvas.create_rectangle(
                    start_x - 3,
                    lane_top + 8,
                    start_x + 3,
                    lane_bottom - 8,
                    fill=self.colors["warning"],
                    outline=self.colors["warning"],
                    tags=("transition-handle", transition_tag),
                )
                self.canvas.create_text(
                    (start_x + end_x) / 2,
                    lane_top + 18,
                    text=f"{clip.crossfade_in:.2f}s",
                    fill=self.colors["text"],
                    tags=("transition", transition_tag),
                )

    def _draw_clip(self, clip, lane_top: int, lane_bottom: int) -> None:
        x1 = _LEFT_GUTTER + clip.timeline_start * self.pixels_per_second
        x2 = _LEFT_GUTTER + clip.timeline_end * self.pixels_per_second
        clip_top = lane_top + 8
        clip_bottom = lane_bottom - 8
        fill = self.colors["surface_alt"]
        selected = clip.id in self.selected_clip_ids
        outline = self.colors["highlight"] if selected else self.colors["border"]
        self.canvas.create_rectangle(
            x1,
            clip_top,
            max(x2, x1 + 3),
            clip_bottom,
            fill=fill,
            outline=outline,
            width=3 if selected and clip.id == self.selected_clip_id else 2 if selected else 1,
            tags=("clip", f"clip:{clip.id}"),
        )
        self.canvas.create_text(
            x1 + 7,
            clip_top + 11,
            text=clip.source_path.stem[: max(0, int((x2 - x1 - 18) / 7))],
            anchor="w",
            fill=self.colors["text"],
            tags=("clip", f"clip:{clip.id}"),
        )
        waveform = self.waveforms.get(clip.source_path)
        if waveform is None:
            return
        waveform_left = int(x1 + 5)
        waveform_right = max(waveform_left + 1, int(x2 - 5))
        sample_count = min(waveform_right - waveform_left, 1600)
        # Each peak represents a time bin in the original source, not this clip.
        count = len(waveform.peaks)
        start = max(0, min(count, math.floor(clip.source_start / waveform.duration * count)))
        end = max(start + 1, min(count, math.ceil(clip.source_end / waveform.duration * count)))
        peaks = resample_peaks(waveform.peaks[start:end], sample_count)
        center = (clip_top + clip_bottom) / 2 + 9
        amplitude = (clip_bottom - clip_top) * 0.30
        step = (waveform_right - waveform_left) / max(len(peaks) - 1, 1)
        for index, peak in enumerate(peaks):
            x = waveform_left + index * step
            extent = max(0.5, peak * amplitude)
            self.canvas.create_line(
                x,
                center - extent,
                x,
                center + extent,
                fill=self.colors["highlight"],
                tags=("clip", f"clip:{clip.id}"),
            )

    def _draw_markers(self, height: int) -> None:
        for marker in self.project.markers:
            x = _LEFT_GUTTER + marker.position * self.pixels_per_second
            self.canvas.create_line(
                x, _RULER_HEIGHT, x, height, fill=self.colors["warning"], width=2, tags=(f"marker:{marker.id}",)
            )
            if marker.label:
                self.canvas.create_text(
                    x + 4,
                    _RULER_HEIGHT + 5,
                    text=marker.label,
                    anchor="nw",
                    fill=self.colors["warning"],
                    tags=(f"marker:{marker.id}",),
                )

    def _select_at_pointer(self, event) -> None:
        if not self.context_enabled("interact"):
            return "break"
        self.cancel_drag()
        self.canvas.focus_set()
        if self._arm_region_drag(event):
            return "break"
        if self._arm_fade_drag(event):
            return "break"
        transition = self._transition_at_pointer(event)
        if transition is not None:
            first_clip, second_clip = transition
            self._drag_transition = (first_clip.id, second_clip.id, first_clip.timeline_end, event.x)
            self._drag_clip_id = None
            self._drag_origin = None
            self.set_selection([first_clip.id, second_clip.id], primary_id=second_clip.id)
            self.redraw()
            if self.on_selection_changed:
                self.on_selection_changed(second_clip.id)
            return "break"
        canvas_x = self.canvas.canvasx(event.x)
        position = canvas_x_to_seconds(canvas_x, self.pixels_per_second)
        position = self.snap_position(position)
        self.playhead_position = position
        clip_id = self._clip_id_at_pointer(event)
        control_pressed = bool(event.state & 0x0004)
        if control_pressed:
            selected_ids = list(self.selected_clip_ids)
            if clip_id is not None:
                if clip_id in selected_ids:
                    selected_ids.remove(clip_id)
                else:
                    selected_ids.append(clip_id)
            self.set_selection(selected_ids, primary_id=clip_id)
        elif clip_id is not None and clip_id in self.selected_clip_ids:
            self.set_selection(self.selected_clip_ids, primary_id=clip_id)
        else:
            self.select_single_clip(clip_id)
        if not control_pressed and clip_id is not None:
            self._drag_clip_id = clip_id
            self._drag_origin = (event.x, event.y)
            self._arm_clip_drag(clip_id, event)
        else:
            self._drag_clip_id = None
            self._drag_origin = None
        self.redraw()
        if self.on_cursor_moved:
            self.on_cursor_moved(position)
        if self.on_selection_changed:
            self.on_selection_changed(self.selected_clip_id)

    def _clip_id_at_pointer(self, event) -> str | None:
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        item_ids = self.canvas.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)
        for item_id in reversed(item_ids):
            clip_id = next(
                (tag.removeprefix("clip:") for tag in self.canvas.gettags(item_id) if tag.startswith("clip:")),
                None,
            )
            if clip_id:
                return clip_id
        return None

    def _transition_at_pointer(self, event) -> tuple[AudioEditClip, AudioEditClip] | None:
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        item_ids = self.canvas.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)
        for item_id in reversed(item_ids):
            if "transition-handle" not in self.canvas.gettags(item_id):
                continue
            tag = next(
                (tag for tag in self.canvas.gettags(item_id) if tag.startswith("transition:")),
                None,
            )
            if tag is None:
                continue
            _, first_id, second_id = tag.split(":", 2)
            track = next(
                (track for track in self.project.tracks if any(clip.id == first_id for clip in track.clips)), None
            )
            if track is None:
                return None
            ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
            first_index = next((index for index, clip in enumerate(ordered) if clip.id == first_id), None)
            if first_index is None or first_index + 1 >= len(ordered) or ordered[first_index + 1].id != second_id:
                return None
            return ordered[first_index], ordered[first_index + 1]
        return None

    def _context_menu(self):
        return tk.Menu(
            self,
            tearoff=False,
            background=self.colors["surface"],
            foreground=self.colors["text"],
            activebackground=self.colors["highlight"],
            activeforeground=self.colors["highlight_text"],
            disabledforeground=self.colors["text_secondary"],
        )

    def _action_state(self, action):
        return "normal" if self.context_enabled(action) else "disabled"

    def _show_clip_context_menu(self, event) -> str | None:
        clip_id = self._clip_id_at_pointer(event)
        if clip_id is None:
            callback = self.context_actions.get("paste")
            if callback is None:
                return None
            menu = self._context_menu()
            menu.add_command(
                label=self.translate("audio_editor.context_paste"), command=callback, state=self._action_state("paste")
            )
            self._append_marker_action(menu, event)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"
        self.canvas.focus_set()
        selection_changed = clip_id not in self.selected_clip_ids or clip_id != self.selected_clip_id
        if clip_id not in self.selected_clip_ids:
            self.select_single_clip(clip_id)
        else:
            self.set_selection(self.selected_clip_ids, primary_id=clip_id)
        self.redraw()
        if selection_changed and self.on_selection_changed:
            self.on_selection_changed(self.selected_clip_id)
        if self.context_actions:
            menu = self._context_menu()
            for action, label_key in (
                ("copy", "audio_editor.context_copy"),
                ("cut", "audio_editor.context_cut"),
                ("duplicate", "audio_editor.context_duplicate"),
            ):
                callback = self.context_actions.get(action)
                if callback is not None:
                    menu.add_command(
                        label=self.translate(label_key), command=callback, state=self._action_state(action)
                    )
            if self.on_remove_clip is not None:
                menu.add_command(
                    label=self.translate(
                        "audio_editor.context_delete_selected"
                        if len(self.selected_clip_ids) > 1
                        else "audio_editor.delete_clip"
                    ),
                    command=lambda selected_id=clip_id: self.on_remove_clip(selected_id),
                    state=self._action_state("delete"),
                )
            menu.add_separator()
            actions = [
                ("start_here", "audio_editor.start_here"),
                ("end_here", "audio_editor.end_here"),
                ("listen_start", "audio_editor.listen_start"),
                ("listen_end", "audio_editor.listen_end"),
            ]
            if len(self.selected_clip_ids) > 1:
                actions.extend(
                    (
                        ("paste", "audio_editor.context_paste"),
                        ("move", "audio_editor.context_move_selected"),
                        ("trim", "audio_editor.context_trim_selected"),
                        ("remove_range", "audio_editor.context_remove_range_selected"),
                        ("split", "audio_editor.context_split_selected"),
                        ("fades", "audio_editor.context_fades_selected"),
                    )
                )
            else:
                actions.extend(
                    (
                        ("paste", "audio_editor.context_paste"),
                        ("split", "audio_editor.split_at_cursor"),
                        ("move", "audio_editor.move_to_cursor"),
                    )
                )
            actions.append(("properties", "audio_editor.properties"))
            for action, label_key in actions:
                callback = self.context_actions.get(action)
                if callback is not None:
                    menu.add_command(
                        label=self.translate(label_key), command=callback, state=self._action_state(action)
                    )
            self._append_marker_action(menu, event)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        return "break"

    def _move_clip_at_pointer(self, event) -> None:
        if self._region_origin is not None:
            self._commit_region_drag(event)
            return
        if self._fade_drag is not None:
            self._commit_fade_drag(event)
            return
        if self._drag_transition is not None:
            first_id, second_id, end_position, origin_x = self._drag_transition
            self._drag_transition = None
            if self.on_transition_changed is not None and abs(event.x - origin_x) >= 4:
                duration = max(
                    0.0,
                    end_position - canvas_x_to_seconds(self.canvas.canvasx(event.x), self.pixels_per_second),
                )
                self.on_transition_changed(first_id, second_id, duration)
            return
        self._commit_clip_drag(event)

    def _on_zoom_mousewheel(self, event) -> str:
        if event.delta == 0:
            return "break"
        self.zoom(1.25 if event.delta > 0 else 0.8, anchor_x=event.x)
        self.event_generate("<<TimelineZoom>>")
        return "break"

    def _scroll_horizontal(self, *args) -> None:
        if len(args) == 3 and args[0] == "scroll" and args[2] == "units":
            self.canvas.xview_scroll(int(args[1]) * 20, "units")
        else:
            self.canvas.xview(*args)

    def _on_mousewheel(self, event) -> None:
        self.canvas.xview_scroll(int(-20 * (event.delta / 120)), "units")

    def _on_vertical_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _play_from_pointer(self, event):
        if self.on_play_from_position is not None and self.context_enabled("interact"):
            self.cancel_drag()
            position = canvas_x_to_seconds(self.canvas.canvasx(event.x), self.pixels_per_second)
            self.on_play_from_position(position)
        return "break"

    def _append_marker_action(self, menu, event):
        marker = self._marker_at_pointer(event)
        if marker is not None and self.on_marker_removed is not None:
            menu.add_separator()
            menu.add_command(
                label=self.translate("audio_editor.remove_marker", marker=marker.label),
                command=lambda marker_id=marker.id: self.on_marker_removed(marker_id),
                state=self._action_state("interact"),
            )
        if self.on_marker_added is not None and event.y >= _RULER_HEIGHT:
            position = canvas_x_to_seconds(self.canvas.canvasx(event.x), self.pixels_per_second)
            menu.add_separator()
            menu.add_command(
                label=self.translate("audio_editor.add_marker_here"),
                command=lambda: self.on_marker_added(position),
                state=self._action_state("interact"),
            )

    def _marker_at_pointer(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for item in reversed(self.canvas.find_overlapping(x - 6, y - 3, x + 6, y + 3)):
            for tag in self.canvas.gettags(item):
                if tag.startswith("marker:"):
                    marker_id = tag.removeprefix("marker:")
                    return next((marker for marker in self.project.markers if marker.id == marker_id), None)
        return None

    def _add_marker_at_pointer(self, event) -> None:
        if self.on_marker_added is not None and event.y >= _RULER_HEIGHT:
            position = canvas_x_to_seconds(self.canvas.canvasx(event.x), self.pixels_per_second)
            self.on_marker_added(position)

    def _translate(self, key: str) -> str:
        return self.translate(key)

    @staticmethod
    def _format_time(seconds: float) -> str:
        whole_seconds = int(math.floor(seconds))
        return f"{whole_seconds // 60:02d}:{whole_seconds % 60:02d}"
