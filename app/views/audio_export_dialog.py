"""One themed dialog for export destination and codec-specific settings."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from ..models.audio_export_settings import AudioExportSettings
from ..services.audio_edit_service import _safe_output_name
from ..utils.window_chrome import theme_window_caption


class AudioExportDialog(tk.Toplevel):
    def __init__(self, parent, *, translate, colors, folder, name, settings):
        super().__init__(parent)
        self.withdraw()
        self.translate = translate
        self.result = None
        self.title(translate("audio_editor.export_settings_title"))
        self.transient(parent)
        self.configure(background=colors["background"])
        self.resizable(False, False)
        self.name_var = tk.StringVar(value=name)
        self.folder_var = tk.StringVar(value=str(folder))
        self.format_var = tk.StringVar(value=settings.format)
        self.rate_var = tk.StringVar(value=str(settings.sample_rate))
        self.bitrate_var = tk.StringVar(value=str(settings.bitrate_kbps))
        self.depth_var = tk.StringVar(value=str(settings.bit_depth))
        self.quality_var = tk.StringVar(value=str(settings.ogg_quality))
        self.error_var = tk.StringVar()
        content = ttk.Frame(self, padding=20, style="Editor.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(1, weight=1)
        ttk.Label(content, text=translate("audio_editor.export_settings_title"), style="Editor.Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16)
        )
        self._label(content, "audio_editor.export_filename", 1)
        self.name_entry = ttk.Entry(content, textvariable=self.name_var, width=44)
        self.name_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)
        self._label(content, "audio_editor.export_folder", 2)
        ttk.Entry(content, textvariable=self.folder_var, width=36).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Button(
            content, text=translate("audio_editor.export_browse"), command=self._browse, style="Editor.TButton"
        ).grid(row=2, column=2, padx=(8, 0))
        ttk.Separator(content).grid(row=3, column=0, columnspan=3, sticky="ew", pady=12)
        self._label(content, "audio_editor.export_format", 4)
        format_box = ttk.Combobox(
            content, textvariable=self.format_var, values=(".mp3", ".wav", ".flac", ".ogg"), state="readonly", width=16
        )
        format_box.grid(row=4, column=1, sticky="w", pady=5)
        format_box.bind("<<ComboboxSelected>>", lambda _event: self._sync_format())
        self._label(content, "audio_editor.export_sample_rate", 5)
        self.rate_box = ttk.Combobox(content, textvariable=self.rate_var, state="readonly", width=16)
        self.rate_box.grid(row=5, column=1, sticky="w", pady=5)
        self._optional_fields = {}
        for key, variable, values, row in (
            ("export_bitrate", self.bitrate_var, (128, 192, 256, 320), 6),
            ("export_ogg_quality", self.quality_var, (3, 5, 7, 9), 7),
            ("export_bit_depth", self.depth_var, (16, 24), 8),
        ):
            label = self._label(content, "audio_editor." + key, row)
            box = ttk.Combobox(content, textvariable=variable, values=values, state="readonly", width=16)
            box.grid(row=row, column=1, sticky="w", pady=5)
            self._optional_fields[key] = (label, box)
        ttk.Label(
            content, text=translate("audio_editor.export_safe_hint"), wraplength=480, style="Editor.Muted.TLabel"
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(14, 8))
        tk.Label(
            content,
            textvariable=self.error_var,
            wraplength=480,
            background=colors["background"],
            foreground=colors["error"],
            anchor="w",
            justify="left",
        ).grid(row=10, column=0, columnspan=3, sticky="ew")
        actions = ttk.Frame(content, style="Editor.TFrame")
        actions.grid(row=11, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(
            actions, text=translate("audio_editor.export_cancel"), command=self.destroy, style="Editor.TButton"
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions, text=translate("audio_editor.export"), command=self._accept, style="Editor.Primary.TButton"
        ).pack(side="left")
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", self._on_return)
        self._sync_format()
        self.update_idletasks()
        x = max(0, parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2)
        y = max(0, parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2)
        self.geometry(f"+{x}+{y}")
        theme_window_caption(self, colors)
        self.deiconify()
        self.grab_set()
        self.name_entry.focus_set()

    def _label(self, content, key, row):
        label = ttk.Label(content, text=self.translate(key), style="Editor.Muted.TLabel")
        label.grid(row=row, column=0, sticky="w", padx=(0, 16), pady=5)
        return label

    def _sync_format(self):
        format = self.format_var.get()
        rates = tuple(str(value) for value in AudioExportSettings.sample_rates(format))
        self.rate_box.configure(values=rates)
        if self.rate_var.get() not in rates:
            self.rate_var.set("44100")
        visible = (
            "export_bitrate" if format == ".mp3" else "export_ogg_quality" if format == ".ogg" else "export_bit_depth"
        )
        for key, widgets in self._optional_fields.items():
            for widget in widgets:
                widget.grid() if key == visible else widget.grid_remove()
        self.error_var.set("")

    def _browse(self):
        folder = filedialog.askdirectory(parent=self, initialdir=self.folder_var.get(), mustexist=True)
        if folder:
            self.folder_var.set(folder)

    def _on_return(self, event):
        if isinstance(event.widget, ttk.Button):
            event.widget.invoke()
        elif not isinstance(event.widget, (ttk.Combobox, tk.Listbox)):
            self._accept()
        return "break"

    def _accept(self):
        name = _safe_output_name(self.name_var.get())
        folder_text = self.folder_var.get().strip()
        folder = Path(folder_text).expanduser()
        if not name or not folder_text or not folder.is_dir():
            self.error_var.set(self.translate("audio_editor.export_invalid_destination"))
            return
        try:
            settings = AudioExportSettings(
                format=self.format_var.get(),
                sample_rate=int(self.rate_var.get()),
                bitrate_kbps=int(self.bitrate_var.get()),
                bit_depth=int(self.depth_var.get()),
                ogg_quality=int(self.quality_var.get()),
            )
        except ValueError:
            self.error_var.set(self.translate("audio_editor.export_invalid_settings"))
            return
        self.result = folder, name, settings
        self.destroy()


def choose_audio_export(parent, **kwargs):
    dialog = AudioExportDialog(parent, **kwargs)
    parent.wait_window(dialog)
    return dialog.result
