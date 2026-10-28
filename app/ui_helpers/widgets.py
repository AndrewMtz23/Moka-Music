import tkinter as tk
from difflib import SequenceMatcher
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
        self._scroll_callback = None
        self.lock_gutter = tk.Canvas(parent, width=26, highlightthickness=0, borderwidth=0)
        super().configure(yscrollcommand=self._on_scroll)
        super().bind("<Configure>", lambda _event: self._draw_locks(), add="+")
        for sequence in ("<ButtonPress-1>", "<ButtonRelease-1>", "<B1-Motion>", "<ButtonPress-3>"):
            self.lock_gutter.bind(
                sequence,
                lambda event, sequence=sequence: self.event_generate(sequence, x=1, y=event.y, state=event.state),
            )
        self.lock_gutter.bind("<MouseWheel>", lambda event: self.event_generate("<MouseWheel>", delta=event.delta))
        self.bind("<Destroy>", self._destroy_gutter, add="+")
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
        self._draw_locks()

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
        self._draw_locks()
        return item_id

    def item(self, item_id) -> dict[str, object]:
        try:
            return self._items[int(item_id)]
        except (IndexError, ValueError, TypeError):
            return {"text": "", "values": (), "tags": ()}

    def sync_items(self, items: list[dict[str, object]]) -> None:
        """Reconcile library rows without rebuilding unchanged native list entries."""
        if self._items == items:
            return
        old_items = self._items
        old_keys = [item["tags"][0] for item in old_items]
        new_keys = [item["tags"][0] for item in items]
        selected = {old_keys[int(index)] for index in self.selection()}
        anchor_index = self.index("anchor")
        anchor_key = old_keys[anchor_index] if 0 <= anchor_index < len(old_keys) else None
        focused = (
            old_keys[self._selected_index]
            if self._selected_index is not None and self._selected_index < len(old_keys)
            else None
        )
        top_key = old_keys[self.nearest(0)] if old_keys else None
        old_by_key = dict(zip(old_keys, old_items, strict=True))
        repaint = set()

        if self._placeholder_visible:
            tk.Listbox.delete(self, 0, "end")
        for operation, old_start, old_end, new_start, new_end in reversed(
            SequenceMatcher(a=old_keys, b=new_keys, autojunk=False).get_opcodes()
        ):
            if operation == "equal":
                for old_index, new_index in zip(range(old_start, old_end), range(new_start, new_end), strict=True):
                    before, after = old_items[old_index], items[new_index]
                    if self._format_item(before["text"], before["values"]) != self._format_item(
                        after["text"], after["values"]
                    ):
                        tk.Listbox.delete(self, old_index)
                        tk.Listbox.insert(self, old_index, self._format_item(after["text"], after["values"]))
                        repaint.add(new_index)
            else:
                if old_end > old_start:
                    tk.Listbox.delete(self, old_start, old_end - 1)
                if new_end > new_start:
                    tk.Listbox.insert(
                        self,
                        old_start,
                        *[self._format_item(item["text"], item["values"]) for item in items[new_start:new_end]],
                    )
                    repaint.update(range(new_start, new_end))

        self._items = [dict(item) for item in items]
        self._placeholder_visible = False
        self._selected_index = None
        tk.Listbox.selection_clear(self, 0, "end")
        for index, item in enumerate(items):
            key = new_keys[index]
            if index in repaint or old_by_key.get(key) != item:
                self._paint_item(index)
            if key in selected:
                tk.Listbox.selection_set(self, index)
            if key == focused:
                self._selected_index = index
                tk.Listbox.activate(self, index)
            if key == anchor_key:
                self.selection_anchor(index)
        if top_key in new_keys:
            self.yview(new_keys.index(top_key))
        self._draw_locks()

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
        self._draw_locks()

    def selection_clear(self, first, last=None) -> None:
        super().selection_clear(first, last)
        self._sync_selected_index()

    select_clear = selection_clear

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
        options = {key: value for key, value in kwargs.items() if isinstance(value, str)}
        if self._tag_styles.get(tag) == options:
            return
        self._tag_styles[tag] = options
        for index, item in enumerate(self._items):
            if tag in item.get("tags", ()):
                self._paint_item(index)
        if tag == "placeholder" and self._placeholder_visible and self.size():
            options = self._tag_styles.get(tag, {})
            if "foreground" in options:
                self.itemconfig(0, foreground=options["foreground"])
        self._draw_locks()

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
        self._draw_locks()

    def configure(self, cnf=None, **kwargs):
        if "yscrollcommand" in kwargs:
            self._scroll_callback = kwargs.pop("yscrollcommand")
            kwargs["yscrollcommand"] = self._on_scroll
        result = super().configure(cnf, **kwargs)
        if hasattr(self, "lock_gutter"):
            self._draw_locks()
        return result

    config = configure

    def _on_scroll(self, first, last) -> None:
        callback = self._scroll_callback
        if callable(callback):
            callback(first, last)
        elif callback:
            self.tk.call(callback, first, last)
        self._draw_locks()

    def _draw_locks(self) -> None:
        """Paint only visible rows in a fixed right-hand gutter."""
        gutter = self.lock_gutter
        gutter.delete("all")
        gutter.configure(background=self.cget("background"))
        if not self._items or self._placeholder_visible:
            return
        selected = set(self.curselection())
        for index in range(self.nearest(0), min(len(self._items), self.nearest(self.winfo_height()) + 1)):
            bbox = self.bbox(index)
            if not bbox:
                continue
            _, y, _, height = bbox
            prefix = "select" if index in selected else ""
            background = self.itemcget(index, prefix + "background") or self.cget(prefix + "background")
            foreground = self.itemcget(index, prefix + "foreground") or self.cget(prefix + "foreground")
            gutter.create_rectangle(0, y, 26, y + height, fill=background, outline="")
            if "track_locked" in self._items[index].get("tags", ()):
                gutter.create_text(
                    13, y + height / 2, text="\N{LOCK}", fill=foreground, font=self.cget("font"), tags="lock"
                )

    def _destroy_gutter(self, event) -> None:
        if event.widget is self:
            self.lock_gutter.destroy()


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
