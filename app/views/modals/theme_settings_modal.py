from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Callable

from ...ui.theme import THEME_PRESETS, is_valid_hex_color, palette_with_accent


THEME_CHOICES = (
    ("light", "theme_settings.light"),
    ("dark", "theme_settings.dark"),
    ("system", "theme_settings.system"),
    ("moka_classic", "theme_settings.moka_classic"),
    ("midnight_blue", "theme_settings.midnight_blue"),
    ("forest", "theme_settings.forest"),
    ("rose", "theme_settings.rose"),
    ("high_contrast", "theme_settings.high_contrast"),
    ("oled_black", "theme_settings.oled_black"),
)

FONT_SCALE_CHOICES = (0.85, 1.0, 1.15, 1.3)
DENSITY_CHOICES = (
    ("compact", "theme_settings.density_compact"),
    ("normal", "theme_settings.density_normal"),
    ("comfortable", "theme_settings.density_comfortable"),
)

THEME_SETTINGS_MODAL_GEOMETRY = "980x620"
THEME_SETTINGS_MODAL_MIN_SIZE = (880, 560)
THEME_SETTINGS_FULLSCREEN_SHORTCUT = "F11"


def request_theme_selection(
    parent,
    translator: Callable[..., str],
    current_theme: str,
    *,
    font_scale: float = 1.0,
    density: str = "normal",
    accent_color: str = "",
    custom_themes: list[dict[str, object]] | None = None,
) -> dict[str, object] | None:
    modal = tk.Toplevel(parent)
    modal.title(translator("theme_settings.title"))
    modal.transient(parent)
    modal.grab_set()
    modal.geometry(THEME_SETTINGS_MODAL_GEOMETRY)
    modal.minsize(*THEME_SETTINGS_MODAL_MIN_SIZE)
    modal.resizable(True, True)

    result: dict[str, object] | None = None
    custom_themes = custom_themes or []
    theme_options = theme_choice_labels(translator, custom_themes)
    custom_theme_by_id = {str(theme.get("id", "") or ""): theme for theme in custom_themes}
    theme_var = tk.StringVar(value=current_theme if current_theme in {choice[0] for choice in theme_options} else "light")
    font_scale_var = tk.StringVar(value=font_scale_label(font_scale))
    density_var = tk.StringVar(value=density_label(translator, density))
    accent_var = tk.StringVar(value=accent_color.lower() if is_valid_hex_color(accent_color) else "")
    fullscreen_var = tk.BooleanVar(value=False)

    container = ttk.Frame(modal, padding=18)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=0, minsize=280)
    container.columnconfigure(1, weight=1, minsize=600)
    container.rowconfigure(1, weight=1)

    ttk.Label(
        container,
        text=translator("theme_settings.description"),
        style="Muted.TLabel",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

    theme_panel = ttk.LabelFrame(container, text=translator("theme_settings.theme"), padding=10)
    theme_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
    theme_panel.columnconfigure(0, weight=1)
    theme_panel.rowconfigure(0, weight=1)

    preview_panel = ttk.LabelFrame(container, text=translator("theme_settings.preview"), padding=10)
    preview_panel.grid(row=1, column=1, sticky="nsew")
    preview_panel.columnconfigure(0, weight=1, minsize=560)
    preview_panel.rowconfigure(0, weight=1)

    theme_list = tk.Listbox(
        theme_panel,
        height=min(len(theme_options), 12),
        width=28,
        exportselection=False,
        activestyle="none",
        borderwidth=0,
        highlightthickness=1,
    )
    theme_list.grid(row=0, column=0, sticky="nsew")
    for _theme_id, label in theme_options:
        theme_list.insert("end", label)

    options_frame = ttk.Frame(theme_panel)
    options_frame.grid(row=1, column=0, sticky="ew", pady=(20, 0))
    options_frame.columnconfigure(0, weight=1)
    ttk.Label(options_frame, text=translator("theme_settings.font_size")).grid(row=0, column=0, sticky="w")
    font_menu = ttk.Combobox(
        options_frame,
        textvariable=font_scale_var,
        values=[font_scale_label(value) for value in FONT_SCALE_CHOICES],
        state="readonly",
        width=18,
    )
    font_menu.grid(row=1, column=0, sticky="ew", pady=(4, 10))
    ttk.Label(options_frame, text=translator("theme_settings.density")).grid(row=2, column=0, sticky="w")
    density_menu = ttk.Combobox(
        options_frame,
        textvariable=density_var,
        values=[translator(label_key) for _density_id, label_key in DENSITY_CHOICES],
        state="readonly",
        width=18,
    )
    density_menu.grid(row=3, column=0, sticky="ew", pady=(4, 10))

    ttk.Label(options_frame, text=translator("theme_settings.accent_color")).grid(row=4, column=0, sticky="w")
    accent_row = ttk.Frame(options_frame)
    accent_row.grid(row=5, column=0, sticky="ew", pady=(4, 0))
    accent_row.columnconfigure(1, weight=1)
    accent_swatch = tk.Label(accent_row, width=3, height=1, borderwidth=1, relief="solid")
    accent_swatch.grid(row=0, column=0, sticky="w", padx=(0, 6))
    accent_value = ttk.Label(accent_row, text="")
    accent_value.grid(row=0, column=1, sticky="ew")
    accent_buttons = ttk.Frame(options_frame)
    accent_buttons.grid(row=6, column=0, sticky="ew", pady=(6, 0))
    accent_buttons.columnconfigure(0, weight=1)
    accent_buttons.columnconfigure(1, weight=1)

    preview = tk.Frame(preview_panel, borderwidth=1, relief="solid")
    preview.grid(row=0, column=0, sticky="nsew")
    preview.columnconfigure(0, weight=1)

    preview_widgets = build_preview_widgets(preview, translator)
    preview_widgets["theme_list"] = theme_list

    def selected_theme_id() -> str:
        selection = theme_list.curselection()
        if not selection:
            return theme_var.get()
        return theme_options[int(selection[0])][0]

    def update_preview(*_args) -> None:
        theme_id = selected_theme_id()
        theme_var.set(theme_id)
        palette = preview_palette(theme_id, accent_var.get(), custom_themes)
        theme_list.configure(
            background=palette["surface"],
            foreground=palette["text"],
            selectbackground=palette["highlight"],
            selectforeground=palette["highlight_text"],
            highlightbackground=palette["border"],
            highlightcolor=palette["primary"],
        )
        apply_preview_palette(preview_widgets, palette)
        apply_preview_layout(preview_widgets, selected_font_scale(font_scale_var.get()), selected_density(translator, density_var.get()))
        accent_swatch.configure(background=accent_var.get() or palette["primary"])
        accent_value.configure(text=accent_var.get() or translator("theme_settings.default_accent"))

    def apply_custom_theme_options(theme_id: str) -> None:
        custom_theme = custom_theme_by_id.get(theme_id)
        if not custom_theme:
            return
        font_scale_var.set(font_scale_label(float(custom_theme.get("font_scale", 1.0) or 1.0)))
        density_var.set(density_label(translator, str(custom_theme.get("density", "normal") or "normal")))
        accent_color = str(custom_theme.get("accent_color", "") or "")
        accent_var.set(accent_color.lower() if is_valid_hex_color(accent_color) else "")

    def select_theme(*_args) -> None:
        apply_custom_theme_options(selected_theme_id())
        update_preview()

    def choose_accent() -> None:
        theme_id = selected_theme_id()
        current_color = accent_var.get() if is_valid_hex_color(accent_var.get()) else preview_palette(theme_id, custom_themes=custom_themes)["primary"]
        _rgb, selected_color = colorchooser.askcolor(
            parent=modal,
            color=current_color,
            title=translator("theme_settings.accent_color"),
        )
        if selected_color:
            accent_var.set(selected_color.lower())
            update_preview()

    def clear_accent() -> None:
        accent_var.set("")
        update_preview()

    def set_fullscreen(enabled: bool) -> None:
        fullscreen_var.set(enabled)
        modal.attributes("-fullscreen", enabled)
        fullscreen_button.configure(
            text=translator("theme_settings.exit_fullscreen")
            if enabled
            else translator("theme_settings.fullscreen")
        )

    def toggle_fullscreen(_event=None) -> str:
        set_fullscreen(not fullscreen_var.get())
        return "break"

    def exit_fullscreen(_event=None) -> str | None:
        if fullscreen_var.get():
            set_fullscreen(False)
            return "break"
        return None

    initial_index = next(
        (index for index, (theme_id, _label) in enumerate(theme_options) if theme_id == theme_var.get()),
        0,
    )
    theme_list.selection_set(initial_index)
    theme_list.activate(initial_index)
    theme_list.bind("<<ListboxSelect>>", select_theme)
    font_menu.bind("<<ComboboxSelected>>", update_preview)
    density_menu.bind("<<ComboboxSelected>>", update_preview)
    ttk.Button(
        accent_buttons,
        text=translator("theme_settings.choose_color"),
        command=choose_accent,
        style="Secondary.TButton",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    ttk.Button(
        accent_buttons,
        text=translator("theme_settings.clear_accent"),
        command=clear_accent,
        style="Secondary.TButton",
    ).grid(row=0, column=1, sticky="ew")

    def save() -> None:
        nonlocal result
        result = {
            "theme": theme_var.get(),
            "font_scale": selected_font_scale(font_scale_var.get()),
            "density": selected_density(translator, density_var.get()),
            "accent_color": accent_var.get() if is_valid_hex_color(accent_var.get()) else "",
        }
        modal.destroy()

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(22, 0))
    fullscreen_button = ttk.Button(
        button_row,
        text=translator("theme_settings.fullscreen"),
        command=toggle_fullscreen,
        style="Secondary.TButton",
    )
    fullscreen_button.pack(side="left")
    ttk.Button(
        button_row,
        text=translator("metadata_edit.cancel"),
        command=modal.destroy,
        style="Secondary.TButton",
    ).pack(side="right")
    ttk.Button(
        button_row,
        text=translator("theme_settings.save"),
        command=save,
    ).pack(side="right", padx=(0, 8))

    modal.bind(f"<{THEME_SETTINGS_FULLSCREEN_SHORTCUT}>", toggle_fullscreen)
    modal.bind("<Escape>", exit_fullscreen)
    update_preview()
    modal.wait_window()
    return result


def theme_choice_labels(translator: Callable[..., str], custom_themes: list[dict[str, object]] | None = None) -> list[tuple[str, str]]:
    choices = [(theme_id, translator(label_key)) for theme_id, label_key in THEME_CHOICES]
    for theme in custom_themes or []:
        theme_id = str(theme.get("id", "") or "")
        name = str(theme.get("name", "") or "")
        if theme_id and name:
            choices.append((theme_id, name))
    return choices


def preview_palette(theme_id: str, accent_color: str = "", custom_themes: list[dict[str, object]] | None = None) -> dict[str, str]:
    for theme in custom_themes or []:
        if str(theme.get("id", "") or "") == theme_id:
            base_theme = str(theme.get("base_theme", "light") or "light")
            theme_accent = accent_color or str(theme.get("accent_color", "") or "")
            return palette_with_accent(THEME_PRESETS.get(base_theme, THEME_PRESETS["light"]), theme_accent)
    if theme_id == "system":
        return palette_with_accent(THEME_PRESETS["light"], accent_color)
    return palette_with_accent(THEME_PRESETS.get(theme_id, THEME_PRESETS["light"]), accent_color)


def font_scale_label(value: float) -> str:
    return f"{int(round(value * 100))}%"


def selected_font_scale(label: str) -> float:
    try:
        return max(0.85, min(1.3, int(label.rstrip("%")) / 100))
    except (TypeError, ValueError):
        return 1.0


def density_label(translator: Callable[..., str], density: str) -> str:
    mapping = {density_id: translator(label_key) for density_id, label_key in DENSITY_CHOICES}
    return mapping.get(density, mapping["normal"])


def selected_density(translator: Callable[..., str], label: str) -> str:
    mapping = {translator(label_key): density_id for density_id, label_key in DENSITY_CHOICES}
    return mapping.get(label, "normal")


def build_preview_widgets(parent: tk.Frame, translator: Callable[..., str]) -> dict[str, tk.Widget]:
    widgets: dict[str, tk.Widget] = {"preview": parent}
    parent.rowconfigure(2, weight=1)

    header = tk.Frame(parent, borderwidth=0)
    header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
    header.columnconfigure(1, weight=1)
    widgets["header"] = header
    widgets["primary_button"] = tk.Label(header, text=translator("button.select_folder"), padx=12, pady=8)
    widgets["primary_button"].grid(row=0, column=0, sticky="w", padx=(0, 8))
    widgets["secondary_button"] = tk.Label(header, text="↻", padx=12, pady=8)
    widgets["secondary_button"].grid(row=0, column=1, sticky="w")
    widgets["sort_field"] = tk.Label(header, text=translator("sort.by_bitrate"), anchor="w", padx=10, pady=8)
    widgets["sort_field"].grid(row=0, column=2, sticky="e", padx=(8, 0))

    controls = tk.Frame(parent, borderwidth=0)
    controls.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
    controls.columnconfigure(1, weight=1)
    widgets["controls"] = controls
    widgets["search_label"] = tk.Label(controls, text=translator("search.label"), padx=0, pady=6)
    widgets["search_label"].grid(row=0, column=0, sticky="w", padx=(0, 6))
    widgets["search_field"] = tk.Label(controls, text=translator("search.placeholder"), anchor="w", padx=10, pady=8)
    widgets["search_field"].grid(row=0, column=1, sticky="ew", padx=(0, 10))
    widgets["filter_label"] = tk.Label(controls, text=translator("filter.label"), padx=0, pady=6)
    widgets["filter_label"].grid(row=0, column=2, sticky="w", padx=(0, 6))
    widgets["filter_field"] = tk.Label(controls, text=translator("filter.bitrate_128"), anchor="w", padx=10, pady=8)
    widgets["filter_field"].grid(row=0, column=3, sticky="e")

    sample_list = tk.Frame(parent, borderwidth=0)
    sample_list.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
    sample_list.columnconfigure(0, weight=1)
    widgets["list"] = sample_list
    rows = [
        ("selected_row", "0. MOKA - See You Again [META]"),
        ("alternate_row", "1. MOKA - LA PRIMERA [128 kbps]"),
        ("normal_row", "2. MOKA - La Prision"),
        ("warning_row", "3. MOKA - Bruce Wayne [DUP]"),
        ("error_row", "4. MOKA - Archivo danado [ERR]"),
    ]
    for index, (key, text) in enumerate(rows):
        widgets[key] = tk.Label(sample_list, text=text, anchor="w", padx=8, pady=6)
        widgets[key].grid(row=index, column=0, sticky="ew")

    footer = tk.Frame(parent, borderwidth=0)
    footer.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
    footer.columnconfigure(0, weight=1)
    widgets["footer"] = footer
    widgets["status"] = tk.Label(footer, text=translator("filter.results", shown=114, total=794), anchor="w", padx=10, pady=8)
    widgets["status"].grid(row=0, column=0, sticky="ew")
    widgets["success_chip"] = tk.Label(footer, text=translator("toast.done"), padx=10, pady=8)
    widgets["success_chip"].grid(row=0, column=1, sticky="e", padx=(8, 0))

    return widgets


def apply_preview_palette(widgets: dict[str, tk.Widget], palette: dict[str, str]) -> None:
    for key in ("preview", "header", "controls", "list", "footer"):
        widgets[key].configure(background=palette["surface"])
    for key in ("search_label", "filter_label"):
        widgets[key].configure(background=palette["surface"], foreground=palette["text"])
    widgets["primary_button"].configure(background=palette["primary"], foreground=palette["button_text"])
    widgets["secondary_button"].configure(background=palette["secondary"], foreground=palette["text"])
    for key in ("search_field", "filter_field", "sort_field"):
        widgets[key].configure(background=palette["field"], foreground=palette["text_secondary"])
    widgets["selected_row"].configure(background=palette["highlight"], foreground=palette["highlight_text"])
    widgets["alternate_row"].configure(background=palette["surface_alt"], foreground=palette["text"])
    widgets["normal_row"].configure(background=palette["surface"], foreground=palette["text"])
    widgets["warning_row"].configure(background=palette["surface_alt"], foreground=palette["warning"])
    widgets["error_row"].configure(background=palette["surface"], foreground=palette["error"])
    widgets["status"].configure(background=palette["surface_alt"], foreground=palette["text_secondary"])
    widgets["success_chip"].configure(background=palette["success"], foreground=palette["highlight_text"])


def apply_preview_layout(widgets: dict[str, tk.Widget], font_scale: float, density: str) -> None:
    density_padding = {
        "compact": 4,
        "normal": 6,
        "comfortable": 8,
    }.get(density, 6)
    font_size = max(9, int(10 * font_scale))
    small_font_size = max(8, int(9 * font_scale))
    for key in (
        "primary_button",
        "secondary_button",
        "sort_field",
        "search_label",
        "search_field",
        "filter_label",
        "filter_field",
        "selected_row",
        "alternate_row",
        "normal_row",
        "warning_row",
        "error_row",
        "status",
        "success_chip",
    ):
        widgets[key].configure(font=("Segoe UI", font_size), pady=density_padding)
    widgets["status"].configure(font=("Segoe UI", small_font_size))
