"""Region audition controls, separate from saved project edits."""


class EditorLoopMixin:
    def _region_changed(self, region):
        self._invalidate_preview()
        if region is None:
            self._loop_var.set(False)
        if hasattr(self, "_region_label"):
            self._region_label.configure(
                text=(
                    self.translate("audio_editor.region_hint")
                    if region is None
                    else self.translate("audio_editor.region_value", start=f"{region[0]:.2f}", end=f"{region[1]:.2f}")
                )
            )

    def _clear_preview_region(self):
        if self._render_busy:
            return
        self.timeline.set_preview_region(None)
        self._loop_var.set(False)

    def _toggle_region_loop(self):
        if self._render_busy:
            return
        if self._loop_var.get() and self.timeline.selection_region is None:
            self._loop_var.set(False)
            self._status_var.set(self.translate("audio_editor.region_hint"))
            return
        self._invalidate_preview()

    def _requested_preview_region(self):
        if self._audition_region is not None:
            return self._audition_region
        return self.timeline.selection_region if self._loop_var.get() else None

    def _play_preview_file(self, path):
        looping = self._preview_region_snapshot is not None and not self._preview_is_audition
        callback = self._play_loop_preview if looping else self._play_preview
        if callback is None:
            raise RuntimeError(self.translate("audio_editor.preview_unavailable"))
        self._playback_modified = True
        callback(path)
