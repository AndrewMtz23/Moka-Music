import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import eyed3.id3
from mutagen.easyid3 import EasyID3

from app.controllers.metadata_controller import MetadataController
from app.models import FilterMode, SortMode, TrackInfo
from app.services.library_cache_service import LibraryCache
from app.services.track_scan_service import TrackScanResult
from app.ui.interaction_workflow import InteractionWorkflowMixin


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
    def test_existing_manual_assignments_do_not_become_explicit_locks(self):
        controller, _ = self.track_library({"a.mp3": 210, "b.mp3": 302})
        controller.set_track_number_manual("a.mp3", True)
        controller.set_track_number_manual("b.mp3", True)
        controller.cargar_archivos_mp3(controller.carpeta)
        self.assertFalse(controller.get_track_info("a.mp3").is_track_locked)
        self.assertFalse(controller.get_track_info("b.mp3").is_track_locked)
        controller.change_track_number_lock("a.mp3", True)
        controller.cargar_archivos_mp3(controller.carpeta)
        self.assertTrue(controller.get_track_info("a.mp3").is_track_locked)
        self.assertFalse(controller.get_track_info("b.mp3").is_track_locked)
        self.assertEqual(controller.get_track_info("b.mp3").metadata["track_number"], "302")

    def test_explicit_lock_survives_rename_and_protects_automatic_numbering(self):
        controller, metadata = self.track_library({"a.mp3": 210, "b.mp3": 0})
        controller.change_track_number_lock("a.mp3", True)
        Path(controller.carpeta, "a.mp3").rename(Path(controller.carpeta, "renamed.mp3"))
        metadata["renamed.mp3"] = metadata.pop("a.mp3")
        controller.rename_file("a.mp3", "renamed.mp3")
        self.assertTrue(controller.get_track_info("renamed.mp3").is_track_locked)
        self.assertFalse(controller.get_track_info("renamed.mp3").is_manually_set)
        controller.apply_track_numbers_from_order()
        self.assertEqual(controller.get_track_info("renamed.mp3").metadata["track_number"], "210")
        self.assertFalse(controller.library_cache.is_track_number_locked(Path(controller.carpeta, "a.mp3")))

    def test_context_lock_preserves_number_without_writing_audio(self):
        controller, metadata = self.track_library({"song.mp3": 210})
        result = controller.change_track_number_lock("song.mp3", True)
        self.assertTrue(result.success)
        self.assertTrue(controller.get_track_info("song.mp3").is_track_locked)
        controller.metadata_editor.aplicar_metadatos_en_lote.assert_not_called()
        controller.cargar_archivos_mp3(controller.carpeta)
        self.assertTrue(controller.get_track_info("song.mp3").is_track_locked)
        self.assertTrue(controller.change_track_number_lock("song.mp3", False).success)
        self.assertFalse(controller.get_track_info("song.mp3").is_track_locked)
        controller.metadata_editor.aplicar_metadatos_en_lote.assert_not_called()

    def test_context_lock_rejects_missing_number_and_database_failure(self):
        controller, _ = self.track_library({"song.mp3": 210})
        with patch.object(controller.library_cache, "set_track_number_locked", side_effect=OSError("disk")):
            self.assertFalse(controller.change_track_number_lock("song.mp3", True).success)
        self.assertFalse(controller.get_track_info("song.mp3").is_track_locked)
        controller.get_track_info("song.mp3").metadata["track_number"] = ""
        self.assertFalse(controller.change_track_number_lock("song.mp3", True).success)

    def test_return_to_incoming_closes_gap_without_changing_moved_track(self):
        controller, metadata = self.track_library({"ten.mp3": 10, "eleven.mp3": 11})
        controller.close_gaps_on_move = True
        controller.aplicar_cambios_a_archivo("ten.mp3", {"track_number": "10"})
        controller.change_track_number_lock("ten.mp3", True)
        incoming_folder = Path(controller.carpeta, "incoming")
        incoming_folder.mkdir()
        incoming = MetadataController(library_cache=LibraryCache(incoming_folder / "cache.sqlite"))
        incoming.cargar_archivos_mp3(str(incoming_folder))
        from app.controllers.song_actions_controller import SongActions

        class App(InteractionWorkflowMixin):
            pass

        app = App()
        app.controller_principal = controller
        app.controller_nueva = incoming
        app.tree_principal = Mock()
        app.tree_principal.selection.return_value = ("0",)
        app.tree_principal.item.return_value = {"tags": ("ten.mp3",)}
        app.tree_nueva = Mock()
        app.preview = Mock()
        app.song_actions = SongActions()
        app.t = lambda key, **kwargs: key
        app._filename_from_tree_item = lambda item: item["tags"][0]
        app._handle_action_result = Mock()
        app._select_filename_in_tree = Mock()
        app._load_song_preview = Mock()
        app._move_to_incoming()
        self.assertFalse(Path(controller.carpeta, "ten.mp3").exists())
        self.assertTrue((incoming_folder / "ten.mp3").exists())
        self.assertEqual(controller.archivos, ["eleven.mp3"])
        self.assertEqual(metadata["eleven.mp3"]["track_number"], "10")
        self.assertEqual(incoming.get_track_info("ten.mp3").metadata["track_number"], "10")
        self.assertTrue(incoming.get_track_info("ten.mp3").is_manually_set)
        self.assertTrue(incoming.get_track_info("ten.mp3").is_track_locked)

    def test_gap_closure_skips_explicit_locks_and_stops_at_existing_gap(self):
        controller, metadata = self.track_library(
            {"eleven.mp3": 11, "locked.mp3": 12, "thirteen.mp3": 13, "far.mp3": 718}
        )
        controller.change_track_number_lock("locked.mp3", True)
        result = controller.close_track_number_gap(10)
        self.assertTrue(result.success)
        self.assertEqual(metadata["eleven.mp3"]["track_number"], "10")
        self.assertEqual(metadata["locked.mp3"]["track_number"], "12")
        self.assertEqual(metadata["thirteen.mp3"]["track_number"], "11")
        self.assertEqual(metadata["far.mp3"]["track_number"], "718")
        self.assertFalse(controller.get_track_info("thirteen.mp3").is_manually_set)

    def test_gap_closure_does_not_treat_legacy_manual_flags_as_locks(self):
        controller, metadata = self.track_library({"ten.mp3": 10, "eleven.mp3": 11})
        for filename in controller.archivos:
            controller.set_track_number_manual(filename, True)
        controller.cargar_archivos_mp3(controller.carpeta)
        self.assertTrue(controller.close_track_number_gap(9).success)
        self.assertEqual(metadata["ten.mp3"]["track_number"], "9")
        self.assertEqual(metadata["eleven.mp3"]["track_number"], "10")

    def test_delete_from_main_closes_gap_but_secondary_does_not(self):
        from app.services.file_service import delete_song

        for main in (True, False):
            with self.subTest(main=main):
                controller, metadata = self.track_library({"nine.mp3": 9, "ten.mp3": 10})
                controller.close_gaps_on_move = main
                result = delete_song(controller, "nine.mp3", move_to_trash=False)
                self.assertTrue(result.success)
                self.assertFalse(Path(controller.carpeta, "nine.mp3").exists())
                self.assertEqual(metadata["ten.mp3"]["track_number"], "9" if main else "10")

    def test_delete_reports_partial_numbering_failure_after_successful_removal(self):
        from app.services.file_service import delete_song

        controller, _ = self.track_library({"nine.mp3": 9, "ten.mp3": 10})
        controller.close_gaps_on_move = True
        controller.metadata_editor.aplicar_metadatos_en_lote = Mock(return_value=(0, ["read-only"]))
        result = delete_song(controller, "nine.mp3", move_to_trash=False)
        self.assertTrue(result.success)
        self.assertEqual(result.errors, ["read-only"])
        self.assertNotIn("nine.mp3", controller.archivos)

    def test_gap_closure_stops_on_write_failure(self):
        controller, metadata = self.track_library({"eleven.mp3": 11, "twelve.mp3": 12})
        controller.metadata_editor.aplicar_metadatos_en_lote = Mock(return_value=(0, ["read-only"]))
        result = controller.close_track_number_gap(10)
        self.assertFalse(result.success)
        self.assertEqual(result.errors, ["read-only"])
        self.assertEqual(metadata["eleven.mp3"]["track_number"], "11")
        self.assertEqual(controller.metadata_editor.aplicar_metadatos_en_lote.call_count, 1)

    def test_reinserting_same_track_number_shifts_unlocked_collision(self):
        controller, metadata = self.track_library({"returned.mp3": 10, "neighbor.mp3": 10, "next.mp3": 11})
        result = controller.aplicar_cambios_a_archivo("returned.mp3", {"track_number": "10"})
        self.assertTrue(result.success)
        self.assertEqual(metadata["returned.mp3"]["track_number"], "10")
        self.assertEqual(metadata["neighbor.mp3"]["track_number"], "11")
        self.assertEqual(metadata["next.mp3"]["track_number"], "12")

    def test_load_does_not_cache_a_file_changed_during_batch_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            first = folder / "a.mp3"
            first.write_bytes(b"original")
            (folder / "b.mp3").write_bytes(b"original")
            controller = MetadataController(library_cache=LibraryCache(folder / "cache.sqlite"))

            def scan(filepath):
                if Path(filepath).name == "b.mp3":
                    first.write_bytes(b"edited while b scans")
                return TrackScanResult(Path(filepath).name, str(filepath), {"title": "Old"}, 1.0, {})

            with patch("app.controllers.metadata_controller.scan_track", side_effect=scan):
                controller.cargar_archivos_mp3(str(folder))
            self.assertIsNone(controller.library_cache.get_valid_track(first))
            self.assertIsNotNone(controller.library_cache.get_valid_track(folder / "b.mp3"))

    def test_cached_folder_load_uses_one_database_connection(self):
        controller, _metadata = self.track_library({f"{index}.mp3": index for index in range(20)})
        cache = controller.library_cache
        with patch.object(cache, "_connection", wraps=cache._connection) as connections:
            controller.refresh_library()
        self.assertEqual(controller.load_metrics_snapshot()["cache_hits"], 20)
        self.assertEqual(connections.call_count, 1)

    def test_numbering_skips_unchanged_files(self):
        controller, _metadata = self.track_library({"a.mp3": 0, "b.mp3": 1, "c.mp3": 2})
        editor = controller.metadata_editor.aplicar_metadatos_en_lote
        self.assertTrue(controller.apply_track_numbers_from_order().success)
        editor.assert_not_called()
        controller.reorder_files(["b.mp3", "a.mp3", "c.mp3"])
        self.assertTrue(controller.apply_track_numbers_from_order().success)
        self.assertEqual([Path(call.args[0][0]).name for call in editor.call_args_list], ["b.mp3", "a.mp3"])

    def test_edit_track_210_moves_row_between_209_and_211_with_real_id3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)

            def write_track(path, number):
                tag = eyed3.id3.Tag()
                tag.track_num = (number, 0)
                tag.save(str(path), version=eyed3.id3.ID3_V2_3)

            for name, number in {"before.mp3": 209, "after.mp3": 211, "wrong_way.mp3": 847}.items():
                path = folder / name
                path.write_bytes(b"")
                write_track(path, number)

            def write_metadata(paths, metadata, _cover=None):
                for path in paths:
                    write_track(path, int(metadata["track_number"]))
                return len(paths), []

            # Keep real ID3 serialization; only the absent MPEG audio frames are stubbed.
            with patch(
                "app.services.track_scan_service.mutagen.File",
                side_effect=lambda path, easy=False: EasyID3(path) if easy else None,
            ):
                controller = MetadataController(library_cache=LibraryCache(folder / "cache.sqlite"))
                controller.cargar_archivos_mp3(str(folder))
                controller.metadata_editor.aplicar_metadatos_en_lote = Mock(side_effect=write_metadata)
                result = controller.aplicar_cambios_a_archivo("wrong_way.mp3", {"track_number": "210"})
                self.assertTrue(result.success)
                self.assertEqual(controller.get_sorted_files(), ["before.mp3", "wrong_way.mp3", "after.mp3"])
                self.assertEqual(controller.get_track_info("wrong_way.mp3").metadata["track_number"], "210")
                controller.refresh_library()
                self.assertEqual(controller.get_sorted_files(), ["before.mp3", "wrong_way.mp3", "after.mp3"])

    def track_library(self, numbers):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        metadata = {name: {"track_number": str(number)} for name, number in numbers.items()}
        for name in numbers:
            (folder / name).write_bytes(b"audio")

        def scan(filepath):
            return TrackScanResult(
                filename=Path(filepath).name,
                filepath=str(filepath),
                metadata=dict(metadata[Path(filepath).name]),
                duration=0.0,
                audio_quality={},
                has_cover_art=False,
            )

        scanner = patch("app.controllers.metadata_controller.scan_track", side_effect=scan)
        scanner.start()
        self.addCleanup(scanner.stop)
        controller = MetadataController(library_cache=LibraryCache(folder / "cache.sqlite"))
        controller.cargar_archivos_mp3(str(folder))

        def write(paths, values, portada_path=None):
            for path in paths:
                metadata[Path(path).name].update(values)
            return len(paths), []

        controller.metadata_editor.aplicar_metadatos_en_lote = Mock(side_effect=write)
        return controller, metadata

    def test_manual_number_survives_reorder_and_reload(self):
        controller, metadata = self.track_library({"near.mp3": 0, "kites.mp3": 1})
        self.assertTrue(controller.aplicar_cambios_a_archivo("near.mp3", {"track_number": "302"}).success)
        controller.refresh_library()
        controller.reorder_files(["kites.mp3", "near.mp3"])
        controller.apply_track_numbers_from_order()
        self.assertEqual(metadata["near.mp3"]["track_number"], "302")
        self.assertTrue(controller.get_track_info("near.mp3").is_manually_set)
        reloaded = MetadataController(library_cache=LibraryCache(controller.library_cache.db_path))
        reloaded.cargar_archivos_mp3(controller.carpeta)
        self.assertTrue(reloaded.get_track_info("near.mp3").is_manually_set)

    def test_edit_stops_shifting_at_gap(self):
        controller, metadata = self.track_library({"new.mp3": 9, "one.mp3": 1, "far.mp3": 8})
        result = controller.aplicar_cambios_a_archivo("new.mp3", {"track_number": "1"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["shifted_filenames"], ["one.mp3"])
        self.assertEqual(metadata["one.mp3"]["track_number"], "2")
        self.assertEqual(metadata["far.mp3"]["track_number"], "8")

    def test_shift_skips_locked_number(self):
        controller, metadata = self.track_library({"new.mp3": 9, "one.mp3": 1, "locked.mp3": 2, "far.mp3": 8})
        controller.aplicar_cambios_a_archivo("locked.mp3", {"track_number": "2"})
        result = controller.aplicar_cambios_a_archivo("new.mp3", {"track_number": "1"})
        self.assertTrue(result.success)
        self.assertEqual(metadata["locked.mp3"]["track_number"], "2")
        self.assertEqual(metadata["one.mp3"]["track_number"], "3")
        self.assertEqual(metadata["far.mp3"]["track_number"], "8")

    def test_global_reorder_reserves_manual_numbers(self):
        controller, metadata = self.track_library({"a.mp3": 0, "locked.mp3": 1, "b.mp3": 5})
        controller.aplicar_cambios_a_archivo("locked.mp3", {"track_number": "1"})
        controller.reorder_files(["a.mp3", "b.mp3", "locked.mp3"])
        controller.apply_track_numbers_from_order()
        self.assertEqual(metadata["locked.mp3"]["track_number"], "1")
        self.assertEqual(metadata["b.mp3"]["track_number"], "2")

    def test_move_modal_assigns_exact_number_without_global_reorder(self):
        controller, metadata = self.track_library({"near.mp3": 0, "kites.mp3": 1})
        controller.aplicar_cambios_a_archivo("near.mp3", {"track_number": "302"})
        app = Mock()
        app.controller_principal = controller
        with patch("app.ui.interaction_workflow.request_track_position", return_value=718):
            InteractionWorkflowMixin._position_moved_song_in_main(app, "kites.mp3")
        self.assertEqual(metadata["near.mp3"]["track_number"], "302")
        self.assertEqual(metadata["kites.mp3"]["track_number"], "718")
        self.assertTrue(controller.get_track_info("kites.mp3").is_manually_set)

    def test_rename_preserves_lock(self):
        controller, metadata = self.track_library({"old.mp3": 302})
        controller.aplicar_cambios_a_archivo("old.mp3", {"track_number": "302"})
        Path(controller.carpeta, "old.mp3").rename(Path(controller.carpeta, "new.mp3"))
        metadata["new.mp3"] = metadata.pop("old.mp3")
        controller.rename_file("old.mp3", "new.mp3")
        controller.apply_track_numbers_from_order()
        self.assertEqual(metadata["new.mp3"]["track_number"], "302")

    def test_move_preserves_lock(self):
        from app.services.file_service import move_song_between_libraries

        controller, metadata = self.track_library({"song.mp3": 302})
        controller.aplicar_cambios_a_archivo("song.mp3", {"track_number": "302"})
        destination = Path(controller.carpeta, "destination")
        destination.mkdir()
        other = MetadataController(library_cache=LibraryCache(destination / "cache.sqlite"))
        other.cargar_archivos_mp3(str(destination))
        other.metadata_editor = controller.metadata_editor
        self.assertTrue(move_song_between_libraries(controller, other, "song.mp3").success)
        other.apply_track_numbers_from_order()
        self.assertEqual(metadata["song.mp3"]["track_number"], "302")

    def test_bulk_explicit_number_is_locked(self):
        controller, metadata = self.track_library({"a.mp3": 0, "b.mp3": 1})
        count, errors = controller.aplicar_cambios_a_archivos(controller.archivos, {"track_number": "302"})
        self.assertEqual((count, errors), (2, []))
        controller.apply_track_numbers_from_order()
        self.assertEqual([value["track_number"] for value in metadata.values()], ["302", "302"])

    def test_failed_edit_does_not_lock_target(self):
        controller, _metadata = self.track_library({"song.mp3": 0})
        controller.metadata_editor.aplicar_metadatos_en_lote = Mock(return_value=(0, ["write failed"]))
        self.assertFalse(controller.aplicar_cambios_a_archivo("song.mp3", {"track_number": "302"}).success)
        self.assertFalse(controller.get_track_info("song.mp3").is_manually_set)

    def test_explicit_collision_preserves_both_manual_assignments(self):
        controller, metadata = self.track_library({"a.mp3": 302, "b.mp3": 0})
        controller.aplicar_cambios_a_archivo("a.mp3", {"track_number": "302"})
        controller.aplicar_cambios_a_archivo("b.mp3", {"track_number": "302"})
        controller.apply_track_numbers_from_order()
        self.assertEqual([value["track_number"] for value in metadata.values()], ["302", "302"])

    def test_loads_only_supported_audio_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "a.mp3").write_bytes(b"")
            (path / "b.wav").write_bytes(b"")
            (path / "notes.txt").write_text("ignore", encoding="utf-8")

            controller = MetadataController(library_cache=LibraryCache(path / "cache.sqlite"))
            files = controller.cargar_archivos_mp3(temp_dir)

            self.assertEqual(files, ["a.mp3", "b.wav"])
            metrics = controller.load_metrics_snapshot()
            self.assertEqual(metrics["file_count"], 2)
            self.assertIn("scan_seconds", metrics)
            self.assertIn("slowest_scans", metrics)

    def test_load_uses_track_scanner_for_precache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "a.mp3").write_bytes(b"")

            def fake_scan(filepath):
                return TrackScanResult(
                    filename=Path(filepath).name,
                    filepath=str(filepath),
                    metadata={"title": "Scanned", "artist": "Fast"},
                    duration=42.0,
                    audio_quality={"bitrate_kbps": 320},
                    has_cover_art=True,
                )

            controller = MetadataController(library_cache=LibraryCache(path / "cache.sqlite"))
            with patch("app.controllers.metadata_controller.scan_track", side_effect=fake_scan):
                controller.cargar_archivos_mp3(temp_dir)

            cached = controller.get_track_info("a.mp3")
            self.assertEqual(cached.metadata["title"], "Scanned")
            self.assertEqual(cached.duration, 42.0)
            self.assertEqual(cached.audio_quality["bitrate_kbps"], 320)
            self.assertTrue(controller._cover_cache["a.mp3"])

    def test_load_uses_persistent_cache_on_second_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            audio = path / "a.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(path / "cache.sqlite")

            first_result = TrackScanResult(
                filename="a.mp3",
                filepath=str(audio),
                metadata={"title": "Cached"},
                duration=9.0,
                audio_quality={"bitrate_kbps": 256},
                has_cover_art=False,
            )

            controller = MetadataController(library_cache=cache)
            with patch("app.controllers.metadata_controller.scan_track", return_value=first_result) as scanner:
                controller.cargar_archivos_mp3(temp_dir)
                self.assertEqual(scanner.call_count, 1)

            second_controller = MetadataController(library_cache=cache)
            with patch("app.controllers.metadata_controller.scan_track") as scanner:
                second_controller.cargar_archivos_mp3(temp_dir)
                scanner.assert_not_called()

            cached = second_controller.get_track_info("a.mp3")
            metrics = second_controller.load_metrics_snapshot()
            self.assertEqual(cached.metadata["title"], "Cached")
            self.assertEqual(metrics["cache_hits"], 1)
            self.assertEqual(metrics["cache_misses"], 0)

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

    def test_duplicate_filenames_reuses_cached_result_until_signature_changes(self):
        controller = MetadataController()
        controller.archivos = ["a.mp3", "b.mp3"]
        controller._metadata_cache = {
            "a.mp3": TrackInfo("a.mp3", "a.mp3", {"title": "Same", "artist": "One"}, 0.0, None),
            "b.mp3": TrackInfo("b.mp3", "b.mp3", {"title": "Same", "artist": "One"}, 0.0, None),
        }

        with patch(
            "app.controllers.metadata_controller.duplicate_filenames", return_value={"a.mp3", "b.mp3"}
        ) as duplicates:
            self.assertEqual(controller.duplicate_filenames(), {"a.mp3", "b.mp3"})
            self.assertEqual(controller.duplicate_filenames(), {"a.mp3", "b.mp3"})
            self.assertEqual(duplicates.call_count, 1)

            controller._metadata_cache["b.mp3"].metadata["title"] = "Other"
            self.assertEqual(controller.duplicate_filenames(), {"a.mp3", "b.mp3"})
            self.assertEqual(duplicates.call_count, 2)

    def test_issue_keys_cache_base_issues_and_keep_duplicates_dynamic(self):
        controller = MetadataController()
        controller.carpeta = "music"
        controller.archivos = ["song.mp3"]
        controller._metadata_cache = {
            "song.mp3": TrackInfo(
                "song.mp3",
                "music/song.mp3",
                {"title": "Song", "artist": "", "album": "", "year": "", "track_number": "0"},
                0.0,
                None,
            )
        }
        controller._cover_cache = {"song.mp3": True}

        first = controller.issue_keys_for_file("song.mp3", set())
        second = controller.issue_keys_for_file("song.mp3", {"song.mp3"})

        self.assertEqual(first, ["missing_artist", "missing_album", "missing_year"])
        self.assertEqual(second, ["missing_artist", "missing_album", "missing_year", "duplicate"])

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
