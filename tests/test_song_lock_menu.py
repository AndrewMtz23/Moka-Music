import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.controllers.song_actions_controller import SongActions
from app.i18n import I18n


class SongLockMenuTests(unittest.TestCase):
    def test_context_menu_toggles_the_clicked_tracks_lock(self):
        for locked in (False, True):
            with self.subTest(locked=locked):
                controller, tree, callback = Mock(), Mock(), Mock()
                controller.get_track_info.return_value = SimpleNamespace(is_track_locked=locked)
                tree.identify_row.return_value = "clicked"
                tree.item.return_value = {"tags": ("song.mp3",)}
                menu = Mock()
                with patch("app.controllers.song_actions_controller.tk.Menu", return_value=menu):
                    SongActions(I18n("es").t).mostrar_boton_contextual(
                        Mock(),
                        controller,
                        SimpleNamespace(carpeta=""),
                        tree,
                        Mock(),
                        Mock(),
                        SimpleNamespace(y=10, x_root=20, y_root=30),
                        on_result=callback,
                    )
                action = menu.add_command.call_args_list[0].kwargs
                self.assertIn("Desbloquear" if locked else "Bloquear", action["label"])
                self.assertIn("🔓" if locked else "🔒", action["label"])
                action["command"]()
                controller.change_track_number_lock.assert_called_once_with("song.mp3", not locked)
                callback.assert_called_once_with(controller.change_track_number_lock.return_value)
                tree.selection_set.assert_called_once_with("clicked")
