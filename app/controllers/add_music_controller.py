from tkinter import ttk
from typing import Callable, Optional

from ..models import ActionResult
from ..services.file_service import add_song_to_library
from ..services.song_info_service import SongInfo
from ..ui_helpers.file_dialogs import FileHandler


def abrir_selector_archivo(file_handler: Optional[FileHandler] = None) -> Optional[str]:
    handler = file_handler or FileHandler()
    return handler.seleccionar_archivo_audio()


def agregar_a_lista(
    ruta_archivo: str,
    controller_destino,
    tree_destino: ttk.Treeview,
    file_handler: Optional[FileHandler] = None,
    song_info: Optional[SongInfo] = None,
    translator: Optional[Callable[..., str]] = None,
) -> ActionResult:
    """Copy a song into the destination library and update controller state.

    The UI layer owns rendering and refreshes the list widget after this
    function returns. ``tree_destino`` and ``file_handler`` are kept in the
    signature for compatibility with existing callers.
    """
    return add_song_to_library(
        ruta_archivo,
        controller_destino,
        song_info=song_info,
        translator=translator,
    )
