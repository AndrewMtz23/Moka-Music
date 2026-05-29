import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from app.controllers.metadata_controller import MetadataController
from app.models import FilterMode, SortMode, TrackInfo


class FakeMetadataEditor:
    def __init__(self, cover_art: bytes | None = None):
        self.cover_art = cover_art
        self.applied_metadata: list[tuple[list[str], dict[str, str]]] = []
        self.applied_covers: list[tuple[str, bytes | None]] = []

    def obtener_metadatos(self, ruta: str):
        return {
            "title": Path(ruta).stem,
            "artist": "Artist",
            "album": "Album",
            "genre": "",
            "year": "",
            "track_number": "0",
        }

    def obtener_portada(self, _ruta: str):
        return self.cover_art

    def aplicar_metadatos_en_lote(self, rutas, datos, portada_path=None):
        self.applied_metadata.append((list(rutas), dict(datos)))
        return 1, []

    def aplicar_portada_desde_bytes(self, ruta: str, image_data: bytes | None):
        self.applied_covers.append((ruta, image_data))
        return True, []


class ControllerTests(unittest.TestCase):
    def test_loads_only_supported_audio_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "a.mp3").write_bytes(b"")
            (path / "b.wav").write_bytes(b"")
            (path / "notes.txt").write_text("ignore", encoding="utf-8")

            controller = MetadataController()
            files = controller.cargar_archivos_mp3(temp_dir)

            self.assertEqual(files, ["a.mp3", "b.wav"])

    def test_sort_mode_by_filename_keeps_case_insensitive_order(self):
        controller = MetadataController()
        controller.archivos = ["z.mp3", "A.mp3", "m.mp3"]
        controller.set_sort_mode(SortMode.FILENAME)
        self.assertEqual(controller.archivos, ["A.mp3", "m.mp3", "z.mp3"])

    def test_sort_modes_use_metadata_and_duration(self):
        controller = MetadataController()
        controller.archivos = ["b.mp3", "a.mp3", "c.mp3"]
        controller._metadata_cache = {
            "b.mp3": TrackInfo("b.mp3", "b.mp3", {"artist": "Zeta", "album": "Beta"}, 30.0, None),
            "a.mp3": TrackInfo("a.mp3", "a.mp3", {"artist": "Alpha", "album": "Gamma"}, 10.0, None),
            "c.mp3": TrackInfo("c.mp3", "c.mp3", {"artist": "Mono", "album": "Alpha"}, 20.0, None),
        }

        controller.set_sort_mode(SortMode.ARTIST)
        self.assertEqual(controller.archivos, ["a.mp3", "c.mp3", "b.mp3"])

        controller.set_sort_mode(SortMode.ALBUM)
        self.assertEqual(controller.archivos, ["c.mp3", "b.mp3", "a.mp3"])

        controller.set_sort_mode(SortMode.DURATION)
        self.assertEqual(controller.archivos, ["a.mp3", "c.mp3", "b.mp3"])

    def test_reorder_files_switches_to_manual_order(self):
        controller = MetadataController()
        controller.archivos = ["one.mp3", "two.mp3", "three.mp3"]

        controller.reorder_files(["three.mp3", "one.mp3", "two.mp3"])

        self.assertEqual(controller.archivos, ["three.mp3", "one.mp3", "two.mp3"])
        self.assertEqual(controller._sort_mode, SortMode.MANUAL)

    def test_filters_missing_cover_and_duplicates(self):
        controller = MetadataController()
        controller.carpeta = "music"
        controller.archivos = ["a.mp3", "b.mp3", "c.mp3"]
        controller._metadata_cache = {
            "a.mp3": TrackInfo("a.mp3", "a.mp3", {"title": "Same", "artist": "One"}, 0.0, None),
            "b.mp3": TrackInfo("b.mp3", "b.mp3", {"title": "Same", "artist": "One"}, 0.0, None),
            "c.mp3": TrackInfo("c.mp3", "c.mp3", {"title": "Other", "artist": "Two"}, 0.0, None),
        }
        controller._cover_cache = {"a.mp3": True, "b.mp3": False, "c.mp3": False}

        self.assertEqual(controller.filter_files(mode=FilterMode.MISSING_COVER), ["b.mp3", "c.mp3"])
        self.assertEqual(controller.filter_files(mode=FilterMode.DUPLICATES), ["a.mp3", "b.mp3"])

    def test_backup_includes_cover_art_for_selected_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                folder = Path(temp_dir) / "music"
                folder.mkdir()
                (folder / "a.mp3").write_bytes(b"fake")
                (folder / "b.mp3").write_bytes(b"fake")

                controller = MetadataController()
                controller.carpeta = str(folder)
                controller.archivos = ["a.mp3", "b.mp3"]
                controller.metadata_editor = FakeMetadataEditor(cover_art=b"cover-bytes")

                backup_path = controller.crear_respaldo_metadatos({"artist": "New"}, ["a.mp3"])
                payload = json.loads(backup_path.read_text(encoding="utf-8"))

                self.assertEqual(payload["track_count"], 1)
                self.assertEqual(payload["tracks"][0]["filename"], "a.mp3")
                self.assertEqual(
                    payload["tracks"][0]["cover_art_b64"],
                    base64.b64encode(b"cover-bytes").decode("ascii"),
                )
            finally:
                os.chdir(original_cwd)

    def test_restore_backup_restores_cover_art_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio_path = folder / "a.mp3"
            audio_path.write_bytes(b"fake")
            cover_art = b"previous-cover"
            backup_path = folder / "backup.json"
            backup_path.write_text(
                json.dumps(
                    {
                        "library_folder": str(folder),
                        "tracks": [
                            {
                                "filename": "a.mp3",
                                "filepath": str(audio_path),
                                "metadata": {"title": "Old title"},
                                "cover_art_b64": base64.b64encode(cover_art).decode("ascii"),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            controller = MetadataController()
            controller.carpeta = str(folder)
            controller.archivos = ["a.mp3"]
            fake_editor = FakeMetadataEditor()
            controller.metadata_editor = fake_editor

            result = controller.restaurar_respaldo_metadatos(backup_path)

            self.assertTrue(result.success)
            self.assertEqual(fake_editor.applied_metadata[0][1], {"title": "Old title"})
            self.assertEqual(fake_editor.applied_covers[0][1], cover_art)

    def test_apply_track_numbers_from_order_starts_at_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "a.mp3").write_bytes(b"fake")
            (folder / "b.mp3").write_bytes(b"fake")
            controller = MetadataController()
            controller.carpeta = str(folder)
            controller.archivos = ["a.mp3", "b.mp3"]
            fake_editor = FakeMetadataEditor()
            controller.metadata_editor = fake_editor

            result = controller.apply_track_numbers_from_order()

            self.assertTrue(result.success)
            self.assertEqual(
                [metadata for _paths, metadata in fake_editor.applied_metadata],
                [{"track_number": "0"}, {"track_number": "1"}],
            )

    def test_editing_track_number_shifts_existing_tracks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            for filename in ("zero.mp3", "one.mp3", "two.mp3"):
                (folder / filename).write_bytes(b"fake")
            controller = MetadataController()
            controller.carpeta = str(folder)
            controller.archivos = ["zero.mp3", "one.mp3", "two.mp3"]
            controller._metadata_cache = {
                "zero.mp3": TrackInfo("zero.mp3", str(folder / "zero.mp3"), {"track_number": "0"}, 0.0, None),
                "one.mp3": TrackInfo("one.mp3", str(folder / "one.mp3"), {"track_number": "1"}, 0.0, None),
                "two.mp3": TrackInfo("two.mp3", str(folder / "two.mp3"), {"track_number": "2"}, 0.0, None),
            }
            fake_editor = FakeMetadataEditor()
            controller.metadata_editor = fake_editor

            result = controller.aplicar_cambios_a_archivo("zero.mp3", {"track_number": "1"})

            self.assertTrue(result.success)
            self.assertEqual(result.data["shifted_filenames"], ["two.mp3", "one.mp3"])
            self.assertEqual(
                [metadata for _paths, metadata in fake_editor.applied_metadata],
                [{"track_number": "3"}, {"track_number": "2"}, {"track_number": "1"}],
            )
