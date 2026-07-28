import tempfile
import unittest
from pathlib import Path

from app.controllers.playlist_workflow_controller import PlaylistWorkflowController
from app.models import ActionResult, TrackInfo


class FakeSongInfo:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, path):
        self.invalidated.append(path)


class FakeController:
    def __init__(self, folder, files, metadata):
        self.carpeta = str(folder)
        self.archivos = list(files)
        self.metadata = {filename: dict(values) for filename, values in metadata.items()}
        self.backups = []

    def get_track_info(self, filename):
        return TrackInfo(
            filename,
            str(Path(self.carpeta) / filename),
            self.metadata.get(filename, {}),
            0.0,
            None,
        )

    def reorder_files(self, ordered_filenames):
        known_files = [filename for filename in ordered_filenames if filename in self.archivos]
        remaining_files = [filename for filename in self.archivos if filename not in known_files]
        self.archivos = known_files + remaining_files

    def aplicar_cambios_a_archivo(self, filename, metadata):
        if filename not in self.archivos:
            return ActionResult.fail("missing")
        self.metadata.setdefault(filename, {}).update(metadata)
        return ActionResult.ok("ok")

    def rename_file(self, old_name, new_name):
        index = self.archivos.index(old_name)
        self.archivos[index] = new_name
        self.metadata[new_name] = self.metadata.pop(old_name, {})

    def crear_respaldo_metadatos(self, metadata, filenames=None):
        self.backups.append((dict(metadata), list(filenames or [])))
        return Path(self.carpeta) / "backup.json"


class PlaylistWorkflowControllerTests(unittest.TestCase):
    def test_build_insert_plan_contains_positions_track_numbers_and_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = FakeController(
                temp_dir,
                ["a.mp3", "b.mp3", "c.mp3"],
                {
                    "a.mp3": {"artist": "A", "title": "One"},
                    "b.mp3": {"artist": "B", "title": "Two"},
                    "c.mp3": {"artist": "C", "title": "Three"},
                },
            )

            plan = PlaylistWorkflowController().build_insert_plan(
                controller=controller,
                tree="tree",
                filenames=["c.mp3"],
                position=1,
            )

            self.assertEqual(plan.original_order, ["a.mp3", "b.mp3", "c.mp3"])
            self.assertEqual(plan.final_order, ["c.mp3", "a.mp3", "b.mp3"])
            self.assertEqual(
                [
                    (item.old_name, item.old_position, item.new_position, item.track_number, item.new_name)
                    for item in plan.items
                ],
                [
                    ("c.mp3", 3, 1, 0, "000 - C - Three.mp3"),
                    ("a.mp3", 1, 2, 1, "001 - A - One.mp3"),
                    ("b.mp3", 2, 3, 2, "002 - B - Two.mp3"),
                ],
            )

    def test_execute_plan_updates_track_numbers_renames_and_records_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            for filename in ("a.mp3", "b.mp3", "c.mp3"):
                (folder / filename).write_bytes(b"audio")

            controller = FakeController(
                folder,
                ["a.mp3", "b.mp3", "c.mp3"],
                {
                    "a.mp3": {"artist": "A", "title": "One"},
                    "b.mp3": {"artist": "B", "title": "Two"},
                    "c.mp3": {"artist": "C", "title": "Three"},
                },
            )
            workflow = PlaylistWorkflowController()
            plan = workflow.build_insert_plan(
                controller=controller,
                tree="tree",
                filenames=["c.mp3"],
                position=1,
            )
            song_info = FakeSongInfo()

            result = workflow.execute_plan(
                plan,
                song_info=song_info,
                preview_controller=controller,
                preview_filename="c.mp3",
            )

            self.assertTrue(result.success)
            self.assertEqual(result.track_numbers_updated, 3)
            self.assertEqual(result.renamed, 3)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.preview_filename, "000 - C - Three.mp3")
            self.assertEqual(result.changed_pairs, {(id(controller), id("tree"))})
            self.assertEqual(result.backup_path, folder / "backup.json")
            self.assertEqual(controller.backups[0][1], ["a.mp3", "b.mp3", "c.mp3"])
            self.assertEqual(
                controller.archivos,
                ["000 - C - Three.mp3", "001 - A - One.mp3", "002 - B - Two.mp3"],
            )
            self.assertEqual(controller.metadata["000 - C - Three.mp3"]["track_number"], "0")
            self.assertEqual(controller.metadata["001 - A - One.mp3"]["track_number"], "1")
            self.assertEqual(controller.metadata["002 - B - Two.mp3"]["track_number"], "2")
            self.assertTrue((folder / "000 - C - Three.mp3").exists())
            self.assertTrue((folder / "001 - A - One.mp3").exists())
            self.assertTrue((folder / "002 - B - Two.mp3").exists())
            self.assertGreaterEqual(len(song_info.invalidated), 9)

    def test_action_result_wraps_success_and_errors(self):
        workflow = PlaylistWorkflowController()
        result = workflow.action_result(
            workflow.execute_plan(
                workflow.build_plan_from_order(
                    controller=FakeController("", [], {}),
                    tree="tree",
                    final_order=[],
                ),
                song_info=FakeSongInfo(),
                create_backup=False,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.message, "Playlist actualizada.")


if __name__ == "__main__":
    unittest.main()
