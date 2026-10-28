import tkinter as tk
import unittest
from unittest.mock import patch

from app.ui_helpers.widgets import LibraryListbox


def row(name, title=None):
    return {"text": title or name, "values": (1, name), "tags": (name, "odd_row")}


class LibraryListboxTests(unittest.TestCase):
    def test_lock_gutter_stays_on_right_when_resizing_and_scrolling(self):
        self.root.geometry("420x180+10000+10000")
        self.root.deiconify()
        self.tree.pack_forget()
        self.tree.lock_gutter.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        rows = [row(str(index)) for index in range(100)]
        for index in (0, 99):
            rows[index]["tags"] += ("track_locked",)
        self.tree.sync_items(rows)
        self.root.update()
        gutter = self.tree.lock_gutter
        self.assertEqual(len(gutter.find_withtag("lock")), 1)
        self.assertNotIn("\N{LOCK}", self.tree.get(0))
        self.tree.selection_set("0")
        self.tree.selection_clear(0, "end")
        self.root.update()
        self.assertFalse(self.tree.selection())
        self.assertEqual(gutter.itemcget(gutter.find_withtag("lock")[0], "fill"), self.tree.cget("foreground"))
        for width in (420, 600):
            self.root.geometry(f"{width}x180+10000+10000")
            self.root.update()
            self.assertGreaterEqual(gutter.winfo_rootx(), self.tree.winfo_rootx() + self.tree.winfo_width())
        self.tree.yview_moveto(1)
        self.root.update()
        self.assertEqual(len(gutter.find_withtag("lock")), 1)
        self.tree.sync_items([row(str(index)) for index in range(100)])
        self.root.update()
        self.assertFalse(gutter.find_withtag("lock"))

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.tree = LibraryListbox(self.root, height=5)
        self.tree.pack()

    def test_unchanged_rows_are_not_deleted_or_inserted(self):
        rows = [row("a"), row("b")]
        self.tree.sync_items(rows)
        with (
            patch.object(tk.Listbox, "delete", autospec=True) as delete,
            patch.object(tk.Listbox, "insert", autospec=True) as insert,
        ):
            self.tree.sync_items(rows)
        delete.assert_not_called()
        insert.assert_not_called()
        self.assertEqual(self.tree.get(0, "end"), (" 1. a", " 1. b"))

    def test_edit_updates_only_changed_row_and_preserves_multiselection(self):
        self.tree.sync_items([row("a"), row("b"), row("c")])
        tk.Listbox.selection_set(self.tree, 0, 1)
        original_delete = tk.Listbox.delete
        with patch.object(tk.Listbox, "delete", autospec=True, side_effect=original_delete) as delete:
            self.tree.sync_items([row("a"), row("b", "Edited"), row("c")])
        self.assertEqual(delete.call_count, 1)
        self.assertEqual(self.tree.get(0, "end"), (" 1. a", " 1. Edited", " 1. c"))
        self.assertEqual(self.tree.selection(), ("0", "1"))

    def test_reorder_insert_remove_preserves_selection_by_filename(self):
        self.tree.sync_items([row("a"), row("b"), row("c")])
        self.tree.selection_set("1")
        self.tree.sync_items([row("c"), row("new"), row("b")])
        self.assertEqual([self.tree.item(i)["tags"][0] for i in self.tree.get_children()], ["c", "new", "b"])
        self.assertEqual(self.tree.selection(), ("2",))
        self.assertEqual(self.tree.focus(), "2")
        self.tree.sync_items([])
        self.assertEqual(self.tree.get_children(), ())
        self.assertEqual(self.tree.selection(), ())

    def test_reorder_preserves_range_selection_anchor(self):
        self.tree.sync_items([row("a"), row("b"), row("c"), row("d"), row("e")])
        self.tree.selection_set("3")
        self.tree.selection_anchor(3)
        self.tree.sync_items([row("a"), row("d"), row("b"), row("c"), row("e")])
        self.assertEqual(self.tree.item(self.tree.index("anchor"))["tags"][0], "d")

    def test_style_changes_repaint_without_replacing_text(self):
        self.tree.tag_configure("odd_row", foreground="#ff0000")
        self.tree.sync_items([row("a")])
        self.assertEqual(self.tree.itemcget(0, "foreground"), "#ff0000")
        self.tree.tag_configure("odd_row", foreground="#0000ff")
        self.assertEqual(self.tree.itemcget(0, "foreground"), "#0000ff")
        with patch.object(self.tree, "_paint_item", wraps=self.tree._paint_item) as paint:
            self.tree.tag_configure("odd_row", foreground="#0000ff")
        paint.assert_not_called()

    def test_refresh_keeps_scroll_anchor(self):
        rows = [row(str(index)) for index in range(100)]
        self.tree.sync_items(rows)
        self.tree.yview_moveto(0.5)
        top_name = self.tree.item(self.tree.nearest(0))["tags"][0]
        self.tree.sync_items([row("new")] + rows)
        self.assertEqual(self.tree.item(self.tree.nearest(0))["tags"][0], top_name)
