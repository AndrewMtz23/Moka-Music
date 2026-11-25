"""Non-destructive fade handles and their pointer preview."""

from .audio_timeline_interaction import _LANE_GAP, _LANE_HEIGHT, _LANE_TOP, _LEFT_GUTTER


class TimelineFadeMixin:
    def _draw_fades(self):
        for lane, track in enumerate(self.project.tracks):
            ordered = sorted(track.clips, key=lambda clip: (clip.timeline_start, clip.id))
            for index, clip in enumerate(ordered):
                outgoing = index + 1 < len(ordered) and ordered[index + 1].crossfade_in > 0
                for side, duration, blocked in (
                    ("in", clip.fade_in, clip.crossfade_in > 0),
                    ("out", clip.fade_out, outgoing),
                ):
                    if blocked:
                        continue
                    if duration:
                        self._draw_fade_envelope(clip, lane, side, duration, "fade-envelope")
                    if clip.id not in self.selected_clip_ids or clip.duration * self.pixels_per_second < 28:
                        continue
                    x, y = self._fade_handle_position(clip, lane, side, duration)
                    self.canvas.create_rectangle(
                        x - 5,
                        y - 5,
                        x + 5,
                        y + 5,
                        fill=self.colors["highlight"],
                        outline=self.colors["text"],
                        tags=("fade-handle", f"fade-handle:{clip.id}:{side}", f"clip:{clip.id}"),
                    )

    def _fade_handle_position(self, clip, lane, side, duration):
        x1 = _LEFT_GUTTER + clip.timeline_start * self.pixels_per_second
        x2 = _LEFT_GUTTER + clip.timeline_end * self.pixels_per_second
        x = x1 + duration * self.pixels_per_second if side == "in" else x2 - duration * self.pixels_per_second
        x = min(max(x, x1 + 10), x2 - 10)
        y = _LANE_TOP + lane * (_LANE_HEIGHT + _LANE_GAP) + (34 if side == "in" else 50)
        return x, y

    def _draw_fade_envelope(self, clip, lane, side, duration, tag):
        x1 = _LEFT_GUTTER + clip.timeline_start * self.pixels_per_second
        x2 = _LEFT_GUTTER + clip.timeline_end * self.pixels_per_second
        top = _LANE_TOP + lane * (_LANE_HEIGHT + _LANE_GAP) + 30
        bottom = _LANE_TOP + lane * (_LANE_HEIGHT + _LANE_GAP) + _LANE_HEIGHT - 12
        points = (
            (x1, bottom, x1 + duration * self.pixels_per_second, top)
            if side == "in"
            else (x2 - duration * self.pixels_per_second, top, x2, bottom)
        )
        self.canvas.create_line(
            *points,
            fill=self.colors["highlight"],
            width=2,
            dash=(4, 2) if tag == "fade-preview" else (),
            tags=(tag, f"clip:{clip.id}"),
        )

    def _fade_at_pointer(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            for tag in self.canvas.gettags(item):
                if tag.startswith("fade-handle:"):
                    _, clip_id, side = tag.split(":", 2)
                    return clip_id, side
        return None

    def _arm_fade_drag(self, event):
        handle = self._fade_at_pointer(event)
        if handle is None or event.state & 0x0004:
            return False
        clip_id, side = handle
        clip = next(clip for track in self.project.tracks for clip in track.clips if clip.id == clip_id)
        self._fade_drag = (clip, side, self.canvas.canvasx(event.x))
        self._drag_origin = (event.x, event.y)
        self._drag_pointer = (event.x, event.y)
        self.select_single_clip(clip_id)
        self.redraw()
        if self.on_selection_changed:
            self.on_selection_changed(clip_id)
        return True

    def _fade_value(self):
        clip, side, origin_x = self._fade_drag
        delta = (self.canvas.canvasx(self._drag_pointer[0]) - origin_x) / self.pixels_per_second
        value = clip.fade_in + delta if side == "in" else clip.fade_out - delta
        other = clip.fade_out if side == "in" else clip.fade_in
        return max(0, min(value, clip.duration - other))

    def _draw_fade_preview(self):
        self.canvas.delete("fade-preview")
        clip, side, _ = self._fade_drag
        duration = self._fade_value()
        lane = next(index for index, track in enumerate(self.project.tracks) if clip in track.clips)
        self._draw_fade_envelope(clip, lane, side, duration, "fade-preview")
        x, y = self._fade_handle_position(clip, lane, side, duration)
        self.canvas.create_rectangle(
            x - 5, y - 5, x + 5, y + 5, fill=self.colors["highlight"], outline=self.colors["text"], tags="fade-preview"
        )
        self.canvas.create_text(x, y + 16, text=f"{duration:.2f} s", fill=self.colors["text"], tags="fade-preview")
        self.canvas.configure(cursor="sb_h_double_arrow")

    def _drag_fade(self, event):
        if not self.context_enabled("move"):
            self.cancel_drag()
            return "break"
        if not self._drag_active and abs(event.x - self._drag_origin[0]) < 4:
            return "break"
        self._drag_active = True
        self._drag_pointer = (event.x, event.y)
        self._draw_fade_preview()
        self._schedule_edge_scroll()
        return "break"

    def _commit_fade_drag(self, event):
        clip, side, _ = self._fade_drag
        moved = self._drag_active or abs(event.x - self._drag_origin[0]) >= 4
        self._drag_pointer = (event.x, event.y)
        duration = self._fade_value()
        self.cancel_drag()
        if moved and self.on_fade_changed is not None and self.context_enabled("move"):
            self.on_fade_changed(clip.id, side, duration)
