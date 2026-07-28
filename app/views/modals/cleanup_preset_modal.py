import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

CleanupActionOption = tuple[str, str]
CleanupPresetResult = dict[str, object]


def show_cleanup_preset_modal(
    parent,
    translator: Callable[..., str],
    action_options: list[CleanupActionOption],
) -> Optional[CleanupPresetResult]:
    modal = tk.Toplevel(parent)
    modal.title(translator("presets.create_title"))
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    result: Optional[CleanupPresetResult] = None
    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)
    ttk.Label(container, text=translator("presets.create_description"), wraplength=520).grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(0, 12),
    )

    name_var = tk.StringVar(value="")
    ttk.Label(container, text=translator("presets.name")).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
    ttk.Entry(container, textvariable=name_var, width=42).grid(row=1, column=1, sticky="ew", pady=5)

    action_vars: dict[str, tk.BooleanVar] = {}
    for row, (action, label_key) in enumerate(action_options, start=2):
        action_vars[action] = tk.BooleanVar(value=False)
        ttk.Checkbutton(container, variable=action_vars[action], text=translator(label_key)).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=3,
        )

    button_row = ttk.Frame(container)
    button_row.grid(row=len(action_options) + 2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def save_preset() -> None:
        nonlocal result
        name = name_var.get().strip()
        actions = [action for action, variable in action_vars.items() if variable.get()]
        if not name:
            messagebox.showwarning(translator("dialog.metadata"), translator("presets.name_required"), parent=modal)
            return
        if not actions:
            messagebox.showwarning(translator("dialog.metadata"), translator("presets.actions_required"), parent=modal)
            return
        result = {"name": name, "actions": actions}
        modal.destroy()

    ttk.Button(button_row, text=translator("presets.save"), command=save_preset).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")
    container.columnconfigure(1, weight=1)
    modal.wait_window()
    return result
