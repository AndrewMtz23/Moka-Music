import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable


def confirm_rename_metadata(parent, translator: Callable[..., str], plan) -> bool:
    modal = tk.Toplevel(parent)
    modal.title(translator("rename_metadata.title"))
    modal.transient(parent)
    modal.geometry("760x420")
    modal.minsize(640, 300)

    confirmed = tk.BooleanVar(value=False)

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.rowconfigure(1, weight=1)
    container.columnconfigure(0, weight=1)

    ttk.Label(
        container,
        text=translator("rename_metadata.description", count=len(plan)),
        wraplength=700,
    ).grid(row=0, column=0, sticky="w", pady=(0, 10))

    tree = ttk.Treeview(container, columns=("old", "new"), show="headings", selectmode="none")
    tree.heading("old", text=translator("rename_metadata.old_name"))
    tree.heading("new", text=translator("rename_metadata.new_name"))
    tree.column("old", width=320, anchor="w")
    tree.column("new", width=380, anchor="w")
    tree.grid(row=1, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=1, column=1, sticky="ns")

    for item in plan:
        tree.insert("", "end", values=(item.old_name, item.new_name))

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def apply_rename_plan() -> None:
        if not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("rename_metadata.confirm", count=len(plan)),
            parent=modal,
        ):
            return
        confirmed.set(True)
        modal.destroy()

    ttk.Button(button_row, text=translator("rename_metadata.apply"), command=apply_rename_plan).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    modal.wait_window()
    return bool(confirmed.get())
