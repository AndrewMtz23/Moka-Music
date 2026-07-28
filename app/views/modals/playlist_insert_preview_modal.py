import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable

PreviewRow = tuple[str, str, str, str, str]


def playlist_preview_rows(plan) -> list[PreviewRow]:
    rows: list[PreviewRow] = []
    for item in getattr(plan, "items", []):
        old_position = "" if item.old_position is None else str(item.old_position)
        rows.append(
            (
                item.old_name,
                old_position,
                str(item.new_position),
                str(item.track_number),
                item.new_name,
            )
        )
    return rows


def playlist_preview_issues(plan) -> list[str]:
    issues: list[str] = []
    seen_names: dict[str, int] = {}
    for item in getattr(plan, "items", []):
        metadata = {}
        try:
            cached = item.controller.get_track_info(item.old_name)
            metadata = cached.metadata if cached else {}
        except Exception:
            metadata = {}
        title = str(metadata.get("title", "") or "").strip()
        artist = str(metadata.get("artist", "") or "").strip()
        if not title:
            issues.append(f"{item.old_name}: missing_title")
        if not artist and " - " not in item.old_name:
            issues.append(f"{item.old_name}: missing_artist")
        seen_names[item.new_name] = seen_names.get(item.new_name, 0) + 1

    for name, count in seen_names.items():
        if count > 1:
            issues.append(f"{name}: duplicate_name")
    return issues


