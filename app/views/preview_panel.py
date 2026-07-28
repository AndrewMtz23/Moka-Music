import io
import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

from PIL import Image, ImageDraw, ImageFont, ImageTk

from ..i18n import I18n
from ..services.audio_quality_service import format_audio_quality
from ..utils.text_cleanup import remove_feature_text

COVER_SIZE = 112


class PreviewPanel(ttk.Frame):
    def __init__(
        self,
        parent,
        translator: Optional[Callable[..., str]] = None,
        *,
        show_inline_editor: bool = True,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.t = translator or I18n().t
        self.show_inline_editor = show_inline_editor
        self.current_song_data: Optional[dict[str, Any]] = None
        self.cover_image: Optional[ImageTk.PhotoImage] = None
        self.default_cover: Optional[ImageTk.PhotoImage] = None
        self.on_save_requested: Optional[Callable[[], None]] = None
        self.on_cover_requested: Optional[Callable[[], None]] = None
        self.on_clear_metadata_requested: Optional[Callable[[], None]] = None
        self.on_edit_metadata_requested: Optional[Callable[[], None]] = None

        self._setup_ui()
        self._create_default_cover()

    def _setup_ui(self) -> None:
        self.main_frame = ttk.LabelFrame(self, text=self.t("preview.title"))
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        cover_frame = ttk.Frame(self.main_frame)
        cover_frame.grid(row=0, column=0, sticky="nw", padx=(12, 16), pady=(8, 6))
        self.cover_frame = cover_frame

        self.cover_label = ttk.Label(cover_frame, text=self.t("preview.no_cover"))
        self.cover_label.pack()
        self.cover_hint_label = ttk.Label(
            cover_frame,
            text=self.t("preview.cover_drop_hint"),
            anchor="center",
            justify="center",
        )
        self.cover_hint_label.pack(fill="x", pady=(6, 0))

        info_frame = ttk.Frame(self.main_frame)
        info_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=(8, 6))
        self._create_info_section(info_frame)
        if self.show_inline_editor:
            self._create_editor_section(info_frame)
        else:
            self.edit_vars = {
                "title": tk.StringVar(value=""),
                "artist": tk.StringVar(value=""),
                "album_artist": tk.StringVar(value=""),
                "album": tk.StringVar(value=""),
                "genre": tk.StringVar(value=""),
                "year": tk.StringVar(value=""),
                "track_number": tk.StringVar(value=""),
                "comment": tk.StringVar(value=""),
            }
            self.edit_labels = {}

    def _create_info_section(self, parent) -> None:
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill="x", pady=(0, 12))

        self.title_label = ttk.Label(
            title_frame,
            text=self.t("preview.no_song"),
            font=("Segoe UI", 12, "bold"),
        )
        self.title_label.pack(side="left", anchor="w", fill="x", expand=True)

        self.clear_metadata_button = ttk.Button(
            title_frame,
            text=self._action_text("preview.clear_metadata", "\u232b"),
            command=self._emit_clear_metadata_requested,
            style="Secondary.TButton",
        )
        self.clear_metadata_button.pack(side="right", padx=(8, 0))

        self.edit_metadata_button = ttk.Button(
            title_frame,
            text=self._action_text("preview.edit_metadata", "\u270e"),
            command=self._emit_edit_metadata_requested,
        )
        self.edit_metadata_button.pack(side="right", padx=(8, 0))

        info_container = ttk.Frame(parent)
        info_container.pack(fill="both", expand=True)
        info_container.columnconfigure(1, weight=1)
        info_container.columnconfigure(3, weight=1)

        self.info_labels: dict[str, ttk.Label] = {}
        self.field_name_labels: dict[str, ttk.Label] = {}
        field_layout = [
            (0, 0, "preview.artist", "artist", 1),
            (0, 2, "preview.album_artist", "album_artist", 1),
            (1, 0, "preview.album", "album", 1),
            (1, 2, "preview.year", "year", 1),
            (2, 0, "preview.genre", "genre", 1),
            (2, 2, "preview.track", "track_number", 1),
            (3, 0, "preview.comment", "comment", 1),
            (3, 2, "preview.duration", "duration", 1),
            (4, 0, "preview.audio_quality", "audio_quality", 3),
            (5, 0, "preview.file", "file_name", 3),
        ]

        for row, column, label_key, field_name, value_span in field_layout:
            label = ttk.Label(info_container, text=f"{self.t(label_key)}:", width=11, anchor="w")
            label.grid(row=row, column=column, sticky="nw", padx=(0, 6), pady=2)
            value_label = ttk.Label(info_container, text="-", anchor="w", justify="left")
            value_label.grid(
                row=row,
                column=column + 1,
                columnspan=value_span,
                sticky="ew",
                padx=(0, 16 if column == 0 and value_span == 1 else 0),
                pady=2,
            )
            self.field_name_labels[field_name] = label
            self.info_labels[field_name] = value_label
        info_container.bind("<Configure>", self._update_info_wraplengths, add="+")

    def _create_editor_section(self, parent) -> None:
        self.editor_frame = ttk.LabelFrame(parent, text=self.t("preview.editor_title"))
        self.editor_frame.pack(fill="x", pady=(14, 0))

        self.edit_vars = {
            "title": tk.StringVar(value=""),
            "artist": tk.StringVar(value=""),
            "album_artist": tk.StringVar(value=""),
            "album": tk.StringVar(value=""),
            "genre": tk.StringVar(value=""),
            "year": tk.StringVar(value=""),
            "track_number": tk.StringVar(value=""),
            "comment": tk.StringVar(value=""),
        }
        self.edit_labels: dict[str, ttk.Label] = {}

        fields = [
            ("preview.title_field", "title"),
            ("preview.artist", "artist"),
            ("preview.album_artist", "album_artist"),
            ("preview.album", "album"),
            ("preview.genre", "genre"),
            ("preview.year", "year"),
            ("preview.track", "track_number"),
            ("preview.comment", "comment"),
        ]

        for index, (label_key, field_name) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            label = ttk.Label(self.editor_frame, text=f"{self.t(label_key)}:")
            label.grid(row=row, column=column, sticky="w", padx=(8, 6), pady=5)
            entry = ttk.Entry(self.editor_frame, textvariable=self.edit_vars[field_name], width=24)
            entry.grid(row=row, column=column + 1, sticky="ew", padx=(0, 10), pady=5)
            self.edit_labels[field_name] = label

        self.editor_frame.columnconfigure(1, weight=1)
        self.editor_frame.columnconfigure(3, weight=1)

        quick_row = ttk.Frame(self.editor_frame)
        quick_row.grid(row=4, column=0, columnspan=4, sticky="ew", padx=8, pady=(8, 0))

        self.title_from_file_button = ttk.Button(
            quick_row,
            text=self.t("preview.title_from_file"),
            command=self.title_from_filename,
            style="Secondary.TButton",
        )
        self.title_from_file_button.pack(side="left", padx=(0, 6))

        self.normalize_feat_button = ttk.Button(
            quick_row,
            text=self.t("preview.normalize_feat"),
            command=self.normalize_feature_credits,
            style="Secondary.TButton",
        )
        self.normalize_feat_button.pack(side="left", padx=(0, 6))

        self.clear_people_button = ttk.Button(
            quick_row,
            text=self.t("preview.clear_people"),
            command=self.clear_people_fields,
            style="Secondary.TButton",
        )
        self.clear_people_button.pack(side="left", padx=(0, 6))

        self.clear_optional_button = ttk.Button(
            quick_row,
            text=self.t("preview.clear_optional"),
            command=self.clear_optional_fields,
            style="Secondary.TButton",
        )
        self.clear_optional_button.pack(side="left")

        button_row = ttk.Frame(self.editor_frame)
        button_row.grid(row=5, column=0, columnspan=4, sticky="ew", padx=8, pady=(8, 8))

        self.save_button = ttk.Button(
            button_row,
            text=self.t("preview.save_song"),
            command=self._emit_save_requested,
        )
        self.save_button.pack(side="left")

        self.cover_button = ttk.Button(
            button_row,
            text=self.t("preview.pick_cover"),
            command=self._emit_cover_requested,
            style="Secondary.TButton",
        )
        self.cover_button.pack(side="left", padx=(6, 0))

    def _create_default_cover(self) -> None:
        try:
            image = Image.new("RGB", (COVER_SIZE, COVER_SIZE), color="#eeeeeb")
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except Exception:
                font = ImageFont.load_default()
            draw.multiline_text(
                (COVER_SIZE // 2, COVER_SIZE // 2),
                self.t("preview.default_cover"),
                fill="#666666",
                font=font,
                anchor="mm",
                align="center",
            )
            self.default_cover = ImageTk.PhotoImage(image)
            self.cover_label.configure(image=self.default_cover, text="")
        except Exception as exc:
            self.logger.error("Error creating default cover: %s", exc)
            self.cover_label.configure(text=self.t("preview.no_cover"), font=("Segoe UI", 10))

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator
        self.refresh_texts()

    def refresh_texts(self) -> None:
        self.main_frame.configure(text=self.t("preview.title"))
        label_keys = {
            "artist": "preview.artist",
            "album_artist": "preview.album_artist",
            "album": "preview.album",
            "year": "preview.year",
            "genre": "preview.genre",
            "track_number": "preview.track",
            "comment": "preview.comment",
            "duration": "preview.duration",
            "audio_quality": "preview.audio_quality",
            "file_name": "preview.file",
        }
        for field_name, label in self.field_name_labels.items():
            label.configure(text=f"{self.t(label_keys[field_name])}:")
        edit_label_keys = {
            "title": "preview.title_field",
            "artist": "preview.artist",
            "album_artist": "preview.album_artist",
            "album": "preview.album",
            "genre": "preview.genre",
            "year": "preview.year",
            "track_number": "preview.track",
            "comment": "preview.comment",
        }
        if self.show_inline_editor:
            self.editor_frame.configure(text=self.t("preview.editor_title"))
            for field_name, label in self.edit_labels.items():
                label.configure(text=f"{self.t(edit_label_keys[field_name])}:")
            self.save_button.configure(text=self.t("preview.save_song"))
            self.cover_button.configure(text=self.t("preview.pick_cover"))
            self.title_from_file_button.configure(text=self.t("preview.title_from_file"))
            self.normalize_feat_button.configure(text=self.t("preview.normalize_feat"))
            self.clear_people_button.configure(text=self.t("preview.clear_people"))
            self.clear_optional_button.configure(text=self.t("preview.clear_optional"))
        self.cover_hint_label.configure(text=self.t("preview.cover_drop_hint"))
        self.clear_metadata_button.configure(text=self._action_text("preview.clear_metadata", "\u232b"))
        self.edit_metadata_button.configure(text=self._action_text("preview.edit_metadata", "\u270e"))
        if self.current_song_data:
            self.update_preview(self.current_song_data)
        else:
            self.title_label.configure(text=self.t("preview.no_song"))

    def _action_text(self, key: str, icon: str) -> str:
        return f"{icon} {self.t(key)}"

    def update_preview(self, song_data: dict[str, Any]) -> None:
        self.current_song_data = song_data
        title = (
            song_data.get("title")
            or os.path.splitext(song_data.get("file_name", ""))[0]
            or self.t("preview.unknown_title")
        )
        self.title_label.configure(text=title)

        info_mapping = {
            "artist": song_data.get("artist", ""),
            "album_artist": song_data.get("album_artist", ""),
            "album": song_data.get("album", ""),
            "year": str(song_data.get("year", "")),
            "genre": song_data.get("genre", ""),
            "track_number": str(song_data.get("track_number", "")),
            "comment": song_data.get("comment", ""),
            "duration": self._format_duration(song_data.get("duration", 0)),
            "audio_quality": format_audio_quality(song_data.get("audio_quality", {})),
            "file_name": song_data.get("file_name", ""),
        }

        for field, value in info_mapping.items():
            self.info_labels[field].configure(text=value or "-")
        self._update_info_wraplengths()

        for field in self.edit_vars:
            self.edit_vars[field].set(str(song_data.get(field, "") or ""))

        self._update_cover(song_data)

    def _update_cover(self, song_data: dict[str, Any]) -> None:
        try:
            cover_data = song_data.get("cover_art")
            if isinstance(cover_data, bytes):
                with Image.open(io.BytesIO(cover_data)) as image:
                    image = image.convert("RGB")
                    image = image.resize((COVER_SIZE, COVER_SIZE), Image.LANCZOS)
                    self.cover_image = ImageTk.PhotoImage(image)
            elif isinstance(cover_data, str) and os.path.exists(cover_data):
                with Image.open(cover_data) as image:
                    image = image.convert("RGB")
                    image = image.resize((COVER_SIZE, COVER_SIZE), Image.LANCZOS)
                    self.cover_image = ImageTk.PhotoImage(image)
            else:
                self.cover_image = self.default_cover
            self.cover_label.configure(image=self.cover_image, text="")
        except Exception as exc:
            self.logger.error("Error updating cover preview: %s", exc)
            self.cover_label.configure(image=self.default_cover, text="")

    def _format_duration(self, duration_seconds: float) -> str:
        if not duration_seconds or duration_seconds <= 0:
            return "0:00"
        try:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}:{seconds:02d}"
        except (TypeError, ValueError):
            return "0:00"

    def clear_preview(self) -> None:
        self.current_song_data = None
        self.title_label.configure(text=self.t("preview.no_song"))
        for label in self.info_labels.values():
            label.configure(text="-")
        self.cover_label.configure(image=self.default_cover, text="")
        for variable in self.edit_vars.values():
            variable.set("")

    def get_current_song(self) -> Optional[dict[str, Any]]:
        return self.current_song_data

    def get_edited_metadata(self) -> dict[str, str]:
        return {key: variable.get().strip() for key, variable in self.edit_vars.items()}

    def title_from_filename(self) -> None:
        song = self.current_song_data or {}
        file_name = str(song.get("file_name", "")).strip()
        if file_name:
            self.edit_vars["title"].set(os.path.splitext(file_name)[0])

    def normalize_feature_credits(self) -> None:
        title = self.edit_vars["title"].get().strip()
        artist = self.edit_vars["artist"].get().strip()
        self.edit_vars["title"].set(remove_feature_text(title))
        self.edit_vars["artist"].set(remove_feature_text(artist))

    def clear_people_fields(self) -> None:
        self.edit_vars["artist"].set("")
        self.edit_vars["album_artist"].set("")

    def clear_optional_fields(self) -> None:
        for field in ("artist", "album_artist", "album", "genre", "year", "comment"):
            self.edit_vars[field].set("")

    def update_cover_from_file(self, cover_path: str) -> None:
        try:
            if not os.path.exists(cover_path):
                return
            with Image.open(cover_path) as image:
                image = image.convert("RGB")
                image = image.resize((COVER_SIZE, COVER_SIZE), Image.LANCZOS)
                self.cover_image = ImageTk.PhotoImage(image)
            self.cover_label.configure(image=self.cover_image, text="")
            if self.current_song_data is not None:
                self.current_song_data["cover_art"] = cover_path
        except Exception as exc:
            self.logger.error("Error updating cover from file: %s", exc)

    def _emit_save_requested(self) -> None:
        if self.on_save_requested:
            self.on_save_requested()

    def _emit_cover_requested(self) -> None:
        if self.on_cover_requested:
            self.on_cover_requested()

    def _emit_clear_metadata_requested(self) -> None:
        if self.on_clear_metadata_requested:
            self.on_clear_metadata_requested()

    def _emit_edit_metadata_requested(self) -> None:
        if self.on_edit_metadata_requested:
            self.on_edit_metadata_requested()

    def set_loading_state(self, loading: bool = True) -> None:
        if loading:
            self.title_label.configure(text=self.t("preview.loading"))
            for label in self.info_labels.values():
                label.configure(text="...")

    def show_error_state(self, error_message: Optional[str] = None) -> None:
        self.title_label.configure(text=error_message or self.t("preview.could_not_read"))
        for label in self.info_labels.values():
            label.configure(text=self.t("preview.error"))
        self.cover_label.configure(image=self.default_cover, text="")

    def _update_info_wraplengths(self, _event=None) -> None:
        try:
            width = max(180, self.info_labels["audio_quality"].winfo_width())
        except Exception:
            width = 360
        for field in ("audio_quality", "file_name", "comment"):
            label = self.info_labels.get(field)
            if label is not None:
                label.configure(wraplength=width)
