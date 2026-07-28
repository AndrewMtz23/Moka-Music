import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

MetadataField = tuple[str, str]


def request_batch_metadata(
    parent,
    translator: Callable[..., str],
    fields: list[MetadataField],
    selected_count: int,
) -> Optional[dict[str, str]]:
    modal = tk.Toplevel(parent)
    modal.title(translator("batch_edit.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    result: Optional[dict[str, str]] = None
    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=translator("batch_edit.description", count=selected_count),
        wraplength=620,
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
    ttk.Label(container, text=translator("batch_edit.apply")).grid(row=1, column=0, sticky="w", padx=(0, 8))
    ttk.Label(container, text=translator("batch_edit.field")).grid(row=1, column=1, sticky="w", padx=(0, 8))
    ttk.Label(container, text=translator("batch_edit.value")).grid(row=1, column=2, sticky="w")

    apply_vars: dict[str, tk.BooleanVar] = {}
    value_vars: dict[str, tk.StringVar] = {}
    for index, (field, label_key) in enumerate(fields, start=2):
        apply_vars[field] = tk.BooleanVar(value=False)
        value_vars[field] = tk.StringVar(value="")
        ttk.Checkbutton(container, variable=apply_vars[field]).grid(row=index, column=0, sticky="w", pady=4)
        ttk.Label(container, text=translator(label_key)).grid(row=index, column=1, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(container, textvariable=value_vars[field], width=56).grid(
            row=index,
            column=2,
            sticky="ew",
            pady=4,
        )

    button_row = ttk.Frame(container)
    button_row.grid(row=len(fields) + 2, column=0, columnspan=3, sticky="ew", pady=(14, 0))

    def save_batch() -> None:
        nonlocal result
        metadata = {field: value_vars[field].get().strip() for field, _label_key in fields if apply_vars[field].get()}
        if not metadata:
            messagebox.showwarning(
                translator("dialog.metadata"), translator("message.no_metadata_to_apply"), parent=modal
            )
            return
        result = metadata
        modal.destroy()

    ttk.Button(button_row, text=translator("batch_edit.save"), command=save_batch).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("batch_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.columnconfigure(0, weight=1)
    container.columnconfigure(2, weight=1)
    modal.wait_window()
    return result
