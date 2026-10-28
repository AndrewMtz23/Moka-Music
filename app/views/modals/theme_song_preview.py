"""Isolated theme sample; never changes application styles or playback."""

import tkinter as tk
from io import BytesIO

from PIL import Image, ImageDraw, ImageTk

from ...utils.audio_utils import AudioUtils


class ThemeSongPreview(tk.Frame):
    def __init__(self, parent, translator, song=None):
        super().__init__(parent, borderwidth=0)
        self.t = translator
        self.song = dict(song or {})
        self.columnconfigure(1, weight=1)
        self.disc = tk.Canvas(self, width=90, height=90, borderwidth=0, highlightthickness=0)
        self.disc.grid(row=0, column=0, rowspan=3, padx=(0, 12))
        self.title = tk.Label(self, text=self.song.get("title") or self.t("player.no_track"), anchor="w", width=1)
        self.title.grid(row=0, column=1, sticky="ew")
        subtitle = " · ".join(str(self.song.get(key) or "") for key in ("artist", "album") if self.song.get(key))
        self.subtitle = tk.Label(self, text=subtitle, anchor="w", width=1)
        self.subtitle.grid(row=1, column=1, sticky="ew")
        number = self.song.get("track_number")
        track = f"{self.t('preview.track')}: {number}" if number is not None and str(number).strip() else ""
        duration = AudioUtils.format_time(self.song.get("duration") or 0)
        self.info = tk.Label(
            self, text=" · ".join(value for value in (track, duration if self.song else "") if value), anchor="w"
        )
        self.info.grid(row=2, column=1, sticky="ew")
        self.play = tk.Label(self, text="▶", padx=12, pady=6)
        self.play.grid(row=0, column=2, rowspan=3, padx=(12, 0))
        self.photo = self._load_cover(self.song.get("cover_art"))

    def _load_cover(self, cover):
        try:
            if not cover:
                return None
            with Image.open(BytesIO(cover) if isinstance(cover, bytes) else cover) as source:
                image = source.convert("RGBA").resize((78, 78), Image.Resampling.LANCZOS)
            mask = Image.new("L", (78, 78), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 77, 77), fill=255)
            image.putalpha(mask)
            return ImageTk.PhotoImage(image, master=self)
        except (OSError, ValueError, TypeError):
            return None

    def apply_appearance(self, palette, font_scale, density):
        self.configure(background=palette["surface"])
        for label in (self.title, self.subtitle, self.info):
            label.configure(
                background=palette["surface"],
                foreground=palette["text_secondary"],
                font=("Segoe UI", max(8, int(9 * font_scale))),
            )
        self.title.configure(foreground=palette["text"], font=("Segoe UI Semibold", max(9, int(11 * font_scale))))
        self.play.configure(
            background=palette["primary"],
            foreground=palette["button_text"],
            font=("Segoe UI", max(12, int(16 * font_scale))),
        )
        self.grid_configure(pady=(8, {"compact": 6, "normal": 10, "comfortable": 14}.get(density, 10)))
        self.disc.configure(background=palette["surface"])
        self.disc.delete("all")
        self.disc.create_oval(5, 5, 85, 85, fill=palette["surface_alt"], outline=palette["border"])
        if self.photo:
            self.disc.create_image(45, 45, image=self.photo)
        self.disc.create_oval(34, 34, 56, 56, fill=palette["surface"], outline=palette["border"])
        self.disc.create_oval(42, 42, 48, 48, fill=palette["primary"], outline="")
        self.disc.create_line(47, 48, 82, 77, fill=palette["primary"], width=2)
