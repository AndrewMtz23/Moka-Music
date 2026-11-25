"""Single-clip intro/outro edits and short boundary auditions."""


class EditorQuickTrimMixin:
    def _play_from_position(self, position):
        if self._render_busy or not 0 <= position < self._project.duration:
            return
        self._invalidate_preview()
        self.timeline.set_playhead_position(position)
        self._cursor_moved(position)
        self._audition_region = (position, self._project.duration)
        self._start_preview()

    def _navigate_cursor(self, direction, *, step=0.1):
        if self._render_busy:
            return
        selected = [
            clip for track in self._project.tracks for clip in track.clips if clip.id in self.timeline.selected_clip_ids
        ]
        if direction == "start":
            position = min((clip.timeline_start for clip in selected), default=0.0)
        elif direction == "end":
            position = max((clip.timeline_end for clip in selected), default=self._project.duration)
        elif direction in ("forward", "backward"):
            position = self.timeline.playhead_position + (step if direction == "forward" else -step)
        else:
            return
        if self._preview_active:
            self._stop_active_preview(restore=True)
        position = min(self._project.duration, max(0.0, position))
        self.timeline.cancel_drag()
        self.timeline.set_playhead_position(position)
        canvas = self.timeline.canvas
        x = canvas.coords("playhead")[0]
        width = canvas.winfo_width()
        if not canvas.canvasx(0) + 20 <= x <= canvas.canvasx(width) - 20:
            canvas.xview_moveto(max(0, x - width / 2) / self.timeline.content_width)
        self._cursor_moved(position)

    def _quick_trim_clip(self):
        if self._render_busy or len(self.timeline.selected_clip_ids) != 1:
            return None
        return next(
            (
                clip
                for track in self._project.tracks
                for clip in track.clips
                if clip.id in self.timeline.selected_clip_ids
            ),
            None,
        )

    def _trim_at_cursor(self, edge):
        clip = self._quick_trim_clip()
        if clip is None or edge not in ("left", "right"):
            return
        position = self.timeline.playhead_position
        if not clip.timeline_start < position < clip.timeline_end:
            self._status_var.set(self.translate("audio_editor.cursor_inside_clip"))
            return
        self._trim_clip_on_timeline(clip.id, edge, position)

    def _audition_edge(self, edge):
        clip = self._quick_trim_clip()
        if clip is None or edge not in ("left", "right"):
            return
        self._invalidate_preview()
        start, end = clip.timeline_start, clip.timeline_end
        self._audition_region = (start, min(end, start + 5)) if edge == "left" else (max(start, end - 5), end)
        self._start_preview()
