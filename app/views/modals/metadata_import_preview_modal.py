from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ...services.metadata_import_service import MetadataImportItem
from ...services.playlist_export_service import METADATA_EXPORT_KEYS


def confirm_metadata_import(
    parent,
    translator: Callable[..., str],
    items: list[MetadataImportItem],
    current_metadata_by_filename: dict[str, dict[str, str]],
) -> list[str] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("metadata_import.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("860x520")
    modal.minsize(760, 460)

    result: list[str] | None = None
    available_fields = [
        field
        for field in ("title", "artist", "album", "album_artist", "genre", "year", "track_number", "comment")
        if any(field in item.metadata for item in items)
    ]
    field_vars = {field: tk.BooleanVar(value=True) for field in available_fields}

    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(2, weight=1)

    ttk.Label(
        container,
        text=translator("metadata_import.description", count=len(items)),
        style="Muted.TLabel",
    ).grid(row=0, column=0, sticky="w", pady=(0, 10))

    field_frame = ttk.LabelFrame(container, text=translator("metadata_import.fields"), padding=10)
    field_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    for index, field in enumerate(available_fields):
        ttk.Checkbutton(
            field_frame,
            text=translator(f"online_metadata.field_{field}", default=field),
            variable=field_vars[field],
        ).grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 16), pady=2)

    tree_frame = ttk.Frame(container)
    tree_frame.grid(row=2, column=0, sticky="nsew")
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)

    tree = ttk.Treeview(
        tree_frame,
        columns=("filename", "field", "current", "incoming"),
        show="headings",
        selectmode="browse",
    )
    tree.heading("filename", text=translator("playback_history.filename"))
    tree.heading("field", text=translator("metadata_import.field"))
    tree.heading("current", text=translator("metadata_import.current"))
    tree.heading("incoming", text=translator("metadata_import.incoming"))
    tree.column("filename", width=210, anchor="w")
    tree.column("field", width=120, anchor="w")
    tree.column("current", width=220, anchor="w")
    tree.column("incoming", width=220, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)

    for item in items:
        current_metadata = current_metadata_by_filename.get(item.filename, {})
        for field, incoming_value in item.metadata.items():
            if field not in METADATA_EXPORT_KEYS:
                continue
            current_value = str(current_metadata.get(field, "") or "")
            if current_value == incoming_value:
                continue
            tree.insert(
                "",
                "end",
                values=(
                    item.filename,
                    translator(f"online_metadata.field_{field}", default=field),
                    current_value,
                    incoming_value,
                ),
            )

    def apply() -> None:
        nonlocal result
        selected_fields = [field for field, variable in field_vars.items() if variable.get()]
        if not selected_fields:
            return
        result = selected_fields
        modal.destroy()

    button_row = ttk.Frame(container)
    button_row.grid(row=3, column=0, sticky="ew", pady=(14, 0))
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")
    ttk.Button(
        button_row,
        text=translator("metadata_import.apply"),
        command=apply,
    ).pack(side="right", padx=(0, 8))

    modal.wait_window()
    return result
