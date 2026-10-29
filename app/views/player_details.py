"""Small, cache-backed playback queue and metadata status view."""

import tkinter as tk
from dataclasses import dataclass
from io import BytesIO
from tkinter import ttk

from PIL import Image, ImageTk

from ..ui_helpers.widgets import ToolTip
from ..utils.audio_utils import AudioUtils


@dataclass
class QueueRow:
    frame: ttk.Frame
    cover: ttk.Label
    number: ttk.Label
    title: ttk.Label
    subtitle: ttk.Label
    duration: ttk.Label


class PlayerDetails(ttk.Frame):
    def __init__(self, parent, translator):
        super().__init__(parent, style="Player.TFrame")
        self.t = translator
        self.track = None
        self.upcoming = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.heading = ttk.Label(self, style="PlayerDetailsHeading.TLabel")
        self.heading.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.rows = []
        self._photos = {}
        self._tooltips = []
        self.status = ttk.Label(self, style="PlayerDetailsMuted.TLabel", wraplength=500)
        self.status.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        queue = ttk.Frame(self, style="Player.TFrame")
        queue.grid(row=2, column=0, sticky="nsew")
        queue.rowconfigure(0, weight=1)
        queue.columnconfigure(0, weight=1)
        self.viewport = tk.Canvas(queue, width=1, height=1, highlightthickness=0, borderwidth=0)
        self.viewport.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(queue, orient="vertical", command=self.viewport.yview)
        self.viewport.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.viewport, style="Player.TFrame")
        self.content.columnconfigure(0, weight=1)
        self.content_window = self.viewport.create_window(0, 0, anchor="nw", window=self.content)
        self.viewport.bind("<Configure>", self._resize_viewport)
        self.content.bind("<Configure>", self._update_scrollregion)
        self.viewport.bind("<MouseWheel>", self._scroll)
        for index in range(5):
            row = ttk.Frame(self.content, style="Player.TFrame")
            row.grid(row=index + 1, column=0, sticky="ew", pady=1)
            row.columnconfigure(2, weight=1)
            number = ttk.Label(row, width=5, anchor="e", style="PlayerDetailsHeading.TLabel")
            number.grid(row=0, column=0, rowspan=2, padx=(0, 8))
            cover = ttk.Label(row, text="♫", anchor="center", width=3, style="PlayerDetails.TLabel")
            cover.grid(row=0, column=1, rowspan=2, padx=(0, 8))
            title = ttk.Label(row, width=1, style="PlayerDetails.TLabel")
            title.grid(row=0, column=2, sticky="ew")
            subtitle = ttk.Label(row, width=1, style="PlayerDetailsMuted.TLabel")
            subtitle.grid(row=1, column=2, sticky="ew", pady=(1, 4))
            duration = ttk.Label(row, style="PlayerDetailsMuted.TLabel")
            duration.grid(row=0, column=3, rowspan=2, padx=(8, 0))
            self.rows.append(QueueRow(row, cover, number, title, subtitle, duration))
            for widget in (row, cover, number, title, subtitle, duration):
                widget.bind("<MouseWheel>", self._scroll)
            self._tooltips.append(ToolTip(title, lambda title=title: str(title.cget("text"))))
            self._tooltips.append(ToolTip(subtitle, lambda subtitle=subtitle: str(subtitle.cget("text"))))
        self.bind("<Configure>", lambda event: self.status.configure(wraplength=max(1, event.width)))
        self.refresh_theme()
        self.render()

    def refresh_theme(self):
        self.viewport.configure(background=ttk.Style().lookup("Player.TFrame", "background"))

    def fit_height(self, height):
        """Prefer queue rows over secondary metadata when vertical space is scarce."""
        row = self.rows[0]
        line_height = max(28, row.title.winfo_reqheight(), row.duration.winfo_reqheight())
        heading_height = self.heading.winfo_reqheight()
        full_height = (
            heading_height + 4 + self.status.winfo_reqheight() + 6 + line_height + row.subtitle.winfo_reqheight() + 7
        )
        compact = height < full_height
        if getattr(self, "_compact", None) != compact:
            self._compact = compact
            self.heading.grid_configure(pady=(0, 2 if compact else 4))
            if compact:
                self.status.grid_remove()
            else:
                self.status.grid()
            for widgets in self.rows:
                if compact:
                    widgets.subtitle.grid_remove()
                else:
                    widgets.subtitle.grid()
                for widget in (widgets.cover, widgets.number, widgets.duration):
                    widget.grid_configure(rowspan=1 if compact else 2)
            self.viewport.yview_moveto(0)
        return height >= heading_height + 2 + line_height + 4

    def _resize_viewport(self, event):
        self.viewport.itemconfigure(self.content_window, width=max(1, event.width))
        self._update_scrollregion()

    def _update_scrollregion(self, _event=None):
        self.viewport.configure(scrollregion=self.viewport.bbox("all"))
        if self.content.winfo_reqheight() > self.viewport.winfo_height():
            self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        else:
            self.scrollbar.grid_remove()
            self.viewport.yview_moveto(0)

    def _scroll(self, event):
        if self.content.winfo_reqheight() > self.viewport.winfo_height():
            self.viewport.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def update_context(self, track, upcoming, *, repeat=False):
        changed = (self.track.filepath if self.track else None) != (track.filepath if track else None)
        self.track = track
        self.upcoming = upcoming[:5]
        self.render(repeat=repeat)
        if changed:
            self.viewport.yview_moveto(0)

    def render(self, *, repeat=False):
        self.heading.configure(text=self.t("player.up_next_repeat" if repeat else "player.up_next"))
        photos = {}
        for index, widgets in enumerate(self.rows):
            row, cover, title, duration = widgets.frame, widgets.cover, widgets.title, widgets.duration
            if index >= len(self.upcoming):
                if index == 0:
                    row.grid()
                    cover.configure(image="", text="♫")
                    title.configure(text=self.t("player.queue_empty" if self.track else "player.queue_start"))
                    duration.configure(text="")
                    widgets.number.configure(text="")
                    widgets.subtitle.configure(text="")
                else:
                    row.grid_remove()
                continue
            row.grid()
            track = self.upcoming[index]
            name = track.metadata.get("title") or track.filename
            artist = track.metadata.get("artist") or ""
            album = track.metadata.get("album") or self.t("player.queue_no_album")
            title.configure(text=name)
            widgets.subtitle.configure(text=f"{artist} · {album}" if artist else album)
            value = track.metadata.get("track_number")
            number = str(value).strip() if value is not None else ""
            widgets.number.configure(text=f"#{number}" if number else "—")
            duration.configure(text=AudioUtils.format_time(track.duration))
            photo = None
            if track.cover_art:
                key = (track.filepath, id(track.cover_art))
                photo = self._photos.get(key)
                if photo is None:
                    try:
                        with Image.open(BytesIO(track.cover_art)) as source:
                            photo = ImageTk.PhotoImage(source.convert("RGB").resize((28, 28), Image.Resampling.LANCZOS))
                    except (OSError, ValueError):
                        pass
                photos[key] = photo
            cover.configure(image=photo or "", text="" if photo else "♫")
        self._photos = photos
        if self.track:
            complete = all(
                str(self.track.metadata.get(key, "") or "").strip()
                for key in ("title", "artist", "album", "year", "track_number")
            )
            statuses = [
                self.t("player.status_locked" if self.track.is_track_locked else "player.status_unlocked"),
                self.t("player.status_cover" if self.track.cover_art else "player.status_no_cover"),
                self.t("player.status_complete" if complete else "player.status_incomplete"),
            ]
            self.status.configure(text="  ·  ".join(statuses))
        else:
            self.status.configure(text="")
