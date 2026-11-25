import gc
import math
import shutil
import struct
import tkinter as tk
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import mutagen

from app.i18n import I18n
from app.models.audio_edit_project import AudioEditClip, AudioEditProject, AudioEditTrack
from app.models.audio_export_settings import AudioExportSettings
from app.services.audio_edit_service import AudioEditError, build_render_command, export_audio_project
from app.ui.theme import THEME_PRESETS
from app.views.audio_editor_dashboard import AudioEditorDashboard
from app.views.audio_export_dialog import AudioExportDialog


class ExportSettingsTests(unittest.TestCase):
    def test_invalid_combinations_are_rejected(self):
        for values in (
            {"format": ".aac"},
            {"format": ".mp3", "sample_rate": 96000},
            {"sample_rate": 12345},
            {"bit_depth": 20},
            {"bitrate_kbps": 123},
            {"ogg_quality": 20},
            {"sample_rate": float("nan")},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                AudioExportSettings(**values)

    @patch("pathlib.Path.is_file", return_value=True)
    def test_settings_control_entire_chain_and_codec(self, _is_file):
        project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (AudioEditClip(Path("source.wav"), 0, 1),)),))
        settings = AudioExportSettings(format=".wav", sample_rate=96000, bit_depth=24)
        command = build_render_command(project, Path("output.wav"), export_settings=settings)
        self.assertIn("aresample=96000", command[command.index("-filter_complex") + 1])
        self.assertNotIn("aresample=44100", command[command.index("-filter_complex") + 1])
        self.assertEqual(command[command.index("-codec:a") + 1], "pcm_s24le")
        self.assertEqual(command[command.index("-ar") + 1], "96000")
        with self.assertRaises(AudioEditError):
            build_render_command(project, Path("output.mp3"), export_settings=settings)
        default = build_render_command(project, Path("preview.wav"))
        self.assertIn("aresample=44100", default[default.index("-filter_complex") + 1])
        self.assertIn("pcm_s16le", default)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_real_exports_match_requested_parameters_without_overwriting(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.wav"
            with wave.open(str(source), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(48000)
                audio.writeframes(
                    b"".join(
                        struct.pack("<h", int(5000 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(48000)
                    )
                )
            original = source.read_bytes()
            project = AudioEditProject(tracks=(AudioEditTrack("t", "Track", (AudioEditClip(source, 0, 1),)),))
            configurations = (
                [
                    AudioExportSettings(format=extension, sample_rate=rate, bit_depth=depth)
                    for extension in (".wav", ".flac")
                    for rate in (44100, 48000, 96000)
                    for depth in (16, 24)
                ]
                + [
                    AudioExportSettings(format=".mp3", sample_rate=rate, bitrate_kbps=bitrate)
                    for rate in (44100, 48000)
                    for bitrate in (128, 192, 256, 320)
                ]
                + [
                    AudioExportSettings(format=".ogg", sample_rate=rate, ogg_quality=quality)
                    for rate in (44100, 48000)
                    for quality in (3, 5, 7, 9)
                ]
            )
            published = {}
            for settings in configurations:
                with self.subTest(settings=settings):
                    extension = settings.format
                    output = export_audio_project(project, root, "source", extension, export_settings=settings)
                    self.assertNotEqual(output, source)
                    self.assertNotIn(output, published)
                    published[output] = output.read_bytes()
                    info = mutagen.File(str(output)).info
                    self.assertEqual(info.sample_rate, settings.sample_rate)
                    self.assertAlmostEqual(info.length, 1, delta=0.1)
                    if extension in (".wav", ".flac"):
                        self.assertEqual(info.bits_per_sample, settings.bit_depth)
                    elif extension == ".mp3":
                        # Mutagen derives this from frame bytes/sample count;
                        # 44.1 kHz frame padding produces a few bps of rounding.
                        self.assertAlmostEqual(info.bitrate, settings.bitrate_kbps * 1000, delta=100)
                    else:
                        # Vorbis stores nominal bitrate, not the requested quality.
                        # Check the quality passed to the real encoder separately.
                        command = build_render_command(project, output, export_settings=settings)
                        self.assertEqual(command[command.index("-q:a") + 1], str(settings.ogg_quality))
                        self.assertGreater(info.bitrate, 0)
            for path, contents in published.items():
                self.assertEqual(path.read_bytes(), contents)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(list(root.glob(".mokamusic-render-*")))


class ExportDialogTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = tk.Tk()
        self.root.withdraw()
        self.dialog = AudioExportDialog(
            self.root,
            translate=I18n("en").t,
            colors=THEME_PRESETS["dark"],
            folder=Path(self.folder.name),
            name="Mix",
            settings=AudioExportSettings(),
        )
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.dialog.winfo_exists():
            self.dialog.destroy()
        self.root.destroy()
        self.dialog = self.root = None
        gc.collect()

    def test_format_change_limits_fields_and_rates(self):
        dialog = self.dialog
        dialog.format_var.set(".wav")
        dialog._sync_format()
        dialog.rate_var.set("96000")
        dialog.depth_var.set("24")
        dialog.format_var.set(".mp3")
        dialog._sync_format()
        self.assertEqual(dialog.rate_var.get(), "44100")
        self.assertNotIn("96000", dialog.rate_box.cget("values"))

    def test_accept_returns_export_request_and_cancel_returns_none(self):
        self.dialog._accept()
        folder, name, settings = self.dialog.result
        self.assertEqual(folder, Path(self.folder.name))
        self.assertEqual(name, "Mix")
        self.assertEqual(settings, AudioExportSettings())

    def test_cancel_has_no_export_request(self):
        self.dialog.destroy()
        self.assertIsNone(self.dialog.result)

    def test_editor_forwards_selected_settings_and_cancellation_keeps_preferences(self):
        self.dialog.destroy()
        editor = AudioEditorDashboard(self.root, source_paths=[], translate=I18n("en").t, colors=THEME_PRESETS["dark"])
        try:
            editor._clips = [AudioEditClip(Path(self.folder.name) / "source.wav", 0, 1)]
            editor._refresh_project()
            with (
                patch("app.views.audio_editor_dashboard.choose_audio_export", return_value=None),
                patch.object(editor, "_start_render") as start,
            ):
                editor._choose_export()
                start.assert_not_called()
                self.assertEqual(editor._export_settings, AudioExportSettings())
            selected = AudioExportSettings(format=".flac", sample_rate=96000, bit_depth=24)
            request = Path(self.folder.name), "Mix", selected
            with (
                patch("app.views.audio_editor_dashboard.choose_audio_export", return_value=request),
                patch(
                    "app.views.audio_editor_dashboard.export_audio_project",
                    return_value=Path(self.folder.name) / "Mix.flac",
                ) as export,
            ):
                editor._choose_export()
                editor._render_thread.join(5)
                self.assertFalse(editor._render_thread.is_alive())
                self.assertEqual(export.call_args.kwargs["export_settings"], selected)
                self.assertEqual(export.call_args.args[3], ".flac")
                self.assertEqual(editor._export_format_var.get(), ".flac")
        finally:
            editor._finish_render()
            editor.close()

    def test_blank_folder_and_dot_names_show_inline_error(self):
        self.dialog.folder_var.set("")
        self.dialog._accept()
        self.assertIsNone(self.dialog.result)
        self.assertTrue(self.dialog.winfo_exists())
        self.dialog.folder_var.set(self.folder.name)
        for name in (".", "...", "   "):
            self.dialog.name_var.set(name)
            self.dialog._accept()
            self.assertIsNone(self.dialog.result)
            self.assertTrue(self.dialog.error_var.get())

    def test_enter_on_cancel_does_not_accept_export(self):
        self.root.deiconify()
        self.dialog.update()
        content = self.dialog.winfo_children()[0]
        actions = content.winfo_children()[-1]
        cancel = actions.winfo_children()[0]
        cancel.focus_force()
        self.dialog.update()
        cancel.event_generate("<Return>")
        self.root.update()
        self.assertIsNone(self.dialog.result)
        self.assertFalse(self.dialog.winfo_exists())

    def test_invalid_name_or_folder_keeps_dialog_open(self):
        self.dialog.name_var.set("  ")
        self.dialog._accept()
        self.assertIsNone(self.dialog.result)
        self.assertTrue(self.dialog.error_var.get())
        self.dialog.name_var.set("Mix")
        self.dialog.folder_var.set(str(Path(self.folder.name) / "absent"))
        self.dialog._accept()
        self.assertIsNone(self.dialog.result)
        self.assertTrue(self.dialog.winfo_exists())
