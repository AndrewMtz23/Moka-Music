from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ...services.library_stats_service import format_duration


def show_library_stats_modal(parent, translator: Callable[..., str], library_name: str, stats: dict[str, object]) -> None:
    modal = tk.Toplevel(parent)
    modal.title(translator("library_stats.title"))
    modal.transient(parent)
    modal.geometry("760x520")
    modal.minsize(640, 420)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    summary = ttk.LabelFrame(container, text=library_name)
    summary.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    for column in range(4):
        summary.columnconfigure(column, weight=1)

    summary_values = [
        ("library_stats.total_tracks", stats.get("total_tracks", 0)),
        ("library_stats.total_duration", format_duration(float(stats.get("total_duration", 0) or 0))),
        ("library_stats.complete_metadata", stats.get("complete_metadata", 0)),
        ("library_stats.completion", f"{stats.get('completion_percent', 0)}%"),
    ]
    for column, (label_key, value) in enumerate(summary_values):
        ttk.Label(summary, text=translator(label_key), style="Muted.TLabel").grid(row=0, column=column, sticky="w", padx=8, pady=(8, 2))
        ttk.Label(summary, text=str(value), style="Title.TLabel").grid(row=1, column=column, sticky="w", padx=8, pady=(0, 8))

    notebook = ttk.Notebook(container)
    notebook.grid(row=1, column=0, sticky="nsew")
    _add_counter_tab(notebook, translator, "library_stats.genres", stats.get("genres", []))
    _add_counter_tab(notebook, translator, "library_stats.years", stats.get("years", []))
    _add_counter_tab(notebook, translator, "library_stats.top_artists", stats.get("top_artists", []))
    _add_counter_tab(notebook, translator, "library_stats.top_albums", stats.get("top_albums", []))

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
    ttk.Button(button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton").pack(side="right")


def _add_counter_tab(notebook: ttk.Notebook, translator: Callable[..., str], title_key: str, rows) -> None:
    frame = ttk.Frame(notebook, padding=8)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    columns = ("name", "count")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="none")
    tree.heading("name", text=translator("library_stats.value"))
    tree.heading("count", text=translator("library_stats.count"))
    tree.column("name", width=420, anchor="w", stretch=True)
    tree.column("count", width=100, anchor="center", stretch=False)
    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")
    for name, count in rows or []:
        tree.insert("", "end", values=(name, count))
    notebook.add(frame, text=translator(title_key))
