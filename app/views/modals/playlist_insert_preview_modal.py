import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable


PreviewRow = tuple[str, str, str, str, str]


def playlist_preview_rows(plan) -> list[PreviewRow]:
    rows: list[PreviewRow] = []
    for item in getattr(plan, "items", []):
        old_position = "" if item.old_position is None else str(item.old_position)
        rows.append(
            (
                item.old_name,
                old_position,
                str(item.new_position),
                str(item.track_number),
                item.new_name,
            )
        )
    return rows


def confirm_playlist_insert_preview(parent, translator: Callable[..., str], plan) -> bool:
    rows = playlist_preview_rows(plan)
    modal = tk.Toplevel(parent)
    modal.title(translator("playlist_preview.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("980x460")
    modal.minsize(760, 340)

    confirmed = tk.BooleanVar(value=False)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.rowconfigure(1, weight=1)
    container.columnconfigure(0, weight=1)

    ttk.Label(
        container,
        text=translator("playlist_preview.description", count=len(rows)),
        wraplength=900,
    ).grid(row=0, column=0, sticky="w", pady=(0, 10))

    columns = ("file", "old_position", "new_position", "track", "new_name")
    tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="none")
    tree.heading("file", text=translator("playlist_preview.file"))
    tree.heading("old_position", text=translator("playlist_preview.old_position"))
    tree.heading("new_position", text=translator("playlist_preview.new_position"))
    tree.heading("track", text=translator("playlist_preview.track"))
    tree.heading("new_name", text=translator("playlist_preview.new_name"))
    tree.column("file", width=240, anchor="w")
    tree.column("old_position", width=100, anchor="center")
    tree.column("new_position", width=110, anchor="center")
    tree.column("track", width=90, anchor="center")
    tree.column("new_name", width=380, anchor="w")
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=1, column=1, sticky="ns")

    for row in rows:
        tree.insert("", "end", values=row)

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def apply_playlist_plan() -> None:
        if not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("playlist_preview.confirm", count=len(rows)),
            parent=modal,
        ):
            return
        confirmed.set(True)
        modal.destroy()

    ttk.Button(button_row, text=translator("playlist_preview.apply"), command=apply_playlist_plan).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.wait_window()
    return bool(confirmed.get())
