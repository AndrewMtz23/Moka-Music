from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..models.audio_edit_project import AudioEditProcessing
from ..utils import themed_messagebox as messagebox


def edit_audio_processing(
    parent: tk.Misc,
    processing: AudioEditProcessing,
    translate: Callable[..., str],
) -> AudioEditProcessing | None:
    dialog = tk.Toplevel(parent)
    dialog.title(translate("audio_editor.processing_title"))
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.grab_set()
    result: AudioEditProcessing | None = None

    content = ttk.Frame(dialog, padding=14)
    content.pack(fill="both", expand=True)
    ttk.Label(
        content,
        text=translate("audio_editor.processing_order"),
        wraplength=420,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    eq_frame = ttk.LabelFrame(content, text=translate("audio_editor.eq_title"), padding=8)
    eq_frame.grid(row=1, column=0, sticky="ew", padx=(0, 8))
    eq_values = (
        ("audio_editor.eq_low", processing.low_gain_db),
        ("audio_editor.eq_mid", processing.mid_gain_db),
        ("audio_editor.eq_high", processing.high_gain_db),
    )
    variables: dict[str, tk.StringVar] = {}
    for row, (key, value) in enumerate(eq_values):
        variables[key] = tk.StringVar(value=f"{value:g}")
        ttk.Label(eq_frame, text=translate(key)).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Spinbox(
            eq_frame,
            from_=-12,
            to=12,
            increment=0.5,
            textvariable=variables[key],
            width=8,
        ).grid(row=row, column=1, sticky="ew", pady=2)

    compressor_frame = ttk.LabelFrame(content, text=translate("audio_editor.compressor_title"), padding=8)
    compressor_frame.grid(row=1, column=1, sticky="ew")
    compressor_enabled = tk.BooleanVar(value=processing.compressor_enabled)
    ttk.Checkbutton(
        compressor_frame,
        text=translate("audio_editor.compressor_enabled"),
        variable=compressor_enabled,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    compressor_fields = (
        ("audio_editor.compressor_threshold", processing.compressor_threshold_db, -60, 0, 1),
        ("audio_editor.compressor_ratio", processing.compressor_ratio, 1, 20, 0.5),
        ("audio_editor.compressor_attack", processing.compressor_attack_ms, 0.1, 1000, 1),
        ("audio_editor.compressor_release", processing.compressor_release_ms, 1, 1000, 10),
        ("audio_editor.compressor_makeup", processing.compressor_makeup_db, 0, 12, 0.5),
    )
    for row, (key, value, minimum, maximum, increment) in enumerate(compressor_fields, start=1):
        variables[key] = tk.StringVar(value=f"{value:g}")
        ttk.Label(compressor_frame, text=translate(key)).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Spinbox(
            compressor_frame,
            from_=minimum,
            to=maximum,
            increment=increment,
            textvariable=variables[key],
            width=9,
        ).grid(row=row, column=1, sticky="ew", pady=2)

    bypassed = tk.BooleanVar(value=processing.bypassed)
    ttk.Checkbutton(
        content,
        text=translate("audio_editor.processing_bypass"),
        variable=bypassed,
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 4))
    ttk.Label(
        content,
        text=translate("audio_editor.processing_limiter_notice"),
        wraplength=420,
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 10))

    buttons = ttk.Frame(content)
    buttons.grid(row=4, column=0, columnspan=2, sticky="e")
    ttk.Button(
        buttons,
        text=translate("audio_editor.cancel"),
        command=dialog.destroy,
    ).pack(side="right", padx=(6, 0))

    def apply() -> None:
        nonlocal result
        try:
            result = AudioEditProcessing(
                low_gain_db=variables["audio_editor.eq_low"].get(),
                mid_gain_db=variables["audio_editor.eq_mid"].get(),
                high_gain_db=variables["audio_editor.eq_high"].get(),
                compressor_enabled=compressor_enabled.get(),
                compressor_threshold_db=variables["audio_editor.compressor_threshold"].get(),
                compressor_ratio=variables["audio_editor.compressor_ratio"].get(),
                compressor_attack_ms=variables["audio_editor.compressor_attack"].get(),
                compressor_release_ms=variables["audio_editor.compressor_release"].get(),
                compressor_makeup_db=variables["audio_editor.compressor_makeup"].get(),
                bypassed=bypassed.get(),
            )
        except ValueError as exc:
            messagebox.showerror(
                translate("dialog.error"),
                translate("audio_editor.processing_invalid", error=exc),
                parent=dialog,
            )
            return
        dialog.destroy()

    ttk.Button(
        buttons,
        text=translate("audio_editor.apply_processing"),
        command=apply,
    ).pack(side="right")
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    if hasattr(parent, "_style_editor_dialog"):
        parent._style_editor_dialog(dialog)
    dialog.wait_window()
    return result
