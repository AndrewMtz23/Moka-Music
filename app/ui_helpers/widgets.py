import tkinter as tk
from typing import Callable, Optional


class LibraryListbox(tk.Listbox):
    """Listbox with a small Treeview-like API used by library panels."""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("borderwidth", 0)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("cursor", "arrow")
        kwargs.setdefault("activestyle", "none")
        kwargs.setdefault("exportselection", False)
        kwargs.setdefault("selectmode", "extended")
        super().__init__(parent, **kwargs)
        self._items: list[dict[str, object]] = []
        self._tag_styles: dict[str, dict[str, str]] = {}
        self._selected_index: Optional[int] = None
        self._placeholder_visible = False
        self.tag_configure("selected", background="#111111", foreground="#ffffff")
        super().bind("<<ListboxSelect>>", self._sync_selected_index, add="+")

    def heading(self, *_args, **_kwargs) -> None:
        return

    def column(self, *_args, **_kwargs) -> None:
        return

    def get_children(self) -> tuple[str, ...]:
        return tuple(str(index) for index in range(len(self._items)))

    def delete(self, *items) -> None:
        self._items.clear()
        self._selected_index = None
        self._placeholder_visible = False
        super().delete(0, "end")

    def show_placeholder(self, message: str) -> None:
        self._items.clear()
        self._selected_index = None
        self._placeholder_visible = True
        super().delete(0, "end")
        super().insert("end", message)
        self.itemconfig(0, foreground=self._tag_styles.get("placeholder", {}).get("foreground", "#666666"))

    def insert(self, _parent, index, text="", values=(), tags=()) -> str:
        item_id = str(len(self._items))
        values = tuple(values or ())
        self._items.append({"text": text, "values": values, "tags": tuple(tags or ())})
        self._placeholder_visible = False
        super().insert("end", self._format_item(text, values))
        self._paint_item(len(self._items) - 1)
        return item_id

    def item(self, item_id) -> dict[str, object]:
        try:
            return self._items[int(item_id)]
        except (IndexError, ValueError, TypeError):
            return {"text": "", "values": (), "tags": ()}

    def selection(self) -> tuple[str, ...]:
        selection = self.curselection()
        if not selection or self._placeholder_visible:
            return ()
        return tuple(str(index) for index in selection)

    def selection_set(self, item_id) -> None:
        try:
            index = int(item_id)
        except (ValueError, TypeError):
            return
        if index < 0 or index >= len(self._items):
            return
        self._selected_index = index
        super().selection_clear(0, "end")
        super().selection_set(index)
        super().activate(index)
        self.see(index)

    def focus(self, item_id=None):
        if item_id is None:
            return str(self._selected_index) if self._selected_index is not None else ""
        try:
            index = int(item_id)
        except (ValueError, TypeError):
            return ""
        if 0 <= index < len(self._items):
            self._selected_index = index
            super().activate(index)
        return str(item_id)

    def see(self, item_id) -> None:
        try:
            super().see(int(item_id))
        except (ValueError, TypeError, tk.TclError):
            return

    def identify_row(self, y: int) -> str:
        if self._placeholder_visible:
            return ""
        row = self.nearest(y)
        return str(row) if 0 <= row < len(self._items) else ""

    def tag_configure(self, tag: str, **kwargs) -> None:
        self._tag_styles[tag] = {key: value for key, value in kwargs.items() if isinstance(value, str)}
        for index, item in enumerate(self._items):
            if tag in item.get("tags", ()):
                self._paint_item(index)
        if tag == "placeholder" and self._placeholder_visible and self.size():
            options = self._tag_styles.get(tag, {})
            if "foreground" in options:
                self.itemconfig(0, foreground=options["foreground"])

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<TreeviewSelect>>":
            sequence = "<<ListboxSelect>>"
        return super().bind(sequence, func, add)

    def _format_item(self, text: str, values: tuple[object, ...]) -> str:
        number = str(values[0]) if values else ""
        return f"{number:>2}. {text}"

    def _paint_item(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return
        options = {}
        for tag in self._items[index].get("tags", ()):
            options.update(self._tag_styles.get(tag, {}))
        if options:
            item_options = {
                key: value
                for key, value in options.items()
                if key in {"background", "foreground", "selectbackground", "selectforeground"}
            }
            if item_options:
                self.itemconfig(index, **item_options)

    def _sync_selected_index(self, _event=None) -> None:
        selection = self.curselection()
        self._selected_index = int(selection[0]) if selection and not self._placeholder_visible else None


class ToolTip:
    """Small delayed tooltip for icon-only controls."""

    def __init__(self, widget, text_getter: Callable[[], str], delay_ms: int = 450):
        self.widget = widget
        self.text_getter = text_getter
        self.delay_ms = delay_ms
        self._after_id: Optional[str] = None
        self._tip_window: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _show(self) -> None:
        self._after_id = None
        text = self.text_getter().strip()
        if not text or self._tip_window is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._tip_window = tk.Toplevel(self.widget)
        self._tip_window.wm_overrideredirect(True)
        self._tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self._tip_window,
            text=text,
            background="#111318",
            foreground="#f5f7fb",
            borderwidth=1,
            relief="solid",
            padx=8,
            pady=4,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip_window is not None:
            self._tip_window.destroy()
            self._tip_window = None

    def _cancel(self) -> None:
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
