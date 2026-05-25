from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable


BackupRecord = dict[str, object]


def show_backup_history_modal(
    parent,
    translator: Callable[..., str],
    backups: list[BackupRecord],
    on_restore_requested: Callable[[Path, object], bool],
) -> None:
    modal = tk.Toplevel(parent)
    modal.title(translator("backup.history_title"))
    modal.transient(parent)
    modal.geometry("860x420")
    modal.minsize(720, 320)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)

    columns = ("created_at", "track_count", "action", "folder", "path")
    tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
    tree.heading("created_at", text=translator("backup.column_date"))
    tree.heading("track_count", text=translator("backup.column_tracks"))
    tree.heading("action", text=translator("backup.column_action"))
    tree.heading("folder", text=translator("backup.column_folder"))
    tree.heading("path", text=translator("backup.column_file"))
    tree.column("created_at", width=150, anchor="w")
    tree.column("track_count", width=70, anchor="center")
    tree.column("action", width=180, anchor="w")
    tree.column("folder", width=250, anchor="w")
    tree.column("path", width=180, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")

    for index, backup in enumerate(backups):
        path = backup["path"]
        tree.insert(
            "",
            "end",
            iid=str(index),
            values=(
                backup["created_at"],
                backup["track_count"],
                backup["action"],
                backup["folder"],
                path.name if isinstance(path, Path) else str(path),
            ),
        )
    if backups:
        tree.selection_set("0")

    button_row = ttk.Frame(container)
    button_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def restore_selected() -> None:
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(translator("dialog.selection"), translator("backup.select_backup"), parent=modal)
            return
        backup = backups[int(selection[0])]
        path = backup["path"]
        if not isinstance(path, Path):
            return
        if not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("backup.confirm_restore", path=path),
            parent=modal,
        ):
            return
        if on_restore_requested(path, modal):
            modal.destroy()

    ttk.Button(button_row, text=translator("backup.restore_selected"), command=restore_selected).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")
