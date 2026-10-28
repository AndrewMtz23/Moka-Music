"""Bridge Windows thumbnail events to existing Tk playback commands."""

import logging
import sys
from queue import Empty, SimpleQueue

from ..services.windows_taskbar import WindowsThumbnailToolbar, root_window_handle


class TaskbarController:
    def __init__(
        self,
        root,
        *,
        state,
        commands,
        translator,
        native_factory=WindowsThumbnailToolbar,
        hwnd_factory=root_window_handle,
        platform=sys.platform,
    ):
        self.root = root
        self.state = state
        self.commands = commands
        self.t = translator
        self.events = SimpleQueue()
        self.native = None
        self.job = None
        self.ready = False
        self.last_state = None
        self.closed = False
        self.map_binding = None
        self.native_factory = native_factory
        self.hwnd_factory = hwnd_factory
        if platform != "win32":
            return
        self.map_binding = root.bind("<Map>", self._on_map, add="+")
        if root.winfo_ismapped():
            self._attach()

    def _on_map(self, event):
        if event.widget is self.root and not self.closed and self.native is None:
            self._attach()

    def _attach(self):
        # Tk creates its outer HWND when mapped. Hooking winfo_id() before
        # that point attaches to the client and misses TaskbarButtonCreated.
        try:
            self.native = self.native_factory(self.hwnd_factory(self.root), self.events.put)
            self.job = self.root.after(150, self._poll)
        except Exception:
            logging.getLogger(__name__).exception("Windows thumbnail controls could not be initialized")
            self.close()

    def _poll(self):
        self.job = None
        if self.closed:
            return
        try:
            while True:
                try:
                    event = self.events.get_nowait()
                except Empty:
                    break
                if event == "destroyed":
                    self.close()
                    return
                if event == "ready":
                    self.ready = True
                    self.last_state = None
                elif event in self.commands:
                    state = self.state()
                    if state and state.available and state.current_file:
                        self.commands[event]()
            if self.ready:
                state = self.state()
                enabled = bool(state and state.available and state.current_file)
                playing = bool(enabled and state.is_playing)
                labels = (
                    self.t("player.previous"),
                    self.t("player.pause" if playing else "player.play"),
                    self.t("player.next"),
                )
                signature = (enabled, playing, labels)
                if signature != self.last_state:
                    self.native.update(enabled=enabled, playing=playing, labels=labels)
                    self.last_state = signature
        except Exception:
            logging.getLogger(__name__).exception("Windows thumbnail controls failed")
            self.close()
            return
        self.job = self.root.after(300, self._poll)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.map_binding:
            self.root.unbind("<Map>", self.map_binding)
            self.map_binding = None
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        if self.native is not None:
            self.native.close()
            self.native = None
