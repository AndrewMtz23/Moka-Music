import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import patch

from app.ui.theme import StyleManager
from app.utils import themed_messagebox
from app.utils.window_chrome import theme_application_captions


class ThemedDialogTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.attributes("-alpha", 0)
        self.style = StyleManager(self.root)
        self.style.set_theme("midnight_blue")
        self.root.update()
        self.addCleanup(self.root.destroy)

    def choose(self, label):
        def find(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and child.cget("text") == label:
                    child.invoke()
                    return True
                if find(child):
                    return True
            return False

        self.root.after(100, lambda: find(self.root))

    def test_yes_no_cancel_return_types(self):
        for label, expected in (("Sí", True), ("No", False), ("Cancelar", None)):
            self.choose(label)
            self.assertIs(themed_messagebox.askyesnocancel("Test", "Confirm?", parent=self.root), expected)

    def test_exit_cancel_and_accept(self):
        for label, expected in (("Cancelar", False), ("Aceptar", True)):
            self.choose(label)
            self.assertIs(themed_messagebox.askokcancel("Exit", "Confirm?", parent=self.root), expected)

    def test_close_button_cancels_confirmation(self):
        def close_dialog():
            dialog = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
            dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))

        self.root.after(100, close_dialog)
        self.assertFalse(themed_messagebox.askokcancel("Exit", "Confirm?", parent=self.root))

    def test_nested_dialog_restores_existing_modal_grab(self):
        modal = tk.Toplevel(self.root)
        modal.update()
        modal.grab_set()
        self.choose("Aceptar")
        themed_messagebox.showinfo("Info", "Message", parent=modal)
        self.assertEqual(self.root.grab_current(), modal)
        modal.destroy()

    @patch("app.utils.window_chrome.sys.platform", "win32")
    def test_new_and_existing_dialogs_receive_updated_caption_palette(self):
        with patch("app.utils.window_chrome._apply_caption") as apply:
            modal = tk.Toplevel(self.root)
            self.root.update()
            self.assertTrue(any(call.args[0] is modal for call in apply.call_args_list))
            palette = {"background": "#ffffff", "text": "#111111"}
            theme_application_captions(self.root, palette)
            self.assertEqual(modal._caption_palette, palette)
            modal.destroy()

    def test_keyboard_escape_cancels_and_enter_uses_focused_button(self):
        for key, label, expected in (
            ("<Escape>", "Aceptar", False),
            ("<Return>", "Cancelar", False),
            ("<Return>", "Aceptar", True),
        ):

            def press(key=key, label=label):
                dialog = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
                pending = [dialog]
                while pending:
                    widget = pending.pop()
                    if isinstance(widget, ttk.Button) and widget.cget("text") == label:
                        widget.focus_force()
                        widget.event_generate(key)
                        return
                    pending.extend(widget.winfo_children())

            self.root.after(100, press)
            self.assertIs(themed_messagebox.askokcancel("Exit", "Confirm?", parent=self.root), expected)

    def test_message_text_matches_light_and_dark_palettes(self):
        for theme in ("light", "midnight_blue"):
            self.style.set_theme(theme)
            observed = []

            def inspect(observed=observed):
                pending = list(self.root.winfo_children())
                while pending:
                    widget = pending.pop()
                    if isinstance(widget, tk.Label) and widget.cget("text") == "Readable message":
                        observed.append((widget.cget("background"), widget.cget("foreground")))
                    pending.extend(widget.winfo_children())

            self.root.after(50, inspect)
            self.choose("Aceptar")
            themed_messagebox.showinfo("Theme", "Readable message", parent=self.root)
            colors = self.style.get_theme_colors()
            self.assertEqual(observed, [(colors["background"], colors["text"])])
