from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable


def show_info_modal(
    parent,
    *,
    title: str,
    body: str | Iterable[str],
    theme_colors: dict[str, str],
    icon_text: str = "i",
) -> None:
    colors = _info_colors(theme_colors)
    modal = tk.Toplevel(parent)
    modal.title(title)
    modal.configure(background=colors["background"])
    modal.resizable(False, False)
    modal.transient(parent)
    modal.grab_set()

    container = tk.Frame(modal, background=colors["background"], padx=16, pady=16)
    container.pack(fill="both", expand=True)

    card = tk.Frame(
        container,
        background=colors["surface"],
        highlightbackground=colors["border"],
        highlightthickness=1,
        padx=18,
        pady=16,
    )
    card.pack(fill="both", expand=True)

    header = tk.Frame(card, background=colors["surface"])
    header.pack(fill="x", pady=(0, 12))

    icon = tk.Canvas(header, width=42, height=42, background=colors["surface"], borderwidth=0, highlightthickness=0)
    icon.pack(side="left", padx=(0, 12))
    icon.create_oval(3, 3, 39, 39, fill=colors["primary"], outline="")
    icon.create_text(21, 21, text=icon_text, fill=colors["primary_text"], font=("Segoe UI Semibold", 17))

    tk.Label(
        header,
        text=title,
        background=colors["surface"],
        foreground=colors["text"],
        font=("Segoe UI Semibold", 14),
        anchor="w",
    ).pack(side="left", fill="x", expand=True)

    body_frame = tk.Frame(card, background=colors["surface"])
    body_frame.pack(fill="both", expand=True)

    if isinstance(body, str):
        lines = body.splitlines()
    else:
        lines = list(body)

    if _looks_like_key_value(lines):
        _render_key_values(body_frame, lines, colors)
    elif _looks_like_numbered_steps(lines):
        _render_numbered_steps(body_frame, lines, colors)
    else:
        tk.Label(
            body_frame,
            text="\n".join(lines),
            background=colors["surface"],
            foreground=colors["text"],
            font=("Segoe UI", 10),
            justify="left",
            wraplength=520,
            anchor="w",
        ).pack(fill="x")

    footer = tk.Frame(card, background=colors["surface"])
    footer.pack(fill="x", pady=(16, 0))
    ttk.Button(footer, text="OK", command=modal.destroy, style="Accent.TButton").pack(side="right")

    modal.bind("<Escape>", lambda _event: modal.destroy())
    modal.update_idletasks()
    x = parent.winfo_rootx() + max(20, (parent.winfo_width() - modal.winfo_width()) // 2)
    y = parent.winfo_rooty() + max(20, (parent.winfo_height() - modal.winfo_height()) // 3)
    modal.geometry(f"+{x}+{y}")
    modal.focus_set()


def _render_key_values(parent, lines: list[str], colors: dict[str, str]) -> None:
    for index, line in enumerate(lines):
        row = tk.Frame(parent, background=colors["surface_alt"] if index % 2 else colors["surface"], padx=10, pady=6)
        row.pack(fill="x")
        if ":" in line:
            key, value = line.split(":", 1)
        else:
            key, value = line, ""
        tk.Label(
            row,
            text=key.strip(),
            background=row["background"],
            foreground=colors["muted"],
            font=("Segoe UI Semibold", 9),
            width=18,
            anchor="w",
        ).pack(side="left")
        tk.Label(
            row,
            text=value.strip(),
            background=row["background"],
            foreground=colors["text"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=390,
        ).pack(side="left", fill="x", expand=True)


def _render_numbered_steps(parent, lines: list[str], colors: dict[str, str]) -> None:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        number, text = stripped.split(".", 1)
        row = tk.Frame(parent, background=colors["surface_alt"], padx=10, pady=8)
        row.pack(fill="x", pady=(0, 8))
        badge = tk.Canvas(
            row, width=28, height=28, background=colors["surface_alt"], borderwidth=0, highlightthickness=0
        )
        badge.pack(side="left", padx=(0, 10))
        badge.create_oval(2, 2, 26, 26, fill=colors["primary"], outline="")
        badge.create_text(14, 14, text=number.strip(), fill=colors["primary_text"], font=("Segoe UI Semibold", 9))
        tk.Label(
            row,
            text=text.strip(),
            background=colors["surface_alt"],
            foreground=colors["text"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=430,
        ).pack(side="left", fill="x", expand=True)


def _looks_like_key_value(lines: list[str]) -> bool:
    relevant = [line for line in lines if line.strip()]
    return bool(relevant) and all(":" in line for line in relevant[:8])


def _looks_like_numbered_steps(lines: list[str]) -> bool:
    relevant = [line.strip() for line in lines if line.strip()]
    if not relevant:
        return False
    for index, line in enumerate(relevant, start=1):
        if not line.startswith(f"{index}."):
            return False
    return True


def _info_colors(theme_colors: dict[str, str]) -> dict[str, str]:
    return {
        "background": theme_colors.get("background", "#f6f6f4"),
        "surface": theme_colors.get("surface", "#ffffff"),
        "surface_alt": theme_colors.get("surface_alt", "#f3f4f6"),
        "text": theme_colors.get("text", "#111111"),
        "muted": theme_colors.get("text_secondary", "#666666"),
        "primary": theme_colors.get("highlight", theme_colors.get("primary", "#2563eb")),
        "primary_text": theme_colors.get("highlight_text", theme_colors.get("button_text", "#ffffff")),
        "border": theme_colors.get("border_soft", "#e5e7eb"),
    }
