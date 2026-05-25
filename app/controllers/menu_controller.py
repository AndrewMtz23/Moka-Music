from dataclasses import dataclass
from typing import Callable
import tkinter as tk


@dataclass
class MenuCallbacks:
    open_main_folder: Callable[[], None]
    open_incoming_folder: Callable[[], None]
    select_cover: Callable[[], None]
    exit_app: Callable[[], None]
    change_theme: Callable[[str], None]
    show_quality_report: Callable[[], None]
    show_backup_history: Callable[[], None]
    undo_last_metadata_change: Callable[[], None]
    change_language: Callable[[str], None]
    show_about: Callable[[], None]


class MenuController:
    def __init__(self, root, translator: Callable[..., str], callbacks: MenuCallbacks) -> None:
        self.root = root
        self.t = translator
        self.callbacks = callbacks

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def build(self) -> tk.Menu:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=self.t("menu.open_main_folder"), command=self.callbacks.open_main_folder)
        file_menu.add_command(label=self.t("menu.open_incoming_folder"), command=self.callbacks.open_incoming_folder)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.select_cover"), command=self.callbacks.select_cover)
        file_menu.add_separator()
        file_menu.add_command(label=self.t("menu.exit"), command=self.callbacks.exit_app)
        menubar.add_cascade(label=self.t("menu.file"), menu=file_menu)

        theme_menu = tk.Menu(menubar, tearoff=0)
        theme_menu.add_command(label=self.t("menu.theme_dark"), command=lambda: self.callbacks.change_theme("dark"))
        theme_menu.add_command(label=self.t("menu.theme_light"), command=lambda: self.callbacks.change_theme("light"))
        theme_menu.add_command(label=self.t("menu.theme_system"), command=lambda: self.callbacks.change_theme("system"))
        menubar.add_cascade(label=self.t("menu.theme"), menu=theme_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label=self.t("menu.quality_report"), command=self.callbacks.show_quality_report)
        tools_menu.add_command(label=self.t("menu.backup_history"), command=self.callbacks.show_backup_history)
        tools_menu.add_command(label=self.t("menu.undo_last_metadata"), command=self.callbacks.undo_last_metadata_change)
        menubar.add_cascade(label=self.t("menu.tools"), menu=tools_menu)

        language_menu = tk.Menu(menubar, tearoff=0)
        language_menu.add_command(label=self.t("menu.language_es"), command=lambda: self.callbacks.change_language("es"))
        language_menu.add_command(label=self.t("menu.language_en"), command=lambda: self.callbacks.change_language("en"))
        menubar.add_cascade(label=self.t("menu.language"), menu=language_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=self.t("menu.about"), command=self.callbacks.show_about)
        menubar.add_cascade(label=self.t("menu.help"), menu=help_menu)

        return menubar

    def install(self) -> None:
        self.root.config(menu=self.build())
