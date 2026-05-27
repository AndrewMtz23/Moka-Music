import unittest

from app.ui.theme import THEME_PRESETS
from app.i18n import I18n
from app.views.modals.theme_settings_modal import (
    THEME_CHOICES,
    THEME_SETTINGS_MODAL_GEOMETRY,
    THEME_SETTINGS_FULLSCREEN_SHORTCUT,
    THEME_SETTINGS_MODAL_MIN_SIZE,
    density_label,
    font_scale_label,
    preview_palette,
    selected_density,
    selected_font_scale,
    theme_choice_labels,
)


class ThemeSettingsModalTests(unittest.TestCase):
    def test_preview_palette_falls_back_to_light_for_system_and_unknown(self):
        self.assertEqual(preview_palette("system")["background"], "#f6f6f4")
        self.assertEqual(preview_palette("unknown")["background"], "#f6f6f4")

    def test_preview_palette_returns_dark_palette(self):
        self.assertEqual(preview_palette("dark")["background"], "#0f0f10")
        self.assertIn("warning", preview_palette("dark"))
        self.assertIn("error", preview_palette("dark"))
        self.assertIn("success", preview_palette("dark"))

    def test_theme_choices_include_new_presets(self):
        theme_ids = [theme_id for theme_id, _label_key in THEME_CHOICES]

        self.assertIn("moka_classic", theme_ids)
        self.assertIn("midnight_blue", theme_ids)
        self.assertIn("forest", theme_ids)
        self.assertIn("rose", theme_ids)
        self.assertIn("high_contrast", theme_ids)
        self.assertIn("oled_black", theme_ids)

    def test_theme_modal_has_room_for_preview_and_options(self):
        self.assertEqual(THEME_SETTINGS_MODAL_GEOMETRY, "980x620")
        self.assertEqual(THEME_SETTINGS_MODAL_MIN_SIZE, (880, 560))
        self.assertEqual(THEME_SETTINGS_FULLSCREEN_SHORTCUT, "F11")

    def test_preview_palette_uses_shared_theme_presets(self):
        self.assertEqual(preview_palette("forest"), THEME_PRESETS["forest"])

    def test_preview_palette_applies_custom_accent(self):
        palette = preview_palette("light", "#336699")

        self.assertEqual(palette["primary"], "#336699")
        self.assertEqual(palette["highlight"], "#336699")
        self.assertEqual(palette["button_text"], "#ffffff")
        self.assertEqual(preview_palette("light", "bad")["primary"], THEME_PRESETS["light"]["primary"])

    def test_custom_themes_are_available_in_preview_choices(self):
        translator = I18n("es").t
        custom_themes = [
            {
                "id": "custom_moka",
                "name": "Mi Moka",
                "base_theme": "dark",
                "accent_color": "#336699",
            }
        ]

        self.assertIn(("custom_moka", "Mi Moka"), theme_choice_labels(translator, custom_themes))
        self.assertEqual(preview_palette("custom_moka", custom_themes=custom_themes)["primary"], "#336699")
        self.assertEqual(preview_palette("custom_moka", custom_themes=custom_themes)["background"], "#0f0f10")

    def test_font_scale_helpers_round_trip_labels(self):
        self.assertEqual(font_scale_label(1.15), "115%")
        self.assertEqual(selected_font_scale("115%"), 1.15)
        self.assertEqual(selected_font_scale("bad"), 1.0)

    def test_density_helpers_round_trip_translated_labels(self):
        translator = I18n("es").t

        label = density_label(translator, "comfortable")

        self.assertEqual(label, "Comoda")
        self.assertEqual(selected_density(translator, label), "comfortable")
        self.assertEqual(selected_density(translator, "rara"), "normal")


if __name__ == "__main__":
    unittest.main()
