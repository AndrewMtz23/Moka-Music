import logging
import math
import os
import random
import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

if __name__ == "__main__" and not __package__:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from main import main

    raise SystemExit(main())

from ..controllers.playback_controller import PlaybackController
from ..i18n import I18n
from ..utils.audio_utils import AudioUtils
from ..ui_helpers.widgets import ToolTip


class PlayerControls(ttk.Frame):
    ICON_PREV = "\u23ee"
    ICON_PLAY = "\u25b6"
    ICON_PAUSE = "\u23f8"
    ICON_STOP = "\u23f9"
    ICON_NEXT = "\u23ed"
    ICON_REPEAT = "\u21bb"
    ICON_SHUFFLE = "\u21c4"
    ICON_BACK_10 = "\u21b6 10"
    ICON_FORWARD_10 = "10 \u21b7"

    def __init__(self, parent, translator: Optional[Callable[..., str]] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.t = translator or I18n().t
        self.style = ttk.Style()
        self.playback = PlaybackController()
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

        self._setup_styles()
        self._setup_ui()
        self._start_progress_loop()
        self._start_visualizer_loop()

    def _play_pause_icon(self) -> str:
        return self.ICON_PAUSE if self.playback.state().is_playing else self.ICON_PLAY

    def _setup_styles(self) -> None:
        self.style.configure("Player.TFrame", background="#101114")
        self.style.configure(
            "PlayerTitle.TLabel",
            background="#101114",
            foreground="#f5f7fb",
            font=("Segoe UI Semibold", 11),
            padding=(2, 1),
        )
        self.style.configure(
            "PlayerMuted.TLabel",
            background="#101114",
            foreground="#a1a8b3",
            font=("Segoe UI", 9),
            padding=(2, 1),
        )
        self.style.configure(
            "PlayerIcon.TButton",
            font=("Segoe UI Symbol", 12),
            foreground="#f5f7fb",
            background="#25272d",
            borderwidth=0,
            focusthickness=0,
            relief="flat",
            padding=(10, 7),
        )
        self.style.map(
            "PlayerIcon.TButton",
            background=[("active", "#343741"), ("pressed", "#3d4150")],
            foreground=[("!disabled", "#f5f7fb")],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        self.style.configure(
            "PlayerPrimary.TButton",
            font=("Segoe UI Symbol", 14),
            foreground="#111318",
            background="#f6f7fb",
            borderwidth=0,
            focusthickness=0,
            relief="flat",
            padding=(14, 8),
        )
        self.style.map(
            "PlayerPrimary.TButton",
            background=[("active", "#e5e7eb"), ("pressed", "#d1d5db")],
            foreground=[("!disabled", "#111318")],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        self.style.configure(
            "Player.Horizontal.TProgressbar",
            background="#fb7a35",
            troughcolor="#2b2e35",
            bordercolor="#2b2e35",
            lightcolor="#fb7a35",
            darkcolor="#fb7a35",
            thickness=8,
        )
        self.style.configure(
            "Player.Horizontal.TScale",
            background="#101114",
            troughcolor="#2b2e35",
            bordercolor="#2b2e35",
            lightcolor="#fb7a35",
            darkcolor="#fb7a35",
        )

    def _setup_ui(self) -> None:
        self.main_frame = ttk.LabelFrame(self, text=self.t("player.title"))
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=3)

        player_surface = ttk.Frame(self.main_frame, style="Player.TFrame")
        player_surface.pack(fill="both", expand=True, padx=4, pady=4)

        info_row = ttk.Frame(player_surface, style="Player.TFrame")
        info_row.pack(fill="x", padx=12, pady=(10, 4))

        self.track_info_label = ttk.Label(
            info_row,
            text=self.t("player.no_track"),
            anchor="w",
            style="PlayerTitle.TLabel",
        )
        self.track_info_label.pack(side="left", fill="x", expand=True)

        volume_frame = ttk.Frame(info_row, style="Player.TFrame")
        volume_frame.pack(side="right", padx=(10, 0))

        self.volume_label = ttk.Label(volume_frame, text=self.t("player.volume"), style="PlayerMuted.TLabel")
        self.volume_label.pack(side="left")
        self.volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=1,
            orient="horizontal",
            length=96,
            command=self._on_volume_change,
            style="Player.Horizontal.TScale",
        )
        self.volume_scale.set(self.playback.volume)
        self.volume_scale.pack(side="left", padx=(6, 0))

        controls_frame = ttk.Frame(player_surface, style="Player.TFrame")
        controls_frame.pack(fill="x", padx=12, pady=(2, 8))

        modes_frame = ttk.Frame(controls_frame, style="Player.TFrame")
        modes_frame.pack(side="left")

        self.shuffle_check = ttk.Checkbutton(modes_frame, text=self.ICON_SHUFFLE, variable=self.shuffle_var)
        self.shuffle_check.pack(side="left", padx=(0, 2))

        self.repeat_check = ttk.Checkbutton(modes_frame, text=self.ICON_REPEAT, variable=self.repeat_var)
        self.repeat_check.pack(side="left", padx=(2, 0))

        transport_frame = ttk.Frame(controls_frame, style="Player.TFrame")
        transport_frame.pack(side="left", expand=True)

        self.btn_prev = ttk.Button(
            transport_frame,
            text=self.ICON_PREV,
            command=self.previous_track,
            width=4,
            style="PlayerIcon.TButton",
        )
        self.btn_prev.pack(side="left", padx=(0, 6))

        self.btn_seek_back = ttk.Button(
            transport_frame,
            text=self.ICON_BACK_10,
            command=lambda: self.seek_relative(-10),
            width=6,
            style="PlayerIcon.TButton",
        )
        self.btn_seek_back.pack(side="left", padx=(0, 6))

        self.btn_play_pause = ttk.Button(
            transport_frame,
            text=self._play_pause_icon(),
            command=self.toggle_play_pause,
            width=4,
            style="PlayerPrimary.TButton",
        )
        self.btn_play_pause.pack(side="left", padx=(0, 6))

        self.btn_seek_forward = ttk.Button(
            transport_frame,
            text=self.ICON_FORWARD_10,
            command=lambda: self.seek_relative(10),
            width=6,
            style="PlayerIcon.TButton",
        )
        self.btn_seek_forward.pack(side="left", padx=(0, 6))

        self.btn_stop = ttk.Button(
            transport_frame,
            text=self.ICON_STOP,
            command=self.stop,
            width=4,
            style="PlayerIcon.TButton",
        )
        self.btn_stop.pack(side="left", padx=(0, 6))

        self.btn_next = ttk.Button(
            transport_frame,
            text=self.ICON_NEXT,
            command=self.next_track,
            width=4,
            style="PlayerIcon.TButton",
        )
        self.btn_next.pack(side="left")

        progress_frame = ttk.Frame(player_surface, style="Player.TFrame")
        progress_frame.pack(fill="x", padx=12, pady=(0, 2))

        self.time_label_start = ttk.Label(progress_frame, text="00:00", width=7, style="PlayerMuted.TLabel")
        self.time_label_start.pack(side="left")

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            maximum=100,
            style="Player.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=5)
        self.progress_bar.bind("<Button-1>", self._on_progress_click)
        self.progress_bar.configure(cursor="hand2")

        self.time_label_end = ttk.Label(progress_frame, text="00:00", width=7, style="PlayerMuted.TLabel")
        self.time_label_end.pack(side="right")

        self.time_summary_label = ttk.Label(
            player_surface,
            text="00:00 / 00:00",
            anchor="center",
            style="PlayerMuted.TLabel",
        )
        self.time_summary_label.pack(fill="x", padx=12, pady=(0, 2))

        self.visualizer_canvas = tk.Canvas(
            player_surface,
            height=42,
            borderwidth=0,
            highlightthickness=0,
            background="#0b0d10",
        )
        self.visualizer_canvas.pack(fill="x", padx=12, pady=(4, 10))
        self.visualizer_canvas.bind("<Configure>", lambda _event: self._draw_visualizer())
        self._draw_visualizer()
        self._register_tooltips()
        self._set_transport_enabled(False)

        if not self.playback.available:
            self.track_info_label.configure(text=self.t("player.audio_unavailable"))
            self._set_transport_enabled(False)
            self.repeat_check.state(["disabled"])
            self.shuffle_check.state(["disabled"])

    def _register_tooltips(self) -> None:
        tooltip_targets = [
            (self.btn_prev, "player.previous"),
            (self.btn_seek_back, "player.seek_back"),
            (self.btn_play_pause, "player.play_pause"),
            (self.btn_seek_forward, "player.seek_forward"),
            (self.btn_stop, "player.stop"),
            (self.btn_next, "player.next"),
            (self.shuffle_check, "player.shuffle"),
            (self.repeat_check, "player.repeat"),
            (self.volume_scale, "player.volume_hint"),
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

    def refresh_texts(self) -> None:
        self._setup_styles()
        self.main_frame.configure(text=self.t("player.title"))
        self.btn_prev.configure(text=self.ICON_PREV)
        self.btn_next.configure(text=self.ICON_NEXT)
        self.btn_stop.configure(text=self.ICON_STOP)
        self.volume_label.configure(text=self.t("player.volume"))
        self.repeat_check.configure(text=self.ICON_REPEAT)
        self.shuffle_check.configure(text=self.ICON_SHUFFLE)
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
            self.progress_bar.configure(value=0)
            self._sync_time_display(state.position)
            self.track_info_label.configure(text=self.t("player.loaded", name=os.path.basename(filepath)))
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
        self.track_info_label.configure(text=self.t("player.playing", name=os.path.basename(self.playback.current_file)))
        self._sync_time_display(state.position)

    def pause(self) -> None:
        if not self.playback.current_file:
            return
        state = self.playback.pause()
        self.btn_play_pause.configure(text=self._play_pause_icon())
        current_name = os.path.basename(self.playback.current_file) if self.playback.current_file else self.t("player.no_track")
        self.track_info_label.configure(text=self.t("player.paused", name=current_name))
        self._sync_time_display(state.position)

    def stop(self) -> None:
        state = self.playback.stop()
        self._reset_visualizer()
        self.btn_play_pause.configure(text=self._play_pause_icon())
        self.progress_bar.configure(value=0)
        self._sync_time_display(state.position)
        if self.playback.current_file:
            self.track_info_label.configure(text=self.t("player.stopped", name=os.path.basename(self.playback.current_file)))
        else:
            self.track_info_label.configure(text=self.t("player.no_track"))

    def restart_current_track(self) -> None:
        if not self.playback.current_file:
            return
        state = self.playback.restart()
        self.progress_bar.configure(value=0)
        self._sync_time_display(state.position)
        self.btn_play_pause.configure(text=self._play_pause_icon())

    def seek_relative(self, seconds: float) -> None:
        if not self.playback.current_file:
            return
        was_playing = self.playback.state().is_playing
        state = self.playback.seek_relative(seconds)
        self._sync_time_display(state.position)
        if not was_playing:
            self.track_info_label.configure(text=self.t("player.seeked", position=AudioUtils.format_time(state.position)))

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
        except Exception as exc:
            self.logger.error("Error changing volume: %s", exc)

    def _on_progress_click(self, event) -> None:
        state = self.playback.state()
        if not state.current_file or state.duration <= 0:
            return
        width = max(1, self.progress_bar.winfo_width())
        ratio = max(0.0, min(1.0, event.x / width))
        new_state = self.playback.seek_absolute(state.duration * ratio)
        self._sync_time_display(new_state.position)
        if new_state.current_file and not new_state.is_playing:
            self.track_info_label.configure(text=self.t("player.seeked", position=AudioUtils.format_time(new_state.position)))

    def _start_progress_loop(self) -> None:
        self._update_progress()

    def _start_visualizer_loop(self) -> None:
        self._update_visualizer()

    def _update_progress(self) -> None:
        state = self.playback.state()
        if state.current_file:
            position = min(state.position, state.duration or 0.0)
            self._sync_time_display(position)

        if self.playback.poll_track_end():
            ended_state = self.playback.mark_ended()
            self.progress_bar.configure(value=100)
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
        self.time_summary_label.configure(
            text=f"{AudioUtils.format_time(position)} / {AudioUtils.format_time(total)}"
        )
        if total > 0:
            progress = max(0.0, min(100.0, position / total * 100.0))
        else:
            progress = 0.0
        self.progress_bar.configure(value=progress)

    def cleanup(self) -> None:
        if self._progress_job:
            self.after_cancel(self._progress_job)
            self._progress_job = None
        if self._visualizer_job:
            self.after_cancel(self._visualizer_job)
            self._visualizer_job = None
        self.playback.cleanup()
