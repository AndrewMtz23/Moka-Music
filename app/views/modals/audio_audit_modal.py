from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def show_audio_audit_modal(
    parent,
    translator: Callable[..., str],
    title: str,
    rows: list[dict[str, object]],
    columns: list[tuple[str, str, int]],
) -> None:
    modal = tk.Toplevel(parent)
    modal.title(title)
    modal.transient(parent)
    modal.geometry("920x500")
    modal.minsize(760, 380)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(container, text=translator("audio_tools.rows_found", count=len(rows)), style="Muted.TLabel").grid(
        row=0,
        column=0,
        sticky="w",
        pady=(0, 10),
    )

    column_ids = [column_id for column_id, _label, _width in columns]
    tree = ttk.Treeview(container, columns=column_ids, show="headings", selectmode="browse")
    for column_id, label, width in columns:
        tree.heading(column_id, text=label)
        tree.column(column_id, width=width, anchor="w", stretch=True)
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    scrollbar.grid(row=1, column=1, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)

    for row in rows:
        tree.insert("", "end", values=[row.get(column_id, "") for column_id in column_ids])

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    ttk.Button(button_row, text=translator("audio_tools.close"), command=modal.destroy, style="Secondary.TButton").pack(side="right")
