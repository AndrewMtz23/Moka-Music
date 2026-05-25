from dataclasses import dataclass
from typing import Callable
import tkinter as tk
from tkinter import ttk

from ..controllers.metadata_controller import MetadataController
from ..models import FilterMode
from ..ui_helpers.widgets import LibraryListbox


@dataclass
class LibraryPanelBundle:
    frame: ttk.LabelFrame
    tree: LibraryListbox
    select_button: ttk.Button
    search_label: ttk.Label
    filter_label: ttk.Label
    sort_menu: ttk.Combobox
    sort_var: tk.StringVar
    search_var: tk.StringVar
    search_entry: ttk.Entry
    filter_var: tk.StringVar
    filter_menu: ttk.Combobox
    result_label: ttk.Label
    action_button: ttk.Button
    clear_button: ttk.Button
    extra_button: ttk.Button | None = None
    second_extra_button: ttk.Button | None = None

    def panel_state(self, controller: MetadataController) -> dict[str, object]:
        return {
            "controller": controller,
            "tree": self.tree,
            "search_var": self.search_var,
            "search_entry": self.search_entry,
            "search_placeholder_active": False,
            "filter_var": self.filter_var,
            "filter_mode": FilterMode.ALL,
            "filter_menu": self.filter_menu,
            "result_label": self.result_label,
        }


def build_library_panel(
    parent,
    *,
    controller: MetadataController,
    title: str,
    is_main: bool,
    t: Callable[..., str],
    style_manager,
    sort_options: list[str],
    filter_options: list[str],
    on_select_folder: Callable[[MetadataController, LibraryListbox], None],
    on_song_select: Callable[[MetadataController, LibraryListbox], None],
    on_play_selected: Callable[[MetadataController, LibraryListbox], None],
    on_start_reorder,
    on_finish_reorder,
    on_context_menu,
    on_sort: Callable[[MetadataController, LibraryListbox, str], None],
    on_refresh: Callable[[MetadataController, LibraryListbox], None],
    on_action: Callable[[MetadataController, LibraryListbox], None],
    on_clear_folder: Callable[[MetadataController, LibraryListbox], None],
    extra_action_text: str = "",
    on_extra_action: Callable[[], None] | None = None,
    second_extra_action_text: str = "",
    on_second_extra_action: Callable[[], None] | None = None,
) -> LibraryPanelBundle:
    frame = ttk.LabelFrame(parent, text=title)
    try:
        parent.add(frame, weight=3 if is_main else 2)
    except tk.TclError:
        parent.add(frame)

    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(2, weight=1)

    toolbar = ttk.Frame(frame)
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

    sort_var = tk.StringVar(value=t("sort.by_name"))
    search_var = tk.StringVar(value="")
    filter_var = tk.StringVar(value=t("filter.all"))

    select_button = ttk.Button(
        toolbar,
        text=t("button.select_folder"),
        command=lambda: on_select_folder(controller, tree),
        style="Secondary.TButton",
    )
    select_button.pack(side="left", padx=(0, 5))

    clear_button = ttk.Button(
        toolbar,
        text=t("button.close_folder"),
        command=lambda: on_clear_folder(controller, tree),
        style="Secondary.TButton",
    )
    clear_button.pack(side="left", padx=(0, 5))

    extra_button = None
    if extra_action_text and on_extra_action is not None:
        extra_button = ttk.Button(
            toolbar,
            text=extra_action_text,
            command=on_extra_action,
            style="Secondary.TButton",
        )
        extra_button.pack(side="left", padx=(0, 5))

    second_extra_button = None
    if second_extra_action_text and on_second_extra_action is not None:
        second_extra_button = ttk.Button(
            toolbar,
            text=second_extra_action_text,
            command=on_second_extra_action,
            style="Secondary.TButton",
        )
        second_extra_button.pack(side="left", padx=(0, 5))

    sort_menu = ttk.Combobox(
        toolbar,
        textvariable=sort_var,
        values=sort_options,
        state="readonly",
        width=18,
    )
    sort_menu.pack(side="right", ipady=1)

    search_row = ttk.Frame(frame)
    search_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    search_label = ttk.Label(search_row, text=t("search.label"))
    search_label.pack(side="left", padx=(0, 4))

    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=1)

    filter_label = ttk.Label(search_row, text=t("filter.label"))
    filter_label.pack(side="left", padx=(0, 4))

    filter_menu = ttk.Combobox(
        search_row,
        textvariable=filter_var,
        values=filter_options,
        state="readonly",
        width=16,
    )
    filter_menu.pack(side="left", ipady=1)

    result_label = ttk.Label(search_row, text=t("filter.results", shown=0, total=0), width=12, anchor="e")
    result_label.pack(side="right", padx=(6, 0))

    scrollbar_frame = ttk.Frame(frame)
    scrollbar_frame.grid(row=2, column=0, sticky="nsew")
    scrollbar_frame.columnconfigure(0, weight=1)
    scrollbar_frame.rowconfigure(0, weight=1)

    colors = style_manager.get_theme_colors()
    tree = LibraryListbox(
        scrollbar_frame,
        font=style_manager.base_font,
        background=colors["surface"],
        foreground=colors["text"],
        selectbackground=colors["highlight"],
        selectforeground=colors["highlight_text"],
        height=13,
    )
    tree.grid(row=0, column=0, sticky="nsew")
    tree.heading("#0", text=t("tree.song_name"))
    tree.heading("num", text="#")
    tree.heading("path", text=t("tree.file_path"))
    tree.column("#0", width=260, anchor="w", minwidth=160, stretch=True)
    tree.column("num", width=44, anchor="center", minwidth=44, stretch=False)
    tree.column("path", width=520, anchor="w", minwidth=260, stretch=True)

    scrollbar = ttk.Scrollbar(scrollbar_frame, orient="vertical", command=tree.yview)
    horizontal_scrollbar = ttk.Scrollbar(scrollbar_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal_scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")
    horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

    tree.bind("<<TreeviewSelect>>", lambda _event: on_song_select(controller, tree))
    tree.bind("<Double-1>", lambda _event: on_play_selected(controller, tree))
    tree.bind("<ButtonPress-1>", lambda event: on_start_reorder(event, controller, tree), add="+")
    tree.bind("<ButtonRelease-1>", lambda event: on_finish_reorder(event, controller, tree), add="+")
    tree.bind("<Button-3>", lambda event: on_context_menu(event, controller, tree))
    sort_menu.bind("<<ComboboxSelected>>", lambda _event: on_sort(controller, tree, sort_var.get()))
    search_var.trace_add("write", lambda *_args: on_refresh(controller, tree))
    filter_menu.bind("<<ComboboxSelected>>", lambda _event: on_refresh(controller, tree))

    action_button = ttk.Button(
        frame,
        text=t("button.add_song" if is_main else "button.move_to_main"),
        command=lambda: on_action(controller, tree),
        style="Secondary.TButton" if is_main else "Accent.TButton",
    )
    action_button.grid(row=3, column=0, sticky="ew", pady=(10, 0), ipady=2)

    return LibraryPanelBundle(
        frame=frame,
        tree=tree,
        select_button=select_button,
        search_label=search_label,
        filter_label=filter_label,
        sort_menu=sort_menu,
        sort_var=sort_var,
        search_var=search_var,
        search_entry=search_entry,
        filter_var=filter_var,
        filter_menu=filter_menu,
        result_label=result_label,
        action_button=action_button,
        clear_button=clear_button,
        extra_button=extra_button,
        second_extra_button=second_extra_button,
    )
