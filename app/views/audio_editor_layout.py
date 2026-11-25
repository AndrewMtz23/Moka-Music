"""Theme-aware editor chrome; audio operations remain in the dashboard."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ..models.audio_edit_project import AudioEditMode
from ..ui_helpers.widgets import ToolTip
from ..utils import themed_messagebox as messagebox
from ..utils.window_chrome import theme_window_caption
from .audio_timeline import AudioTimeline


class EditorToolTip(ToolTip):
    def __init__(self, widget, text_getter, colors):
        self.colors = colors
        super().__init__(widget, text_getter)
        widget.bind("<Destroy>", self._hide, add="+")

    def _show(self):
        super()._show()
        if self._tip_window is not None:
            for label in self._tip_window.winfo_children():
                label.configure(background=self.colors()["surface"], foreground=self.colors()["text"])


class EditorLayoutMixin:
    def _editor_button(self, parent, key, command, *, primary=False, width=None):
        button = ttk.Button(
            parent,
            text=self.translate(key),
            command=lambda: self._run_editor_action(command),
            style="Editor.Primary.TButton" if primary else "Editor.TButton",
        )
        if width is not None:
            button.configure(width=width)
        if hasattr(self, "_tooltips"):
            hint = {
                "audio_editor.zoom_in": "audio_editor.zoom_in_hint",
                "audio_editor.zoom_out": "audio_editor.zoom_out_hint",
            }.get(key, key)
            self._tooltips.append(EditorToolTip(button, lambda: self.translate(hint), lambda: self.colors))
        return button

    def _run_editor_action(self, action):
        if self._render_busy:
            self._status_var.set(self.translate("audio_editor.render_in_progress"))
            return
        action()

    def _build_editor_layout(self):
        self._inspector_visible = False
        self._sources_visible = True
        self._tooltips = []
        self._property_entries = []
        self._property_buttons = []
        self._panel_layout_id = None
        self._configure_editor_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, style="Editor.TFrame", padding=(16, 12))
        header.grid(row=0, column=0, sticky="ew")
        self._editor_header = header
        header.columnconfigure(1, weight=1)
        self._editor_title = ttk.Label(header, text=self.translate("audio_editor.title"), style="Editor.Title.TLabel")
        self._editor_title.grid(row=0, column=0, padx=(0, 20))
        actions = ttk.Frame(header, style="Editor.TFrame")
        actions.grid(row=0, column=1, sticky="w")
        self._editor_actions = actions
        project_button = ttk.Menubutton(
            actions, text=self.translate("audio_editor.project_menu"), width=8, style="Editor.TMenubutton"
        )
        project_button.pack(side="left", padx=(0, 8))
        self._project_menu = tk.Menu(project_button, tearoff=False, postcommand=self._update_project_menu)
        project_button.configure(menu=self._project_menu)
        edit = ttk.Menubutton(
            actions, text=self.translate("audio_editor.edit_menu"), width=8, style="Editor.TMenubutton"
        )
        edit.pack(side="left", padx=(0, 8))
        self._edit_menu = tk.Menu(edit, tearoff=False, postcommand=self._update_edit_menu)
        edit.configure(menu=self._edit_menu)
        self._sources_button = self._editor_button(actions, "audio_editor.sources", self._toggle_sources)
        self._sources_button.pack(side="left", padx=2)
        self._properties_button = self._editor_button(actions, "audio_editor.properties", self._toggle_inspector)
        self._properties_button.pack(side="left", padx=2)
        self._undo_button = self._editor_button(actions, "audio_editor.undo", self._undo, width=3)
        self._undo_button.configure(text="↶")
        self._undo_button.pack(side="left", padx=(8, 2))
        self._redo_button = self._editor_button(actions, "audio_editor.redo", self._redo, width=3)
        self._redo_button.configure(text="↷")
        self._redo_button.pack(side="left", padx=2)
        export = ttk.Frame(header, style="Editor.TFrame")
        export.grid(row=0, column=2, sticky="e")
        self._export_tools = export
        self._format_menu = ttk.Combobox(
            export,
            textvariable=self._export_format_var,
            values=(".mp3", ".wav", ".flac", ".ogg"),
            state="readonly",
            width=6,
        )
        self._format_menu.pack(side="left", padx=(6, 8))
        self._editor_button(export, "audio_editor.export", self._choose_export, primary=True).pack(side="left")

        self._editor_body = ttk.Frame(self, style="Editor.TFrame", padding=(12, 0, 12, 0))
        self._editor_body.grid(row=1, column=0, sticky="nsew")
        self._editor_body.columnconfigure(1, weight=1)
        self._editor_body.rowconfigure(0, weight=1)
        self._source_panel = ttk.Frame(self._editor_body, style="Editor.Panel.TFrame", padding=12, width=240)
        self._source_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._source_panel.grid_propagate(False)
        self._source_panel.columnconfigure(0, weight=1)
        self._source_panel.rowconfigure(2, weight=1)
        ttk.Label(self._source_panel, text=self.translate("audio_editor.sources"), style="Editor.Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        self._editor_button(self._source_panel, "audio_editor.add_file", self._browse_sources).grid(
            row=1, column=0, sticky="ew", pady=(0, 10)
        )
        listing = ttk.Frame(self._source_panel, style="Editor.Panel.TFrame")
        listing.grid(row=2, column=0, sticky="nsew")
        listing.columnconfigure(0, weight=1)
        listing.rowconfigure(0, weight=1)
        self.source_list = tk.Listbox(
            listing,
            width=18,
            selectmode=tk.EXTENDED,
            exportselection=False,
            borderwidth=0,
            highlightthickness=1,
            activestyle="none",
        )
        self.source_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(listing, command=self.source_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.source_list.configure(yscrollcommand=scrollbar.set)
        self.source_list.bind("<Double-Button-1>", lambda _event: self._run_editor_action(self._add_selected_source))
        self._editor_button(self._source_panel, "audio_editor.insert_source", self._add_selected_source).grid(
            row=3, column=0, sticky="ew", pady=(10, 4)
        )
        self._editor_button(self._source_panel, "audio_editor.add_track", self._add_selected_as_track).grid(
            row=4, column=0, sticky="ew"
        )

        self._source_grip = tk.Frame(self._editor_body, width=8, cursor="sb_h_double_arrow", takefocus=True)
        self._source_grip.bind(
            "<Enter>", lambda event: self._source_grip.configure(background=self.colors["highlight"])
        )
        self._source_grip.bind(
            "<Leave>", lambda event: self._source_grip.configure(background=self.colors["border_soft"])
        )
        self._source_grip.bind("<B1-Motion>", self._resize_sources)
        self._source_grip.bind(
            "<Left>", lambda event: self._set_source_width(int(self._source_panel.cget("width")) - 20)
        )
        self._source_grip.bind(
            "<Right>", lambda event: self._set_source_width(int(self._source_panel.cget("width")) + 20)
        )
        self._source_grip.bind("<Double-Button-1>", lambda event: self._set_source_width(240))
        center = ttk.Frame(self._editor_body, style="Editor.Panel.TFrame")
        self._timeline_center = center
        center.grid(row=0, column=1, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)
        tools = ttk.Frame(center, style="Editor.Panel.TFrame", padding=(10, 8))
        tools.grid(row=0, column=0, sticky="ew")
        tools.columnconfigure(1, weight=1)
        mode = ttk.Frame(tools, style="Editor.Panel.TFrame")
        mode.grid(row=0, column=0, sticky="w")
        self._mode_var = tk.StringVar(value=self.translate("audio_editor.mode_sequence"))
        self._mode_menu = ttk.Combobox(
            mode,
            textvariable=self._mode_var,
            width=12,
            state="readonly",
            values=(self.translate("audio_editor.mode_sequence"), self.translate("audio_editor.mode_multitrack")),
        )
        self._mode_menu.pack(side="left")
        self._mode_menu.bind("<<ComboboxSelected>>", self._on_mode_selected)
        self._snap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            mode,
            text=self.translate("audio_editor.snap_short"),
            variable=self._snap_var,
            command=self._toggle_snap,
            style="Editor.TCheckbutton",
        ).pack(side="left", padx=8)
        zoom = ttk.Frame(tools, style="Editor.Panel.TFrame")
        zoom.grid(row=0, column=1, sticky="e")
        self._zoom_tools, self._mode_tools = zoom, mode
        center.bind("<Configure>", self._schedule_panel_layout, add="+")
        self._editor_button(zoom, "audio_editor.zoom_out", lambda: self._zoom(0.8), width=3).pack(side="left")
        self._zoom_label = ttk.Label(zoom, text="100%", width=5, anchor="center", style="Editor.Muted.TLabel")
        self._zoom_label.pack(side="left", padx=3)
        self._editor_button(zoom, "audio_editor.zoom_in", lambda: self._zoom(1.25), width=3).pack(side="left")
        self._editor_button(zoom, "audio_editor.fit", self._fit_project).pack(side="left", padx=(6, 0))
        self.timeline = AudioTimeline(
            center,
            colors=self.colors,
            translate=self.translate,
            on_selection_changed=self._selection_changed,
            on_marker_added=self._add_marker,
            on_marker_removed=self._remove_marker,
            on_cursor_moved=self._cursor_moved,
            on_play_from_position=self._play_from_position,
            on_clip_moved=self._move_clip_on_timeline,
            on_clip_trimmed=self._trim_clip_on_timeline,
            on_fade_changed=self._fade_clip_on_timeline,
            on_region_changed=self._region_changed,
            on_transition_changed=self._apply_crossfade,
            on_remove_clip=self._remove_clip_by_id,
            context_enabled=self._context_action_enabled,
            context_actions={
                name: (lambda action=action: self._run_editor_action(action))
                for name, action in {
                    "copy": self._copy_selected_clips,
                    "cut": self._cut_selected_clips,
                    "paste": self._paste_clips,
                    "start_here": lambda: self._trim_at_cursor("left"),
                    "end_here": lambda: self._trim_at_cursor("right"),
                    "listen_start": lambda: self._audition_edge("left"),
                    "listen_end": lambda: self._audition_edge("right"),
                    "duplicate": self._duplicate_selected_clips,
                    "move": self._move_selected_clip_to_cursor,
                    "trim": self._trim_selected_clip,
                    "remove_range": self._remove_selected_range,
                    "split": self._split_at_cursor,
                    "fades": self._apply_fades,
                    "properties": self._show_properties,
                }.items()
            },
        )
        self.timeline.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        self.timeline.bind("<<TimelineZoom>>", lambda _event: self._refresh_zoom_label())
        self._build_properties()
        self._build_transport()
        self.bind("<Configure>", self._schedule_panel_layout, add="+")
        self.refresh_theme(self.colors)
        self._layout_panels()

    def _build_transport(self):
        footer = ttk.Frame(self, style="Editor.TFrame", padding=(16, 10))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(2, weight=1)
        transport = ttk.Frame(footer, style="Editor.TFrame")
        transport.grid(row=0, column=0, sticky="w")
        self._play_pause_button = ttk.Button(
            transport, text="▶", width=4, style="Editor.Primary.TButton", command=self._toggle_preview
        )
        self._play_pause_button.pack(side="left", padx=(0, 5))
        self._stop_button = ttk.Button(transport, text="■", width=4, style="Editor.TButton", command=self._stop)
        self._stop_button.pack(side="left")
        self._playback_time_var = tk.StringVar(value="00:00")
        ttk.Label(footer, textvariable=self._playback_time_var, style="Editor.Time.TLabel").grid(
            row=0, column=1, padx=16
        )
        self._duration_var = tk.StringVar()
        ttk.Label(footer, textvariable=self._duration_var, style="Editor.Muted.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        self._cancel_button = ttk.Button(
            footer,
            text=self.translate("audio_editor.cancel_render"),
            command=self._render_cancel.set,
            style="Editor.TButton",
            state="disabled",
        )
        self._cancel_button.grid(row=0, column=3, padx=8)
        self._cancel_button.grid_remove()
        self._editor_button(footer, "audio_editor.save_project", self._save_editor_project).grid(
            row=0, column=4, padx=8
        )
        self._editor_button(footer, "audio_editor.help", self._show_editor_help).grid(row=0, column=5)
        region_controls = ttk.Frame(footer, style="Editor.TFrame")
        region_controls.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(
            region_controls,
            text=self.translate("audio_editor.repeat_region"),
            variable=self._loop_var,
            command=self._toggle_region_loop,
        ).pack(side="left")
        self._editor_button(region_controls, "audio_editor.clear_region", self._clear_preview_region).pack(
            side="left", padx=8
        )
        self._region_label = ttk.Label(
            region_controls, text=self.translate("audio_editor.region_hint"), style="Editor.Muted.TLabel"
        )
        self._region_label.pack(side="left")
        self._status_var = tk.StringVar(value=self.translate("audio_editor.ready"))
        self._status_label = ttk.Label(footer, textvariable=self._status_var, style="Editor.Muted.TLabel", anchor="w")
        self._status_label.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        self._tooltips.extend(
            [
                EditorToolTip(
                    self._play_pause_button, lambda: self.translate("audio_editor.preview"), lambda: self.colors
                ),
                EditorToolTip(self._stop_button, lambda: self.translate("audio_editor.stop"), lambda: self.colors),
            ]
        )
        self._update_transport_controls()

    def _build_properties(self):
        self._inspector_panel = ttk.Frame(self._editor_body, style="Editor.Panel.TFrame", padding=12, width=286)
        self._inspector_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self._inspector_panel.grid_propagate(False)
        self._inspector_panel.columnconfigure(0, weight=1)
        self._inspector_panel.rowconfigure(2, weight=1)
        ttk.Label(
            self._inspector_panel, text=self.translate("audio_editor.properties"), style="Editor.Section.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self._selection_title = tk.StringVar(value=self.translate("audio_editor.select_clip_first"))
        ttk.Label(
            self._inspector_panel, textvariable=self._selection_title, wraplength=250, style="Editor.Muted.TLabel"
        ).grid(row=1, column=0, sticky="ew", pady=(6, 12))
        tabs = ttk.Notebook(self._inspector_panel)
        tabs.grid(row=2, column=0, sticky="nsew")
        clip_tab = ttk.Frame(tabs)
        tabs.add(clip_tab, text=self.translate("audio_editor.clip_tab"))
        clip_tab.columnconfigure(0, weight=1)
        clip_tab.rowconfigure(0, weight=1)
        self._properties_canvas = tk.Canvas(clip_tab, highlightthickness=0, width=238)
        self._properties_canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(clip_tab, command=self._properties_canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._properties_canvas.configure(yscrollcommand=scroll.set)
        content = ttk.Frame(self._properties_canvas, style="Editor.Panel.TFrame", padding=(8, 12))
        window = self._properties_canvas.create_window(0, 0, anchor="nw", window=content)
        content.columnconfigure(0, weight=1)
        content.bind(
            "<Configure>",
            lambda _event: self._properties_canvas.configure(scrollregion=self._properties_canvas.bbox("all")),
        )
        self._properties_canvas.bind(
            "<Configure>", lambda event: self._properties_canvas.itemconfigure(window, width=event.width)
        )
        self._properties_canvas.bind(
            "<MouseWheel>", lambda event: self._properties_canvas.yview_scroll(int(-event.delta / 120), "units")
        )
        self._range_start_var = tk.StringVar()
        self._range_end_var = tk.StringVar()
        self._fade_in_var = tk.StringVar(value="0")
        self._fade_out_var = tk.StringVar(value="0")
        self._crossfade_duration_var = tk.StringVar(value="1")
        self._section(content, "audio_editor.range_section", 1)
        self._field_pair(
            content,
            2,
            ("audio_editor.start_short", self._range_start_var),
            ("audio_editor.end_short", self._range_end_var),
        )
        self._property_action(content, "audio_editor.trim", self._trim_selected_clip, 3)
        self._property_action(content, "audio_editor.remove_range", self._remove_selected_range, 4)
        quick_trim = ttk.Frame(content, style="Editor.Panel.TFrame")
        quick_trim.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        quick_trim.columnconfigure(0, weight=1)
        self._quick_trim_buttons = []
        for row, (key, command) in enumerate(
            (
                ("audio_editor.start_here", lambda: self._trim_at_cursor("left")),
                ("audio_editor.end_here", lambda: self._trim_at_cursor("right")),
                ("audio_editor.listen_start", lambda: self._audition_edge("left")),
                ("audio_editor.listen_end", lambda: self._audition_edge("right")),
            )
        ):
            button = self._editor_button(quick_trim, key, command)
            button.grid(row=row, column=0, sticky="ew", pady=2)
            self._quick_trim_buttons.append(button)
        self._range_hint = ttk.Label(quick_trim, text="", wraplength=205, style="Editor.Muted.TLabel")
        self._range_hint.grid(row=4, column=0, sticky="ew", pady=6)
        self._section(content, "audio_editor.fades_section", 5)
        self._field_pair(
            content, 6, ("audio_editor.fade_in", self._fade_in_var), ("audio_editor.fade_out", self._fade_out_var)
        )
        self._property_action(content, "audio_editor.apply_fades", self._apply_fades, 7)
        self._field_pair(content, 8, ("audio_editor.crossfade_duration", self._crossfade_duration_var))
        self._property_action(content, "audio_editor.apply_crossfade", self._apply_crossfade, 9)
        self._section(content, "audio_editor.mix_section", 10)
        self._field_pair(
            content,
            11,
            ("audio_editor.gain_short", self._clip_gain_var),
            ("audio_editor.pan_short", self._clip_pan_var),
        )
        self._property_action(content, "audio_editor.apply_clip_mix", self._apply_clip_mix, 12)
        self._section(content, "audio_editor.effects_section", 13)
        self._property_action(content, "audio_editor.processing_title", self._edit_clip_processing, 14)
        self._property_action(content, "audio_editor.fx_title", self._edit_clip_effects, 15)
        self._track_controls = ttk.Frame(tabs, padding=12, style="Editor.Panel.TFrame")
        tabs.add(self._track_controls, text=self.translate("audio_editor.track_tab"))
        self._track_controls.columnconfigure(0, weight=1)
        ttk.Label(
            self._track_controls, text=self.translate("audio_editor.track_volume"), style="Editor.Section.TLabel"
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))
        self._track_volume = ttk.Scale(self._track_controls, from_=0, to=100, variable=self._track_volume_var)
        self._track_volume.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self._track_volume.bind("<ButtonRelease-1>", self._set_selected_track_volume)
        self._track_volume.bind("<KeyRelease>", self._set_selected_track_volume)
        self._mute_button = self._editor_button(
            self._track_controls, "audio_editor.mute", self._toggle_selected_track_mute
        )
        self._mute_button.grid(row=2, column=0, sticky="ew", pady=4)
        self._solo_button = self._editor_button(
            self._track_controls, "audio_editor.solo", self._toggle_selected_track_solo
        )
        self._solo_button.grid(row=3, column=0, sticky="ew", pady=4)
        self._bind_property_scroll(content)
        self._inspector_panel.grid_remove()

    def _bind_property_scroll(self, widget):
        def scroll(event):
            self._properties_canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"

        widget.bind("<MouseWheel>", scroll, add="+")
        for child in widget.winfo_children():
            self._bind_property_scroll(child)

    def _resize_sources(self, event):
        self._set_source_width(event.x_root - self._source_panel.winfo_rootx())

    def _set_source_width(self, width):
        self._preferred_source_width = max(180, min(600, width))
        self._layout_panels()
        return "break"

    def _section(self, parent, key, row):
        ttk.Label(parent, text=self.translate(key), style="Editor.Section.TLabel").grid(
            row=row, column=0, sticky="w", pady=(12 if row else 0, 8)
        )

    def _field_pair(self, parent, row, *fields):
        group = ttk.Frame(parent, style="Editor.Panel.TFrame")
        group.grid(row=row, column=0, sticky="ew", pady=(0, 5))
        for column, (key, variable) in enumerate(fields):
            group.columnconfigure(column, weight=1)
            ttk.Label(group, text=self.translate(key), style="Editor.Muted.TLabel").grid(
                row=0, column=column, sticky="w"
            )
            entry = ttk.Entry(group, textvariable=variable, width=9)
            entry.grid(
                row=1, column=column, sticky="ew", padx=(0, 6 if column == 0 and len(fields) > 1 else 0), pady=(4, 4)
            )
            self._property_entries.append(entry)

    def _property_action(self, parent, key, command, row):
        button = self._editor_button(parent, key, command)
        button.grid(row=row, column=0, sticky="ew", pady=3)
        self._property_buttons.append(button)

    def _toggle_inspector(self):
        self._inspector_visible = not self._inspector_visible
        self._layout_panels()

    def _show_properties(self):
        self._inspector_visible = True
        self._layout_panels()

    def _toggle_sources(self):
        self._sources_visible = not self._sources_visible
        if self._sources_visible and self.winfo_width() < 1100:
            self._inspector_visible = False
        self._layout_panels()

    def _schedule_panel_layout(self, event):
        if event.widget in (self, self._timeline_center) and self._panel_layout_id is None:
            self._panel_layout_id = self.after_idle(self._layout_panels)

    def _layout_panels(self):
        self._panel_layout_id = None
        narrow = self.winfo_width() < 1100
        show_sources = self._sources_visible and not (narrow and self._inspector_visible)
        (self._source_panel.grid if show_sources else self._source_panel.grid_remove)()
        (self._inspector_panel.grid if self._inspector_visible else self._inspector_panel.grid_remove)()
        self._sources_button.state(["selected"] if show_sources else ["!selected"])
        self._properties_button.state(["selected"] if self._inspector_visible else ["!selected"])
        (self._editor_title.grid_remove if narrow else self._editor_title.grid)()
        if narrow:
            self._undo_button.pack_forget()
            self._redo_button.pack_forget()
        else:
            self._undo_button.pack(side="left", padx=(8, 2), after=self._properties_button)
            self._redo_button.pack(side="left", padx=2, after=self._undo_button)
        required_header_width = self._editor_actions.winfo_reqwidth() + self._export_tools.winfo_reqwidth() + 32
        if not narrow:
            required_header_width += self._editor_title.winfo_reqwidth() + 20
        stacked_header = required_header_width > self.winfo_width()
        self._export_tools.grid_configure(
            row=1 if stacked_header else 0, column=1 if stacked_header else 2, pady=(8, 0) if stacked_header else 0
        )
        if show_sources:
            reserve = 320 if self._inspector_visible else 0
            maximum = max(180, self.winfo_width() - reserve - 480)
            width = min(getattr(self, "_preferred_source_width", 240), maximum)
            self._source_panel.configure(width=width)
            self._source_grip.place(x=width + 1, y=0, relheight=1)
        else:
            self._source_grip.place_forget()
        crowded = (
            self._mode_tools.winfo_reqwidth() + self._zoom_tools.winfo_reqwidth() + 24
            > self._timeline_center.winfo_width()
        )
        self._zoom_tools.grid_configure(
            row=1 if crowded else 0,
            column=0 if crowded else 1,
            sticky="w" if crowded else "e",
            pady=(6, 0) if crowded else 0,
        )
        if hasattr(self, "_status_label"):
            self._status_label.configure(wraplength=max(300, self.winfo_width() - 40))

    def _fit_project(self):
        self.timeline.cancel_drag()
        available = max(100, self.timeline.canvas.winfo_width() - 144)
        self.timeline.pixels_per_second = min(480, max(0.05, available / max(self._project.duration, 1)))
        self.timeline.canvas.xview_moveto(0)
        self.timeline.redraw()
        self._refresh_zoom_label()

    def _show_editor_help(self):
        messagebox.showinfo(
            self.translate("audio_editor.help"),
            self.translate("audio_editor.marker_hint") + "\n\n" + self.translate("audio_editor.shortcuts_hint"),
            parent=self,
        )

    def _context_action_enabled(self, action):
        if self._render_busy:
            return False
        if action == "interact":
            return True
        if action == "paste":
            return bool(self._clipboard)
        if action in ("start_here", "end_here", "listen_start", "listen_end"):
            return self._quick_trim_clip() is not None
        selected = self._selected_clip_entries()
        if not selected:
            return False
        if action == "split":
            primary = next(clip for _, _, clip in selected if clip.id == self.timeline.selected_clip_id)
            cursor = self.timeline.playhead_position
            if self._mode == AudioEditMode.SEQUENCE:
                return all(0 < cursor - primary.timeline_start < clip.duration for _, _, clip in selected)
            return all(clip.timeline_start < cursor < clip.timeline_end for _, _, clip in selected)
        return True

    def _update_edit_menu(self):
        self._edit_menu.delete(0, "end")
        selected = bool(self.timeline.selected_clip_ids)
        for key, accelerator, action, enabled in (
            ("audio_editor.undo", "Ctrl+Z", self._undo, bool(self._undo_stack)),
            ("audio_editor.redo", "Ctrl+Y", self._redo, bool(self._redo_stack)),
            ("audio_editor.context_copy", "Ctrl+C", self._copy_selected_clips, selected),
            ("audio_editor.context_cut", "Ctrl+X", self._cut_selected_clips, selected),
            ("audio_editor.context_paste", "Ctrl+V", self._paste_clips, bool(self._clipboard)),
            ("audio_editor.context_duplicate", "Ctrl+D", self._duplicate_selected_clips, selected),
            ("audio_editor.split_at_cursor", "S", self._split_at_cursor, self._context_action_enabled("split")),
            ("audio_editor.start_here", "", lambda: self._trim_at_cursor("left"), self._quick_trim_clip() is not None),
            ("audio_editor.end_here", "", lambda: self._trim_at_cursor("right"), self._quick_trim_clip() is not None),
            ("audio_editor.listen_start", "", lambda: self._audition_edge("left"), self._quick_trim_clip() is not None),
            ("audio_editor.listen_end", "", lambda: self._audition_edge("right"), self._quick_trim_clip() is not None),
            ("audio_editor.cursor_start", "Home", lambda: self._navigate_cursor("start"), self._project.duration > 0),
            ("audio_editor.cursor_end", "End", lambda: self._navigate_cursor("end"), self._project.duration > 0),
            ("audio_editor.cursor_back", "Left", lambda: self._navigate_cursor("backward"), self._project.duration > 0),
            (
                "audio_editor.cursor_forward",
                "Right",
                lambda: self._navigate_cursor("forward"),
                self._project.duration > 0,
            ),
            (
                "audio_editor.cursor_back_fine",
                "Shift+Left",
                lambda: self._navigate_cursor("backward", step=0.01),
                self._project.duration > 0,
            ),
            (
                "audio_editor.cursor_forward_fine",
                "Shift+Right",
                lambda: self._navigate_cursor("forward", step=0.01),
                self._project.duration > 0,
            ),
            ("audio_editor.delete_clip", "Delete", self._remove_selected_clip, selected),
            ("audio_editor.move_to_cursor", "", self._move_selected_clip_to_cursor, selected),
            ("audio_editor.move_earlier", "", lambda: self._move_selected_clip(-1), selected),
            ("audio_editor.move_later", "", lambda: self._move_selected_clip(1), selected),
            ("audio_editor.properties", "", self._show_properties, selected),
        ):
            self._edit_menu.add_command(
                label=self.translate(key),
                accelerator=accelerator,
                command=lambda action=action: self._run_editor_action(action),
                state="normal" if enabled and not self._render_busy else "disabled",
            )

    def _sync_property_selection(self):
        clips = [
            clip for track in self._project.tracks for clip in track.clips if clip.id in self.timeline.selected_clip_ids
        ]
        enabled = bool(clips) and not self._render_busy
        for widget in self._property_entries + self._property_buttons:
            widget.configure(state="normal" if enabled else "disabled")
        for widget in self._quick_trim_buttons:
            widget.configure(state="normal" if enabled and len(clips) == 1 else "disabled")
        if not clips:
            self._selection_title.set(self.translate("audio_editor.select_clip_first"))
            for variable in (
                self._range_start_var,
                self._range_end_var,
                self._fade_in_var,
                self._fade_out_var,
                self._clip_gain_var,
                self._clip_pan_var,
                self._crossfade_duration_var,
            ):
                variable.set("")
        else:
            self._selection_title.set(
                self.translate("audio_editor.selected_clips", count=len(clips))
                if len(clips) > 1
                else clips[0].source_path.name
            )
            if len(clips) > 1:
                for attribute, variable in (
                    ("gain_db", self._clip_gain_var),
                    ("pan", self._clip_pan_var),
                    ("fade_in", self._fade_in_var),
                    ("fade_out", self._fade_out_var),
                ):
                    if len({getattr(clip, attribute) for clip in clips}) > 1:
                        variable.set("")
        self._range_hint.configure(text=self.translate("audio_editor.multiple_hint") if len(clips) > 1 else "")
        if len(clips) == 1:
            clip = clips[0]
            waveform = self._waveforms.get(clip.source_path)
            self._range_hint.configure(
                text=self.translate(
                    "audio_editor.trim_summary",
                    start=f"{clip.source_start:.2f}",
                    end=f"{max(0, waveform.duration - clip.source_end):.2f}" if waveform else "—",
                    duration=f"{clip.duration:.2f}",
                )
            )
        track = next(
            (
                track
                for track in self._project.tracks
                if any(clip.id == self.timeline.selected_clip_id for clip in track.clips)
            ),
            None,
        )
        for widget in (self._track_volume, self._mute_button, self._solo_button):
            widget.configure(state="normal" if track is not None and not self._render_busy else "disabled")
        if self._mode == AudioEditMode.SEQUENCE:
            self._mute_button.configure(state="disabled")
            self._solo_button.configure(state="disabled")
        self._mute_button.state(["selected"] if track and track.muted else ["!selected"])
        self._solo_button.state(["selected"] if track and track.solo else ["!selected"])
        self._undo_button.configure(state="normal" if self._undo_stack and not self._render_busy else "disabled")
        self._redo_button.configure(state="normal" if self._redo_stack and not self._render_busy else "disabled")

    def _configure_editor_styles(self, font=None):
        colors = self.colors
        style = ttk.Style(self)
        font = font or style.lookup("TLabel", "font") or ("Segoe UI", 10)
        surface = colors["surface"]
        for name in ("Editor.TFrame", "Editor.Panel.TFrame"):
            style.configure(name, background=surface)
        for name in (
            "Editor.TLabel",
            "Editor.Title.TLabel",
            "Editor.Section.TLabel",
            "Editor.Muted.TLabel",
            "Editor.Time.TLabel",
        ):
            style.configure(name, background=surface, foreground=colors["text"], font=font, padding=0)
        actual = tkfont.Font(font=font).actual()
        family, size = actual["family"], actual["size"]
        style.configure("Editor.Title.TLabel", font=(family, size + 1, "bold"))
        style.configure("Editor.Section.TLabel", font=(family, size, "bold"))
        style.configure("Editor.Time.TLabel", font=("Consolas", size + 2))
        style.configure("Editor.Muted.TLabel", foreground=colors["text_secondary"])
        inherited_padding = style.lookup("TButton", "padding") or (12, 8)
        padding = tuple(max(3, round(float(str(value)) * 0.65)) for value in self.tk.splitlist(inherited_padding))
        style.configure(
            "Editor.TButton",
            font=font,
            padding=padding,
            background=colors["surface_alt"],
            foreground=colors["text"],
            borderwidth=1,
            bordercolor=colors["border_soft"],
        )
        style.map(
            "Editor.TButton",
            background=[
                ("selected", colors["surface_alt"]),
                ("pressed", colors["surface_alt"]),
                ("active", colors.get("secondary_hover", colors["border"])),
            ],
            foreground=[
                ("disabled", colors.get("disabled", colors["text_secondary"])),
                ("selected", colors["highlight"]),
                ("pressed", colors["text"]),
            ],
        )
        style.configure(
            "Editor.Primary.TButton",
            font=font,
            padding=padding,
            background=colors.get("primary", colors["highlight"]),
            foreground=colors.get("button_text", colors["highlight_text"]),
        )
        style.map(
            "Editor.Primary.TButton",
            background=[("active", colors.get("primary_hover", colors["highlight"]))],
            foreground=[("disabled", colors["text_secondary"])],
        )
        style.configure("Editor.TCheckbutton", font=font, background=surface, foreground=colors["text"])
        style.configure(
            "Editor.TMenubutton",
            font=font,
            padding=padding,
            background=colors["surface_alt"],
            foreground=colors["text"],
        )

    def _style_editor_dialog(self, dialog):
        dialog.configure(background=self.colors["surface"])

        def visit(parent):
            for widget in parent.winfo_children():
                if isinstance(widget, tk.Listbox):
                    widget.configure(
                        background=self.colors["field"],
                        foreground=self.colors["text"],
                        selectbackground=self.colors["highlight"],
                        selectforeground=self.colors["highlight_text"],
                        highlightbackground=self.colors["border"],
                        highlightcolor=self.colors["highlight"],
                    )
                elif isinstance(widget, ttk.Button):
                    primary = widget.cget("text") == self.translate("audio_editor.apply_processing")
                    widget.configure(style="Editor.Primary.TButton" if primary else "Editor.TButton")
                visit(widget)

        visit(dialog)

    def refresh_theme(self, colors, font=None):
        self.colors = dict(colors)
        theme_window_caption(self, colors)
        self.configure(background=colors["background"])
        self._configure_editor_styles(font)
        self.timeline.colors = self.colors
        self.timeline.canvas.configure(background=colors["background"])
        self.timeline.redraw()
        self.source_list.configure(
            background=colors["field"],
            foreground=colors["text"],
            selectbackground=colors["highlight"],
            selectforeground=colors["highlight_text"],
            highlightbackground=colors["border_soft"],
            highlightcolor=colors["highlight"],
        )
        if font:
            self.source_list.configure(font=font)
        self._properties_canvas.configure(background=colors["surface"])
        self._source_grip.configure(background=colors["border_soft"])
        self._project_menu.configure(
            background=colors["surface"],
            foreground=colors["text"],
            activebackground=colors["highlight"],
            activeforeground=colors["highlight_text"],
        )
        self._edit_menu.configure(
            background=colors["surface"],
            foreground=colors["text"],
            activebackground=colors["highlight"],
            activeforeground=colors["highlight_text"],
        )

        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                self._style_editor_dialog(child)
