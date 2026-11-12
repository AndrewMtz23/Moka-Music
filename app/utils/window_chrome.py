"""Match native Windows captions to a Tk window's palette."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from ctypes import wintypes


def _colorref(color: str) -> int:
    red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    return red | green << 8 | blue << 16


def _apply_caption(window, colors):
    if sys.platform != "win32":
        return
    try:
        if not window.winfo_exists():
            return
        background = colors["background"]
        red, green, blue = (int(background[index : index + 2], 16) for index in (1, 3, 5))
        dark = (0.299 * red + 0.587 * green + 0.114 * blue) < 158
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
        ancestor = user32.GetAncestor
        ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
        ancestor.restype = wintypes.HWND
        # Tk's id identifies the client window; DWM needs its native root wrapper.
        handle = ancestor(window.winfo_id(), 2)
        if not handle:
            return
        setter = dwm.DwmSetWindowAttribute
        setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        setter.restype = ctypes.c_long
        enabled = wintypes.BOOL(dark)
        setter(handle, 20, ctypes.byref(enabled), ctypes.sizeof(enabled))
        # Explicit caption colors on Windows 11 also work with a light OS theme.
        # Older Windows versions ignore unsupported attributes without changing chrome.
        for attribute, value in (
            (35, _colorref(background) if dark else 0xFFFFFFFF),
            (36, _colorref(colors["text"]) if dark else 0xFFFFFFFF),
        ):
            color = wintypes.DWORD(value)
            setter(handle, attribute, ctypes.byref(color), ctypes.sizeof(color))
    except (OSError, AttributeError, ValueError, KeyError, tk.TclError):
        # Native chrome is optional on other platforms / older window managers.
        return


def theme_window_caption(window, colors):
    if sys.platform != "win32":
        return
    window._caption_palette = dict(colors)
    if not getattr(window, "_caption_map_bound", False):

        def on_map(event):
            if event.widget is window:
                _apply_caption(window, window._caption_palette)

        window.bind("<Map>", on_map, add="+")
        window._caption_map_bound = True
    _apply_caption(window, window._caption_palette)


def theme_application_captions(root, colors):
    """Cover existing and future Tk dialogs without replacing native window controls."""
    root._application_caption_palette = dict(colors)
    if not getattr(root, "_application_caption_bound", False):

        def on_map(event):
            widget = event.widget
            if isinstance(widget, (tk.Tk, tk.Toplevel)) and not widget.overrideredirect():
                theme_window_caption(widget, root._application_caption_palette)

        root.bind_all("<Map>", on_map, add="+")
        root._application_caption_bound = True
    pending = [root]
    while pending:
        widget = pending.pop()
        if isinstance(widget, (tk.Tk, tk.Toplevel)) and not widget.overrideredirect():
            theme_window_caption(widget, colors)
        pending.extend(widget.winfo_children())
