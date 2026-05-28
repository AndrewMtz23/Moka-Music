import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict


ThemeMode = str
DensityMode = str

DENSITY_SETTINGS = {
    "compact": {"pad": 0.78, "row": 0.82},
    "normal": {"pad": 1.0, "row": 1.0},
    "comfortable": {"pad": 1.18, "row": 1.18},
}


def is_valid_hex_color(color: str) -> bool:
    if not isinstance(color, str):
        return False
    if len(color) != 7 or not color.startswith("#"):
        return False
    return all(character in "0123456789abcdefABCDEF" for character in color[1:])


def readable_text_color(background: str) -> str:
    if not is_valid_hex_color(background):
        return "#ffffff"
    red = int(background[1:3], 16) / 255
    green = int(background[3:5], 16) / 255
    blue = int(background[5:7], 16) / 255
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return "#111111" if luminance > 0.62 else "#ffffff"


def palette_with_accent(palette: dict[str, str], accent_color: str) -> dict[str, str]:
    next_palette = dict(palette)
    if not is_valid_hex_color(accent_color):
        return next_palette
    text_color = readable_text_color(accent_color)
    next_palette["primary"] = accent_color
    next_palette["primary_hover"] = accent_color
    next_palette["highlight"] = accent_color
    next_palette["button_text"] = text_color
    next_palette["highlight_text"] = text_color
    return next_palette


LIGHT_PALETTE = {
    "background": "#f6f6f4",
    "surface": "#ffffff",
    "surface_alt": "#eeeeeb",
    "field": "#ffffff",
    "primary": "#111111",
    "primary_hover": "#2a2a2a",
    "secondary": "#ededeb",
    "secondary_hover": "#dededb",
    "button_text": "#ffffff",
    "secondary_text": "#111111",
    "text": "#111111",
    "text_secondary": "#666666",
    "disabled": "#a1a1a1",
    "highlight": "#111111",
    "highlight_text": "#ffffff",
    "error": "#b91c1c",
    "success": "#166534",
    "warning": "#92400e",
    "border": "#d7d7d2",
    "border_soft": "#e7e7e3",
}

DARK_PALETTE = {
    "background": "#0f0f10",
    "surface": "#18181b",
    "surface_alt": "#202124",
    "field": "#111113",
    "primary": "#f5f5f5",
    "primary_hover": "#e5e5e5",
    "secondary": "#2b2c30",
    "secondary_hover": "#3a3b40",
    "button_text": "#0f0f10",
    "secondary_text": "#f5f5f5",
    "text": "#f4f4f5",
    "text_secondary": "#a1a1aa",
    "disabled": "#696970",
    "highlight": "#ffffff",
    "highlight_text": "#111113",
    "error": "#ef4444",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "border": "#303036",
    "border_soft": "#242429",
}

THEME_PRESETS: dict[str, dict[str, str]] = {
    "light": LIGHT_PALETTE,
    "dark": DARK_PALETTE,
    "moka_classic": {
        **LIGHT_PALETTE,
        "background": "#f7f3ec",
        "surface": "#fffaf2",
        "surface_alt": "#efe7da",
        "primary": "#6d3d14",
        "primary_hover": "#87511f",
        "highlight": "#6d3d14",
        "warning": "#a16207",
        "border": "#dfd0bd",
        "border_soft": "#eadfce",
    },
    "midnight_blue": {
        **DARK_PALETTE,
        "background": "#09111f",
        "surface": "#111827",
        "surface_alt": "#1f2937",
        "field": "#0b1220",
        "primary": "#93c5fd",
        "primary_hover": "#bfdbfe",
        "secondary": "#1e3a5f",
        "secondary_hover": "#25476f",
        "button_text": "#08111f",
        "highlight": "#60a5fa",
        "highlight_text": "#06111f",
        "warning": "#fbbf24",
        "border": "#2d405f",
        "border_soft": "#1f314a",
    },
    "forest": {
        **DARK_PALETTE,
        "background": "#0c1510",
        "surface": "#132019",
        "surface_alt": "#1c2d23",
        "field": "#0f1a14",
        "primary": "#86efac",
        "primary_hover": "#bbf7d0",
        "secondary": "#244232",
        "secondary_hover": "#31563f",
        "button_text": "#07120c",
        "highlight": "#4ade80",
        "highlight_text": "#06120b",
        "success": "#22c55e",
        "warning": "#eab308",
        "border": "#294637",
        "border_soft": "#20372b",
    },
    "rose": {
        **LIGHT_PALETTE,
        "background": "#fff1f2",
        "surface": "#fff7f7",
        "surface_alt": "#ffe4e6",
        "field": "#ffffff",
        "primary": "#be123c",
        "primary_hover": "#9f1239",
        "highlight": "#be123c",
        "success": "#15803d",
        "warning": "#b45309",
        "border": "#fecdd3",
        "border_soft": "#ffe4e6",
    },
    "high_contrast": {
        **DARK_PALETTE,
        "background": "#000000",
        "surface": "#000000",
        "surface_alt": "#171717",
        "field": "#050505",
        "primary": "#ffffff",
        "primary_hover": "#facc15",
        "secondary": "#262626",
        "secondary_hover": "#404040",
        "button_text": "#000000",
        "secondary_text": "#ffffff",
        "text": "#ffffff",
        "text_secondary": "#e5e5e5",
        "highlight": "#facc15",
        "highlight_text": "#000000",
        "warning": "#facc15",
        "border": "#ffffff",
        "border_soft": "#737373",
    },
    "oled_black": {
        **DARK_PALETTE,
        "background": "#000000",
        "surface": "#050505",
        "surface_alt": "#101010",
        "field": "#000000",
        "primary": "#e5e7eb",
        "primary_hover": "#ffffff",
        "secondary": "#18181b",
        "secondary_hover": "#27272a",
        "highlight": "#e5e7eb",
        "highlight_text": "#000000",
        "border": "#1f1f23",
        "border_soft": "#151519",
    },
}


