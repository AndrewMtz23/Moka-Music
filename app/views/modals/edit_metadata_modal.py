import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional


MetadataField = tuple[str, str]


def request_metadata_edit(
    parent,
    translator: Callable[..., str],
    fields: list[MetadataField],
    current_song: dict[str, object],
    *,
    selected_count: int,
    is_batch_edit: bool,
) -> Optional[dict[str, str]]:
    modal = tk.Toplevel(parent)
    modal.title(translator("metadata_edit.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    result: Optional[dict[str, str]] = None
    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)

    description_key = "metadata_edit.description_batch" if is_batch_edit else "metadata_edit.description"
    columnspan = 3 if is_batch_edit else 2
    ttk.Label(container, text=translator(description_key, count=selected_count), wraplength=560).grid(
        row=0,
        column=0,
        columnspan=columnspan,
        sticky="w",
        pady=(0, 12),
    )
    if is_batch_edit:
        ttk.Label(container, text=translator("batch_edit.apply")).grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Label(container, text=translator("batch_edit.field")).grid(row=1, column=1, sticky="w", padx=(0, 8))
        ttk.Label(container, text=translator("batch_edit.value")).grid(row=1, column=2, sticky="w")

    apply_vars: dict[str, tk.BooleanVar] = {}
    edit_vars: dict[str, tk.StringVar] = {}
    start_row = 2 if is_batch_edit else 1
    for index, (field, label_key) in enumerate(fields, start=start_row):
        label_column = 1 if is_batch_edit else 0
        entry_column = 2 if is_batch_edit else 1
        if is_batch_edit:
            apply_vars[field] = tk.BooleanVar(value=False)
            ttk.Checkbutton(container, variable=apply_vars[field]).grid(
                row=index,
                column=0,
                sticky="w",
                pady=4,
            )
        ttk.Label(container, text=f"{translator(label_key)}:").grid(
            row=index,
            column=label_column,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )
        edit_vars[field] = tk.StringVar(value=str(current_song.get(field, "") or ""))
        ttk.Entry(container, textvariable=edit_vars[field], width=54).grid(
            row=index,
            column=entry_column,
            sticky="ew",
            pady=4,
        )

    button_row = ttk.Frame(container)
    button_row.grid(row=len(fields) + start_row, column=0, columnspan=columnspan, sticky="ew", pady=(14, 0))

    def save_changes() -> None:
        nonlocal result
        if is_batch_edit:
            metadata = {
                field: edit_vars[field].get().strip()
                for field, _label_key in fields
                if apply_vars[field].get()
            }
            if not metadata:
                messagebox.showwarning(
                    translator("dialog.metadata"),
                    translator("message.no_metadata_to_apply"),
                    parent=modal,
                )
                return
            result = metadata
        else:
            result = {field: variable.get().strip() for field, variable in edit_vars.items()}
        modal.destroy()

    ttk.Button(button_row, text=translator("metadata_edit.save"), command=save_changes).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.columnconfigure(0, weight=1)
    container.columnconfigure(2 if is_batch_edit else 1, weight=1)
    modal.wait_window()
    return result
