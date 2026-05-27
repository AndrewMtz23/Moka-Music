import io
import logging
import os
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from ..constants import FileFormats, UISettings
from ..i18n import I18n
from ..services.file_service import (
    is_supported_audio_file,
    is_supported_image_file,
    list_audio_files,
    parse_dropped_audio_files,
    shorten_filename,
)


class FileHandler:
    def __init__(self, translator: Optional[Callable[..., str]] = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.t = translator or I18n().t
        self._last_directory = os.path.expanduser("~")

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def seleccionar_carpeta(self, title: Optional[str] = None) -> Optional[str]:
        try:
            folder = filedialog.askdirectory(title=title or self.t("file.select_folder"), initialdir=self._last_directory)
            if not folder:
                return None
            if not self.validar_carpeta(folder):
                return None
            self._last_directory = folder
            return folder
        except Exception as exc:
            self.logger.error("Error selecting folder: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("file.could_not_open_folder_picker", error=exc))
            return None

    def seleccionar_archivo_audio(self) -> Optional[str]:
        try:
            filepath = filedialog.askopenfilename(
                title=self.t("file.select_audio"),
                initialdir=self._last_directory,
                filetypes=[
                    (self.t("file.audio"), " ".join(f"*{ext}" for ext in FileFormats.AUDIO)),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if not filepath:
                return None
            if not self.validar_audio(filepath):
                return None
            self._last_directory = os.path.dirname(filepath)
            return filepath
        except Exception as exc:
            self.logger.error("Error selecting audio file: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("file.could_not_open_audio_picker", error=exc))
            return None

    def seleccionar_imagen(self) -> Optional[str]:
        try:
            filepath = filedialog.askopenfilename(
                title=self.t("file.select_cover"),
                initialdir=self._last_directory,
                filetypes=[
                    (self.t("file.images"), " ".join(f"*{ext}" for ext in FileFormats.IMAGES)),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if not filepath:
                return None
            if not self.validar_imagen(filepath):
                return None
            self._last_directory = os.path.dirname(filepath)
            return filepath
        except Exception as exc:
            self.logger.error("Error selecting image: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("file.could_not_open_image_picker", error=exc))
            return None

    def seleccionar_destino_playlist(self, initial_name: str = "playlist.m3u8") -> Optional[str]:
        try:
            filepath = filedialog.asksaveasfilename(
                title=self.t("playlist_export.select_destination"),
                initialdir=self._last_directory,
                initialfile=initial_name,
                defaultextension=".m3u8",
                filetypes=[
                    (self.t("playlist_export.m3u8"), "*.m3u8"),
                    (self.t("playlist_export.m3u"), "*.m3u"),
                    (self.t("playlist_export.pls"), "*.pls"),
                    (self.t("playlist_export.json"), "*.json"),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if filepath:
                self._last_directory = os.path.dirname(filepath)
            return filepath or None
        except Exception as exc:
            self.logger.error("Error selecting playlist destination: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("playlist_export.could_not_open_picker", error=exc))
            return None

    def seleccionar_destino_library_view_json(self, initial_name: str = "library_view.json") -> Optional[str]:
        try:
            filepath = filedialog.asksaveasfilename(
                title=self.t("library_view_export.select_destination"),
                initialdir=self._last_directory,
                initialfile=initial_name,
                defaultextension=".json",
                filetypes=[
                    (self.t("playlist_export.json"), "*.json"),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if filepath:
                self._last_directory = os.path.dirname(filepath)
            return filepath or None
        except Exception as exc:
            self.logger.error("Error selecting library view export destination: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("library_view_export.could_not_open_picker", error=exc))
            return None

    def seleccionar_destino_library_report(self, initial_name: str = "library_report.json") -> Optional[str]:
        try:
            filepath = filedialog.asksaveasfilename(
                title=self.t("library_report_export.select_destination"),
                initialdir=self._last_directory,
                initialfile=initial_name,
                defaultextension=".json",
                filetypes=[
                    (self.t("playlist_export.json"), "*.json"),
                    (self.t("library_report_export.csv"), "*.csv"),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if filepath:
                self._last_directory = os.path.dirname(filepath)
            return filepath or None
        except Exception as exc:
            self.logger.error("Error selecting library report destination: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("library_report_export.could_not_open_picker", error=exc))
            return None

    def seleccionar_metadata_json(self) -> Optional[str]:
        try:
            filepath = filedialog.askopenfilename(
                title=self.t("metadata_import.select_file"),
                initialdir=self._last_directory,
                filetypes=[
                    (self.t("playlist_export.json"), "*.json"),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if filepath:
                self._last_directory = os.path.dirname(filepath)
            return filepath or None
        except Exception as exc:
            self.logger.error("Error selecting metadata import file: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("metadata_import.could_not_open_picker", error=exc))
            return None

    def seleccionar_tema_json(self) -> Optional[str]:
        try:
            filepath = filedialog.askopenfilename(
                title=self.t("theme_custom.import_title"),
                initialdir=self._last_directory,
                filetypes=[
                    (self.t("playlist_export.json"), "*.json"),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if filepath:
                self._last_directory = os.path.dirname(filepath)
            return filepath or None
        except Exception as exc:
            self.logger.error("Error selecting theme import file: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("theme_custom.import_picker_failed", error=exc))
            return None

    def seleccionar_destino_tema_json(self, initial_name: str = "mokamusic_theme.json") -> Optional[str]:
        try:
            filepath = filedialog.asksaveasfilename(
                title=self.t("theme_custom.export_title"),
                initialdir=self._last_directory,
                initialfile=initial_name,
                defaultextension=".json",
                filetypes=[
                    (self.t("playlist_export.json"), "*.json"),
                    (self.t("file.all_files"), "*.*"),
                ],
            )
            if filepath:
                self._last_directory = os.path.dirname(filepath)
            return filepath or None
        except Exception as exc:
            self.logger.error("Error selecting theme export destination: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("theme_custom.export_picker_failed", error=exc))
            return None

    def validar_carpeta(self, carpeta: str) -> bool:
        try:
            path = Path(carpeta)
            if not path.exists():
                messagebox.showerror(self.t("dialog.error"), self.t("file.not_found", path=carpeta))
                return False
            if not path.is_dir():
                messagebox.showerror(self.t("dialog.error"), self.t("file.path_not_folder"))
                return False
            return True
        except Exception as exc:
            self.logger.error("Error validating folder: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("file.could_not_validate_folder", error=exc))
            return False

    def validar_audio(self, ruta: str) -> bool:
        path = Path(ruta)
        if not path.exists():
            messagebox.showerror(self.t("dialog.error"), self.t("file.not_found", path=ruta))
            return False
        if not path.is_file():
            messagebox.showerror(self.t("dialog.error"), self.t("file.path_not_file"))
            return False
        if not is_supported_audio_file(path):
            messagebox.showerror(self.t("dialog.error"), self.t("file.unsupported_format", suffix=path.suffix))
            return False
        return True

    def validar_imagen(self, ruta: str) -> bool:
        try:
            path = Path(ruta)
            if not path.exists():
                messagebox.showerror(self.t("dialog.error"), self.t("file.not_found", path=ruta))
                return False
            if not is_supported_image_file(path):
                messagebox.showerror(self.t("dialog.error"), self.t("file.unsupported_format", suffix=path.suffix))
                return False
            if path.stat().st_size > 10 * 1024 * 1024:
                proceed = messagebox.askyesno(
                    self.t("file.large_image_title"),
                    self.t("file.large_image_prompt"),
                )
                if not proceed:
                    return False
            with Image.open(ruta) as image:
                image.verify()
            return True
        except (UnidentifiedImageError, OSError) as exc:
            messagebox.showerror(self.t("dialog.error"), self.t("file.could_not_read_image", error=exc))
            return False
        except Exception as exc:
            self.logger.error("Error validating image: %s", exc)
            messagebox.showerror(self.t("dialog.error"), self.t("file.could_not_validate_image", error=exc))
            return False

    def procesar_imagen_portada(
        self,
        ruta: str,
        size: tuple[int, int] = UISettings.PREVIEW_IMAGE_SIZE,
    ) -> Optional[bytes]:
        try:
            with Image.open(ruta) as image:
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image = ImageOps.fit(image, size, method=Image.LANCZOS)
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=85)
                return output.getvalue()
        except Exception as exc:
            self.logger.error("Error processing cover image: %s", exc)
            return None

    def obtener_archivos_audio(self, carpeta: str) -> list[str]:
        return list_audio_files(carpeta)

    def obtener_nombre_corto(
        self,
        ruta: str,
        max_len: int = UISettings.MAX_FILENAME_DISPLAY,
    ) -> str:
        try:
            return shorten_filename(ruta, max_len)
        except Exception as exc:
            self.logger.warning("Error shortening filename: %s", exc)
            return self.t("file.fallback_name")

    def handle_drop_event(self, raw_data: str) -> list[str]:
        return parse_dropped_audio_files(raw_data)
