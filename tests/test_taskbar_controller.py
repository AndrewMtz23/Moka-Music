import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.controllers.taskbar_controller import TaskbarController
from app.i18n import I18n
from app.services.windows_taskbar import BUTTON_IDS, THBN_CLICKED, WM_COMMAND, thumbnail_command


class TaskbarControllerTests(unittest.TestCase):
    def make_controller(self):
        self.state = SimpleNamespace(available=True, current_file="song.mp3", is_playing=False)
        self.root = Mock()
        self.native = Mock()
        self.commands = {name: Mock() for name in BUTTON_IDS}
        controller = TaskbarController(
            self.root,
            state=lambda: self.state,
            commands=self.commands,
            translator=I18n("es").t,
            native_factory=lambda _hwnd, _emit: self.native,
            hwnd_factory=lambda _root: 1,
            platform="win32",
        )
        self.addCleanup(controller.close)
        return controller

    def test_waits_for_taskbar_then_updates_only_changed_state(self):
        controller = self.make_controller()
        controller._poll()
        self.native.update.assert_not_called()
        controller.events.put("ready")
        controller._poll()
        self.assertFalse(self.native.update.call_args.kwargs["playing"])
        self.native.update.reset_mock()
        controller._poll()
        self.native.update.assert_not_called()
        self.state.is_playing = True
        controller._poll()
        self.assertEqual(self.native.update.call_args.kwargs["labels"][1], "Pausar")
        controller.events.put("ready")
        controller._poll()
        self.assertEqual(self.native.update.call_count, 2)

    def test_commands_reuse_player_and_no_file_disables_controls(self):
        controller = self.make_controller()
        for name in BUTTON_IDS:
            controller.events.put(name)
        controller._poll()
        for callback in self.commands.values():
            callback.assert_called_once_with()
        self.state.current_file = None
        controller.events.put("ready")
        controller.events.put("toggle")
        controller._poll()
        self.commands["toggle"].assert_called_once_with()
        self.assertFalse(self.native.update.call_args.kwargs["enabled"])
        controller.close()
        controller.close()
        self.native.close.assert_called_once_with()

    def test_ignores_other_native_commands(self):
        for action, identifier in BUTTON_IDS.items():
            self.assertEqual(thumbnail_command(WM_COMMAND, (THBN_CLICKED << 16) | identifier), action)
            self.assertIsNone(thumbnail_command(WM_COMMAND, identifier))
        self.assertIsNone(thumbnail_command(0, (THBN_CLICKED << 16) | 4101))

    def test_other_platforms_do_not_initialize_windows(self):
        factory = Mock()
        controller = TaskbarController(
            Mock(), state=Mock(), commands={}, translator=Mock(), native_factory=factory, platform="linux"
        )
        factory.assert_not_called()
        controller.close()

    def test_initializes_when_tk_maps_its_outer_window(self):
        root = Mock()
        root.winfo_ismapped.return_value = False
        factory = Mock()
        controller = TaskbarController(
            root,
            state=lambda: None,
            commands={},
            translator=I18n("es").t,
            native_factory=factory,
            hwnd_factory=lambda _root: 12,
            platform="win32",
        )
        self.addCleanup(controller.close)
        factory.assert_not_called()
        controller._on_map(SimpleNamespace(widget=root))
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args[0], 12)
        controller._on_map(SimpleNamespace(widget=root))
        factory.assert_called_once()

    @unittest.skipUnless(sys.platform == "win32", "Windows native API")
    def test_windows_native_resources_and_message_dispatch(self):
        import ctypes as ct
        import tkinter as tk
        from ctypes import wintypes as wt

        from app.services.windows_taskbar import WindowsThumbnailToolbar, root_window_handle

        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        events = []
        native = WindowsThumbnailToolbar(root_window_handle(root), events.append)
        self.addCleanup(native.close)
        self.assertEqual(len(native.icons), 4)
        user = ct.WinDLL("user32")
        user.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        user.SendMessageW.restype = ct.c_ssize_t
        user.SendMessageW(native.hwnd, WM_COMMAND, (THBN_CLICKED << 16) | BUTTON_IDS["next"], 0)
        self.assertEqual(events, ["next"])
        native.close()
        self.assertFalse(native.interface)
        self.assertFalse(native.icons)
