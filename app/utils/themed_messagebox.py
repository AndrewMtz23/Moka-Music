"""Theme-aware equivalents of the public tkinter.messagebox convenience functions."""

import tkinter as tk
from tkinter import messagebox as native
from tkinter import ttk

from .window_chrome import theme_window_caption


def _show(title, message, kind, choices, cancel, **options):
    parent = options.get("parent") or tk._default_root
    root = parent._root() if parent is not None else None
    colors = getattr(root, "_application_caption_palette", None)
    if not colors:
        return native._show(title, message, kind, choices.replace(" ", ""), **options)
    owner = parent.winfo_toplevel()
    focused = root.focus_get()
    previous_grab = root.grab_current()
    previous_grab_status = previous_grab.grab_status() if previous_grab is not None else None
    dialog = tk.Toplevel(owner)
    dialog.withdraw()
    dialog.title(title or "MokaMusic")
    dialog.transient(owner)
    dialog.resizable(False, False)
    dialog.configure(background=colors["background"])
    theme_window_caption(dialog, colors)
    result = cancel

    def finish(value):
        nonlocal result
        result = value
        dialog.destroy()

    translate = getattr(root, "_message_translate", lambda key: key)
    keys = {"ok": "Aceptar", "cancel": "Cancelar", "yes": "Sí", "no": "No", "retry": "Reintentar"}
    body = tk.Frame(dialog, background=colors["background"], padx=24, pady=20)
    body.pack(fill="both", expand=True)
    symbol = {"info": "i", "warning": "!", "error": "!", "question": "?"}.get(kind, "i")
    tk.Label(
        body,
        text=symbol,
        font=("Segoe UI", 24, "bold"),
        foreground=colors["highlight"],
        background=colors["background"],
    ).grid(row=0, column=0, sticky="n", padx=(0, 18))
    text = str(message or "")
    if options.get("detail"):
        text += "\n\n" + str(options["detail"])
    tk.Label(
        body,
        text=text,
        justify="left",
        anchor="w",
        wraplength=520,
        foreground=colors["text"],
        background=colors["background"],
    ).grid(row=0, column=1, sticky="w")
    buttons = ttk.Frame(body)
    buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(22, 0))
    first = None
    default = options.get("default", choices.split()[0])
    for choice in choices.split():
        key = "dialog.button_" + choice
        label = translate(key)
        if label == key:
            label = keys[choice]
        button = ttk.Button(buttons, text=label, command=lambda value=choice: finish(value))
        button.pack(side="left", padx=(8, 0))
        if choice == default:
            first = button
    dialog.protocol("WM_DELETE_WINDOW", lambda: finish(cancel))
    dialog.bind("<Escape>", lambda event: finish(cancel))
    dialog.bind(
        "<Return>",
        lambda event: dialog.focus_get().invoke() if isinstance(dialog.focus_get(), ttk.Button) else finish(default),
    )
    dialog.update_idletasks()
    width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    x = max(0, owner.winfo_rootx() + (owner.winfo_width() - width) // 2)
    y = max(0, owner.winfo_rooty() + (owner.winfo_height() - height) // 2)
    dialog.geometry(f"+{x}+{y}")
    dialog.deiconify()
    dialog.wait_visibility()
    dialog.grab_set()
    if first is not None:
        first.focus_set()
    try:
        dialog.wait_window()
    finally:
        if previous_grab is not None and previous_grab.winfo_exists():
            if previous_grab_status == "global":
                previous_grab.grab_set_global()
            else:
                previous_grab.grab_set()
        if focused is not None and focused.winfo_exists():
            focused.focus_set()
    return result


def showinfo(title=None, message=None, **options):
    return _show(title, message, "info", "ok", "ok", **options)


def showwarning(title=None, message=None, **options):
    return _show(title, message, "warning", "ok", "ok", **options)


def showerror(title=None, message=None, **options):
    return _show(title, message, "error", "ok", "ok", **options)


def askokcancel(title=None, message=None, **options):
    return _show(title, message, "question", "ok cancel", "cancel", **options) == "ok"


def askyesno(title=None, message=None, **options):
    return _show(title, message, "question", "yes no", "no", **options) == "yes"


def askyesnocancel(title=None, message=None, **options):
    result = _show(title, message, "question", "yes no cancel", "cancel", **options)
    return None if result == "cancel" else result == "yes"


def askretrycancel(title=None, message=None, **options):
    return _show(title, message, "warning", "retry cancel", "cancel", **options) == "retry"


def askquestion(title=None, message=None, **options):
    return _show(title, message, "question", "yes no", "no", **options)
