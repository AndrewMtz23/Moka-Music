"""Audition-region selection on the timeline ruler."""

from .audio_timeline_interaction import _LEFT_GUTTER, _RULER_HEIGHT


class TimelineRegionMixin:
    def set_preview_region(self, region):
        if region is not None:
            start, end = sorted(region)
            start, end = max(0, start), min(self.project.duration, end)
            region = (start, end) if end - start >= 0.05 else None
        changed = region != self.selection_region
        self.selection_region = region
        self._draw_region_selection()
        if changed and self.on_region_changed:
            self.on_region_changed(region)

    def _draw_region_selection(self, region=None, *, preview=False):
        tag = "region-preview" if preview else "region-selection"
        self.canvas.delete(tag)
        region = region if preview else self.selection_region
        if region is None:
            return
        start, end = sorted(region)
        x1, x2 = (_LEFT_GUTTER + value * self.pixels_per_second for value in (start, end))
        color = self.colors["highlight"]
        self.canvas.create_rectangle(
            x1, 1, x2, _RULER_HEIGHT - 1, fill=color, stipple="gray25", outline=color, tags=tag
        )
        for x in (x1, x2):
            self.canvas.create_line(x, _RULER_HEIGHT, x, self.canvas.winfo_height(), fill=color, dash=(3, 4), tags=tag)

    def _arm_region_drag(self, event):
        if not event.state & 0x0001 or not 0 <= self.canvas.canvasy(event.y) < _RULER_HEIGHT:
            return False
        self._region_origin = min(self.project.duration, self.snap_position(self._pointer_time(event.x)))
        self._drag_pointer = (event.x, event.y)
        return True

    def _region_target(self):
        end = min(self.project.duration, self.snap_position(self._pointer_time(self._drag_pointer[0])))
        return tuple(sorted((self._region_origin, end)))

    def _drag_region(self, event):
        self._drag_pointer = (event.x, event.y)
        self._drag_active = True
        self._draw_region_selection(self._region_target(), preview=True)
        self._schedule_edge_scroll()
        return "break"

    def _commit_region_drag(self, event):
        self._drag_pointer = (event.x, event.y)
        region = self._region_target()
        self.cancel_drag()
        self.set_preview_region(region)
