import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable


def request_track_position(
    parent,
    translator: Callable[..., str],
    *,
    title: str,
    prompt: str,
    total: int,
    initial: int = 0,
    min_position: int = 0,
    max_position: int | None = None,
    confirm_text: str | None = None,
) -> int | None:
    lower_bound = int(min_position)
    upper_bound = int(max_position) if max_position is not None else max(lower_bound, int(total or 1) - 1)
    if upper_bound < lower_bound:
        upper_bound = lower_bound
    initial_position = max(lower_bound, min(int(initial or lower_bound), upper_bound))
    result: int | None = None

    modal = tk.Toplevel(parent)
    modal.title(title)
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    colors = _theme_colors(parent)
    modal.configure(background=colors["surface"])

    container = tk.Frame(modal, background=colors["surface"], padx=18, pady=16)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)

    header = tk.Frame(container, background=colors["primary"], padx=14, pady=12)
    header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    header.columnconfigure(0, weight=1)
    tk.Label(
        header,
        text=title,
        background=colors["primary"],
        foreground=colors["primary_text"],
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew")
    tk.Label(
        header,
        text=translator("move_position.subtitle"),
        background=colors["primary"],
        foreground=colors["primary_text"],
        font=("Segoe UI", 9),
        anchor="w",
    ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

    tk.Label(
        container,
        text=prompt,
        background=colors["surface"],
        foreground=colors["text"],
        font=("Segoe UI", 10),
        justify="left",
        wraplength=520,
        anchor="w",
    ).grid(row=1, column=0, sticky="ew", pady=(0, 12))

    input_row = ttk.Frame(container)
    input_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    input_row.columnconfigure(1, weight=1)

    ttk.Label(input_row, text=translator("move_position.target_label")).grid(row=0, column=0, sticky="w", padx=(0, 10))
    value_var = tk.IntVar(value=initial_position)
    spinbox = ttk.Spinbox(
        input_row,
        from_=lower_bound,
        to=upper_bound,
        textvariable=value_var,
        width=8,
        justify="center",
    )
    spinbox.grid(row=0, column=1, sticky="w")

    scale = ttk.Scale(container, from_=lower_bound, to=upper_bound, orient="horizontal")
    scale.set(initial_position)
    scale.grid(row=3, column=0, sticky="ew", pady=(4, 8))

    helper_var = tk.StringVar()
    ttk.Label(container, textvariable=helper_var).grid(row=4, column=0, sticky="w", pady=(0, 14))
    syncing = False

    def current_value() -> int | None:
        try:
            value = int(value_var.get())
        except (TypeError, ValueError, tk.TclError):
            return None
        if value < lower_bound or value > upper_bound:
            return None
        return value

    def sync_helper(*_args) -> None:
        value = current_value()
        if value is None:
            helper_var.set(translator("move_position.invalid", min=lower_bound, max=upper_bound))
        else:
            helper_var.set(translator("move_position.helper", position=value, max=upper_bound))

    def sync_from_scale(value: str) -> None:
        nonlocal syncing
        if syncing:
            return
        try:
            numeric = int(round(float(value)))
        except (TypeError, ValueError):
            return
        syncing = True
        value_var.set(max(lower_bound, min(numeric, upper_bound)))
        syncing = False
        sync_helper()

    def sync_from_spinbox(*_args) -> None:
        nonlocal syncing
        if syncing:
            return
        value = current_value()
        if value is not None:
            syncing = True
            scale.set(value)
            syncing = False
        sync_helper()

    def apply() -> None:
        nonlocal result
        value = current_value()
        if value is None:
            messagebox.showwarning(title, translator("move_position.invalid", min=lower_bound, max=upper_bound), parent=modal)
            return
        result = value
        modal.destroy()

    value_var.trace_add("write", sync_from_spinbox)
    scale.configure(command=sync_from_scale)
    sync_helper()

    button_row = ttk.Frame(container)
    button_row.grid(row=5, column=0, sticky="ew")
    ttk.Button(button_row, text=confirm_text or translator("move_position.confirm"), command=apply).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    spinbox.focus_set()
    modal.bind("<Return>", lambda _event: apply())
    modal.bind("<Escape>", lambda _event: modal.destroy())
    modal.update_idletasks()
    _center_on_parent(modal, parent)
    modal.wait_window()
    return result


def _theme_colors(parent) -> dict[str, str]:
    defaults = {
        "surface": "#fbf3f6",
        "text": "#151015",
        "primary": "#c40f43",
        "primary_text": "#ffffff",
    }
    try:
        app = parent
        while app is not None and not hasattr(app, "style_manager"):
            app = app.master
        colors = app.style_manager.get_theme_colors() if app is not None else {}
    except Exception:
        colors = {}
    return {
        "surface": str(colors.get("surface", defaults["surface"])),
        "text": str(colors.get("text", defaults["text"])),
        "primary": str(colors.get("primary", colors.get("highlight", defaults["primary"]))),
        "primary_text": str(colors.get("primary_text", colors.get("highlight_text", defaults["primary_text"]))),
    }


def _center_on_parent(modal, parent) -> None:
    try:
        parent.update_idletasks()
        width = modal.winfo_width()
        height = modal.winfo_height()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        modal.geometry(f"+{x}+{y}")
    except Exception:
        pass
