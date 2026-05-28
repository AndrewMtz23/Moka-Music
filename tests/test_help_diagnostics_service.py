import unittest
from unittest.mock import patch

from app.services.help_diagnostics_service import (
    active_language_label,
    detect_system_language,
    format_missing_translation_report,
    missing_translation_report,
)


class HelpDiagnosticsServiceTests(unittest.TestCase):
    def test_active_language_label_marks_current_language(self):
        self.assertEqual(active_language_label("Espanol", "es", "es"), "✓ Espanol")
        self.assertEqual(active_language_label("English", "en", "es"), "English")

    @patch("app.services.help_diagnostics_service.locale.getlocale", return_value=("es_MX", "UTF-8"))
    def test_detect_system_language_supports_spanish(self, _getlocale):
        self.assertEqual(detect_system_language(), "es")

    def test_missing_translation_report_has_supported_languages(self):
        report = missing_translation_report()

        self.assertIn("es", report)
        self.assertIn("en", report)

    def test_format_missing_translation_report_includes_counts(self):
        text = format_missing_translation_report({"es": [], "en": ["a", "b"]})

        self.assertIn("es: 0", text)
        self.assertIn("en: 2", text)


if __name__ == "__main__":
    unittest.main()
