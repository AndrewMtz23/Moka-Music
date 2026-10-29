import tkinter as tk
import unittest
from dataclasses import replace
from io import BytesIO
from tkinter import ttk
from unittest.mock import Mock, patch

from PIL import Image, ImageTk

from app.i18n import I18n
from app.models import TrackInfo
from app.views.player_panel import PlayerControls


class PlayerLayoutTests(unittest.TestCase):
    def volume_widgets(self):
        self.player._show_volume_modal()
        self.root.update()
        modal = next(child for child in self.player.winfo_children() if isinstance(child, tk.Toplevel))
        self.addCleanup(modal.destroy)

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        widgets = list(descendants(modal))
        return modal, next(widget for widget in widgets if isinstance(widget, ttk.Scale)), widgets

    def test_volume_clicks_and_drag_follow_pointer(self):
        _modal, slider, _widgets = self.volume_widgets()
        start, y = slider.coords(float(slider.cget("from")))
        end, _ = slider.coords(float(slider.cget("to")))
        for fraction in (0.25, 0.65, 0.4):
            slider.event_generate("<ButtonPress-1>", x=round(start + (end - start) * fraction), y=y)
            slider.event_generate("<ButtonRelease-1>", x=round(start + (end - start) * fraction), y=y)
            self.root.update()
            self.assertAlmostEqual(self.player.playback.set_volume.call_args.args[0], fraction, delta=0.015)
        slider.event_generate("<ButtonPress-1>", x=start, y=y)
        slider.event_generate("<B1-Motion>", x=round(start + (end - start) * 0.8), y=y)
        slider.event_generate("<ButtonRelease-1>", x=end, y=y)
        self.root.update()
        self.assertAlmostEqual(self.player.playback.set_volume.call_args.args[0], 0.8, delta=0.015)

    def test_volume_modal_fits_near_screen_edges(self):
        width, height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        with (
            patch.object(self.player, "winfo_rootx", return_value=width - 100),
            patch.object(self.player, "winfo_rooty", return_value=height - 70),
        ):
            modal, _slider, widgets = self.volume_widgets()
        self.assertLessEqual(modal.winfo_rootx() + modal.winfo_width(), width)
        self.assertLessEqual(modal.winfo_rooty() + modal.winfo_height(), height)
        for widget in widgets:
            self.assertGreaterEqual(widget.winfo_rootx(), modal.winfo_rootx())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), modal.winfo_rootx() + modal.winfo_width())

    def test_volume_buttons_and_keyboard_use_small_steps(self):
        _modal, slider, widgets = self.volume_widgets()
        buttons = {widget.cget("text"): widget for widget in widgets if isinstance(widget, ttk.Button)}
        slider.set(50)
        buttons["+10%"].invoke()
        self.assertAlmostEqual(self.player.playback.set_volume.call_args.args[0], 0.6)
        buttons["−10%"].invoke()
        self.assertAlmostEqual(self.player.playback.set_volume.call_args.args[0], 0.5)
        slider.focus_force()
        slider.event_generate("<Right>")
        self.root.update()
        self.assertAlmostEqual(self.player.playback.set_volume.call_args.args[0], 0.51)
        slider.set(98)
        buttons["+10%"].invoke()
        self.assertEqual(self.player.playback.set_volume.call_args.args[0], 1)
        slider.set(2)
        buttons["−10%"].invoke()
        self.assertEqual(self.player.playback.set_volume.call_args.args[0], 0)

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.geometry("800x720+10000+10000")
        self.addCleanup(self.root.destroy)
        playback = Mock(volume=0.5, available=True)
        playback.state.return_value.is_playing = False
        with (
            patch("app.views.player_panel.PlaybackController", return_value=playback),
            patch.object(PlayerControls, "_start_progress_loop"),
        ):
            self.player = PlayerControls(self.root)
        self.addCleanup(self.player.cleanup)

    def assert_controls_fit(self, width, height=280):
        self.player.place(x=0, y=0, width=width, height=height)
        self.root.update()
        left = self.player.winfo_rootx()
        top = self.player.winfo_rooty()
        widgets = [
            self.player.mute_button,
            self.player.more_button,
            self.player.time_label_start,
            self.player.progress_bar,
            self.player.time_label_end,
            self.player.btn_prev,
            self.player.btn_play_pause,
            self.player.btn_next,
        ]
        if not self.player._compact_layout:
            widgets.extend((self.player.btn_seek_back, self.player.btn_seek_forward, self.player.btn_stop))
        card = self.player.card_frame
        for widget in widgets:
            with self.subTest(width=width, widget=str(widget)):
                self.assertTrue(widget.winfo_ismapped())
                self.assertGreaterEqual(widget.winfo_rootx(), card.winfo_rootx())
                self.assertGreaterEqual(widget.winfo_rooty(), card.winfo_rooty())
                self.assertLessEqual(
                    widget.winfo_rootx() + widget.winfo_width(), card.winfo_rootx() + card.winfo_width()
                )
                self.assertLessEqual(
                    widget.winfo_rooty() + widget.winfo_height(), card.winfo_rooty() + card.winfo_height()
                )
                self.assertGreaterEqual(widget.winfo_rootx(), left)
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), left + width)
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), top + height)
        self.assertGreater(self.player.progress_bar.winfo_width(), 35)
        vinyl = self.player.vinyl_canvas
        self.assertTrue(vinyl.winfo_ismapped())
        self.assertGreaterEqual(vinyl.winfo_rootx(), left)
        self.assertLessEqual(vinyl.winfo_rootx() + vinyl.winfo_width(), left + width)
        self.assertLessEqual(vinyl.winfo_rooty() + vinyl.winfo_height(), top + height)
        if self.player._compact_layout:
            self.assertLessEqual(vinyl.winfo_rootx() + vinyl.winfo_width(), self.player.top_row.winfo_rootx())
            self.assertLessEqual(vinyl.winfo_rooty() + vinyl.winfo_height(), self.player.progress_frame.winfo_rooty())

    def test_controls_fit_when_resizing_with_long_titles(self):
        self.player.track_info_label.configure(text="Una canción con un título muy largo " * 10)
        self.player.artist_label.configure(text="Artista " * 30)
        playback = self.player.playback
        for width, height in (
            (430, 210),
            (680, 280),
            (680, 250),
            (430, 340),
            (320, 340),
            (680, 440),
            (644, 280),
            (643, 280),
            (320, 280),
            (680, 280),
        ):
            self.assert_controls_fit(width, height)
        self.assertIs(self.player.playback, playback)
        playback.play.assert_not_called()

    def test_compact_disc_keeps_and_updates_cover(self):
        self.assert_controls_fit(430)
        for color in ("red", "blue"):
            self.player._cover_photo = ImageTk.PhotoImage(Image.new("RGBA", (146, 146), color))
            self.player._draw_vinyl()
            cover = self.player._compact_cover_photo
            self.assertEqual(
                ImageTk.getimage(cover).getpixel((15, 15)), Image.new("RGBA", (1, 1), color).getpixel((0, 0))
            )
            self.assert_controls_fit(680)
            self.assert_controls_fit(320)
            self.assertIs(self.player._compact_cover_photo, cover)

    def test_queue_and_status_fit_below_player(self):
        artwork = BytesIO()
        Image.new("RGB", (28, 28), "red").save(artwork, format="PNG")
        track = TrackInfo(
            filename="song.mp3",
            filepath="song.mp3",
            metadata={
                "title": "Un título largo " * 20,
                "artist": "Artista " * 15,
                "album": "Álbum",
                "year": "2017",
                "track_number": "0",
            },
            duration=187,
            cover_art=artwork.getvalue(),
            is_track_locked=True,
        )
        upcoming = [
            replace(
                track,
                filename=f"{number}.mp3",
                filepath=f"{number}.mp3",
                metadata={**track.metadata, "track_number": str(number)},
            )
            for number in (0, 302, 718, 4, 9)
        ]
        self.player.update_details(track, upcoming)
        self.assertEqual(len(self.player.details.upcoming), 5)
        self.assertEqual(
            [row.number.cget("text") for row in self.player.details.rows], ["#0", "#302", "#718", "#4", "#9"]
        )
        self.assertIn(track.metadata["album"], self.player.details.rows[0].subtitle.cget("text"))
        for width in (320, 430, 680):
            self.assert_controls_fit(width, 320)
            details = self.player.details
            self.assertTrue(details.winfo_ismapped())
            self.assertIn("🔒", details.status.cget("text"))
            self.assertIn("completos", details.status.cget("text"))
            self.assertEqual(details.rows[0].duration.cget("text"), "03:07")
            self.assertLess(details.viewport.winfo_height(), details.content.winfo_height())
            details.viewport.yview_moveto(1)
            self.root.update()
            last = details.rows[-1].frame
            self.assertLessEqual(
                last.winfo_rooty() + last.winfo_height(),
                details.viewport.winfo_rooty() + details.viewport.winfo_height(),
            )
            details.viewport.yview_moveto(0)
            self.assertLessEqual(
                details.status.winfo_rooty() + details.status.winfo_height(),
                details.winfo_rooty() + details.winfo_height(),
            )
            self.assertGreaterEqual(
                details.winfo_rooty(), self.player.card_frame.winfo_rooty() + self.player.card_frame.winfo_height()
            )
        self.assert_controls_fit(680, 620)
        details = self.player.details
        gap = details.winfo_rooty() - (self.player.card_frame.winfo_rooty() + self.player.card_frame.winfo_height())
        self.assertEqual(gap, 20)
        self.assertFalse(details.scrollbar.winfo_ismapped())
        for row in details.rows:
            self.assertGreaterEqual(row.frame.winfo_rooty(), details.viewport.winfo_rooty())
            self.assertLessEqual(
                row.frame.winfo_rooty() + row.frame.winfo_height(),
                details.viewport.winfo_rooty() + details.viewport.winfo_height(),
            )
        self.player.update_details(None, [])
        self.assertEqual(self.player.details.status.cget("text"), "")
        track.metadata = {}
        track.is_track_locked = False
        self.player.update_details(track, [track, track])
        self.assert_controls_fit(320, 320)
        details = self.player.details
        self.assertLessEqual(
            details.status.winfo_rooty() + details.status.winfo_height(),
            details.winfo_rooty() + details.winfo_height(),
        )
        details.t = I18n("en").t
        details.render()
        self.root.update()
        self.assertLessEqual(
            details.status.winfo_rooty() + details.status.winfo_height(),
            details.winfo_rooty() + details.winfo_height(),
        )
