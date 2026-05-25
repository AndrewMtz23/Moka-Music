import os
import random
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class PlaybackSelection:
    item_id: object
    filename: str
    filepath: str


class PlaybackSelectionController:
    def __init__(
        self,
        filename_from_item: Callable[[dict[str, object]], str],
        *,
        chooser: Callable[[list[object]], object] | None = None,
    ) -> None:
        self.filename_from_item = filename_from_item
        self.chooser = chooser or random.choice

    def selected_track(self, controller, tree) -> Optional[PlaybackSelection]:
        selection = tree.selection()
        if not selection or not controller.carpeta:
            return None
        return self.track_for_item(controller, tree, selection[0])

    def track_for_item(self, controller, tree, item_id) -> Optional[PlaybackSelection]:
        filename = self.filename_from_item(tree.item(item_id))
        if not filename or not controller.carpeta:
            return None
        return PlaybackSelection(
            item_id=item_id,
            filename=filename,
            filepath=os.path.join(controller.carpeta, filename),
        )

    def relative_item(self, tree, *, offset: int, shuffle: bool) -> Optional[object]:
        children = list(tree.get_children())
        if not children:
            return None
        selection = tree.selection()
        if not selection:
            return None

        current_item = selection[0]
        if shuffle and offset > 0 and len(children) > 1:
            candidates = [item for item in children if item != current_item]
            return self.chooser(candidates)

        try:
            current_index = children.index(current_item)
        except ValueError:
            return None
        target_index = current_index + offset
        if target_index < 0 or target_index >= len(children):
            return None
        return children[target_index]
