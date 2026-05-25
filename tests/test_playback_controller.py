import unittest

from app.controllers.playback_controller import PlaybackController


class FakeAudioPlayer:
    def __init__(self):
        self.available = True
        self.volume = 0.8
        self.duration = 120.0
        self.loaded = None
        self.position = 0.0
        self.playing = False
        self.ended = False
        self.cleaned = False

    def load(self, filepath):
        self.loaded = filepath

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def stop(self):
        self.playing = False
        self.position = 0.0

    def seek(self, position, resume=True):
        self.position = max(0.0, min(float(position), self.duration))
        self.playing = bool(resume)
        return self.position

    def get_position(self):
        return self.position

    def is_playing(self):
        return self.playing

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))

    def poll_track_end(self):
        was_ended = self.ended
        self.ended = False
        return was_ended

    def cleanup(self):
        self.cleaned = True


class PlaybackControllerTests(unittest.TestCase):
    def test_load_play_pause_and_stop_track(self):
        player = FakeAudioPlayer()
        controller = PlaybackController(player)

        state = controller.load("song.mp3")
        self.assertEqual(state.current_file, "song.mp3")
        self.assertEqual(state.duration, 120.0)

        state = controller.play()
        self.assertTrue(state.is_playing)

        player.position = 12.0
        state = controller.pause()
        self.assertFalse(state.is_playing)
        self.assertEqual(state.position, 12.0)

        state = controller.stop()
        self.assertEqual(state.position, 0.0)
        self.assertFalse(state.is_playing)

    def test_seek_volume_track_end_and_cleanup(self):
        player = FakeAudioPlayer()
        controller = PlaybackController(player)
        controller.load("song.mp3")
        player.position = 30.0

        state = controller.seek_relative(15)
        self.assertEqual(state.position, 45.0)

        state = controller.seek_absolute(200)
        self.assertEqual(state.position, 120.0)

        state = controller.set_volume(2.0)
        self.assertEqual(state.volume, 1.0)

        player.ended = True
        self.assertTrue(controller.poll_track_end())
        ended = controller.mark_ended()
        self.assertEqual(ended.position, 120.0)

        controller.cleanup()
        self.assertTrue(player.cleaned)


if __name__ == "__main__":
    unittest.main()
