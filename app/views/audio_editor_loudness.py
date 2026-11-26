"""Cancelable loudness analysis and explicit application on the Tk thread."""

import threading
from dataclasses import replace

from ..services.audio_edit_service import AudioEditCancelled
from ..services.audio_loudness_service import analyze_clip_loudness
from ..utils import themed_messagebox as messagebox


class EditorLoudnessMixin:
    def _level_selected_clip(self):
        clip = self._quick_trim_clip()
        if clip is None:
            return
        project = self._project
        track = next(track for track in project.tracks if clip in track.clips)
        self._cancel_editor_drag()
        self._invalidate_preview()
        self._render_cancel.clear()
        self._render_busy = True
        self._set_render_controls_busy(True)
        self._cancel_button.configure(state="normal")
        self._status_var.set(self.translate("audio_editor.level_analyzing"))

        def work():
            try:
                result = analyze_clip_loudness(clip, track_volume=track.volume, cancel_event=self._render_cancel)
                self._render_results.put(("level_complete", (project, clip.id, result)))
            except AudioEditCancelled as exc:
                self._render_results.put(("cancelled", str(exc)))
            except Exception as exc:
                self._render_results.put(("level_error", str(exc)))
            finally:
                if self._closing:
                    self._cleanup_temp_directory()

        self._render_thread = threading.Thread(target=work, daemon=True)
        try:
            self._render_thread.start()
        except RuntimeError as exc:
            self._finish_render()
            self._status_var.set(self.translate("audio_editor.worker_failed", error=exc))

    def _complete_leveling(self, payload):
        project, clip_id, result = payload
        self._finish_render()
        if self._render_cancel.is_set():
            self._status_var.set(self.translate("audio_editor.render_cancelled"))
            return
        clip = self._quick_trim_clip()
        if self._project != project or clip is None or clip.id != clip_id:
            self._status_var.set(self.translate("audio_editor.level_stale"))
            return
        if not messagebox.askyesno(
            self.translate("audio_editor.level_volume"),
            self.translate(
                "audio_editor.level_proposal",
                measured=f"{result.integrated_lufs + clip.leveling_gain_db:.1f}",
                gain=f"{result.gain_db - clip.leveling_gain_db:+.1f}",
                predicted=f"{result.integrated_lufs + result.gain_db:.1f}",
            ),
            parent=self,
        ):
            self._status_var.set(self.translate("audio_editor.level_declined"))
            return
        if self._project != project or self._closing:
            return
        self._apply_clip_edit(lambda current: replace(current, leveling_gain_db=result.gain_db))
        self._status_var.set(self.translate("audio_editor.level_applied"))

    def _clear_clip_leveling(self):
        clip = self._quick_trim_clip()
        if clip is not None and clip.leveling_gain_db:
            self._apply_clip_edit(lambda current: replace(current, leveling_gain_db=0))
