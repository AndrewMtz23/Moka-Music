from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable

from ...services.audio_conversion_service import SUPPORTED_OUTPUT_FORMATS


def request_audio_conversion_options(parent, translator: Callable[..., str], count: int) -> dict[str, object] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("audio_conversion.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("520x220")
    modal.resizable(False, False)

    result: dict[str, object] | None = None
    folder_var = tk.StringVar(value="")
    format_var = tk.StringVar(value=".mp3")
    overwrite_var = tk.BooleanVar(value=False)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(1, weight=1)

    ttk.Label(container, text=translator("audio_conversion.description", count=count), style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
    ttk.Label(container, text=translator("audio_conversion.format")).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Combobox(container, textvariable=format_var, values=list(SUPPORTED_OUTPUT_FORMATS), state="readonly", width=12).grid(row=1, column=1, sticky="w", pady=4)

    ttk.Label(container, text=translator("audio_conversion.destination")).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(container, textvariable=folder_var).grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Button(container, text=translator("audio_conversion.browse"), command=lambda: _choose_folder(parent, translator, folder_var)).grid(row=2, column=2, sticky="e", padx=(8, 0), pady=4)

    ttk.Checkbutton(container, text=translator("audio_conversion.overwrite"), variable=overwrite_var).grid(row=3, column=1, sticky="w", pady=4)

    def apply() -> None:
        nonlocal result
        if not folder_var.get().strip():
            return
        result = {
            "format": format_var.get(),
            "destination": folder_var.get().strip(),
            "overwrite": overwrite_var.get(),
        }
        modal.destroy()

    button_row = ttk.Frame(container)
    button_row.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(18, 0))
    ttk.Button(button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton").pack(side="right")
    ttk.Button(button_row, text=translator("audio_conversion.convert"), command=apply).pack(side="right", padx=(0, 8))

    modal.wait_window()
    return result


def _choose_folder(parent, translator: Callable[..., str], folder_var: tk.StringVar) -> None:
    folder = filedialog.askdirectory(parent=parent, title=translator("audio_conversion.destination"))
    if folder:
        folder_var.set(folder)
