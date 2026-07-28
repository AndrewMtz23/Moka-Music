"""Audio and file utility helpers used by playback and metadata views."""

import io
import logging
import math
import os
import time
from pathlib import Path
from typing import Optional, Tuple, Union

import mutagen
from PIL import Image, ImageOps


class AudioUtils:
    """Utilidades avanzadas para el reproductor con:
    - Procesamiento de tiempo
    - Manipulación de metadatos
    - Conversión de formatos
    - Operaciones con imágenes
    """

    @staticmethod
    def format_time(seconds: Union[int, float], precision: str = "normal") -> str:
        """
        Formatea segundos a HH:MM:SS o MM:SS según la duración.

        Args:
            seconds: Tiempo en segundos
            precision: 'normal' (redondeo) o 'exact' (decimales)

        Returns:
            str: Tiempo formateado
        """
        try:
            seconds = float(seconds)
            if seconds < 0:
                return "00:00"

            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60

            if precision == "exact":
                secs_str = f"{secs:06.3f}".zfill(6)
            else:
                secs_str = f"{int(round(secs)):02d}"

            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs_str}"
            return f"{minutes:02d}:{secs_str}"
        except (ValueError, TypeError):
            return "00:00"

    @staticmethod
    def parse_time(time_str: str) -> float:
        """
        Convierte una cadena de tiempo (HH:MM:SS o MM:SS) a segundos.

        Args:
            time_str: Cadena de tiempo a convertir

        Returns:
            float: Segundos equivalentes
        """
        try:
            parts = list(map(float, time_str.split(":")))
            if len(parts) == 3:  # HH:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:  # MM:SS
                return parts[0] * 60 + parts[1]
            elif len(parts) == 1:  # SS
                return parts[0]
            return 0.0
        except (ValueError, AttributeError):
            return 0.0

    @staticmethod
    def get_audio_duration(file_path: str) -> float:
        """
        Obtiene la duración de un archivo de audio en segundos.

        Args:
            file_path: Ruta al archivo de audio

        Returns:
            float: Duración en segundos
        """
        try:
            audio = mutagen.File(file_path, easy=True)
            return audio.info.length if audio else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def create_waveform_image(
        audio_path: str,
        width: int = 300,
        height: int = 80,
        bg_color: Tuple[int, int, int] = (30, 30, 40),
        wave_color: Tuple[int, int, int] = (100, 150, 255),
    ) -> Optional[Image.Image]:
        """
        Genera una imagen de forma de onda para el audio (placeholder).

        Args:
            audio_path: Ruta al archivo de audio
            width: Ancho de la imagen
            height: Alto de la imagen
            bg_color: Color de fondo (R,G,B)
            wave_color: Color de la onda (R,G,B)

        Returns:
            Optional[Image.Image]: Imagen PIL o None si hay error
        """
        try:
            # Implementación real usaría análisis de audio
            # Esta es una implementación de placeholder

            # Crear imagen base
            img = Image.new("RGB", (width, height), bg_color)

            # Dibujar onda simulada
            for x in range(width):
                y_pos = int((math.sin(x / 10) + 1) * (height // 3))
                for y in range(height // 2 - y_pos, height // 2 + y_pos):
                    if 0 <= y < height:
                        img.putpixel((x, y), wave_color)

            return img
        except Exception as e:
            logging.error(f"Error generando waveform: {str(e)}")
            return None

    @staticmethod
    def process_cover_image(
        image_path: str, output_size: Tuple[int, int] = (300, 300), quality: int = 85
    ) -> Optional[bytes]:
        """
        Procesa una imagen para usar como portada de álbum.

        Args:
            image_path: Ruta a la imagen original
            output_size: Tamaño de salida (ancho, alto)
            quality: Calidad JPEG (1-100)

        Returns:
            Optional[bytes]: Datos de imagen JPEG o None si hay error
        """
        try:
            with Image.open(image_path) as img:
                # Convertir a RGB si es necesario
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Redimensionar manteniendo relación de aspecto
                img = ImageOps.fit(img, output_size, method=Image.LANCZOS)

                # Guardar en buffer de memoria
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                return buffer.getvalue()
        except Exception as e:
            logging.error(f"Error procesando portada: {str(e)}")
            return None

    @staticmethod
    def format_file_size(bytes_size: int) -> str:
        """
        Formatea el tamaño de archivo en unidades legibles.

        Args:
            bytes_size: Tamaño en bytes

        Returns:
            str: Cadena formateada (ej. "1.23 MB")
        """
        units = ["B", "KB", "MB", "GB"]
        size = float(bytes_size)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{bytes_size} B"

    @staticmethod
    def get_bitrate(file_path: str) -> str:
        """
        Obtiene el bitrate de un archivo de audio.

        Args:
            file_path: Ruta al archivo de audio

        Returns:
            str: Bitrate en kbps
        """
        try:
            audio = mutagen.File(file_path)
            if audio:
                bitrate = audio.info.bitrate // 1000
                return f"{bitrate} kbps"
            return "N/A"
        except Exception:
            return "N/A"

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 120) -> str:
        """
        Limpia un nombre de archivo para hacerlo seguro.

        Args:
            filename: Nombre original
            max_length: Longitud máxima permitida

        Returns:
            str: Nombre sanitizado
        """
        # Caracteres no permitidos
        invalid_chars = '<>:"/\\|?*\0'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # Limitar longitud
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[: max_length - len(ext)] + ext

        return filename.strip()

    @staticmethod
    def get_file_metadata(file_path: str) -> dict:
        """
        Obtiene metadatos básicos de un archivo.

        Args:
            file_path: Ruta al archivo

        Returns:
            dict: Diccionario con metadatos
        """
        try:
            path = Path(file_path)
            return {
                "size": path.stat().st_size,
                "modified": time.ctime(path.stat().st_mtime),
                "created": time.ctime(path.stat().st_ctime),
                "extension": path.suffix.lower(),
                "bitrate": AudioUtils.get_bitrate(file_path),
            }
        except Exception:
            return {}


# ===== FUNCIONES DE COMPATIBILIDAD =====
# Estas funciones proporcionan acceso directo a los métodos más utilizados
# para mantener compatibilidad con imports directos


def format_time(seconds: Union[int, float], precision: str = "normal") -> str:
    """Función de compatibilidad que delega a AudioUtils.format_time"""
    return AudioUtils.format_time(seconds, precision)


def parse_time(time_str: str) -> float:
    """Función de compatibilidad que delega a AudioUtils.parse_time"""
    return AudioUtils.parse_time(time_str)


def get_audio_duration(file_path: str) -> float:
    """Función de compatibilidad que delega a AudioUtils.get_audio_duration"""
    return AudioUtils.get_audio_duration(file_path)


def format_file_size(bytes_size: int) -> str:
    """Función de compatibilidad que delega a AudioUtils.format_file_size"""
    return AudioUtils.format_file_size(bytes_size)


def get_bitrate(file_path: str) -> str:
    """Función de compatibilidad que delega a AudioUtils.get_bitrate"""
    return AudioUtils.get_bitrate(file_path)


def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """Función de compatibilidad que delega a AudioUtils.sanitize_filename"""
    return AudioUtils.sanitize_filename(filename, max_length)


def get_file_metadata(file_path: str) -> dict:
    """Función de compatibilidad que delega a AudioUtils.get_file_metadata"""
    return AudioUtils.get_file_metadata(file_path)
