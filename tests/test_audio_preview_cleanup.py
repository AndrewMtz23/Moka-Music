import os
import subprocess
import sys
import textwrap
import unittest


class PreviewCleanupTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows file-lock regression")
    def test_clearing_preview_releases_native_file_handle(self):
        # Isolate SDL so this test neither opens speakers nor resets the
        # application's global mixer used by other tests.
        script = textwrap.dedent("""
            from pathlib import Path
            from tempfile import TemporaryDirectory
            from unittest.mock import Mock
            import wave
            from app.controllers.playback_controller import PlaybackController
            from app.services.playback.audio_player import audio_player
            from app.views.player_panel import PlayerControls

            with TemporaryDirectory() as folder:
                source = Path(folder) / 'preview.wav'
                with wave.open(str(source), 'wb') as audio:
                    audio.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
                    audio.writeframes(b'\\0' * 44100 * 4)
                try:
                    assert audio_player.available
                    controller = PlaybackController(audio_player)
                    controller.load(str(source))
                    controller.play()
                    controller.stop()
                    # Normal stop must retain the track for replay.
                    controller.play()
                    panel = Mock(playback=controller)
                    PlayerControls.clear_file(panel)
                    source.unlink()  # Fails on Windows if SDL still holds it.
                    assert not source.exists()
                    assert controller.current_file is None
                    assert audio_player.current_track is None
                    assert controller.state().duration == 0
                    assert not controller.state().is_playing
                    PlayerControls.clear_file(panel)  # idempotent
                finally:
                    audio_player.cleanup()
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "SDL_AUDIODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