def request_playlist_insert_preview(
    parent,
    translator: Callable[..., str],
    plan,
    rebuild_plan: Callable[[list[str]], object] | None = None,
):
    modal = tk.Toplevel(parent)
    modal.title(translator("playlist_preview.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry("1100x520")
    modal.minsize(760, 340)

    current_plan = plan
    original_plan = plan
    result = None
    visible_index_to_plan_index: dict[str, int] = {}
    drag_start_item = ""

    container = ttk.Frame(modal, padding=12)
    container.pack(fill="both", expand=True)
    container.rowconfigure(3, weight=1)
    container.columnconfigure(0, weight=1)

    description_label = ttk.Label(
        container,
        wraplength=900,
    )
    description_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
    issue_label = ttk.Label(container, foreground="#b45309", wraplength=1000)
    issue_label.grid(row=0, column=0, sticky="e", pady=(0, 10))

    reorder_row = ttk.Frame(container)
    reorder_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    search_row = ttk.Frame(container)
    search_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    search_row.columnconfigure(1, weight=1)
    search_var = tk.StringVar(value="")
    ttk.Label(search_row, text=translator("playlist_preview.search")).grid(row=0, column=0, sticky="w", padx=(0, 6))
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

    columns = ("file", "old_position", "new_position", "track", "new_name")
    tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="extended")
    tree.heading("file", text=translator("playlist_preview.file"))
    tree.heading("old_position", text=translator("playlist_preview.old_position"))
    tree.heading("new_position", text=translator("playlist_preview.new_position"))
    tree.heading("track", text=translator("playlist_preview.track"))
    tree.heading("new_name", text=translator("playlist_preview.new_name"))
    tree.column("file", width=240, anchor="w")
    tree.column("old_position", width=100, anchor="center")
    tree.column("new_position", width=110, anchor="center")
    tree.column("track", width=90, anchor="center")
    tree.column("new_name", width=380, anchor="w")
    tree.grid(row=3, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=3, column=1, sticky="ns")

    def row_matches_query(row: PreviewRow, query: str) -> bool:
        if not query:
            return True
        haystack = " ".join(row).casefold()
        return query.casefold() in haystack

    def render(selected_names: list[str] | None = None) -> None:
        visible_index_to_plan_index.clear()
        rows = playlist_preview_rows(current_plan)
        issues = playlist_preview_issues(current_plan)
        query = search_var.get().strip()
        visible_rows = [(plan_index, row) for plan_index, row in enumerate(rows) if row_matches_query(row, query)]
        description = translator("playlist_preview.description", count=len(rows))
        if query:
            description += " " + translator("playlist_preview.search_results", shown=len(visible_rows), total=len(rows))
        description_label.configure(text=description)
        if issues:
            issue_label.configure(text=translator("playlist_preview.issues", count=len(issues)))
        else:
            issue_label.configure(text="")
        tree.delete(*tree.get_children())
        selected_names = selected_names or []
        selected_ids: list[str] = []
        for visible_index, (plan_index, row) in enumerate(visible_rows):
            item_id = str(visible_index)
            visible_index_to_plan_index[item_id] = plan_index
            tree.insert("", "end", iid=item_id, values=row)
            if row[0] in selected_names:
                selected_ids.append(item_id)
        if selected_ids:
            tree.selection_set(selected_ids)
            tree.focus(selected_ids[0])
            tree.see(selected_ids[0])

    def selected_indices() -> list[int]:
        return sorted(
            visible_index_to_plan_index[item_id]
            for item_id in tree.selection()
            if item_id in visible_index_to_plan_index
        )

    def selected_names() -> list[str]:
        return [
            current_plan.items[index].old_name for index in selected_indices() if 0 <= index < len(current_plan.items)
        ]

    def rebuild_from_order(order: list[str], selected: list[str]) -> None:
        nonlocal current_plan
        if rebuild_plan is None:
            return
        current_plan = rebuild_plan(order)
        render(selected)

    def restore_original_order() -> None:
        nonlocal current_plan
        current_plan = original_plan
        render()

    def move_selected(offset: int) -> None:
        indices = selected_indices()
        if not indices:
            return
        names = selected_names()
        order = [item.old_name for item in current_plan.items]
        if offset < 0:
            for index in indices:
                if index <= 0 or index - 1 in indices:
                    continue
                order[index - 1], order[index] = order[index], order[index - 1]
        else:
            for index in reversed(indices):
                if index >= len(order) - 1 or index + 1 in indices:
                    continue
                order[index + 1], order[index] = order[index], order[index + 1]
        rebuild_from_order(order, names)

    def move_to_position() -> None:
        names = selected_names()
        if not names:
            return
        position = simpledialog.askinteger(
            translator("playlist_preview.move_title"),
            translator("playlist_preview.move_prompt", count=len(names)),
            parent=modal,
            minvalue=1,
            maxvalue=len(current_plan.items),
        )
        if position is None:
            return
        order = [item.old_name for item in current_plan.items if item.old_name not in names]
        insert_at = max(0, min(position - 1, len(order)))
        order[insert_at:insert_at] = names
        rebuild_from_order(order, names)

    def move_names_before_target(names: list[str], target_name: str) -> None:
        if not names or target_name in names:
            return
        order = [item.old_name for item in current_plan.items]
        remaining = [name for name in order if name not in names]
        try:
            target_index = remaining.index(target_name)
        except ValueError:
            return
        remaining[target_index:target_index] = names
        rebuild_from_order(remaining, names)

    def on_drag_start(event) -> None:
        nonlocal drag_start_item
        drag_start_item = tree.identify_row(event.y)

    def on_drag_release(event) -> None:
        nonlocal drag_start_item
        if not drag_start_item:
            return
        target_item = tree.identify_row(event.y)
        source_item = drag_start_item
        drag_start_item = ""
        if not target_item or target_item == source_item:
            return
        source_plan_index = visible_index_to_plan_index.get(source_item)
        target_plan_index = visible_index_to_plan_index.get(target_item)
        if source_plan_index is None or target_plan_index is None:
            return
        source_name = current_plan.items[source_plan_index].old_name
        target_name = current_plan.items[target_plan_index].old_name
        names = selected_names()
        if source_name not in names:
            names = [source_name]
        move_names_before_target(names, target_name)

    ttk.Button(reorder_row, text=translator("playlist_preview.move_up"), command=lambda: move_selected(-1)).pack(
        side="left",
        padx=(0, 6),
    )
    ttk.Button(reorder_row, text=translator("playlist_preview.move_down"), command=lambda: move_selected(1)).pack(
        side="left",
        padx=(0, 6),
    )
    ttk.Button(reorder_row, text=translator("playlist_preview.move_to"), command=move_to_position).pack(
        side="left",
        padx=(0, 6),
    )
    ttk.Button(
        reorder_row,
        text=translator("playlist_preview.restore_order"),
        command=restore_original_order,
        style="Secondary.TButton",
    ).pack(side="left", padx=(8, 6))

    def clear_search() -> None:
        search_var.set("")

    ttk.Button(
        search_row, text=translator("playlist_preview.clear_search"), command=clear_search, style="Secondary.TButton"
    ).grid(
        row=0,
        column=2,
        sticky="e",
    )
    search_var.trace_add("write", lambda *_args: render(selected_names()))
    tree.bind("<ButtonPress-1>", on_drag_start, add="+")
    tree.bind("<ButtonRelease-1>", on_drag_release, add="+")

    button_row = ttk.Frame(container)
    button_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def apply_playlist_plan() -> None:
        nonlocal result
        rows = playlist_preview_rows(current_plan)
        issues = playlist_preview_issues(current_plan)
        if issues and not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("playlist_preview.confirm_with_issues", count=len(issues)),
            parent=modal,
        ):
            return
        if not messagebox.askyesno(
            translator("dialog.confirm"),
            translator("playlist_preview.confirm", count=len(rows)),
            parent=modal,
        ):
            return
        result = current_plan
        modal.destroy()

    ttk.Button(button_row, text=translator("playlist_preview.apply"), command=apply_playlist_plan).pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")

    render()
    search_entry.focus_set()
    modal.wait_window()
    return result


def confirm_playlist_insert_preview(parent, translator: Callable[..., str], plan) -> bool:
    return request_playlist_insert_preview(parent, translator, plan) is not None
