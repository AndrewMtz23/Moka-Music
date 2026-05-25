import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, Literal


ThemeMode = Literal["dark", "light", "system"]


class StyleManager:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.style = ttk.Style()
        self.logger = logging.getLogger(__name__)
        self.current_theme: ThemeMode = "light"
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
        font_size = max(10, int(10 * self.scaling_factor))
        small_size = max(9, int(9 * self.scaling_factor))
        self.base_font = ("Segoe UI", font_size)
        self.small_font = ("Segoe UI", small_size)
        self.heading_font = ("Segoe UI Semibold", font_size)
        self.title_font = ("Segoe UI Semibold", font_size + 1)

        self.root.option_add("*Font", self.base_font)
        self.root.option_add("*Menu.Font", self.small_font)

    def _create_theme_styles(self) -> None:
        self.dark_palette = {
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
        self.light_palette = {
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
        self._create_common_styles()

    def _create_common_styles(self) -> None:
        pad_x = int(10 * self.scaling_factor)
        pad_y = int(7 * self.scaling_factor)
        row_height = int(30 * self.scaling_factor)

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
        palette = self.dark_palette if self.current_theme == "dark" else self.light_palette
        return palette.get(color_name, "#000000")

    def set_theme(self, theme: ThemeMode) -> None:
        if theme == "system":
            try:
                import darkdetect

                detected = darkdetect.theme()
                theme = "dark" if detected and detected.lower() == "dark" else "light"
            except Exception:
                theme = "light"

        self.current_theme = "dark" if theme == "dark" else "light"
        self._apply_theme_colors()

    def _apply_theme_colors(self) -> None:
        self.root.configure(bg=self._get_color("background"))
        self._create_common_styles()

    def adjust_for_dpi(self) -> None:
        self._setup_base_theme()
        self._create_common_styles()

    def get_theme_colors(self) -> Dict[str, str]:
        return self.dark_palette if self.current_theme == "dark" else self.light_palette

    def create_rounded_style(self, widget_type: str, radius: int = 10):
        return f"Rounded.{widget_type}"
