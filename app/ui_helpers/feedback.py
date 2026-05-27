from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ProgressDialog:
    def __init__(self, root, *, title: str, message: str, total: int, cancel_text: str) -> None:
        self.root = root
        self.total = max(1, int(total))
        self.cancelled = False
        self.window = tk.Toplevel(root)
        self.window.title(title)
        self.window.transient(root)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill="both", expand=True)

        self.message_label = ttk.Label(frame, text=message, width=44, anchor="w")
        self.message_label.pack(fill="x", pady=(0, 8))

        self.detail_label = ttk.Label(frame, text="", width=44, anchor="w")
        self.detail_label.pack(fill="x", pady=(0, 10))

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=self.total)
        self.progress.pack(fill="x", pady=(0, 10))

        self.counter_label = ttk.Label(frame, text=f"0 / {self.total}", anchor="e")
        self.counter_label.pack(fill="x")

        self.cancel_button = ttk.Button(frame, text=cancel_text, command=self.cancel, style="Secondary.TButton")
        self.cancel_button.pack(anchor="e", pady=(10, 0))

        self._center()
        self.window.grab_set()
        self.root.update_idletasks()

    def update(self, completed: int, total: int | None = None, detail: str = "") -> bool:
        if total is not None and total > 0 and total != self.total:
            self.total = total
            self.progress.configure(maximum=self.total)
        completed = max(0, min(int(completed), self.total))
        self.progress.configure(value=completed)
        self.counter_label.configure(text=f"{completed} / {self.total}")
        if detail:
            self.detail_label.configure(text=detail)
        self.root.update_idletasks()
        return not self.cancelled

    def cancel(self) -> None:
        self.cancelled = True
        self.cancel_button.configure(state="disabled")

    def close(self) -> None:
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        self.window.destroy()
        self.root.update_idletasks()

    def _center(self) -> None:
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()
        parent_x = self.root.winfo_rootx()
        parent_y = self.root.winfo_rooty()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()
        x = parent_x + max(0, (parent_width - width) // 2)
        y = parent_y + max(0, (parent_height - height) // 2)
        self.window.geometry(f"+{x}+{y}")


def show_toast(root, message: str, *, kind: str = "success", duration_ms: int = 2800) -> None:
    colors = {
        "success": ("#12351f", "#d9ffe5", "#2f8f46"),
        "warning": ("#3b300f", "#fff2bf", "#b98a00"),
        "error": ("#401a1a", "#ffe0e0", "#bf4040"),
        "info": ("#17263a", "#e3efff", "#3e78bd"),
    }
    background, foreground, border = colors.get(kind, colors["info"])
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)

    label = tk.Label(
        toast,
        text=message,
        background=background,
        foreground=foreground,
        borderwidth=1,
        relief="solid",
        padx=14,
        pady=10,
        font=("Segoe UI", 10),
        wraplength=360,
        justify="left",
        highlightthickness=1,
        highlightbackground=border,
    )
    label.pack()
    toast.update_idletasks()

    width = toast.winfo_reqwidth()
    height = toast.winfo_reqheight()
    x = root.winfo_rootx() + root.winfo_width() - width - 28
    y = root.winfo_rooty() + root.winfo_height() - height - 28
    toast.geometry(f"+{max(0, x)}+{max(0, y)}")
    toast.after(duration_ms, toast.destroy)
