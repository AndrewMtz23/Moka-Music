from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UndoAction:
    label: str
    backup_paths: tuple[Path, ...]


class UndoController:
    def __init__(self, limit: int = 25) -> None:
        self.limit = limit
        self.undo_stack: list[UndoAction] = []
        self.redo_stack: list[UndoAction] = []

    def record(self, label: str, backup_paths: list[Path] | tuple[Path, ...]) -> None:
        paths = tuple(Path(path) for path in backup_paths if path)
        if not paths:
            return
        self.undo_stack.append(UndoAction(label=label, backup_paths=paths))
        if len(self.undo_stack) > self.limit:
            self.undo_stack = self.undo_stack[-self.limit :]
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo_label(self) -> str:
        return self.undo_stack[-1].label if self.undo_stack else ""

    def redo_label(self) -> str:
        return self.redo_stack[-1].label if self.redo_stack else ""

    def pop_undo(self) -> UndoAction | None:
        return self.undo_stack.pop() if self.undo_stack else None

    def pop_redo(self) -> UndoAction | None:
        return self.redo_stack.pop() if self.redo_stack else None

    def push_undo(self, action: UndoAction) -> None:
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.limit:
            self.undo_stack = self.undo_stack[-self.limit :]

    def push_redo(self, action: UndoAction) -> None:
        self.redo_stack.append(action)
        if len(self.redo_stack) > self.limit:
            self.redo_stack = self.redo_stack[-self.limit :]