class StyleManager:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.style = ttk.Style()
        self.logger = logging.getLogger(__name__)
        self.current_theme: ThemeMode = "light"
        self.current_palette: dict[str, str] = dict(THEME_PRESETS["light"])
        self.custom_theme_palettes: dict[str, dict[str, str]] = {}
        self.font_scale = 1.0
        self.density: DensityMode = "normal"
        self.accent_color = ""
        self.scaling_factor = self._detect_scaling()
        self._setup_base_theme()
        self._create_theme_styles()
        self.set_theme("light")

    def _detect_scaling(self) -> float:
        try:
            from ctypes import windll

            windll.shcore.SetProcessDpiAwareness(1)
            return self.root.winfo_fpixels("1i") / 72.0
        except Exception:
            return 1.0

    def _setup_base_theme(self) -> None:
        self.style.theme_use("clam")
        font_size = max(9, int(10 * self.scaling_factor * self.font_scale))
        small_size = max(8, int(9 * self.scaling_factor * self.font_scale))
        self.base_font = ("Segoe UI", font_size)
        self.small_font = ("Segoe UI", small_size)
        self.heading_font = ("Segoe UI Semibold", font_size)
        self.title_font = ("Segoe UI Semibold", font_size + 1)

        self.root.option_add("*Font", self.base_font)
        self.root.option_add("*Menu.Font", self.small_font)
        self.root.option_add("*Menu.borderWidth", 0)
        self.root.option_add("*Menu.relief", "flat")

    def _create_theme_styles(self) -> None:
        self.light_palette = dict(THEME_PRESETS["light"])
        self.dark_palette = dict(THEME_PRESETS["dark"])
        self._create_common_styles()

    def _create_common_styles(self) -> None:
        density = DENSITY_SETTINGS.get(self.density, DENSITY_SETTINGS["normal"])
        pad_multiplier = density["pad"]
        row_multiplier = density["row"]
        pad_x = int(10 * self.scaling_factor * pad_multiplier)
        pad_y = int(7 * self.scaling_factor * pad_multiplier)
        row_height = int(30 * self.scaling_factor * row_multiplier * self.font_scale)

        self.style.configure("TFrame", background=self._get_color("surface"))
        self.style.configure("Panel.TFrame", background=self._get_color("surface"))

        self.style.configure(
            "TLabel",
            font=self.base_font,
            foreground=self._get_color("text"),
            background=self._get_color("surface"),
            padding=(2, 2),
        )
        self.style.configure(
            "Muted.TLabel",
            font=self.small_font,
            foreground=self._get_color("text_secondary"),
            background=self._get_color("surface"),
        )
        self.style.configure(
            "Title.TLabel",
            font=self.title_font,
            foreground=self._get_color("text"),
            background=self._get_color("surface"),
        )

        self.style.configure(
            "TLabelframe",
            background=self._get_color("surface"),
            bordercolor=self._get_color("border"),
            darkcolor=self._get_color("border"),
            lightcolor=self._get_color("border"),
            relief="solid",
            borderwidth=1,
            padding=(12, 10),
        )
        self.style.configure(
            "TLabelframe.Label",
            font=self.heading_font,
            foreground=self._get_color("text_secondary"),
            background=self._get_color("surface"),
            padding=(6, 0),
        )

        self.style.configure(
            "TButton",
            font=self.heading_font,
            foreground=self._get_color("button_text"),
            background=self._get_color("primary"),
            borderwidth=0,
            focusthickness=0,
            focuscolor=self._get_color("primary"),
            relief="flat",
            padding=(pad_x + 4, pad_y),
        )
        self.style.map(
            "TButton",
            background=[
                ("disabled", self._get_color("secondary")),
                ("pressed", self._get_color("primary_hover")),
                ("active", self._get_color("primary_hover")),
            ],
            foreground=[
                ("disabled", self._get_color("disabled")),
                ("!disabled", self._get_color("button_text")),
            ],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )

        self.style.configure(
            "Secondary.TButton",
            font=self.heading_font,
            foreground=self._get_color("secondary_text"),
            background=self._get_color("secondary"),
            borderwidth=0,
            relief="flat",
            padding=(pad_x + 4, pad_y),
        )
        self.style.map(
            "Secondary.TButton",
            background=[("active", self._get_color("secondary_hover")), ("pressed", self._get_color("secondary_hover"))],
            foreground=[("!disabled", self._get_color("secondary_text"))],
        )

        self.style.configure(
            "Accent.TButton",
            font=self.heading_font,
            foreground=self._get_color("button_text"),
            background=self._get_color("primary"),
            borderwidth=0,
            relief="flat",
            padding=(pad_x + 4, pad_y),
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", self._get_color("primary_hover")), ("pressed", self._get_color("primary_hover"))],
            foreground=[("!disabled", self._get_color("button_text"))],
        )

        self.style.configure(
            "TEntry",
            font=self.base_font,
            foreground=self._get_color("text"),
            background=self._get_color("field"),
            fieldbackground=self._get_color("field"),
            insertcolor=self._get_color("text"),
            bordercolor=self._get_color("border"),
            lightcolor=self._get_color("border"),
            darkcolor=self._get_color("border"),
            borderwidth=1,
            relief="solid",
            padding=(pad_x, pad_y),
        )
        self.style.map(
            "TEntry",
            bordercolor=[("focus", self._get_color("primary")), ("!focus", self._get_color("border"))],
        )

        self.style.configure(
            "TCombobox",
            font=self.base_font,
            foreground=self._get_color("text"),
            background=self._get_color("field"),
            fieldbackground=self._get_color("field"),
            selectbackground=self._get_color("field"),
            selectforeground=self._get_color("text"),
            bordercolor=self._get_color("border"),
            lightcolor=self._get_color("border"),
            darkcolor=self._get_color("border"),
            arrowcolor=self._get_color("text_secondary"),
            relief="solid",
            padding=(pad_x, pad_y),
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", self._get_color("field"))],
            foreground=[("readonly", self._get_color("text"))],
            bordercolor=[("focus", self._get_color("primary")), ("!focus", self._get_color("border"))],
        )

        self.style.configure(
            "TCheckbutton",
            font=self.base_font,
            foreground=self._get_color("text"),
            background=self._get_color("surface"),
            indicatorcolor=self._get_color("field"),
            bordercolor=self._get_color("border"),
            padding=(6, 2),
        )
        self.style.map(
            "TCheckbutton",
            foreground=[("disabled", self._get_color("disabled")), ("!disabled", self._get_color("text"))],
            background=[("active", self._get_color("surface"))],
            indicatorcolor=[
                ("selected", self._get_color("primary")),
                ("!selected", self._get_color("field")),
            ],
        )

        self.style.configure(
            "Treeview",
            font=self.base_font,
            foreground=self._get_color("text"),
            background=self._get_color("surface"),
            fieldbackground=self._get_color("surface"),
            bordercolor=self._get_color("border_soft"),
            borderwidth=0,
            rowheight=row_height,
        )
        self.style.configure(
            "Treeview.Heading",
            font=self.heading_font,
            foreground=self._get_color("text_secondary"),
            background=self._get_color("surface_alt"),
            bordercolor=self._get_color("border_soft"),
            relief="flat",
            padding=(8, 8),
        )
        self.style.map(
            "Treeview",
            background=[("selected", self._get_color("highlight"))],
            foreground=[("selected", self._get_color("highlight_text"))],
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", self._get_color("surface_alt"))],
            foreground=[("active", self._get_color("text"))],
        )

        self.style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=self._get_color("surface_alt"),
            troughcolor=self._get_color("surface"),
            bordercolor=self._get_color("surface"),
            arrowcolor=self._get_color("text_secondary"),
            relief="flat",
            width=12,
        )
        self.style.configure(
            "Horizontal.TScrollbar",
            gripcount=0,
            background=self._get_color("surface_alt"),
            troughcolor=self._get_color("surface"),
            bordercolor=self._get_color("surface"),
            arrowcolor=self._get_color("text_secondary"),
            relief="flat",
            width=12,
        )

        self.style.configure(
            "Horizontal.TProgressbar",
            background=self._get_color("primary"),
            troughcolor=self._get_color("surface_alt"),
            bordercolor=self._get_color("surface_alt"),
            lightcolor=self._get_color("primary"),
            darkcolor=self._get_color("primary"),
            thickness=int(8 * self.scaling_factor),
        )

        self.style.configure(
            "Horizontal.TScale",
            background=self._get_color("surface"),
            troughcolor=self._get_color("surface_alt"),
            bordercolor=self._get_color("border"),
            lightcolor=self._get_color("primary"),
            darkcolor=self._get_color("primary"),
        )

        self.style.configure("Success.TLabel", foreground=self._get_color("success"))
        self.style.configure("Error.TLabel", foreground=self._get_color("error"))
        self.style.configure("Warning.TLabel", foreground=self._get_color("warning"))

    def _get_color(self, color_name: str) -> str:
        return self.current_palette.get(color_name, "#000000")

    def set_theme(self, theme: ThemeMode) -> None:
        if theme == "system":
            try:
                import darkdetect

                detected = darkdetect.theme()
                theme = "dark" if detected and detected.lower() == "dark" else "light"
            except Exception:
                theme = "light"

        palette = self.custom_theme_palettes.get(theme)
        if palette is None and theme not in THEME_PRESETS:
            theme = "light"
            palette = THEME_PRESETS[theme]
        elif palette is None:
            palette = THEME_PRESETS[theme]

        self.current_theme = theme
        self.current_palette = palette_with_accent(palette, self.accent_color)
        self._apply_theme_colors()

    def set_custom_themes(self, custom_themes: list[dict[str, object]]) -> None:
        palettes: dict[str, dict[str, str]] = {}
        for theme in custom_themes:
            theme_id = str(theme.get("id", "") or "")
            base_theme = str(theme.get("base_theme", "light") or "light")
            if not theme_id:
                continue
            base_palette = THEME_PRESETS.get(base_theme, THEME_PRESETS["light"])
            accent_color = str(theme.get("accent_color", "") or "")
            palettes[theme_id] = palette_with_accent(base_palette, accent_color)
        self.custom_theme_palettes = palettes

    def set_appearance_options(
        self,
        *,
        font_scale: float | None = None,
        density: DensityMode | None = None,
        accent_color: str | None = None,
    ) -> None:
        if font_scale is not None:
            self.font_scale = max(0.85, min(1.3, float(font_scale)))
        if density is not None:
            self.density = density if density in DENSITY_SETTINGS else "normal"
        if accent_color is not None:
            self.accent_color = accent_color.lower() if is_valid_hex_color(accent_color) else ""
            base_palette = self.custom_theme_palettes.get(self.current_theme, THEME_PRESETS.get(self.current_theme, THEME_PRESETS["light"]))
            self.current_palette = palette_with_accent(base_palette, self.accent_color)
        self._setup_base_theme()
        self._apply_theme_colors()

    def _apply_theme_colors(self) -> None:
        self.root.configure(bg=self._get_color("background"))
        self.root.option_add("*Menu.background", self._get_color("surface"))
        self.root.option_add("*Menu.foreground", self._get_color("text"))
        self.root.option_add("*Menu.activeBackground", self._get_color("primary"))
        self.root.option_add("*Menu.activeForeground", self._get_color("button_text"))
        self.root.option_add("*Menu.disabledForeground", self._get_color("disabled"))
        self.root.option_add("*Menu.selectColor", self._get_color("primary"))
        self._create_common_styles()

    def adjust_for_dpi(self) -> None:
        self._setup_base_theme()
        self._create_common_styles()

    def get_theme_colors(self) -> Dict[str, str]:
        return self.current_palette

    def create_rounded_style(self, widget_type: str, radius: int = 10):
        return f"Rounded.{widget_type}"
