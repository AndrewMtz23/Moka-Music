from typing import Callable, Optional

from ..views.modals.batch_edit_modal import request_batch_metadata
from ..views.modals.clear_metadata_modal import request_clear_metadata
from ..views.modals.edit_metadata_modal import request_metadata_edit

MetadataField = tuple[str, str]

METADATA_FIELDS: list[MetadataField] = [
    ("title", "preview.title_field"),
    ("artist", "preview.artist"),
    ("album_artist", "preview.album_artist"),
    ("album", "preview.album"),
    ("genre", "preview.genre"),
    ("year", "preview.year"),
    ("track_number", "preview.track"),
    ("comment", "preview.comment"),
]


class MetadataDialogController:
    def __init__(self, translator: Callable[..., str]) -> None:
        self.t = translator
        self.fields = METADATA_FIELDS

    def set_translator(self, translator: Callable[..., str]) -> None:
        self.t = translator

    def request_clear(self, parent, current_song: dict[str, object]) -> Optional[dict[str, str]]:
        return request_clear_metadata(parent, self.t, METADATA_FIELDS, current_song)

    def request_edit(
        self,
        parent,
        current_song: dict[str, object],
        *,
        selected_count: int,
        is_batch_edit: bool,
    ) -> Optional[dict[str, str]]:
        return request_metadata_edit(
            parent,
            self.t,
            METADATA_FIELDS,
            current_song,
            selected_count=selected_count,
            is_batch_edit=is_batch_edit,
        )

    def request_batch(self, parent, *, selected_count: int) -> Optional[dict[str, str]]:
        return request_batch_metadata(parent, self.t, METADATA_FIELDS, selected_count)
