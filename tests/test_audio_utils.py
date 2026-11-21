import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.utils.audio_utils import AudioUtils


class UntaggedAudio:
    info = SimpleNamespace(length=123.4)

    def __bool__(self):
        return False


class AudioUtilsTests(unittest.TestCase):
    @patch("app.utils.audio_utils.mutagen.File", return_value=UntaggedAudio())
    def test_audio_duration_is_read_when_audio_has_no_metadata_tags(self, mutagen_file):
        duration = AudioUtils.get_audio_duration("song.mp3")

        self.assertEqual(duration, 123.4)
        mutagen_file.assert_called_once_with("song.mp3", easy=True)


if __name__ == "__main__":
    unittest.main()
