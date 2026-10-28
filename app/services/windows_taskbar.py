"""Windows thumbnail toolbar. All native handles belong to the Tk UI thread."""

import ctypes as ct
import logging
import sys
from ctypes import wintypes as wt
from io import BytesIO
from uuid import UUID

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)
WM_COMMAND = 0x0111
WM_NCDESTROY = 0x0082
THBN_CLICKED = 0x1800
BUTTON_IDS = {"previous": 4101, "toggle": 4102, "next": 4103}


def thumbnail_command(message, wparam):
    if message != WM_COMMAND or (wparam >> 16) & 0xFFFF != THBN_CLICKED:
        return None
    return next((action for action, identifier in BUTTON_IDS.items() if identifier == (wparam & 0xFFFF)), None)


class ThumbButton(ct.Structure):
    _fields_ = [
        ("mask", wt.DWORD),
        ("id", wt.UINT),
        ("bitmap", wt.UINT),
        ("icon", wt.HICON),
        ("tip", wt.WCHAR * 260),
        ("flags", wt.DWORD),
    ]


class WindowsThumbnailToolbar:
    """Small ITaskbarList3 adapter; callbacks only enqueue messages for Tk."""

    def __init__(self, hwnd, emit):
        if sys.platform != "win32":
            raise OSError("Windows taskbar is unavailable")
        self.hwnd = hwnd
        self.emit = emit
        self.interface = ct.c_void_p()
        self.icons = {}
        self.com_initialized = False
        self.hooked = False
        self.added = False
        self.user = ct.WinDLL("user32", use_last_error=True)
        self.common = ct.WinDLL("comctl32", use_last_error=True)
        self.ole = ct.OleDLL("ole32")
        self.callback_type = ct.WINFUNCTYPE(
            ct.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, ct.c_size_t, ct.c_size_t
        )
        self.callback = self.callback_type(self._window_message)
        self._bind_functions()
        self.created_message = self.user.RegisterWindowMessageW("TaskbarButtonCreated")
        try:
            self.ole.CoInitializeEx(None, 2)  # STA; balance S_OK and S_FALSE alike.
            self.com_initialized = True
            clsid = (ct.c_ubyte * 16).from_buffer_copy(UUID("56fdf344-fd6d-11d0-958a-006097c9a090").bytes_le)
            iid = (ct.c_ubyte * 16).from_buffer_copy(UUID("ea1afb91-9e28-4b86-90e9-9e9f8a5eefaf").bytes_le)
            self.ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(self.interface))
            self._call(3, (), ())  # ITaskbarList::HrInit
            for name in ("previous", "play", "pause", "next"):
                self.icons[name] = self._create_icon(name)
            if not self.common.SetWindowSubclass(hwnd, self.callback, id(self), 0):
                raise ct.WinError(ct.get_last_error())
            self.hooked = True
        except Exception:
            self.close()
            raise

    def _bind_functions(self):
        functions = (
            (self.user.RegisterWindowMessageW, [wt.LPCWSTR], wt.UINT),
            (self.user.GetSystemMetrics, [ct.c_int], ct.c_int),
            (
                self.user.CreateIconFromResourceEx,
                [ct.c_void_p, wt.DWORD, wt.BOOL, wt.DWORD, ct.c_int, ct.c_int, wt.UINT],
                wt.HICON,
            ),
            (self.user.DestroyIcon, [wt.HICON], wt.BOOL),
            (self.common.SetWindowSubclass, [wt.HWND, self.callback_type, ct.c_size_t, ct.c_size_t], wt.BOOL),
            (self.common.RemoveWindowSubclass, [wt.HWND, self.callback_type, ct.c_size_t], wt.BOOL),
            (self.common.DefSubclassProc, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM], ct.c_ssize_t),
            (self.ole.CoInitializeEx, [ct.c_void_p, wt.DWORD], ct.c_long),
            (self.ole.CoCreateInstance, [ct.c_void_p, ct.c_void_p, wt.DWORD, ct.c_void_p, ct.c_void_p], ct.c_long),
            (self.ole.CoUninitialize, [], None),
        )
        for function, arguments, result in functions:
            function.argtypes, function.restype = arguments, result

    def _call(self, index, argtypes, args):
        table = ct.cast(self.interface, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        method = ct.WINFUNCTYPE(ct.c_long, ct.c_void_p, *argtypes)(table[index])
        result = method(self.interface, *args)
        if result < 0:
            raise OSError(f"Taskbar HRESULT 0x{result & 0xFFFFFFFF:08X}")

    def _create_icon(self, name):
        size = max(32, self.user.GetSystemMetrics(11))  # SM_CXICON
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        ink = (238, 238, 238, 255)

        def box(coords):
            draw.rectangle(tuple(round(value * size) for value in coords), fill=ink, outline=(50, 50, 50, 255))

        if name == "pause":
            box((0.28, 0.22, 0.42, 0.78))
            box((0.58, 0.22, 0.72, 0.78))
        else:
            draw.polygon(
                [(round(x * size), round(y * size)) for x, y in ((0.28, 0.2), (0.28, 0.8), (0.76, 0.5))],
                fill=ink,
                outline=(50, 50, 50, 255),
            )
            if name in ("next", "previous"):
                box((0.78, 0.2, 0.86, 0.8))
            if name == "previous":
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        data = BytesIO()
        image.save(data, format="PNG")
        raw = data.getvalue()
        buffer = ct.create_string_buffer(raw)
        icon = self.user.CreateIconFromResourceEx(buffer, len(raw), True, 0x00030000, size, size, 0)
        if not icon:
            raise ct.WinError(ct.get_last_error())
        return icon

    def _window_message(self, hwnd, message, wparam, lparam, _identifier, _data):
        try:
            if message == self.created_message:
                self.added = False  # Explorer can recreate the taskbar after a restart.
                self.emit("ready")
            action = thumbnail_command(message, wparam)
            if action:
                self.emit(action)
                return 0
            if message == WM_NCDESTROY:
                self.common.RemoveWindowSubclass(hwnd, self.callback, id(self))
                self.hooked = False
                self.emit("destroyed")
        except Exception:
            logger.exception("Taskbar window message failed")
        return self.common.DefSubclassProc(hwnd, message, wparam, lparam)

    def update(self, *, enabled, playing, labels):
        buttons = (ThumbButton * 3)()
        for index, action in enumerate(BUTTON_IDS):
            button = buttons[index]
            button.mask = 0xE  # THB_ICON | THB_TOOLTIP | THB_FLAGS
            button.id = BUTTON_IDS[action]
            icon = "pause" if playing else "play"
            button.icon = self.icons[icon if action == "toggle" else action]
            button.tip = labels[index][:259]
            button.flags = 0 if enabled else 1  # THBF_DISABLED
        self._call(16 if self.added else 15, (wt.HWND, wt.UINT, ct.POINTER(ThumbButton)), (self.hwnd, 3, buttons))
        self.added = True

    def close(self):
        if self.hooked:
            self.common.RemoveWindowSubclass(self.hwnd, self.callback, id(self))
            self.hooked = False
        if self.interface:
            table = ct.cast(self.interface, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
            ct.WINFUNCTYPE(wt.ULONG, ct.c_void_p)(table[2])(self.interface)  # Release
            self.interface = ct.c_void_p()
        for icon in self.icons.values():
            self.user.DestroyIcon(icon)
        self.icons.clear()
        if self.com_initialized:
            self.ole.CoUninitialize()
            self.com_initialized = False


def root_window_handle(root):
    user = ct.WinDLL("user32", use_last_error=True)
    user.GetAncestor.argtypes = [wt.HWND, wt.UINT]
    user.GetAncestor.restype = wt.HWND
    return user.GetAncestor(root.winfo_id(), 2)  # GA_ROOT: Tk's outer wrapper, not its client.
