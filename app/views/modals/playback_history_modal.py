from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def show_playback_history_modal(parent, translator: Callable[..., str], summary: dict[str, object]) -> None:
    modal = tk.Toplevel(parent)
    modal.title(translator("playback_history.title"))
    modal.transient(parent)
    modal.geometry("860x540")
    modal.minsize(700, 420)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    summary_frame = ttk.LabelFrame(container, text=translator("playback_history.summary"))
    summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    for column in range(3):
        summary_frame.columnconfigure(column, weight=1)

    values = [
        ("playback_history.unique_tracks", summary.get("unique_tracks", 0)),
        ("playback_history.total_plays", summary.get("total_plays", 0)),
        ("playback_history.last_played", summary.get("last_played", "")),
    ]
    for column, (label_key, value) in enumerate(values):
        ttk.Label(summary_frame, text=translator(label_key), style="Muted.TLabel").grid(
            row=0, column=column, sticky="w", padx=8, pady=(8, 2)
        )
        ttk.Label(summary_frame, text=str(value or "-"), style="Title.TLabel").grid(
            row=1, column=column, sticky="w", padx=8, pady=(0, 8)
        )

    table_frame = ttk.Frame(container)
    table_frame.grid(row=1, column=0, sticky="nsew")
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    columns = ("last_played", "count", "artist", "title", "filename")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
    tree.heading("last_played", text=translator("playback_history.last_played"))
    tree.heading("count", text=translator("playback_history.play_count"))
    tree.heading("artist", text=translator("playback_history.artist"))
    tree.heading("title", text=translator("playback_history.title_field"))
    tree.heading("filename", text=translator("playback_history.filename"))
    tree.column("last_played", width=190, anchor="w", stretch=False)
    tree.column("count", width=80, anchor="center", stretch=False)
    tree.column("artist", width=160, anchor="w", stretch=True)
    tree.column("title", width=220, anchor="w", stretch=True)
    tree.column("filename", width=240, anchor="w", stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")

    for row in summary.get("rows", []) or []:
        tree.insert(
            "",
            "end",
            values=(
                row.get("last_played", ""),
                row.get("play_count", 0),
                row.get("artist", ""),
                row.get("title", ""),
                row.get("filename", ""),
            ),
        )

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
    ttk.Button(
        button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton"
    ).pack(side="right")
