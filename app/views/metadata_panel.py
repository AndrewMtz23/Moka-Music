from dataclasses import dataclass
from typing import Callable
import tkinter as tk
from tkinter import ttk


@dataclass
class MetadataPanelBundle:
    frame: ttk.LabelFrame
    meta_vars: dict[str, tk.StringVar]
    cleanup_preset_var: tk.StringVar
    cleanup_preset_menu: ttk.Combobox
    text_widgets: dict[str, object]


def build_metadata_panel(
    parent,
    *,
    t: Callable[..., str],
    on_apply_selected: Callable[[], None],
    on_batch_edit: Callable[[], None],
    on_apply_all: Callable[[], None],
    on_clear_fields: Callable[[], None],
    on_quick_cleanup: Callable[[str], None],
    on_number_tracks: Callable[[], None],
    on_rename_from_metadata: Callable[[], None],
    on_auto_cover: Callable[[], None],
    on_apply_preset: Callable[[], None],
    on_create_preset: Callable[[], None],
    on_delete_preset: Callable[[], None],
) -> MetadataPanelBundle:
    text_widgets: dict[str, object] = {}
    meta_frame = ttk.LabelFrame(parent, text=t("metadata.global"))
    meta_frame.pack(fill="x", pady=(0, 4))
    text_widgets["metadata_frame"] = meta_frame

    meta_vars = {
        "artist": tk.StringVar(value=""),
        "album_artist": tk.StringVar(value=""),
        "album": tk.StringVar(value=""),
        "genre": tk.StringVar(value=""),
        "year": tk.StringVar(value=""),
        "comment": tk.StringVar(value=""),
    }

    row1 = ttk.Frame(meta_frame)
    row1.pack(fill="x", pady=(0, 8), padx=2)
    artist_label = ttk.Label(row1, text=t("metadata.artist"))
    artist_label.pack(side="left", padx=(0, 5))
    text_widgets["artist_label"] = artist_label
    ttk.Entry(row1, textvariable=meta_vars["artist"], width=30).pack(
        side="left",
        fill="x",
        expand=True,
        padx=(0, 10),
    )
    genre_label = ttk.Label(row1, text=t("metadata.genre"))
    genre_label.pack(side="left", padx=(0, 5))
    text_widgets["genre_label"] = genre_label
    ttk.Entry(row1, textvariable=meta_vars["genre"], width=20).pack(
        side="left",
        fill="x",
        expand=True,
    )

    row2 = ttk.Frame(meta_frame)
    row2.pack(fill="x", pady=(0, 8), padx=2)
    album_label = ttk.Label(row2, text=t("metadata.album"))
    album_label.pack(side="left", padx=(0, 5))
    text_widgets["album_label"] = album_label
    ttk.Entry(row2, textvariable=meta_vars["album"], width=30).pack(
        side="left",
        fill="x",
        expand=True,
        padx=(0, 10),
    )
    year_label = ttk.Label(row2, text=t("metadata.year"))
    year_label.pack(side="left", padx=(0, 5))
    text_widgets["year_label"] = year_label
    ttk.Entry(row2, textvariable=meta_vars["year"], width=10).pack(side="left")

    row3 = ttk.Frame(meta_frame)
    row3.pack(fill="x", pady=(0, 8), padx=2)
    album_artist_label = ttk.Label(row3, text=t("metadata.album_artist"))
    album_artist_label.pack(side="left", padx=(0, 5))
    text_widgets["album_artist_label"] = album_artist_label
    ttk.Entry(row3, textvariable=meta_vars["album_artist"], width=30).pack(
        side="left",
        fill="x",
        expand=True,
        padx=(0, 10),
    )
    comment_label = ttk.Label(row3, text=t("metadata.comment"))
    comment_label.pack(side="left", padx=(0, 5))
    text_widgets["comment_label"] = comment_label
    ttk.Entry(row3, textvariable=meta_vars["comment"], width=30).pack(
        side="left",
        fill="x",
        expand=True,
    )

    button_row = ttk.Frame(meta_frame)
    button_row.pack(fill="x", pady=(4, 0), padx=2)
    apply_selected = ttk.Button(button_row, text=t("button.apply_selected"), command=on_apply_selected)
    apply_selected.pack(side="left", padx=(0, 5))
    text_widgets["apply_selected_button"] = apply_selected
    batch_edit = ttk.Button(button_row, text=t("button.batch_edit"), command=on_batch_edit)
    batch_edit.pack(side="left", padx=(0, 5))
    text_widgets["batch_edit_button"] = batch_edit
    apply_all = ttk.Button(button_row, text=t("button.apply_all"), command=on_apply_all)
    apply_all.pack(side="left", padx=(0, 5))
    text_widgets["apply_all_button"] = apply_all
    clear_fields = ttk.Button(button_row, text=t("button.clear_fields"), command=on_clear_fields)
    clear_fields.pack(side="right")
    text_widgets["clear_fields_button"] = clear_fields

    quick_frame = ttk.LabelFrame(meta_frame, text=t("quick_actions.title"))
    quick_frame.pack(fill="x", pady=(10, 0), padx=2)
    text_widgets["quick_actions_frame"] = quick_frame

    quick_buttons = [
        ("quick_remove_feat_button", "quick_actions.remove_feat", lambda: on_quick_cleanup("remove_feat")),
        (
            "quick_remove_parentheses_button",
            "quick_actions.remove_parentheses",
            lambda: on_quick_cleanup("remove_parentheses"),
        ),
        ("quick_title_only_button", "quick_actions.title_only", lambda: on_quick_cleanup("title_only")),
        (
            "quick_title_from_file_button",
            "quick_actions.title_from_file",
            lambda: on_quick_cleanup("title_from_file"),
        ),
        ("quick_number_tracks_button", "quick_actions.number_tracks", on_number_tracks),
        ("quick_copy_artist_button", "quick_actions.copy_artist", lambda: on_quick_cleanup("copy_artist")),
        ("quick_rename_metadata_button", "quick_actions.rename_from_metadata", on_rename_from_metadata),
        ("quick_auto_cover_button", "quick_actions.auto_cover", on_auto_cover),
    ]
    for index, (name, text_key, command) in enumerate(quick_buttons):
        button = ttk.Button(
            quick_frame,
            text=t(text_key),
            command=command,
            style="Secondary.TButton",
        )
        button.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)
        quick_frame.columnconfigure(index % 3, weight=1)
        text_widgets[name] = button

    preset_row = ttk.Frame(quick_frame)
    preset_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=4, pady=(8, 4))
    preset_row.columnconfigure(1, weight=1)

    preset_label = ttk.Label(preset_row, text=t("presets.label"))
    preset_label.grid(row=0, column=0, sticky="w", padx=(0, 6))
    text_widgets["preset_label"] = preset_label

    cleanup_preset_var = tk.StringVar(value="")
    cleanup_preset_menu = ttk.Combobox(
        preset_row,
        textvariable=cleanup_preset_var,
        values=[],
        state="readonly",
        width=28,
    )
    cleanup_preset_menu.grid(row=0, column=1, sticky="ew", padx=(0, 6))

    apply_preset_button = ttk.Button(
        preset_row,
        text=t("presets.apply"),
        command=on_apply_preset,
        style="Secondary.TButton",
    )
    apply_preset_button.grid(row=0, column=2, sticky="ew", padx=(0, 6))
    text_widgets["apply_preset_button"] = apply_preset_button

    create_preset_button = ttk.Button(
        preset_row,
        text=t("presets.create"),
        command=on_create_preset,
        style="Secondary.TButton",
    )
    create_preset_button.grid(row=0, column=3, sticky="ew", padx=(0, 6))
    text_widgets["create_preset_button"] = create_preset_button

    delete_preset_button = ttk.Button(
        preset_row,
        text=t("presets.delete"),
        command=on_delete_preset,
        style="Secondary.TButton",
    )
    delete_preset_button.grid(row=0, column=4, sticky="ew")
    text_widgets["delete_preset_button"] = delete_preset_button

    return MetadataPanelBundle(
        frame=meta_frame,
        meta_vars=meta_vars,
        cleanup_preset_var=cleanup_preset_var,
        cleanup_preset_menu=cleanup_preset_menu,
        text_widgets=text_widgets,
    )
