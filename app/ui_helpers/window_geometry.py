"""Position small dialogs inside the working area of their anchor's monitor."""

import ctypes
import sys
from ctypes import wintypes


def monitor_work_area(anchor):
    if sys.platform == "win32":

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("monitor", wintypes.RECT),
                ("work", wintypes.RECT),
                ("flags", wintypes.DWORD),
            ]

        user = ctypes.WinDLL("user32", use_last_error=True)
        user.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user.MonitorFromPoint.restype = wintypes.HANDLE
        user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        user.GetMonitorInfoW.restype = wintypes.BOOL
        point = wintypes.POINT(anchor.winfo_rootx(), anchor.winfo_rooty())
        monitor = user.MonitorFromPoint(point, 2)  # Nearest monitor, including secondary screens.
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if user.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    return 0, 0, anchor.winfo_screenwidth(), anchor.winfo_screenheight()


def place_popup(window, anchor):
    window.update_idletasks()
    left, top, right, bottom = monitor_work_area(anchor)
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    # Leave room for the native title bar and resize borders (also at high DPI).
    margin = 12
    title_space = 48
    x = max(left + margin, min(anchor.winfo_rootx() + anchor.winfo_width() - width, right - width - margin))
    y = max(top + title_space, min(anchor.winfo_rooty() + 34, bottom - height - title_space))
    window.geometry(f"{width}x{height}+{x}+{y}")
