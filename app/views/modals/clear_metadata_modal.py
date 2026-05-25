import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional


MetadataField = tuple[str, str]


def request_clear_metadata(
    parent,
    translator: Callable[..., str],
    fields: list[MetadataField],
    current_song: dict[str, object],
) -> Optional[dict[str, str]]:
    modal = tk.Toplevel(parent)
    modal.title(translator("metadata_clear.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    result: Optional[dict[str, str]] = None
    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)

    ttk.Label(container, text=translator("metadata_clear.description"), wraplength=560).grid(
        row=0,
        column=0,
        columnspan=3,
        sticky="w",
        pady=(0, 12),
    )
    ttk.Label(container, text=translator("metadata_clear.keep")).grid(row=1, column=0, sticky="w", padx=(0, 8))
    ttk.Label(container, text=translator("metadata_clear.field")).grid(row=1, column=1, sticky="w", padx=(0, 8))
    ttk.Label(container, text=translator("metadata_clear.value")).grid(row=1, column=2, sticky="w")

    keep_vars: dict[str, tk.BooleanVar] = {}
    for index, (field, label_key) in enumerate(fields, start=2):
        keep_vars[field] = tk.BooleanVar(value=False)
        value = str(current_song.get(field, "") or "")
        ttk.Checkbutton(container, variable=keep_vars[field]).grid(row=index, column=0, sticky="w", pady=3)
        ttk.Label(container, text=translator(label_key)).grid(row=index, column=1, sticky="w", padx=(0, 8), pady=3)
        ttk.Label(container, text=value or "-", width=46, anchor="w").grid(row=index, column=2, sticky="ew", pady=3)

    button_row = ttk.Frame(container)
    button_row.grid(row=len(fields) + 2, column=0, columnspan=3, sticky="ew", pady=(14, 0))

    def apply_clear() -> None:
        nonlocal result
        if not messagebox.askyesno(
            translator("metadata_clear.title"),
            translator("metadata_clear.confirm"),
            parent=modal,
        ):
            return
        result = {
            field: str(current_song.get(field, "") or "").strip() if keep_vars[field].get() else ""
            for field, _label_key in fields
        }
        modal.destroy()

    ttk.Button(button_row, text=translator("metadata_clear.apply"), command=apply_clear).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_clear.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.columnconfigure(0, weight=1)
    container.columnconfigure(2, weight=1)
    modal.wait_window()
    return result
