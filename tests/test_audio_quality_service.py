import unittest

from app.services.audio_quality_service import format_audio_quality


class AudioQualityServiceTests(unittest.TestCase):
    def test_format_audio_quality_summarizes_technical_data(self):
        summary = format_audio_quality(
            {
                "bitrate_kbps": 320,
                "sample_rate": 44100,
                "channels": "stereo",
                "format": "MP3",
                "file_size_mb": 5.25,
            }
        )

        self.assertIn("320 kbps", summary)
        self.assertIn("44100 Hz", summary)
        self.assertIn("stereo", summary)
        self.assertIn("MP3", summary)
        self.assertIn("5.2 MB", summary)

    def test_format_audio_quality_reports_corrupt_state(self):
        self.assertEqual(format_audio_quality({"possibly_corrupt": True}), "Problema al leer audio")


if __name__ == "__main__":
    unittest.main()
