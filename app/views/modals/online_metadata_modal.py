from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from ...services.online_metadata_service import OnlineMetadataResult


FIELDS = ("title", "artist", "album", "year", "genre")


def request_online_metadata_selection(
    parent,
    translator: Callable[..., str],
    results: list[OnlineMetadataResult],
) -> Optional[dict[str, str]]:
    modal = tk.Toplevel(parent)
    modal.title(translator("online_metadata.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("880x500")
    modal.minsize(760, 420)

    selected_metadata: Optional[dict[str, str]] = None
    field_vars = {field: tk.BooleanVar(value=True) for field in FIELDS}

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(
        container,
        text=translator("online_metadata.description", count=len(results)),
        wraplength=820,
    ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

    columns = ("score", "title", "artist", "album", "year", "genre")
    tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
    headings = {
        "score": translator("online_metadata.score"),
        "title": translator("metadata.title"),
        "artist": translator("metadata.artist"),
        "album": translator("metadata.album"),
        "year": translator("metadata.year"),
        "genre": translator("metadata.genre"),
    }
    widths = {"score": 70, "title": 210, "artist": 180, "album": 220, "year": 70, "genre": 120}
    for column in columns:
        tree.heading(column, text=headings[column].rstrip(":"))
        tree.column(column, width=widths[column], anchor="w", stretch=column not in {"score", "year"})
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=1, column=1, sticky="ns")

    for index, result in enumerate(results):
        tree.insert(
            "",
            "end",
            iid=str(index),
            values=(result.score, result.title, result.artist, result.album, result.year, result.genre),
        )
    if results:
        tree.selection_set("0")
        tree.focus("0")

    field_frame = ttk.LabelFrame(container, text=translator("online_metadata.fields"))
    field_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    for index, field in enumerate(FIELDS):
        ttk.Checkbutton(
            field_frame,
            text=translator(f"online_metadata.field_{field}"),
            variable=field_vars[field],
        ).grid(row=0, column=index, sticky="w", padx=8, pady=8)

    button_row = ttk.Frame(container)
    button_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def apply_selection() -> None:
        nonlocal selected_metadata
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(
                translator("dialog.selection"),
                translator("online_metadata.select_result"),
                parent=modal,
            )
            return
        result = results[int(selection[0])]
        metadata = result.metadata()
        selected_metadata = {
            field: value
            for field, value in metadata.items()
            if field_vars.get(field) is not None and field_vars[field].get()
        }
        if not selected_metadata:
            messagebox.showwarning(
                translator("dialog.metadata"),
                translator("message.no_metadata_to_apply"),
                parent=modal,
            )
            return
        modal.destroy()

    ttk.Button(button_row, text=translator("online_metadata.apply"), command=apply_selection).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.wait_window()
    return selected_metadata
