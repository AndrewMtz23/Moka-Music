from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def show_library_compare_modal(parent, translator: Callable[..., str], comparison: dict[str, object]) -> None:
    modal = tk.Toplevel(parent)
    modal.title(translator("library_compare.title"))
    modal.transient(parent)
    modal.geometry("920x560")
    modal.minsize(760, 420)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    summary = ttk.LabelFrame(container, text=translator("library_compare.summary_title"))
    summary.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    for column in range(3):
        summary.columnconfigure(column, weight=1)

    values = [
        ("library_compare.total_incoming", comparison.get("total_incoming", 0)),
        ("library_compare.new_tracks", comparison.get("new_tracks", 0)),
        ("library_compare.duplicates", comparison.get("duplicates", 0)),
    ]
    for column, (label_key, value) in enumerate(values):
        ttk.Label(summary, text=translator(label_key), style="Muted.TLabel").grid(row=0, column=column, sticky="w", padx=8, pady=(8, 2))
        ttk.Label(summary, text=str(value), style="Title.TLabel").grid(row=1, column=column, sticky="w", padx=8, pady=(0, 8))

    table_frame = ttk.Frame(container)
    table_frame.grid(row=1, column=0, sticky="nsew")
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    columns = ("status", "incoming", "artist", "title", "matched", "score")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
    tree.heading("status", text=translator("library_compare.status"))
    tree.heading("incoming", text=translator("library_compare.incoming"))
    tree.heading("artist", text=translator("library_compare.artist"))
    tree.heading("title", text=translator("library_compare.title_field"))
    tree.heading("matched", text=translator("library_compare.matched"))
    tree.heading("score", text=translator("library_compare.score"))
    tree.column("status", width=110, anchor="center", stretch=False)
    tree.column("incoming", width=250, anchor="w", stretch=True)
    tree.column("artist", width=140, anchor="w", stretch=True)
    tree.column("title", width=180, anchor="w", stretch=True)
    tree.column("matched", width=250, anchor="w", stretch=True)
    tree.column("score", width=90, anchor="center", stretch=False)
    tree.tag_configure("new", foreground="#1f8f55")
    tree.tag_configure("duplicate", foreground="#b45309")
    tree.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")

    for row in comparison.get("rows", []) or []:
        status_key = "library_compare.status_duplicate" if row.status == "duplicate" else "library_compare.status_new"
        score = f"{row.score}%" if row.score else ""
        tree.insert(
            "",
            "end",
            values=(
                translator(status_key),
                row.incoming_filename,
                row.incoming_artist,
                row.incoming_title,
                row.matched_filename,
                score,
            ),
            tags=(row.status,),
        )

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
    ttk.Button(button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton").pack(side="right")
