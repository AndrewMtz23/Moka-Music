from typing import Callable
from tkinter import ttk
import tkinter as tk


GuideAction = tuple[str, str, Callable[[], None]]


def show_incoming_folder_guide(parent, translator: Callable[..., str], actions: list[GuideAction]) -> None:
    modal = tk.Toplevel(parent)
    modal.title(translator("incoming_guide.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=translator("incoming_guide.description"),
        wraplength=520,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

    for index, (label_key, description_key, callback) in enumerate(actions, start=1):
        ttk.Button(
            container,
            text=translator(label_key),
            command=callback,
            style="Secondary.TButton",
            width=24,
        ).grid(row=index, column=0, sticky="ew", padx=(0, 10), pady=4)
        ttk.Label(
            container,
            text=translator(description_key),
            wraplength=360,
        ).grid(row=index, column=1, sticky="w", pady=4)

    ttk.Button(
        container,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
    ).grid(row=len(actions) + 1, column=1, sticky="e", pady=(14, 0))

    modal.wait_window()
