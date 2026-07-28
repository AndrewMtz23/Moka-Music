from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ...services.metadata_tools_service import METADATA_TOOL_FIELDS


def request_search_replace_metadata(parent, translator: Callable[..., str]) -> dict[str, object] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("metadata_tools.search_replace"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("440x260")
    modal.resizable(False, False)

    result: dict[str, object] | None = None
    field_labels = [
        (field, translator(f"online_metadata.field_{field}", default=field)) for field in METADATA_TOOL_FIELDS
    ]
    field_var = tk.StringVar(value=field_labels[0][1])
    search_var = tk.StringVar()
    replacement_var = tk.StringVar()
    case_var = tk.BooleanVar(value=False)

    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)
    container.columnconfigure(1, weight=1)

    ttk.Label(container, text=translator("metadata_tools.field")).grid(
        row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 10)
    )
    ttk.Combobox(
        container,
        textvariable=field_var,
        values=[label for _field, label in field_labels],
        state="readonly",
    ).grid(row=0, column=1, sticky="ew", pady=(0, 10))

    ttk.Label(container, text=translator("metadata_tools.search")).grid(
        row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 10)
    )
    ttk.Entry(container, textvariable=search_var).grid(row=1, column=1, sticky="ew", pady=(0, 10))

    ttk.Label(container, text=translator("metadata_tools.replace")).grid(
        row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 10)
    )
    ttk.Entry(container, textvariable=replacement_var).grid(row=2, column=1, sticky="ew", pady=(0, 10))

    ttk.Checkbutton(
        container,
        text=translator("metadata_tools.case_sensitive"),
        variable=case_var,
    ).grid(row=3, column=1, sticky="w")

    def apply() -> None:
        nonlocal result
        search_text = search_var.get()
        if not search_text:
            return
        label_to_field = {label: field for field, label in field_labels}
        result = {
            "field": label_to_field.get(field_var.get(), "title"),
            "search_text": search_text,
            "replacement": replacement_var.get(),
            "case_sensitive": case_var.get(),
        }
        modal.destroy()

    button_row = ttk.Frame(container)
    button_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(20, 0))
    ttk.Button(
        button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton"
    ).pack(side="right")
    ttk.Button(button_row, text=translator("change_preview.apply"), command=apply).pack(side="right", padx=(0, 8))

    modal.wait_window()
    return result
