"""Named project lifecycle, separate from last-session recovery."""

import queue
import threading
from pathlib import Path
from tkinter import filedialog

from ..models.audio_edit_project import AudioEditProject
from ..services.audio_project_storage import load_editor_project, load_editor_session, save_editor_project
from ..utils import themed_messagebox as messagebox


class EditorProjectsMixin:
    def _project_state(self):
        return self._project, tuple(self._paths)

    def _project_is_dirty(self):
        return self._saved_document_state != self._project_state()

    def _update_project_title(self):
        if not hasattr(self, "_saved_document_state"):
            return
        name = self._project_path.name if self._project_path else self.translate("audio_editor.untitled_project")
        mark = " *" if self._project_is_dirty() else ""
        self.title(f"{name}{mark} — {self.translate('audio_editor.title')}")

    def _project_action_allowed(self):
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return False
        return True

    def _confirm_project_change(self):
        if not self._project_action_allowed():
            return False
        if not self._project_is_dirty() or self._project_load_failed:
            return True
        answer = messagebox.askyesnocancel(
            self.translate("audio_editor.project_menu"), self.translate("audio_editor.save_changes_prompt"), parent=self
        )
        if answer is None:
            return False
        return self._save_editor_project() if answer else True

    def _new_editor_project(self):
        if not self._confirm_project_change():
            return False
        self._replace_editor_project(AudioEditProject(), [], None)
        return True

    def _open_editor_project(self):
        if not self._project_action_allowed():
            return False
        selected = filedialog.askopenfilename(
            parent=self,
            title=self.translate("audio_editor.open_project"),
            filetypes=[("MokaMusic project", "*.moka-project.json *.json")],
        )
        if not selected:
            return False
        path = Path(selected).resolve()
        try:
            project, sources = load_editor_project(path)
        except (OSError, ValueError) as exc:
            self._project_error("audio_editor.project_load_error", exc)
            return False
        if not self._confirm_project_change():
            return False
        # Saving in the prompt may replace the very file selected for opening.
        try:
            project, sources = load_editor_project(path)
        except (OSError, ValueError) as exc:
            self._project_error("audio_editor.project_load_error", exc)
            return False
        self._replace_editor_project(project, sources, path)
        return True

    def _replace_editor_project(self, project, sources, path):
        self._pending_relink = None
        self._relink_ready = None
        self._cancel_editor_drag()
        self._invalidate_preview()
        self._cancel_event.set()
        self._cancel_event = threading.Event()
        self._results = queue.Queue()
        self._workers_active = 0
        self._auto_add_paths.clear()
        self._paths = []
        self._waveforms = {}
        self._failed_paths.clear()
        self._load_errors.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clipboard = ()
        self.timeline.set_preview_region(None)
        self._loop_var.set(False)
        self.timeline.select_single_clip(None)
        self.timeline.playhead_position = 0
        self.timeline.canvas.xview_moveto(0)
        self.timeline.canvas.yview_moveto(0)
        self._project_path = path
        self._project_load_failed = False
        self._restore_project_state(project)
        needed = list(dict.fromkeys(sources + [clip.source_path for track in project.tracks for clip in track.clips]))
        missing = [item for item in needed if not item.is_file()]
        self._add_source_paths(needed)
        self._paths = list(sources)
        self._failed_paths.update(missing)
        self._refresh_source_list()
        self._saved_document_state = self._project_state()
        self._update_project_title()
        self._status_var.set(
            self.translate("audio_editor.project_missing_sources", count=len(missing))
            if missing
            else self.translate("audio_editor.project_opened")
        )
        self._missing_sources_notice = (
            self.translate("audio_editor.project_missing_sources", count=len(missing)) if missing else None
        )
        if missing:
            self._load_errors.append(self._missing_sources_notice)

    def _restore_editor_session(self):
        if self._session_path is None or not self._session_path.exists():
            return False
        self._auto_add_paths.clear()
        try:
            project, sources, document = load_editor_session(self._session_path)
            self._replace_editor_project(project, sources, document)
            if document is not None:
                try:
                    saved_project, saved_sources = load_editor_project(document)
                    self._saved_document_state = saved_project, tuple(saved_sources)
                except (OSError, ValueError):
                    self._saved_document_state = None
            self._update_project_title()
        except (OSError, ValueError) as exc:
            self._project_load_failed = True
            self.after_idle(lambda error=str(exc): self._project_error("audio_editor.project_load_error", error))
        return True

    def _project_error(self, key, error):
        messagebox.showerror(self.translate("audio_editor.title"), self.translate(key, error=error), parent=self)

    def _save_project_as(self):
        if not self._project_action_allowed():
            return False
        selected = filedialog.asksaveasfilename(
            parent=self,
            title=self.translate("audio_editor.save_project_as"),
            defaultextension=".moka-project.json",
            filetypes=[("MokaMusic project", "*.moka-project.json *.json")],
            initialfile=self._project_path.name if self._project_path else "Untitled.moka-project.json",
        )
        if not selected:
            return False
        path = Path(selected).resolve()
        if self._session_path is not None and path == self._session_path.resolve():
            self._project_error("audio_editor.project_save_error", self.translate("audio_editor.reserved_session_path"))
            return False
        return self._write_named_project(path)

    def _save_editor_project(self):
        if not self._project_action_allowed():
            return False
        return self._write_named_project(self._project_path) if self._project_path else self._save_project_as()

    def _write_named_project(self, path):
        if self._project_load_failed:
            self._project_error(
                "audio_editor.project_save_error", self.translate("audio_editor.project_recovery_blocked")
            )
            return False
        if not self._initial_import_complete():
            return False
        try:
            save_editor_project(path, self._project, self._paths)
        except (OSError, ValueError, TypeError) as exc:
            self._project_error("audio_editor.project_save_error", exc)
            return False
        self._project_path = Path(path)
        self._saved_document_state = self._project_state()
        self._update_project_title()
        self._status_var.set(self.translate("audio_editor.project_saved"))
        return True

    def _initial_import_complete(self):
        if any(
            path in self._paths and path not in self._waveforms and path not in self._failed_paths
            for path in self._auto_add_paths
        ):
            self._status_var.set(self.translate("audio_editor.project_wait_loading"))
            return False
        return True

    def _prepare_project_close(self):
        recovery = self._project_state()
        if self._project_path is not None and self._project_is_dirty() and not self._project_load_failed:
            answer = messagebox.askyesnocancel(
                self.translate("audio_editor.project_menu"),
                self.translate("audio_editor.save_changes_prompt"),
                parent=self,
            )
            if answer is None:
                return False
            if answer and not self._save_editor_project():
                return False
            if not answer:
                recovery = self._saved_document_state or (AudioEditProject(), ())
        if self._session_path is not None and not self._project_load_failed:
            if not self._initial_import_complete():
                return False
            try:
                project, sources = recovery
                save_editor_project(self._session_path, project, sources, document_path=self._project_path)
            except (OSError, ValueError, TypeError) as exc:
                self._project_error("audio_editor.project_save_error", exc)
                return False
        return True

    def _update_project_menu(self):
        self._project_menu.delete(0, "end")
        for key, shortcut, action in (
            ("audio_editor.new_project", "Ctrl+N", self._new_editor_project),
            ("audio_editor.open_project", "Ctrl+O", self._open_editor_project),
            ("audio_editor.save_project", "Ctrl+S", self._save_editor_project),
            ("audio_editor.save_project_as", "Ctrl+Shift+S", self._save_project_as),
            ("audio_editor.relink_source", "", self._browse_relink_source),
        ):
            self._project_menu.add_command(
                label=self.translate(key),
                accelerator=shortcut,
                command=action,
                state="disabled" if self._render_busy else "normal",
            )
