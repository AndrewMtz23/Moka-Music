import json
import tempfile
import unittest
from pathlib import Path

from app.controllers.backup_controller import BackupController
from app.models import ActionResult, TrackInfo


def fake_t(key: str, **kwargs) -> str:
    if kwargs:
        args = ",".join(f"{name}={value}" for name, value in sorted(kwargs.items()))
        return f"{key}({args})"
    return key


class FakeSongInfo:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, path):
        self.invalidated.append(path)


class FakeMetadataController:
    def __init__(self, folder="music", files=None, restore_result=None, metadata=None):
        self.carpeta = folder
        self.archivos = files or ["a.mp3"]
        self.created_backups = []
        self.restore_result = restore_result or ActionResult.ok("restored")
        self.metadata = metadata or {}

    def crear_respaldo_metadatos(self, metadata, filenames):
        path = Path(f"{len(self.created_backups)}.json")
        self.created_backups.append((metadata, filenames, path))
        return path

    def restaurar_respaldo_metadatos(self, _backup_path):
        return self.restore_result

    def get_track_info(self, filename):
        return TrackInfo(filename, f"{self.carpeta}/{filename}", self.metadata.get(filename, {}), 0.0, None)


class BackupControllerTests(unittest.TestCase):
    def test_create_metadata_backups_tracks_last_paths(self):
        controller = BackupController(fake_t)
        metadata_controller = FakeMetadataController()

        result = controller.create_metadata_backups(
            [(metadata_controller, object(), ["a.mp3"])],
            {"artist": "New"},
        )

        self.assertEqual(result, Path("0.json"))
        self.assertEqual(controller.last_backup_path, Path("0.json"))
        self.assertEqual(controller.last_backup_paths, [Path("0.json")])
        self.assertEqual(metadata_controller.created_backups[0][0], {"artist": "New"})
        self.assertTrue(controller.has_recent_backup())
        self.assertEqual(controller.recent_backup_label(), "0.json")

    def test_metadata_changes_reports_only_changed_fields(self):
        controller = BackupController(fake_t)
        metadata_controller = FakeMetadataController(
            metadata={
                "a.mp3": {
                    "title": "Old",
                    "artist": "Same",
                }
            }
        )

        changes = controller.metadata_changes(
            [(metadata_controller, object(), ["a.mp3"])],
            {"title": "New", "artist": "Same"},
            lambda field: f"label:{field}",
        )

        self.assertEqual(changes, [("a.mp3", "label:title", "Old", "New")])

    def test_list_metadata_backups_formats_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / "backups"
            backup_dir.mkdir()
            backup_path = backup_dir / "one.json"
            backup_path.write_text(
                json.dumps(
                    {
                        "created_at": "2026-05-22T01:00:00",
                        "library_folder": "music",
                        "track_count": 2,
                        "applied_metadata": {"quick_action": "remove_feat"},
                    }
                ),
                encoding="utf-8",
            )
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)
                history = BackupController(fake_t).list_metadata_backups()
            finally:
                os.chdir(original_cwd)

        self.assertEqual(len(history), 1)
        self.assertEqual(Path(history[0]["path"]).name, backup_path.name)
        self.assertEqual(history[0]["action"], "quick_actions.remove_feat")

    def test_restore_paths_invalidates_and_reports_refreshed_pair(self):
        song_info = FakeSongInfo()
        controller = BackupController(fake_t, song_info)
        metadata_controller = FakeMetadataController(folder="music", files=["a.mp3"])
        tree = object()

        result = controller.restore_paths([Path("backup.json")], [(metadata_controller, tree)])

        self.assertTrue(result.restored)
        self.assertEqual(result.errors, [])
        self.assertIn((id(metadata_controller), id(tree)), result.refreshed_pairs)
        self.assertEqual(song_info.invalidated, ["music\\a.mp3"])


if __name__ == "__main__":
    unittest.main()
