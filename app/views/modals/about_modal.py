from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Callable

GITHUB_URL = "https://github.com/AndrewMtz23/Moka-Music"


def show_about_modal(
    parent,
    t: Callable[..., str],
    *,
    app_name: str,
    version: str,
    copyright_text: str,
    theme_colors: dict[str, str],
) -> None:
    colors = _about_colors(theme_colors)
    modal = tk.Toplevel(parent)
    modal.title(t("dialog.about_title"))
    modal.configure(background=colors["background"])
    modal.resizable(False, False)
    modal.transient(parent)
    modal.grab_set()

    container = tk.Frame(modal, background=colors["background"], padx=18, pady=18)
    container.pack(fill="both", expand=True)

    card = tk.Frame(
        container,
        background=colors["surface"],
        highlightbackground=colors["border"],
        highlightthickness=1,
        padx=22,
        pady=20,
    )
    card.pack(fill="both", expand=True)

    header = tk.Frame(card, background=colors["surface"])
    header.pack(fill="x")

    logo = tk.Canvas(header, width=58, height=58, background=colors["surface"], borderwidth=0, highlightthickness=0)
    logo.pack(side="left", padx=(0, 14))
    logo.create_oval(4, 4, 54, 54, fill=colors["primary"], outline="")
    logo.create_text(29, 29, text="M", fill=colors["primary_text"], font=("Segoe UI Semibold", 24))

    title_area = tk.Frame(header, background=colors["surface"])
    title_area.pack(side="left", fill="x", expand=True)
    tk.Label(
        title_area,
        text=app_name,
        background=colors["surface"],
        foreground=colors["text"],
        font=("Segoe UI Semibold", 18),
        anchor="w",
    ).pack(fill="x")
    tk.Label(
        title_area,
        text=t("about.subtitle", version=version),
        background=colors["surface"],
        foreground=colors["muted"],
        font=("Segoe UI", 10),
        anchor="w",
    ).pack(fill="x", pady=(2, 0))

    body = tk.Label(
        card,
        text=t("about.body"),
        background=colors["surface"],
        foreground=colors["text"],
        font=("Segoe UI", 10),
        justify="left",
        wraplength=430,
        anchor="w",
    )
    body.pack(fill="x", pady=(18, 10))

    badge_row = tk.Frame(card, background=colors["surface"])
    badge_row.pack(fill="x", pady=(2, 12))
    _badge(badge_row, t("about.open_source_badge"), colors).pack(side="left", padx=(0, 8))
    _badge(badge_row, "Python + Tkinter", colors).pack(side="left", padx=(0, 8))
    _badge(badge_row, t("about.local_music_badge"), colors).pack(side="left")

    github_panel = tk.Frame(card, background=colors["surface_alt"], padx=12, pady=10)
    github_panel.pack(fill="x", pady=(0, 14))
    tk.Label(
        github_panel,
        text=t("about.github_label"),
        background=colors["surface_alt"],
        foreground=colors["muted"],
        font=("Segoe UI", 9),
        anchor="w",
    ).pack(fill="x")
    github_link = tk.Label(
        github_panel,
        text=GITHUB_URL,
        background=colors["surface_alt"],
        foreground=colors["primary"],
        font=("Segoe UI Semibold", 10),
        cursor="hand2",
        anchor="w",
    )
    github_link.pack(fill="x", pady=(2, 0))
    github_link.bind("<Button-1>", lambda _event: webbrowser.open(GITHUB_URL))

    footer = tk.Frame(card, background=colors["surface"])
    footer.pack(fill="x")
    tk.Label(
        footer,
        text=copyright_text,
        background=colors["surface"],
        foreground=colors["muted"],
        font=("Segoe UI", 8),
        anchor="w",
    ).pack(side="left", fill="x", expand=True)
    ttk.Button(
        footer,
        text=t("about.open_github"),
        command=lambda: webbrowser.open(GITHUB_URL),
        style="Accent.TButton",
    ).pack(side="right", padx=(8, 0))
    ttk.Button(footer, text="OK", command=modal.destroy, style="Secondary.TButton").pack(side="right")

    modal.bind("<Escape>", lambda _event: modal.destroy())
    modal.update_idletasks()
    x = parent.winfo_rootx() + max(20, (parent.winfo_width() - modal.winfo_width()) // 2)
    y = parent.winfo_rooty() + max(20, (parent.winfo_height() - modal.winfo_height()) // 3)
    modal.geometry(f"+{x}+{y}")
    modal.focus_set()


def _badge(parent, text: str, colors: dict[str, str]) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        background=colors["badge_bg"],
        foreground=colors["text"],
        font=("Segoe UI Semibold", 8),
        padx=9,
        pady=4,
    )


def _about_colors(theme_colors: dict[str, str]) -> dict[str, str]:
    surface = theme_colors.get("surface", "#ffffff")
    surface_alt = theme_colors.get("surface_alt", "#f3f4f6")
    primary = theme_colors.get("highlight", theme_colors.get("primary", "#2563eb"))
    return {
        "background": theme_colors.get("background", "#f6f6f4"),
        "surface": surface,
        "surface_alt": surface_alt,
        "text": theme_colors.get("text", "#111111"),
        "muted": theme_colors.get("text_secondary", "#666666"),
        "primary": primary,
        "primary_text": theme_colors.get("highlight_text", theme_colors.get("button_text", "#ffffff")),
        "border": theme_colors.get("border_soft", "#e5e7eb"),
        "badge_bg": surface_alt,
    }
