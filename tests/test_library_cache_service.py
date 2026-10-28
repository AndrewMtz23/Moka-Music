import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.library_cache_service import LibraryCache
from app.services.track_scan_service import TrackScanResult


class LibraryCacheServiceTests(unittest.TestCase):
    def test_folder_snapshot_does_not_silently_drop_manual_locks_on_database_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            database = folder / "cache.sqlite"
            database.write_text("not a database", encoding="utf-8")
            with self.assertRaises(sqlite3.DatabaseError):
                LibraryCache(database).get_folder_snapshot(folder)

    def test_batch_does_not_cache_metadata_for_a_file_changed_since_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            path = folder / "song.mp3"
            path.write_bytes(b"original")
            stats = path.stat()
            scan = TrackScanResult(path.name, str(path), {"title": "Old"}, 1.0, {})
            path.write_bytes(b"edited after scanning")
            cache = LibraryCache(folder / "cache.sqlite")
            cache.save_tracks([scan], expected_stats={str(path): (stats.st_size, stats.st_mtime)})
            self.assertIsNone(cache.get_valid_track(path))

    def test_folder_snapshot_validates_files_and_preserves_locks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            cache = LibraryCache(folder / "cache.sqlite")
            scans = []
            for name in ("valid.mp3", "changed.mp3", "gone.mp3"):
                path = folder / name
                path.write_bytes(b"audio")
                scans.append(TrackScanResult(name, str(path), {"track_number": "210"}, 1.0, {}))
            cache.save_tracks(scans)
            cache.set_track_number_manual(folder / "valid.mp3", True)
            (folder / "changed.mp3").write_bytes(b"changed audio")
            (folder / "gone.mp3").unlink()
            with patch.object(cache, "_connection", wraps=cache._connection) as connections:
                snapshot = cache.get_folder_snapshot(folder)
            self.assertEqual(set(snapshot.tracks), {"valid.mp3"})
            self.assertEqual(snapshot.manual_paths, {str((folder / "valid.mp3").resolve())})
            self.assertEqual(connections.call_count, 1)

    def test_save_tracks_uses_one_transaction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            cache = LibraryCache(folder / "cache.sqlite")
            cache._ensure_schema()
            scans = []
            for index in range(10):
                path = folder / f"{index}.mp3"
                path.write_bytes(b"audio")
                scans.append(TrackScanResult(path.name, str(path), {"track_number": str(index)}, 1.0, {}))
            with patch.object(cache, "_connection", wraps=cache._connection) as connections:
                cache.save_tracks(scans)
            self.assertEqual(connections.call_count, 1)
            self.assertEqual(len(cache.get_folder_snapshot(folder).tracks), 10)

    def test_old_scanner_cache_is_rescanned_without_losing_manual_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            with patch("app.services.library_cache_service.SCANNER_VERSION", 1):
                cache.save_track(TrackScanResult("song.mp3", str(audio), {"track_number": "210/00"}, 0.0, {}))
            cache.set_track_number_manual(audio, True)
            self.assertIsNone(cache.get_valid_track(audio))
            self.assertTrue(cache.is_track_number_manual(audio))

    def test_save_and_read_valid_track(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            result = TrackScanResult(
                filename="song.mp3",
                filepath=str(audio),
                metadata={"title": "Song", "artist": "Artist"},
                duration=12.5,
                audio_quality={"bitrate_kbps": 320},
                has_cover_art=True,
            )

            cache.save_track(result)
            cached = cache.get_valid_track(audio)

        self.assertIsNotNone(cached)
        self.assertEqual(cached.metadata["title"], "Song")
        self.assertEqual(cached.duration, 12.5)
        self.assertEqual(cached.audio_quality["bitrate_kbps"], 320)
        self.assertTrue(cached.has_cover_art)

    def test_cache_miss_when_file_size_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            cache.save_track(
                TrackScanResult(
                    filename="song.mp3",
                    filepath=str(audio),
                    metadata={"title": "Song"},
                    duration=1.0,
                    audio_quality={},
                )
            )

            audio.write_bytes(b"audio changed")

            self.assertIsNone(cache.get_valid_track(audio))

    def test_invalidate_path_removes_track(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            cache = LibraryCache(root / "cache.sqlite")
            cache.save_track(
                TrackScanResult(
                    filename="song.mp3",
                    filepath=str(audio),
                    metadata={"title": "Song"},
                    duration=1.0,
                    audio_quality={},
                )
            )

            cache.invalidate_path(audio)

            self.assertIsNone(cache.get_valid_track(audio))

    def test_corrupt_database_falls_back_to_cache_miss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            db_path = root / "cache.sqlite"
            db_path.write_text("not sqlite", encoding="utf-8")

            self.assertIsNone(LibraryCache(db_path).get_valid_track(audio))


if __name__ == "__main__":
    unittest.main()
