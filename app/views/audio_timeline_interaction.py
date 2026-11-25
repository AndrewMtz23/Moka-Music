"""Pointer gestures for the timeline; previews never mutate the audio project."""

from __future__ import annotations

import tkinter as tk

from ..models.audio_edit_project import AudioEditMode

_LEFT_GUTTER = 84
_RULER_HEIGHT = 34
_LANE_TOP = 48
_LANE_HEIGHT = 134
_LANE_GAP = 8


def sequence_drop_index(clips, selected_ids, position):
    remaining = [clip for clip in clips if clip.id not in selected_ids]
    return sum(clip.timeline_start + clip.duration / 2 <= position for clip in remaining)


class TimelineInteractionMixin:
    def _init_gestures(self):
        self._drag_active = False
        self._drag_pointer = None
        self._drag_scroll_id = None
        self._drag_grab_offset = 0.0
        self._external_drag = ()
        self._trim_edge = None
        self._fade_drag = None
        self._pan_active = False
        self.canvas.configure(xscrollincrement=1, yscrollincrement=20)
        self.canvas.bind("<B1-Motion>", self._drag_motion)
        self.canvas.bind("<Motion>", self._hover_edge)
        self.canvas.bind("<Button-2>", self._begin_pan)
        self.canvas.bind("<B2-Motion>", self._pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_pan)
        self.bind("<Destroy>", self._destroy_gestures, add="+")

    def _destroy_gestures(self, event):
        if event.widget is self:
            self.cancel_drag()

    def _arm_clip_drag(self, clip_id, event):
        clip = next(clip for track in self.project.tracks for clip in track.clips if clip.id == clip_id)
        self._trim_edge = self._edge_at_pointer(clip, event.x)
        self._drag_grab_offset = (
            self.canvas.canvasx(event.x) - _LEFT_GUTTER
        ) / self.pixels_per_second - clip.timeline_start
        self._drag_pointer = (event.x, event.y)
        self._drag_active = False

    def _drag_motion(self, event):
        if self._region_origin is not None:
            return self._drag_region(event)
        if self._fade_drag is not None:
            return self._drag_fade(event)
        if self._drag_transition is not None:
            # Transition dragging keeps its existing commit path on release.
            return None
        if self._drag_clip_id is None or self._drag_origin is None or not self.context_enabled("move"):
            return None
        if not self._drag_active and max(abs(event.x - self._drag_origin[0]), abs(event.y - self._drag_origin[1])) < 4:
            return None
        self._drag_active = True
        self._drag_pointer = (event.x, event.y)
        self._draw_trim_preview() if self._trim_edge else self._draw_drag_preview()
        self._schedule_edge_scroll()
        return "break"

    def _edge_at_pointer(self, clip, x):
        pointer = self.canvas.canvasx(x)
        edges = {
            "left": _LEFT_GUTTER + clip.timeline_start * self.pixels_per_second,
            "right": _LEFT_GUTTER + clip.timeline_end * self.pixels_per_second,
        }
        edge = min(edges, key=lambda key: abs(edges[key] - pointer))
        return edge if abs(edges[edge] - pointer) <= 6 else None

    def _hover_edge(self, event):
        if self._drag_active or self._pan_active:
            return
        if self._fade_at_pointer(event) and self.context_enabled("interact"):
            self.canvas.configure(cursor="sb_h_double_arrow")
            return
        clip_id = self._clip_id_at_pointer(event)
        clip = next((clip for track in self.project.tracks for clip in track.clips if clip.id == clip_id), None)
        edge = clip and self._edge_at_pointer(clip, event.x)
        self.canvas.configure(cursor="sb_h_double_arrow" if edge and self.context_enabled("interact") else "")

    def _trim_target(self):
        clip = next(clip for track in self.project.tracks for clip in track.clips if clip.id == self._drag_clip_id)
        position = (self.canvas.canvasx(self._drag_pointer[0]) - _LEFT_GUTTER) / self.pixels_per_second
        if position >= 0 or self.project.mode != AudioEditMode.SEQUENCE:
            position = self.snap_position(position, exclude_clip_ids={clip.id})
        waveform = self.waveforms.get(clip.source_path)
        lower = clip.timeline_start - clip.source_start if waveform is not None else clip.timeline_start
        upper = (
            clip.timeline_end + max(0, waveform.duration - clip.source_end)
            if waveform is not None
            else clip.timeline_end
        )
        if self.project.mode == AudioEditMode.MULTITRACK:
            lower = max(0, lower)
        minimum = min(0.05, clip.duration)
        if self._trim_edge == "left":
            position = min(max(position, lower), clip.timeline_end - minimum)
        else:
            position = max(min(position, upper), clip.timeline_start + minimum)
        return clip, position

    def _draw_trim_preview(self):
        self.canvas.delete("trim-preview")
        clip, position = self._trim_target()
        lane = next(index for index, track in enumerate(self.project.tracks) if clip in track.clips)
        start = position if self._trim_edge == "left" else clip.timeline_start
        end = position if self._trim_edge == "right" else clip.timeline_end
        if self.project.mode == AudioEditMode.SEQUENCE and self._trim_edge == "left":
            end -= start - clip.timeline_start
            start = clip.timeline_start
        x1, x2 = (_LEFT_GUTTER + value * self.pixels_per_second for value in (start, end))
        y = _LANE_TOP + lane * (_LANE_HEIGHT + _LANE_GAP) + 8
        color = self.colors["highlight"]
        self.canvas.create_rectangle(
            x1, y, x2, y + _LANE_HEIGHT - 16, outline=color, width=3, dash=(5, 3), tags="trim-preview"
        )
        self.canvas.create_text(
            x1 + 8, y + 30, text=f"{end - start:.2f} s", anchor="w", fill=self.colors["text"], tags="trim-preview"
        )
        self.canvas.configure(cursor="sb_h_double_arrow")

    def _pointer_time(self, x):
        return max(0.0, (self.canvas.canvasx(x) - _LEFT_GUTTER) / self.pixels_per_second)

    def _drop_lane(self, y, allow_new=False):
        canvas_y = self.canvas.canvasy(y)
        if canvas_y < _LANE_TOP:
            return None
        if self.project.mode == AudioEditMode.SEQUENCE:
            return 0
        offset = canvas_y - _LANE_TOP
        index = int(offset // (_LANE_HEIGHT + _LANE_GAP))
        if index >= len(self.project.tracks):
            return len(self.project.tracks) if allow_new else None
        if offset % (_LANE_HEIGHT + _LANE_GAP) >= _LANE_HEIGHT:
            return None
        return index

    def _drag_destination(self):
        if self._drag_pointer is None:
            return None
        x, y = self._drag_pointer
        if not (0 <= x < self.canvas.winfo_width() and 0 <= y < self.canvas.winfo_height()):
            return None
        lane = self._drop_lane(y, allow_new=bool(self._external_drag))
        if lane is None:
            return None
        pointer = self._pointer_time(x)
        if self.project.mode == AudioEditMode.SEQUENCE or self._external_drag:
            return lane, self.snap_position(pointer) if self._external_drag else pointer
        selected = [
            (index, clip)
            for index, track in enumerate(self.project.tracks)
            for clip in track.clips
            if clip.id in self.selected_clip_ids
        ]
        primary = next(((index, clip) for index, clip in selected if clip.id == self._drag_clip_id), None)
        if primary is None:
            return None
        track_index, clip = primary
        track_delta = lane - track_index
        if any(not 0 <= index + track_delta < len(self.project.tracks) for index, _ in selected):
            return None
        target = self.snap_clip_start(
            clip.id,
            max(0, pointer - self._drag_grab_offset),
            group_ids=set(self.selected_clip_ids),
            include_playhead=False,
        )
        delta = max(target - clip.timeline_start, -min(item.timeline_start for _, item in selected))
        return lane, clip.timeline_start + delta

    def _draw_drag_preview(self):
        self.canvas.delete("drag-preview")
        destination = self._drag_destination()
        self.canvas.configure(cursor="fleur" if destination is not None else "X_cursor")
        if destination is None:
            return
        lane, position = destination
        color = self.colors["highlight"]
        if self.project.mode == AudioEditMode.SEQUENCE:
            if not self._external_drag and self._drag_pointer is not None:
                selected_clips = [
                    clip for track in self.project.tracks for clip in track.clips if clip.id in self.selected_clip_ids
                ]
                if selected_clips:
                    px, py = self._drag_pointer
                    gx, gy = self.canvas.canvasx(px) + 16, self.canvas.canvasy(py) + 18
                    label = selected_clips[0].source_path.stem[:40]
                    if len(selected_clips) > 1:
                        label += f" (+{len(selected_clips) - 1})"
                    self.canvas.create_rectangle(
                        gx,
                        gy,
                        gx + 280,
                        gy + 42,
                        fill=self.colors["surface_alt"],
                        outline=color,
                        width=2,
                        tags="drag-preview",
                    )
                    self.canvas.create_text(
                        gx + 10, gy + 21, text=label, anchor="w", fill=self.colors["text"], tags="drag-preview"
                    )
            clips = [clip for track in self.project.tracks for clip in track.clips]
            selected = set() if self._external_drag else set(self.selected_clip_ids)
            remaining = [clip for clip in clips if clip.id not in selected]
            index = sequence_drop_index(clips, selected, position)
            boundary = (
                remaining[index].timeline_start
                if index < len(remaining)
                else max((clip.timeline_end for clip in remaining), default=0)
            )
            x = _LEFT_GUTTER + boundary * self.pixels_per_second
            self.canvas.create_line(x, _LANE_TOP, x, _LANE_TOP + _LANE_HEIGHT, fill=color, width=4, tags="drag-preview")
            self.canvas.create_polygon(
                x - 6, _LANE_TOP, x + 6, _LANE_TOP, x, _LANE_TOP + 8, fill=color, tags="drag-preview"
            )
            return
        if self._external_drag:
            previews = []
            for name, duration in self._external_drag:
                previews.append((lane, position, duration, name))
                position += duration
        else:
            selected = [
                (index, clip)
                for index, track in enumerate(self.project.tracks)
                for clip in track.clips
                if clip.id in self.selected_clip_ids
            ]
            primary_track, primary = next((index, clip) for index, clip in selected if clip.id == self._drag_clip_id)
            previews = [
                (
                    index + lane - primary_track,
                    clip.timeline_start + position - primary.timeline_start,
                    clip.duration,
                    clip.source_path.stem,
                )
                for index, clip in selected
            ]
        for index, start, duration, name in previews:
            x = _LEFT_GUTTER + start * self.pixels_per_second
            y = _LANE_TOP + index * (_LANE_HEIGHT + _LANE_GAP) + 8
            width = max(8, duration * self.pixels_per_second)
            self.canvas.create_rectangle(
                x,
                y,
                x + width,
                y + _LANE_HEIGHT - 16,
                outline=color,
                width=2,
                dash=(5, 3),
                fill=self.colors["surface_alt"],
                stipple="gray25",
                tags="drag-preview",
            )
            self.canvas.create_text(
                x + 7,
                y + 12,
                text=name[: max(0, int((width - 14) / 7))],
                anchor="w",
                fill=self.colors["text"],
                tags="drag-preview",
            )

    def _schedule_edge_scroll(self):
        if self._drag_scroll_id is not None or self._drag_pointer is None:
            return
        x, y = self._drag_pointer
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if 0 <= x < width and 0 <= y < height and (x < 30 or x > width - 30 or y < 30 or y > height - 30):
            self._drag_scroll_id = self.after(40, self._autoscroll_tick)

    def _autoscroll_tick(self):
        self._drag_scroll_id = None
        if not self._drag_active or self._drag_pointer is None:
            return
        if not self._external_drag and not self.context_enabled(
            "interact" if self._region_origin is not None else "move"
        ):
            self.cancel_drag()
            return
        x, y = self._drag_pointer
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if (
            x > width - 30
            and self.canvas.xview()[1] >= 0.99
            and (self.project.mode == AudioEditMode.MULTITRACK or self._trim_edge == "right")
        ):
            region = [float(value) for value in self.canvas.cget("scrollregion").split()]
            region[2] += max(120, width / 2)
            self.canvas.configure(scrollregion=region)
        if x < 30:
            self.canvas.xview_scroll(-20, "units")
        elif x > width - 30:
            self.canvas.xview_scroll(20, "units")
        if y < 30:
            self.canvas.yview_scroll(-1, "units")
        elif y > height - 30:
            self.canvas.yview_scroll(1, "units")
        if self._region_origin is not None:
            self._draw_region_selection(self._region_target(), preview=True)
        elif self._fade_drag is not None:
            self._draw_fade_preview()
        else:
            self._draw_trim_preview() if self._trim_edge else self._draw_drag_preview()
        self._schedule_edge_scroll()

    def start_source_drag(self, items):
        self.cancel_drag()
        self._external_drag = tuple(items)
        self._drag_active = True

    def update_source_drag(self, x, y):
        self._drag_pointer = (x, y)
        self._draw_drag_preview()
        self._schedule_edge_scroll()

    def finish_source_drag(self):
        destination = self._drag_destination()
        self.cancel_drag()
        return destination

    def _commit_clip_drag(self, event):
        if self._drag_clip_id is None or self._drag_origin is None:
            return
        moved = self._drag_active or max(abs(event.x - self._drag_origin[0]), abs(event.y - self._drag_origin[1])) >= 4
        self._drag_pointer = (event.x, event.y)
        if self._trim_edge:
            clip, position = self._trim_target()
            edge = self._trim_edge
            self.cancel_drag()
            if moved and self.on_clip_trimmed is not None and self.context_enabled("move"):
                self.on_clip_trimmed(clip.id, edge, position)
            return
        destination = self._drag_destination() if moved else None
        clip_id = self._drag_clip_id
        self.cancel_drag()
        if destination is not None and self.on_clip_moved is not None and self.context_enabled("move"):
            self.on_clip_moved(clip_id, *destination)

    def cancel_drag(self):
        if self._drag_scroll_id is not None:
            try:
                self.after_cancel(self._drag_scroll_id)
            except tk.TclError:
                pass
        self._drag_scroll_id = None
        self._drag_pointer = None
        self._drag_clip_id = None
        self._drag_origin = None
        self._drag_transition = None
        self._drag_active = False
        self._external_drag = ()
        self._trim_edge = None
        self._fade_drag = None
        self._region_origin = None
        if self.canvas.winfo_exists():
            self.canvas.delete("region-preview")
            self.canvas.delete("fade-preview")
            self.canvas.delete("trim-preview")
            self.canvas.delete("drag-preview")
            self.canvas.configure(cursor="")

    def _begin_pan(self, event):
        self.cancel_drag()
        self._pan_active = True
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def _pan(self, event):
        if self._pan_active:
            self.canvas.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def _end_pan(self, _event=None):
        self._pan_active = False
        self.canvas.configure(cursor="")
        return "break"
