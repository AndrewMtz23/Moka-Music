from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable


def request_youtube_download_options(
    parent,
    translator: Callable[..., str],
    destination: str | Path,
) -> dict[str, object] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("youtube_download.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("680x310")
    modal.resizable(False, False)

    result: dict[str, object] | None = None
    url_var = tk.StringVar(value="")
    authorized_var = tk.BooleanVar(value=False)
    validation_var = tk.StringVar(value="")
    destination_path = Path(destination)

    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)
    container.columnconfigure(1, weight=1)

    ttk.Label(container, text=translator("youtube_download.description"), style="Muted.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
    )
    ttk.Label(container, text=translator("youtube_download.url")).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    url_entry = ttk.Entry(container, textvariable=url_var)
    url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)

    ttk.Label(container, text=translator("youtube_download.incoming_destination")).grid(
        row=2, column=0, sticky="w", padx=(0, 8), pady=4
    )
    ttk.Label(
        container,
        text=str(destination_path),
        style="Muted.TLabel",
        wraplength=480,
    ).grid(row=2, column=1, columnspan=2, sticky="w", pady=4)

    ttk.Checkbutton(
        container,
        text=translator("youtube_download.authorized"),
        variable=authorized_var,
    ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 4))
    ttk.Label(container, text=translator("youtube_download.quality_notice"), style="Muted.TLabel").grid(
        row=4, column=0, columnspan=3, sticky="w", pady=(0, 4)
    )
    ttk.Label(container, textvariable=validation_var, style="Error.TLabel").grid(
        row=5, column=0, columnspan=3, sticky="w"
    )

    def start() -> None:
        nonlocal result
        if not url_var.get().strip():
            validation_var.set(translator("youtube_download.url_required"))
            return
        if not authorized_var.get():
            validation_var.set(translator("youtube_download.authorization_required"))
            return
        result = {
            "url": url_var.get().strip(),
            "destination": str(destination_path),
            "authorized": True,
        }
        modal.destroy()

    buttons = ttk.Frame(container)
    buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(16, 0))
    ttk.Button(
        buttons,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")
    ttk.Button(
        buttons,
        text=translator("youtube_download.start"),
        command=start,
    ).pack(side="right", padx=(0, 8))

    modal.bind("<Return>", lambda _event: start())
    url_entry.focus_set()
    modal.wait_window()
    return result
