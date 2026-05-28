from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable

from ...services.audio_conversion_service import AUDIO_CONVERSION_PRESETS, preset_by_id


def request_audio_conversion_options(parent, translator: Callable[..., str], count: int) -> dict[str, object] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("audio_conversion.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("620x280")
    modal.resizable(False, False)

    result: dict[str, object] | None = None
    folder_var = tk.StringVar(value="")
    preset_options = [
        (translator(f"audio_conversion.preset_{preset.id}"), preset.id)
        for preset in AUDIO_CONVERSION_PRESETS
    ]
    preset_by_label = {label: preset_id for label, preset_id in preset_options}
    preset_var = tk.StringVar(value=preset_options[0][0])
    overwrite_var = tk.BooleanVar(value=False)
    preserve_structure_var = tk.BooleanVar(value=False)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(1, weight=1)

    ttk.Label(container, text=translator("audio_conversion.description", count=count), style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
    ttk.Label(container, text=translator("audio_conversion.preset")).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Combobox(container, textvariable=preset_var, values=[label for label, _preset_id in preset_options], state="readonly", width=28).grid(row=1, column=1, sticky="w", pady=4)

    ttk.Label(container, text=translator("audio_conversion.destination")).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(container, textvariable=folder_var).grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Button(container, text=translator("audio_conversion.browse"), command=lambda: _choose_folder(parent, translator, folder_var)).grid(row=2, column=2, sticky="e", padx=(8, 0), pady=4)

    ttk.Checkbutton(container, text=translator("audio_conversion.overwrite"), variable=overwrite_var).grid(row=3, column=1, sticky="w", pady=4)
    ttk.Checkbutton(container, text=translator("audio_conversion.preserve_structure"), variable=preserve_structure_var).grid(row=4, column=1, sticky="w", pady=4)

    def apply() -> None:
        nonlocal result
        if not folder_var.get().strip():
            return
        preset = preset_by_id(preset_by_label[preset_var.get()])
        result = {
            "preset": preset.id,
            "format": preset.extension,
            "bitrate": preset.bitrate,
            "destination": folder_var.get().strip(),
            "overwrite": overwrite_var.get(),
            "preserve_structure": preserve_structure_var.get(),
        }
        modal.destroy()

    button_row = ttk.Frame(container)
    button_row.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(18, 0))
    ttk.Button(button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton").pack(side="right")
    ttk.Button(button_row, text=translator("audio_conversion.convert"), command=apply).pack(side="right", padx=(0, 8))

    modal.wait_window()
    return result


def _choose_folder(parent, translator: Callable[..., str], folder_var: tk.StringVar) -> None:
    folder = filedialog.askdirectory(parent=parent, title=translator("audio_conversion.destination"))
    if folder:
        folder_var.set(folder)
