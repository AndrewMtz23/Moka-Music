"""Drag sources into the timeline without changing listbox selection mid-gesture."""

import tkinter as tk


class SourceDragMixin:
    def _init_source_drag(self):
        self._source_drag_ghost = None
        self.source_list.bind("<Button-3>", self._source_context_menu)
        self._source_drag_origin = None
        self._source_drag_paths = []
        self._source_drag_active = False
        self.source_list.bind("<ButtonPress-1>", self._source_press, add="+")
        self.source_list.bind("<B1-Motion>", self._source_motion, add="+")
        self.source_list.bind("<ButtonRelease-1>", self._source_release, add="+")
        self.source_list.bind("<B1-Leave>", lambda event: "break" if self._source_drag_origin else None)
        self.bind("<Escape>", self._cancel_editor_drag, add="+")

    def _source_press(self, event):
        self._cancel_editor_drag()
        if self._render_busy or event.state & 5 or not self.source_list.size():
            return
        index = self.source_list.nearest(event.y)
        bbox = self.source_list.bbox(index)
        if bbox is None or not bbox[1] <= event.y <= bbox[1] + bbox[3]:
            return
        indices = self.source_list.curselection()
        if index not in indices:
            indices = (index,)
        self._source_drag_paths = [self._paths[i] for i in indices]
        self._source_drag_origin = (event.x_root, event.y_root)

    def _source_motion(self, event):
        if self._source_drag_origin is None:
            return
        if self._render_busy:
            return self._cancel_editor_drag()
        x, y = self._source_drag_origin
        if not self._source_drag_active or not self.timeline._external_drag:
            if max(abs(event.x_root - x), abs(event.y_root - y)) < 6:
                return "break"
            if any(path not in self._waveforms for path in self._source_drag_paths):
                return self._cancel_editor_drag()
            self.timeline.start_source_drag(
                [(path.stem, self._waveforms[path].duration) for path in self._source_drag_paths]
            )
            self._source_drag_active = True
        self._show_source_drag_ghost(event)
        canvas = self.timeline.canvas
        self.timeline.update_source_drag(event.x_root - canvas.winfo_rootx(), event.y_root - canvas.winfo_rooty())
        return "break"

    def _source_release(self, event):
        active = self._source_drag_active
        paths = list(self._source_drag_paths)
        destination = None
        if active:
            self._source_motion(event)
            destination = self.timeline.finish_source_drag()
        self._cancel_editor_drag()
        if destination is not None:
            self._drop_source_paths(paths, *destination)
        return "break" if active else None

    def _cancel_editor_drag(self, _event=None):
        if self._source_drag_ghost is not None:
            self._source_drag_ghost.destroy()
            self._source_drag_ghost = None
        self._source_drag_origin = None
        self._source_drag_paths = []
        self._source_drag_active = False
        self.timeline.cancel_drag()
        return "break"

    def _show_source_drag_ghost(self, event):
        if self._source_drag_ghost is None:
            ghost = tk.Toplevel(self)
            ghost.withdraw()
            ghost.overrideredirect(True)
            ghost.attributes("-alpha", 0.85)
            ghost.configure(background=self.colors["highlight"])
            name = self._source_drag_paths[0].name
            if len(self._source_drag_paths) > 1:
                name += f"  (+{len(self._source_drag_paths) - 1})"
            tk.Label(
                ghost,
                text=name[:64],
                padx=12,
                pady=9,
                background=self.colors["surface_alt"],
                foreground=self.colors["text"],
                font=("Segoe UI", 10),
            ).pack(padx=2, pady=2)
            self._source_drag_ghost = ghost
        self._source_drag_ghost.geometry(f"+{event.x_root + 18}+{event.y_root + 18}")
        self._source_drag_ghost.deiconify()
        self._source_drag_ghost.lift()

    def _source_context_menu(self, event):
        self._cancel_editor_drag()
        if not self.source_list.size():
            return "break"
        index = self.source_list.nearest(event.y)
        bbox = self.source_list.bbox(index)
        if bbox is None or not bbox[1] <= event.y < bbox[1] + bbox[3]:
            return "break"
        if index not in self.source_list.curselection():
            self.source_list.selection_clear(0, tk.END)
            self.source_list.selection_set(index)
        previous = getattr(self, "_sources_context_menu", None)
        if previous is not None:
            previous.destroy()
        menu = tk.Menu(
            self,
            tearoff=False,
            background=self.colors["surface_alt"],
            foreground=self.colors["text"],
            activebackground=self.colors["highlight"],
        )
        self._sources_context_menu = menu
        path = self._paths[index]
        menu.add_command(
            label=self.translate("audio_editor.relink_source"),
            command=lambda: self._browse_relink_source(path),
            state="normal"
            if not self._render_busy
            and self._pending_relink is None
            and (not path.is_file() or path in self._failed_paths)
            else "disabled",
        )
        menu.add_command(
            label=self.translate("audio_editor.remove_source"),
            command=self._remove_selected_sources,
            state="disabled" if self._render_busy else "normal",
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _remove_selected_sources(self):
        if self._render_busy:
            return
        paths = {self._paths[index] for index in self.source_list.curselection()}
        self._cancel_editor_drag()
        self._paths = [path for path in self._paths if path not in paths]
        self._auto_add_paths.difference_update(paths)
        self._refresh_source_list()
