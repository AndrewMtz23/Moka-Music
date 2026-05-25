import tkinter as tk
from tkinter import ttk
from typing import Callable


ChangeRow = tuple[str, str, str, str]


def confirm_change_preview(parent, translator: Callable[..., str], changes: list[ChangeRow]) -> bool:
    modal = tk.Toplevel(parent)
    modal.title(translator("change_preview.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("860x420")
    modal.minsize(680, 320)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.rowconfigure(1, weight=1)
    container.columnconfigure(0, weight=1)

    ttk.Label(
        container,
        text=translator("change_preview.description", count=len(changes)),
        wraplength=780,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    columns = ("song", "field", "before", "after")
    tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="none")
    tree.heading("song", text=translator("change_preview.song"))
    tree.heading("field", text=translator("change_preview.field"))
    tree.heading("before", text=translator("change_preview.before"))
    tree.heading("after", text=translator("change_preview.after"))
    tree.column("song", width=250, anchor="w")
    tree.column("field", width=120, anchor="w")
    tree.column("before", width=220, anchor="w")
    tree.column("after", width=220, anchor="w")
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=1, column=1, sticky="ns")

    for change in changes:
        tree.insert("", "end", values=change)

    confirmed = tk.BooleanVar(value=False)
    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def apply_changes() -> None:
        confirmed.set(True)
        modal.destroy()

    ttk.Button(button_row, text=translator("change_preview.apply"), command=apply_changes).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.wait_window()
    return bool(confirmed.get())
