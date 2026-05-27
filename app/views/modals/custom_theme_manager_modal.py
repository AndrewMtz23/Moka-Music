from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable

from ...services.custom_theme_service import custom_theme_id, dedupe_theme_id


def manage_custom_themes(
    parent,
    translator: Callable[..., str],
    custom_themes: list[dict[str, object]],
) -> dict[str, object] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("theme_manager.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("640x420")
    modal.minsize(560, 360)

    result: dict[str, object] | None = None
    themes = [dict(theme) for theme in custom_themes]

    container = ttk.Frame(modal, padding=14)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(container, text=translator("theme_manager.description"), style="Muted.TLabel").grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(0, 10),
    )

    listbox = tk.Listbox(container, exportselection=False, activestyle="none", height=10)
    listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 12))

    button_panel = ttk.Frame(container)
    button_panel.grid(row=1, column=1, sticky="ns")

    def refresh_list(selected_index: int | None = None) -> None:
        listbox.delete(0, "end")
        for theme in themes:
            listbox.insert("end", str(theme.get("name", "") or theme.get("id", "")))
        if themes:
            index = min(selected_index if selected_index is not None else 0, len(themes) - 1)
            listbox.selection_set(index)
            listbox.activate(index)

    def selected_index() -> int | None:
        selection = listbox.curselection()
        return int(selection[0]) if selection else None

    def rename_selected() -> None:
        index = selected_index()
        if index is None:
            return
        name = simpledialog.askstring(
            translator("theme_manager.rename"),
            translator("theme_custom.name_prompt"),
            initialvalue=str(themes[index].get("name", "") or ""),
            parent=modal,
        )
        name = str(name or "").strip()
        if not name:
            return
        themes[index]["name"] = name
        refresh_list(index)

    def duplicate_selected() -> None:
        index = selected_index()
        if index is None:
            return
        duplicate = dict(themes[index])
        duplicate["name"] = translator("theme_manager.copy_name", name=duplicate.get("name", "Tema"))
        duplicate["id"] = dedupe_theme_id(custom_theme_id(str(duplicate["name"])), themes)
        themes.insert(index + 1, duplicate)
        refresh_list(index + 1)

    def delete_selected() -> None:
        index = selected_index()
        if index is None:
            return
        if not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("theme_manager.delete_confirm", name=themes[index].get("name", "")),
            parent=modal,
        ):
            return
        themes.pop(index)
        refresh_list(max(0, index - 1))

    def reset_factory() -> None:
        nonlocal result
        if not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("theme_manager.reset_confirm"),
            parent=modal,
        ):
            return
        result = {"themes": [], "reset_factory": True}
        modal.destroy()

    def save() -> None:
        nonlocal result
        result = {"themes": themes, "reset_factory": False}
        modal.destroy()

    ttk.Button(button_panel, text=translator("theme_manager.rename"), command=rename_selected).pack(fill="x", pady=(0, 8))
    ttk.Button(button_panel, text=translator("theme_manager.duplicate"), command=duplicate_selected).pack(fill="x", pady=(0, 8))
    ttk.Button(button_panel, text=translator("theme_manager.delete"), command=delete_selected, style="Secondary.TButton").pack(fill="x", pady=(0, 8))
    ttk.Button(button_panel, text=translator("theme_manager.reset_factory"), command=reset_factory, style="Secondary.TButton").pack(fill="x")

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
    ttk.Button(button_row, text=translator("metadata_edit.cancel"), command=modal.destroy, style="Secondary.TButton").pack(side="right")
    ttk.Button(button_row, text=translator("theme_settings.save"), command=save).pack(side="right", padx=(0, 8))

    refresh_list()
    modal.wait_window()
    return result
