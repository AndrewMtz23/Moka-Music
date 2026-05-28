import logging
import math
import os
import random
import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
from PIL import Image, ImageDraw, ImageTk

if __name__ == "__main__" and not __package__:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from main import main

    raise SystemExit(main())

from ..controllers.playback_controller import PlaybackController
from ..i18n import I18n
from ..services.song_info_service import SongInfo
from ..utils.audio_utils import AudioUtils
from ..ui_helpers.widgets import ToolTip


class PlayerControls(ttk.Frame):
    ICON_PREV = "\u25c0\u25c0"
    ICON_PLAY = "\u25b6"
    ICON_PAUSE = "\u2161"
    ICON_STOP = "\u23f9"
    ICON_NEXT = "\u25b6\u25b6"
    ICON_REPEAT = "\u21bb"
    ICON_SHUFFLE = "\u21c4"
    ICON_BACK_10 = "\u21b6 10"
    ICON_FORWARD_10 = "10 \u21b7"

    def __init__(
        self,
        parent,
        translator: Optional[Callable[..., str]] = None,
        theme_colors: Optional[Callable[[], dict[str, str]]] = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.t = translator or I18n().t
        self._theme_colors = theme_colors
        self.style = ttk.Style()
        self.playback = PlaybackController()
        self.song_info = SongInfo()
        self.on_track_end: Optional[Callable[[], None]] = None
        self.on_next_requested: Optional[Callable[[], None]] = None
        self.on_prev_requested: Optional[Callable[[], None]] = None
        self.repeat_var = tk.BooleanVar(value=False)
        self.shuffle_var = tk.BooleanVar(value=False)
        self._last_position = 0.0
        self._progress_job: Optional[str] = None
        self._visualizer_job: Optional[str] = None
        self._visualizer_bars = 34
        self._visualizer_values = [0.05 for _index in range(self._visualizer_bars)]
        self._visualizer_seed = random.random() * 100.0
        self._tooltips: list[ToolTip] = []
        self._cover_photo = None
        self._current_title = self.t("player.no_track")
        self._current_artist = ""
        self._progress_ratio = 0.0

        self._setup_styles()
        self._setup_ui()
        self._start_progress_loop()

    def _play_pause_icon(self) -> str:
        return self.ICON_PAUSE if self.playback.state().is_playing else self.ICON_PLAY

    def _setup_styles(self) -> None:
        self._sync_theme_colors()
        self.style.configure("Player.TFrame", background=self._player_bg)
        self.style.configure("PlayerCard.TFrame", background=self._player_card)
        self.style.configure(
            "PlayerTitle.TLabel",
            background=self._player_card,
            foreground=self._player_text,
            font=("Segoe UI Semibold", 13),
            padding=(2, 1),
        )
        self.style.configure(
            "PlayerMuted.TLabel",
            background=self._player_card,
            foreground=self._player_muted,
            font=("Segoe UI", 9),
            padding=(2, 1),
        )
        self.style.configure(
            "PlayerTiny.TLabel",
            background=self._player_card,
            foreground=self._player_muted,
            font=("Segoe UI", 8),
            padding=(0, 0),
        )
        self.style.configure(
            "PlayerIcon.TButton",
            font=("Segoe UI Symbol", 14),
            foreground=self._player_text,
            background=self._player_card,
            borderwidth=0,
            focusthickness=0,
            relief="flat",
            padding=(8, 6),
        )
        self.style.map(
            "PlayerIcon.TButton",
            background=[("active", self._player_secondary), ("pressed", self._player_border)],
            foreground=[("!disabled", self._player_text)],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        self.style.configure(
            "PlayerPrimary.TButton",
            font=("Segoe UI Symbol", 18),
            foreground=self._player_primary_text,
            background=self._player_primary,
            borderwidth=0,
            focusthickness=0,
            relief="flat",
            padding=(15, 9),
        )
        self.style.map(
            "PlayerPrimary.TButton",
            background=[("active", self._player_primary_hover), ("pressed", self._player_primary_hover)],
            foreground=[("!disabled", self._player_primary_text)],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        self.style.configure(
            "PlayerRaised.TButton",
            font=("Segoe UI Symbol", 15),
            foreground=self._player_text,
            background=self._player_secondary,
            borderwidth=0,
            focusthickness=0,
            relief="flat",
            padding=(12, 8),
        )
        self.style.map(
            "PlayerRaised.TButton",
            background=[("active", self._player_border), ("pressed", self._player_border)],
            foreground=[("!disabled", self._player_text)],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        self.style.configure(
            "Player.Horizontal.TProgressbar",
            background=self._player_primary,
            troughcolor=self._player_progress_track,
            bordercolor=self._player_progress_track,
            lightcolor=self._player_primary,
            darkcolor=self._player_primary,
            thickness=3,
        )
        self.style.configure(
            "Player.Horizontal.TScale",
            background=self._player_card,
            troughcolor=self._player_progress_track,
            bordercolor=self._player_border,
            lightcolor=self._player_primary,
            darkcolor=self._player_primary,
        )

    def _sync_theme_colors(self) -> None:
        palette = self._theme_colors() if self._theme_colors else {}
        self._player_bg = palette.get("background", "#f4f6fb")
        self._player_card = palette.get("surface", "#ffffff")
        self._player_secondary = palette.get("surface_alt", "#f8fafc")
        self._player_text = palette.get("text", "#111827")
        self._player_muted = palette.get("text_secondary", "#7c8492")
        self._player_primary = palette.get("highlight", palette.get("primary", "#2563eb"))
        self._player_primary_hover = palette.get("primary_hover", self._player_primary)
        self._player_primary_text = palette.get("highlight_text", palette.get("button_text", "#ffffff"))
        self._player_border = palette.get("border_soft", "#d7dbe3")
        self._player_progress_track = palette.get("border", self._player_border)
        if self._is_dark(self._player_bg):
            self._player_shadow_deep = self._blend(self._player_bg, "#000000", 0.38)
            self._player_shadow_soft = self._blend(self._player_card, "#ffffff", 0.08)
            self._player_vinyl_shadow = self._blend(self._player_bg, "#000000", 0.42)
        else:
            self._player_shadow_deep = "#d6dbe7"
            self._player_shadow_soft = "#edf0f6"
            self._player_vinyl_shadow = "#c8cfdd"

    def _is_dark(self, color: str) -> bool:
        red, green, blue = self._hex_to_rgb(color, fallback=(244, 246, 251))
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        return luminance < 128

    def _blend(self, color: str, other: str, ratio: float) -> str:
        red, green, blue = self._hex_to_rgb(color, fallback=(244, 246, 251))
        other_red, other_green, other_blue = self._hex_to_rgb(other, fallback=(255, 255, 255))
        ratio = max(0.0, min(1.0, ratio))
        mixed = (
            int(red + (other_red - red) * ratio),
            int(green + (other_green - green) * ratio),
            int(blue + (other_blue - blue) * ratio),
        )
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"

    def _hex_to_rgb(self, color: str, *, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
            return fallback
        try:
            return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        except ValueError:
            return fallback

    def _setup_ui(self) -> None:
        self.configure(style="Player.TFrame")
        self.main_frame = ttk.Frame(self, style="Player.TFrame")
        self.main_frame.pack(fill="both", expand=True, padx=(64, 14), pady=10)

        self.shadow_canvas = tk.Canvas(self.main_frame, height=230, borderwidth=0, highlightthickness=0, background=self._player_bg)
        self.shadow_canvas.pack(fill="both", expand=True)
        self.shadow_canvas.bind("<Configure>", lambda _event: self._draw_player_shell())

        self.card_frame = ttk.Frame(self.main_frame, style="PlayerCard.TFrame")
        self.card_window = self.shadow_canvas.create_window(112, 22, anchor="nw", window=self.card_frame, width=1, height=1)
        self.vinyl_canvas = tk.Canvas(self.main_frame, width=166, height=166, borderwidth=0, highlightthickness=0, background=self._player_bg)
        self.vinyl_window = self.shadow_canvas.create_window(0, 16, anchor="nw", window=self.vinyl_canvas)
        self.vinyl_canvas.bind("<Configure>", lambda _event: self._draw_vinyl())

        self.card_frame.columnconfigure(0, weight=1)

        top_row = ttk.Frame(self.card_frame, style="PlayerCard.TFrame")
        top_row.grid(row=0, column=0, sticky="ew", padx=(82, 22), pady=(18, 0))
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=0)
        top_row.columnconfigure(2, weight=0)

        text_frame = ttk.Frame(top_row, style="PlayerCard.TFrame")
        text_frame.grid(row=0, column=0, sticky="ew")

        self.track_info_label = ttk.Label(
            text_frame,
            text=self.t("player.no_track"),
            anchor="w",
            style="PlayerTitle.TLabel",
        )
        self.track_info_label.pack(fill="x")

        self.artist_label = ttk.Label(
            text_frame,
            text="",
            anchor="w",
            style="PlayerMuted.TLabel",
        )
        self.artist_label.pack(fill="x")

        self.mute_button = tk.Button(
            top_row,
            text="\U0001f50a",
            command=self._show_volume_modal,
            background=self._player_card,
            foreground=self._player_muted,
            activebackground=self._player_secondary,
            activeforeground=self._player_text,
            borderwidth=0,
            relief="flat",
            padx=7,
            pady=2,
            font=("Segoe UI Symbol", 12),
            cursor="hand2",
        )
        self.mute_button.grid(row=0, column=1, sticky="ne", padx=(8, 4))

        self.more_button = tk.Menubutton(
            top_row,
            text="⋯",
            background=self._player_card,
            foreground=self._player_muted,
            activebackground=self._player_secondary,
            activeforeground=self._player_text,
            borderwidth=0,
            relief="flat",
            padx=7,
            pady=2,
            font=("Segoe UI Semibold", 14),
        )
        self.more_button.grid(row=0, column=2, sticky="ne")
        self.more_menu = tk.Menu(
            self.more_button,
            tearoff=0,
            background=self._player_card,
            foreground=self._player_text,
            activebackground=self._player_primary,
            activeforeground=self._player_primary_text,
            borderwidth=0,
            relief="flat",
        )
        self.more_menu.add_checkbutton(label=self.t("player.shuffle"), variable=self.shuffle_var)
        self.more_menu.add_checkbutton(label=self.t("player.repeat"), variable=self.repeat_var)
        self.more_menu.add_separator()
        self.more_menu.add_command(label=self.t("player.volume_down"), command=lambda: self.adjust_volume(-0.1))
        self.more_menu.add_command(label=self.t("player.volume_up"), command=lambda: self.adjust_volume(0.1))
        self.more_menu.add_separator()
        self.more_menu.add_command(label=self.t("player.seek_back"), command=lambda: self.seek_relative(-10))
        self.more_menu.add_command(label=self.t("player.seek_forward"), command=lambda: self.seek_relative(10))
        self.more_menu.add_command(label=self.t("player.stop"), command=self.stop)
        self.more_button.configure(menu=self.more_menu)

        progress_frame = ttk.Frame(self.card_frame, style="PlayerCard.TFrame")
        progress_frame.grid(row=1, column=0, sticky="ew", padx=(82, 28), pady=(14, 0))
        progress_frame.columnconfigure(1, weight=1)

        self.time_label_start = ttk.Label(progress_frame, text="00:00", width=6, style="PlayerTiny.TLabel")
        self.time_label_start.grid(row=0, column=0, sticky="w")

        self.progress_bar = tk.Canvas(
            progress_frame,
            height=14,
            borderwidth=0,
            highlightthickness=0,
            background=self._player_card,
        )
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=7)
        self.progress_bar.bind("<Button-1>", self._on_progress_click)
        self.progress_bar.bind("<Configure>", lambda _event: self._draw_progress())
        self.progress_bar.configure(cursor="hand2")

        self.time_label_end = ttk.Label(progress_frame, text="00:00", width=6, anchor="e", style="PlayerTiny.TLabel")
        self.time_label_end.grid(row=0, column=2, sticky="e")

        transport_frame = ttk.Frame(self.card_frame, style="PlayerCard.TFrame")
        transport_frame.grid(row=2, column=0, sticky="ew", padx=(82, 28), pady=(12, 20))
        transport_frame.configure(height=86)
        transport_frame.grid_propagate(False)
        transport_inner = ttk.Frame(transport_frame, style="PlayerCard.TFrame")
        transport_inner.place(relx=0.5, y=22, anchor="center")

        self.btn_prev = ttk.Button(
            transport_inner,
            text=self.ICON_PREV,
            command=self.previous_track,
            width=5,
            style="PlayerIcon.TButton",
        )
        self.btn_prev.pack(side="left", padx=(0, 10))

        self.btn_play_pause = ttk.Button(
            transport_inner,
            text=self._play_pause_icon(),
            command=self.toggle_play_pause,
            width=4,
            style="PlayerPrimary.TButton",
        )
        self.btn_play_pause.pack(side="left", padx=(0, 10))

        self.btn_next = ttk.Button(
            transport_inner,
            text=self.ICON_NEXT,
            command=self.next_track,
            width=5,
            style="PlayerRaised.TButton",
        )
        self.btn_next.pack(side="left")

        secondary_frame = ttk.Frame(transport_frame, style="PlayerCard.TFrame")
        secondary_frame.place(relx=0.5, y=64, anchor="center")
        secondary_frame.columnconfigure(0, weight=0)

        self.volume_label = ttk.Label(self.card_frame, text=self.t("player.volume"), style="PlayerMuted.TLabel")
        self.volume_scale = ttk.Scale(
            self.card_frame,
            from_=0,
            to=1,
            orient="horizontal",
            length=86,
            command=self._on_volume_change,
            style="Player.Horizontal.TScale",
        )
        self.volume_scale.set(self.playback.volume)
        self._sync_volume_icon()

        self.shuffle_check = ttk.Checkbutton(secondary_frame, text=self.ICON_SHUFFLE, variable=self.shuffle_var)
        self.shuffle_check.pack(side="left", padx=(0, 2))
        self.repeat_check = ttk.Checkbutton(secondary_frame, text=self.ICON_REPEAT, variable=self.repeat_var)
        self.repeat_check.pack(side="left", padx=(0, 2))
        self.btn_seek_back = ttk.Button(
            secondary_frame,
            text=self.ICON_BACK_10,
            command=lambda: self.seek_relative(-10),
            width=6,
            style="PlayerIcon.TButton",
        )
        self.btn_seek_back.pack(side="left", padx=(2, 2))
        self.btn_seek_forward = ttk.Button(
            secondary_frame,
            text=self.ICON_FORWARD_10,
            command=lambda: self.seek_relative(10),
            width=6,
            style="PlayerIcon.TButton",
        )
        self.btn_seek_forward.pack(side="left", padx=(0, 2))
        self.btn_stop = ttk.Button(
            secondary_frame,
            text=self.ICON_STOP,
            command=self.stop,
            width=4,
            style="PlayerIcon.TButton",
        )
        self.btn_stop.pack(side="left")
        self.time_summary_label = ttk.Label(
            self.card_frame,
            text="00:00 / 00:00",
            anchor="center",
            style="PlayerMuted.TLabel",
        )
        self.visualizer_canvas = tk.Canvas(
            self.card_frame,
            height=1,
            borderwidth=0,
            highlightthickness=0,
            background=self._player_card,
        )
        self._draw_vinyl()
        self._draw_visualizer()
        self._register_tooltips()
        self._set_transport_enabled(False)

        if not self.playback.available:
            self.track_info_label.configure(text=self.t("player.audio_unavailable"))
            self._set_transport_enabled(False)
            self.repeat_check.state(["disabled"])
            self.shuffle_check.state(["disabled"])

    def _draw_player_shell(self) -> None:
        if not hasattr(self, "shadow_canvas"):
            return
        canvas = self.shadow_canvas
        canvas.delete("shell")
        width = max(1, canvas.winfo_width())
        height = max(212, canvas.winfo_height())
        card_x = 112
        card_y = 22
        card_w = max(260, width - card_x - 8)
        card_h = min(186, height - 34)
        canvas.coords(self.card_window, card_x, card_y)
        canvas.itemconfigure(self.card_window, width=card_w, height=card_h)
        canvas.coords(self.vinyl_window, 0, card_y - 5)
        self._rounded_rect(canvas, card_x + 7, card_y + 11, card_x + card_w + 2, card_y + card_h + 10, 20, fill=self._player_shadow_deep, outline="", tags="shell")
        self._rounded_rect(canvas, card_x + 3, card_y + 6, card_x + card_w + 1, card_y + card_h + 5, 20, fill=self._player_shadow_soft, outline="", tags="shell")
        self._rounded_rect(canvas, card_x, card_y, card_x + card_w, card_y + card_h, 20, fill=self._player_card, outline=self._player_border, tags="shell")
        canvas.tag_lower("shell")

    def _rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs) -> None:
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw_vinyl(self) -> None:
        if not hasattr(self, "vinyl_canvas"):
            return
        canvas = self.vinyl_canvas
        canvas.delete("all")
        size = 166
        canvas.create_oval(10, 16, size - 10, size - 4, fill=self._player_vinyl_shadow, outline="")
        if self._cover_photo is None:
            self._cover_photo = self._cover_photo_from_file(None)
        canvas.create_image(size // 2, size // 2, image=self._cover_photo)
        canvas.create_oval(59, 59, 107, 107, fill=self._player_card, outline=self._player_border, width=2)
        canvas.create_oval(77, 77, 89, 89, fill=self._player_border, outline="")
        canvas.create_line(88, 90, 150, 145, fill=self._player_primary, width=2)

    def _register_tooltips(self) -> None:
        tooltip_targets = [
            (self.btn_prev, "player.previous"),
            (self.btn_play_pause, "player.play_pause"),
            (self.btn_next, "player.next"),
            (self.more_button, "player.more"),
            (self.mute_button, "player.volume_hint"),
            (self.progress_bar, "player.seek_hint"),
        ]
        self._tooltips = [
            ToolTip(widget, lambda key=key: self.t(key))
            for widget, key in tooltip_targets
        ]

    def _set_transport_enabled(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled and self.playback.available else ["disabled"]
        for widget in (
            self.btn_play_pause,
            self.btn_stop,
            self.btn_prev,
            self.btn_next,
            self.btn_seek_back,
            self.btn_seek_forward,
        ):
            widget.state(state)

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator
        self.refresh_texts()

    def refresh_theme(self) -> None:
        self._setup_styles()
        self.configure(style="Player.TFrame")
        self.main_frame.configure(style="Player.TFrame")
        self.card_frame.configure(style="PlayerCard.TFrame")
        for canvas in (self.shadow_canvas, self.vinyl_canvas):
            canvas.configure(background=self._player_bg)
        self.progress_bar.configure(background=self._player_card)
        self.visualizer_canvas.configure(background=self._player_card)
        for button in (self.mute_button, self.more_button):
            button.configure(
                background=self._player_card,
                foreground=self._player_muted,
                activebackground=self._player_secondary,
                activeforeground=self._player_text,
            )
        self.more_menu.configure(
            background=self._player_card,
            foreground=self._player_text,
            activebackground=self._player_primary,
            activeforeground=self._player_primary_text,
        )
        self._draw_player_shell()
        self._draw_vinyl()
        self._draw_progress()

    def refresh_texts(self) -> None:
        self._setup_styles()
        self.btn_prev.configure(text=self.ICON_PREV)
        self.btn_next.configure(text=self.ICON_NEXT)
        self.btn_stop.configure(text=self.ICON_STOP)
        self.volume_label.configure(text=self.t("player.volume"))
        self.repeat_check.configure(text=self.ICON_REPEAT)
        self.shuffle_check.configure(text=self.ICON_SHUFFLE)
        self.more_menu.entryconfigure(0, label=self.t("player.shuffle"))
        self.more_menu.entryconfigure(1, label=self.t("player.repeat"))
        self.more_menu.entryconfigure(3, label=self.t("player.volume_down"))
        self.more_menu.entryconfigure(4, label=self.t("player.volume_up"))
        self.more_menu.entryconfigure(6, label=self.t("player.seek_back"))
        self.more_menu.entryconfigure(7, label=self.t("player.seek_forward"))
        self.more_menu.entryconfigure(8, label=self.t("player.stop"))
        self.btn_play_pause.configure(text=self._play_pause_icon())
        if not self.playback.available:
            self.track_info_label.configure(text=self.t("player.audio_unavailable"))
        elif not self.playback.current_file:
            self.track_info_label.configure(text=self.t("player.no_track"))
        self._sync_time_display(self.playback.last_position)

    def load_file(self, filepath: str) -> bool:
        try:
            state = self.playback.load(filepath)
            self._set_transport_enabled(True)
            self._reset_visualizer()
            self._set_progress_ratio(0)
            self._sync_time_display(state.position)
            self._update_track_identity(filepath)
            self.btn_play_pause.configure(text=self._play_pause_icon())
            return True
        except Exception as exc:
            self.logger.error("Error loading track %s: %s", filepath, exc)
            self.track_info_label.configure(text=self.t("player.audio_error", error=exc))
            return False

    def play(self) -> None:
        if not self.playback.current_file:
            return
        state = self.playback.play()
        self.btn_play_pause.configure(text=self._play_pause_icon())
        self.track_info_label.configure(text=self._current_title)
        self.artist_label.configure(text=self._current_artist)
        self._sync_time_display(state.position)

    def pause(self) -> None:
        if not self.playback.current_file:
            return
        state = self.playback.pause()
        self.btn_play_pause.configure(text=self._play_pause_icon())
        self.track_info_label.configure(text=self._current_title)
        self._sync_time_display(state.position)

    def stop(self) -> None:
        state = self.playback.stop()
        self._reset_visualizer()
        self.btn_play_pause.configure(text=self._play_pause_icon())
        self._set_progress_ratio(0)
        self._sync_time_display(state.position)
        if self.playback.current_file:
            self.track_info_label.configure(text=self._current_title)
        else:
            self.track_info_label.configure(text=self.t("player.no_track"))

    def restart_current_track(self) -> None:
        if not self.playback.current_file:
            return
        state = self.playback.restart()
        self._set_progress_ratio(0)
        self._sync_time_display(state.position)
        self.btn_play_pause.configure(text=self._play_pause_icon())

    def seek_relative(self, seconds: float) -> None:
        if not self.playback.current_file:
            return
        was_playing = self.playback.state().is_playing
        state = self.playback.seek_relative(seconds)
        self._sync_time_display(state.position)
        if not was_playing:
            self.artist_label.configure(text=self.t("player.seeked", position=AudioUtils.format_time(state.position)))

    def repeat_enabled(self) -> bool:
        return bool(self.repeat_var.get())

    def shuffle_enabled(self) -> bool:
        return bool(self.shuffle_var.get())

    def set_playback_modes(self, *, repeat: bool, shuffle: bool) -> None:
        self.repeat_var.set(bool(repeat))
        self.shuffle_var.set(bool(shuffle))

    def toggle_play_pause(self) -> None:
        if self.playback.state().is_playing:
            self.pause()
        else:
            self.play()

    def previous_track(self) -> None:
        if self.on_prev_requested:
            self.on_prev_requested()

    def next_track(self) -> None:
        if self.on_next_requested:
            self.on_next_requested()

    def _on_volume_change(self, value: str) -> None:
        try:
            self.playback.set_volume(float(value))
            self._sync_volume_icon()
        except Exception as exc:
            self.logger.error("Error changing volume: %s", exc)

    def adjust_volume(self, delta: float) -> None:
        next_volume = max(0.0, min(1.0, float(self.playback.volume) + float(delta)))
        self.volume_scale.set(next_volume)
        self.playback.set_volume(next_volume)
        self._sync_volume_icon()

    def _show_volume_modal(self) -> None:
        modal = tk.Toplevel(self)
        modal.title(self.t("player.volume_hint"))
        modal.configure(background=self._player_card)
        modal.resizable(False, False)
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        content = ttk.Frame(modal, style="PlayerCard.TFrame", padding=(18, 16))
        content.pack(fill="both", expand=True)

        title = ttk.Label(content, text=self.t("player.volume_hint"), style="PlayerTitle.TLabel")
        title.pack(anchor="w", pady=(0, 10))

        value_label = ttk.Label(content, text=f"{int(float(self.playback.volume or 0.0) * 100)}%", style="PlayerMuted.TLabel")
        value_label.pack(anchor="e")

        volume_var = tk.DoubleVar(value=float(self.playback.volume or 0.0))

        def update_volume(value: str) -> None:
            next_volume = max(0.0, min(1.0, float(value)))
            volume_var.set(next_volume)
            self.volume_scale.set(next_volume)
            self.playback.set_volume(next_volume)
            self._sync_volume_icon()
            value_label.configure(text=f"{int(next_volume * 100)}%")

        def step_volume(delta: float) -> None:
            update_volume(str(volume_var.get() + delta))

        slider = ttk.Scale(
            content,
            from_=0,
            to=1,
            orient="horizontal",
            length=260,
            variable=volume_var,
            command=update_volume,
            style="Player.Horizontal.TScale",
        )
        slider.pack(fill="x", pady=(2, 14))

        actions = ttk.Frame(content, style="PlayerCard.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text=self.t("player.volume_down"), command=lambda: step_volume(-0.1), style="PlayerIcon.TButton").pack(side="left")
        ttk.Button(actions, text=self.t("player.volume_up"), command=lambda: step_volume(0.1), style="PlayerIcon.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="OK", command=modal.destroy, style="PlayerPrimary.TButton").pack(side="right")

        modal.update_idletasks()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        modal.geometry(f"+{parent_x + max(20, self.winfo_width() - 340)}+{parent_y + 34}")
        slider.focus_set()

    def _toggle_mute(self) -> None:
        next_volume = 0.0 if float(self.playback.volume or 0.0) > 0.01 else 0.65
        self.volume_scale.set(next_volume)
        self.playback.set_volume(next_volume)
        self._sync_volume_icon()

    def _on_progress_click(self, event) -> None:
        state = self.playback.state()
        if not state.current_file or state.duration <= 0:
            return
        width = max(1, self.progress_bar.winfo_width())
        ratio = max(0.0, min(1.0, event.x / width))
        new_state = self.playback.seek_absolute(state.duration * ratio)
        self._sync_time_display(new_state.position)
        if new_state.current_file and not new_state.is_playing:
            self.artist_label.configure(text=self.t("player.seeked", position=AudioUtils.format_time(new_state.position)))

    def _start_progress_loop(self) -> None:
        self._update_progress()

    def _start_visualizer_loop(self) -> None:
        return

    def _update_progress(self) -> None:
        state = self.playback.state()
        if state.current_file:
            position = min(state.position, state.duration or 0.0)
            self._sync_time_display(position)

        if self.playback.poll_track_end():
            ended_state = self.playback.mark_ended()
            self._set_progress_ratio(1)
            self._sync_time_display(ended_state.duration)
            self.btn_play_pause.configure(text=self._play_pause_icon())
            if self.on_track_end:
                self.on_track_end()

        self._progress_job = self.after(500, self._update_progress)

    def _update_visualizer(self) -> None:
        state = self.playback.state()
        if state.is_playing and state.current_file:
            position = state.position
            volume = max(0.08, float(state.volume or 0.0))
            for index, current in enumerate(self._visualizer_values):
                wave = math.sin((position * 4.8) + (index * 0.62) + self._visualizer_seed)
                pulse = math.sin((position * 8.5) + (index * 0.21))
                random_lift = random.uniform(0.0, 0.18)
                target = (0.18 + abs(wave) * 0.62 + abs(pulse) * 0.18 + random_lift) * volume
                self._visualizer_values[index] = (current * 0.42) + (min(1.0, target) * 0.58)
        else:
            self._visualizer_values = [max(0.04, value * 0.82) for value in self._visualizer_values]
        self._draw_visualizer()
        self._visualizer_job = self.after(90, self._update_visualizer)

    def _draw_visualizer(self) -> None:
        if not hasattr(self, "visualizer_canvas"):
            return
        canvas = self.visualizer_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        padding = 7
        gap = 3
        usable_width = max(1, width - (padding * 2))
        bar_width = max(3, (usable_width - gap * (self._visualizer_bars - 1)) / self._visualizer_bars)
        baseline = height - padding

        canvas.create_rectangle(0, 0, width, height, fill="#0b0d10", outline="")
        canvas.create_rectangle(0, 0, width, 1, fill="#1f2937", outline="")
        for index, value in enumerate(self._visualizer_values):
            x1 = padding + index * (bar_width + gap)
            x2 = x1 + bar_width
            bar_height = max(3, min(height - padding * 2, value * (height - padding * 2)))
            y1 = baseline - bar_height
            color = self._visualizer_bar_color(value)
            canvas.create_rectangle(x1, y1, x2, baseline, fill=color, outline="")

    def _visualizer_bar_color(self, value: float) -> str:
        value = max(0.0, min(1.0, value))
        red = int(80 + value * 130)
        green = int(160 + value * 70)
        blue = int(190 + value * 45)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _reset_visualizer(self) -> None:
        self._visualizer_values = [0.05 for _index in range(self._visualizer_bars)]
        self._visualizer_seed = random.random() * 100.0
        self._draw_visualizer()

    def _sync_time_display(self, position: float) -> None:
        total = max(0.0, float(self.playback.duration or 0.0))
        position = max(0.0, min(float(position or 0.0), total or float(position or 0.0)))
        self.time_label_start.configure(text=AudioUtils.format_time(position))
        self.time_label_end.configure(text=AudioUtils.format_time(total))
        self.time_summary_label.configure(text="")
        if total > 0:
            progress = max(0.0, min(1.0, position / total))
        else:
            progress = 0.0
        self._set_progress_ratio(progress)

    def _set_progress_ratio(self, ratio: float) -> None:
        self._progress_ratio = max(0.0, min(1.0, float(ratio or 0.0)))
        self._draw_progress()

    def _draw_progress(self) -> None:
        if not hasattr(self, "progress_bar"):
            return
        canvas = self.progress_bar
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        y = height // 2
        start = 2
        end = width - 2
        fill_end = start + (end - start) * self._progress_ratio
        canvas.create_line(start, y, end, y, fill=self._player_progress_track, width=4, capstyle="round")
        canvas.create_line(start, y, fill_end, y, fill=self._player_primary, width=4, capstyle="round")

    def _sync_volume_icon(self) -> None:
        if not hasattr(self, "mute_button"):
            return
        volume = float(self.playback.volume or 0.0)
        icon = "\U0001f507" if volume <= 0.01 else "\U0001f50a"
        self.mute_button.configure(text=icon)

    def _update_track_identity(self, filepath: str) -> None:
        metadata = self.song_info.get_metadata(filepath) or {}
        title = str(metadata.get("title", "") or os.path.splitext(os.path.basename(filepath))[0]).strip()
        artist = str(metadata.get("artist", "") or "").strip()
        self._current_title = title
        self._current_artist = artist or os.path.basename(filepath)
        self.track_info_label.configure(text=self._current_title)
        self.artist_label.configure(text=self._current_artist)
        self._cover_photo = self._cover_photo_from_file(filepath)
        self._draw_vinyl()

    def _cover_photo_from_file(self, filepath: str | None):
        size = 146
        try:
            image = self.song_info.get_cover_image(filepath, (size, size)) if filepath else self.song_info._get_default_cover((size, size))
        except Exception:
            image = self.song_info._get_default_cover((size, size))
        image = image.resize((size, size), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size - 1, size - 1), fill=255)
        image.putalpha(mask)
        return ImageTk.PhotoImage(image)

    def cleanup(self) -> None:
        if self._progress_job:
            self.after_cancel(self._progress_job)
            self._progress_job = None
        if self._visualizer_job:
            self.after_cancel(self._visualizer_job)
            self._visualizer_job = None
        self.playback.cleanup()
