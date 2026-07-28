from typing import Callable, Optional

LibrarySelection = tuple[object, object, list[str]]


class SelectionController:
    def __init__(self, filename_from_item: Callable[[dict[str, object]], str]) -> None:
        self.filename_from_item = filename_from_item

    def panel_for_search(self, panels: list[dict[str, object]], variable) -> Optional[dict[str, object]]:
        for panel in panels:
            if panel.get("search_var") is variable:
                return panel
        return None

    def panel_for_library(
        self,
        panels: list[dict[str, object]],
        controller,
        tree,
    ) -> Optional[dict[str, object]]:
        for panel in panels:
            if panel["controller"] is controller and panel["tree"] is tree:
                return panel
        return None

    def controller_for_tree(
        self,
        tree,
        *,
        main_controller=None,
        main_tree=None,
        incoming_controller=None,
        incoming_tree=None,
        panels: list[dict[str, object]] | None = None,
    ):
        if main_tree is not None and tree == main_tree:
            return main_controller
        if incoming_tree is not None and tree == incoming_tree:
            return incoming_controller
        for panel in panels or []:
            if panel["tree"] is tree:
                return panel["controller"]
        return None

    def tree_for_controller(
        self,
        controller,
        *,
        main_controller=None,
        main_tree=None,
        incoming_controller=None,
        incoming_tree=None,
    ):
        if controller == main_controller:
            return main_tree
        if controller == incoming_controller:
            return incoming_tree
        return None

    def selected_filenames_by_controller(self, pairs: list[tuple[object, object]]) -> list[LibrarySelection]:
        selections: list[LibrarySelection] = []
        for controller, tree in pairs:
            if not getattr(controller, "carpeta", ""):
                continue
            filenames: list[str] = []
            for item_id in tree.selection():
                filename = self.filename_from_item(tree.item(item_id))
                if filename and filename not in filenames:
                    filenames.append(filename)
            if filenames:
                selections.append((controller, tree, filenames))
        return selections
