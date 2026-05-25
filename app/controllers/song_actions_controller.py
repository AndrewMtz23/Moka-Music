import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ..i18n import I18n
from ..models import ActionResult
from ..services.file_service import delete_song, move_song_between_libraries, rename_song, sanitize_filename
from ..services.song_info_service import SongInfo
from ..utils.ui_formatting import filename_from_tree_item
from ..views.preview_panel import PreviewPanel


class SongActions:
    def __init__(self, translator: Optional[Callable[..., str]] = None) -> None:
        self.t = translator or I18n().t
        self.song_info = SongInfo()
        self.logger = logging.getLogger(__name__)

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def mover_cancion(
        self,
        controller_origen,
        controller_destino,
        nombre_archivo: str,
        tree_origen: ttk.Treeview,
        tree_destino: ttk.Treeview,
        preview: PreviewPanel,
    ) -> ActionResult:
        result = move_song_between_libraries(
            controller_origen,
            controller_destino,
            nombre_archivo,
            translator=self.t,
        )
        if result.success:
            preview.clear_preview()
        return result

    def eliminar_cancion(
        self,
        controller,
        nombre_archivo: str,
        treeview: ttk.Treeview,
        preview: PreviewPanel,
        mover_a_papelera: bool = True,
    ) -> ActionResult:
        result = delete_song(
            controller,
            nombre_archivo,
            move_to_trash=mover_a_papelera,
            translator=self.t,
        )
        if result.success:
            preview.clear_preview()
        return result

    def renombrar_cancion(
        self,
        controller,
        nombre_actual: str,
        nuevo_nombre: str,
        treeview: ttk.Treeview,
        preview: PreviewPanel,
    ) -> ActionResult:
        result = rename_song(
            controller,
            nombre_actual,
            nuevo_nombre,
            translator=self.t,
        )
        if result.success:
            filepath = result.data.get("filepath") if result.data else ""
            metadata = self.song_info.get_metadata(filepath) if filepath else None
            if metadata:
                preview.update_preview(metadata)
        return result

    def _sanitize_filename(self, value: str) -> str:
        return sanitize_filename(value)

    def mostrar_boton_contextual(
        self,
        parent,
        controller_origen,
        controller_destino,
        tree_origen: ttk.Treeview,
        tree_destino: ttk.Treeview,
        preview: PreviewPanel,
        event,
        *,
        on_result=None,
    ) -> None:
        item = tree_origen.identify_row(event.y)
        if not item:
            return

        tree_origen.selection_set(item)
        item_data = tree_origen.item(item)
        tags = item_data.get("tags") or []
        if not tags:
            return
        nombre_archivo = self._filename_from_tags(tags)
        if not nombre_archivo:
            return

        menu = tk.Menu(parent, tearoff=0)

        if controller_destino.carpeta:
            menu.add_command(
                label=self.t("context.move_other"),
                command=lambda: self._emit_result(
                    on_result,
                    self.mover_cancion(
                        controller_origen,
                        controller_destino,
                        nombre_archivo,
                        tree_origen,
                        tree_destino,
                        preview,
                    ),
                ),
            )

        menu.add_command(
            label=self.t("context.rename"),
            command=lambda: self._solicitar_nuevo_nombre(
                parent,
                controller_origen,
                nombre_archivo,
                tree_origen,
                preview,
                on_result=on_result,
            ),
        )

        menu.add_command(
            label=self.t("context.delete"),
            command=lambda: self._emit_result(
                on_result,
                self.eliminar_cancion(controller_origen, nombre_archivo, tree_origen, preview),
            ),
        )

        menu.tk_popup(event.x_root, event.y_root)

    def _solicitar_nuevo_nombre(
        self,
        parent,
        controller,
        nombre_actual: str,
        treeview: ttk.Treeview,
        preview: PreviewPanel,
        *,
        on_result=None,
    ) -> None:
        from tkinter.simpledialog import askstring

        current_name = os.path.splitext(nombre_actual)[0]
        nuevo_nombre = askstring(
            self.t("rename.title"),
            self.t("rename.prompt"),
            initialvalue=current_name,
            parent=parent,
        )
        if nuevo_nombre:
            result = self.renombrar_cancion(
                controller,
                nombre_actual,
                nuevo_nombre,
                treeview,
                preview,
            )
            self._emit_result(on_result, result)

    def _emit_result(self, callback, result: ActionResult) -> None:
        if callback:
            callback(result)

    def _filename_from_tags(self, tags) -> str:
        return filename_from_tree_item({"tags": tags})
