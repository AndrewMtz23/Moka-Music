from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def confirm_file_plan_preview(parent, translator: Callable[..., str], title: str, rows: list[tuple[str, str]]) -> bool:
    modal = tk.Toplevel(parent)
    modal.title(title)
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("900x460")
    modal.minsize(720, 340)

    confirmed = tk.BooleanVar(value=False)
    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(
        container,
        text=translator("file_organization.preview_description", count=len(rows)),
        wraplength=820,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    tree = ttk.Treeview(container, columns=("before", "after"), show="headings", selectmode="none")
    tree.heading("before", text=translator("file_organization.before"))
    tree.heading("after", text=translator("file_organization.after"))
    tree.column("before", width=380, anchor="w")
    tree.column("after", width=440, anchor="w")
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=1, column=1, sticky="ns")

    for row in rows:
        tree.insert("", "end", values=row)

    def apply() -> None:
        confirmed.set(True)
        modal.destroy()

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    ttk.Button(button_row, text=translator("file_organization.apply"), command=apply).pack(side="left")
    ttk.Button(button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton").pack(side="right")

    modal.wait_window()
    return bool(confirmed.get())


def show_playlist_validation_modal(parent, translator: Callable[..., str], rows: list[dict[str, str]]) -> None:
    modal = tk.Toplevel(parent)
    modal.title(translator("playlist_validation.title"))
    modal.transient(parent)
    modal.geometry("820x420")
    modal.minsize(680, 320)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(container, text=translator("playlist_validation.description", count=len(rows))).grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(0, 10),
    )
    tree = ttk.Treeview(container, columns=("filename", "issue", "detail"), show="headings", selectmode="none")
    tree.heading("filename", text=translator("audio_tools.filename"))
    tree.heading("issue", text=translator("audio_tools.issue"))
    tree.heading("detail", text=translator("audio_tools.issues"))
    tree.column("filename", width=300, anchor="w")
    tree.column("issue", width=180, anchor="w")
    tree.column("detail", width=260, anchor="w")
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=1, column=1, sticky="ns")

    for row in rows:
        tree.insert("", "end", values=(row.get("filename", ""), row.get("issue", ""), row.get("detail", "")))

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    ttk.Button(button_row, text=translator("audio_tools.close"), command=modal.destroy, style="Secondary.TButton").pack(side="right")
