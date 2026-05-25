import unittest

from app.controllers.cleanup_controller import CleanupController
from app.controllers.metadata_controller import MetadataController
from app.models import ActionResult, TrackInfo


class FakeSongInfo:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, path):
        self.invalidated.append(path)


class CleanupControllerTests(unittest.TestCase):
    def test_normalize_presets_keeps_only_known_actions(self):
        controller = CleanupController()

        presets = controller.normalize_presets(
            [
                {"name": "Mi preset", "actions": ["remove_feat", "unknown", "copy_artist"]},
                {"name": "", "actions": ["remove_feat"]},
                {"name": "Vacio", "actions": []},
            ]
        )

        self.assertEqual(presets, [{"name": "Mi preset", "actions": ["remove_feat", "copy_artist"]}])

    def test_build_plan_combines_actions_per_song(self):
        metadata_controller = MetadataController()
        metadata_controller.carpeta = "music"
        metadata_controller.archivos = ["song.mp3"]
        metadata_controller._metadata_cache = {
            "song.mp3": TrackInfo(
                "song.mp3",
                "music/song.mp3",
                {
                    "title": "Tema (Video Oficial) feat Otro",
                    "artist": "Cantante feat Invitado",
                    "album_artist": "",
                },
                0.0,
                None,
            )
        }
        cleanup = CleanupController()

        plan = cleanup.build_plan(
            [(metadata_controller, object(), ["song.mp3"])],
            ["remove_feat", "remove_parentheses", "copy_artist"],
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][3]["title"], "Tema")
        self.assertEqual(plan[0][3]["artist"], "Cantante")
        self.assertEqual(plan[0][3]["album_artist"], "Cantante")

    def test_action_label_backup_metadata_and_selected_count(self):
        cleanup = CleanupController()

        self.assertEqual(
            cleanup.action_label(["remove_feat", "copy_artist"], "", lambda key: key),
            "quick_actions.remove_feat + quick_actions.copy_artist",
        )
        self.assertEqual(cleanup.action_label(["remove_feat"], "Mi preset", lambda key: key), "Mi preset")
        self.assertEqual(cleanup.backup_metadata(["remove_feat"], "Quitar feat", ""), {"quick_action": "remove_feat"})
        self.assertEqual(
            cleanup.backup_metadata(["remove_feat", "copy_artist"], "Mi preset", "Mi preset"),
            {
                "quick_preset": "Mi preset",
                "quick_actions": ["remove_feat", "copy_artist"],
            },
        )
        self.assertEqual(
            cleanup.selected_count([(object(), object(), ["a.mp3", "b.mp3"]), (object(), object(), ["c.mp3"])]),
            3,
        )

    def test_preview_changes_and_groups_from_plan(self):
        metadata_controller = MetadataController()
        metadata_controller.carpeta = "music"
        metadata_controller.archivos = ["song.mp3"]
        metadata_controller._metadata_cache = {
            "song.mp3": TrackInfo("song.mp3", "music/song.mp3", {"title": "Old"}, 0.0, None)
        }
        tree = object()
        cleanup = CleanupController()
        plan = [(metadata_controller, tree, "song.mp3", {"title": "New"})]

        self.assertEqual(
            cleanup.preview_changes(plan, lambda field: field.title()),
            [("song.mp3", "Title", "Old", "New")],
        )
        self.assertEqual(cleanup.groups_from_plan(plan), [(metadata_controller, tree, ["song.mp3"])])

    def test_execute_plan_reports_changes_and_invalidates_cache(self):
        song_info = FakeSongInfo()
        cleanup = CleanupController(song_info)
        metadata_controller = MetadataController()
        metadata_controller.carpeta = "music"
        metadata_controller.archivos = ["song.mp3"]
        metadata_controller._metadata_cache = {
            "song.mp3": TrackInfo("song.mp3", "music/song.mp3", {"title": "Old"}, 0.0, None)
        }
        metadata_controller.aplicar_cambios_a_archivo = lambda _filename, _updates: ActionResult.ok("ok")
        tree = object()

        result = cleanup.execute_plan(
            [(metadata_controller, tree, "song.mp3", {"title": "New"})],
            preview_controller=metadata_controller,
            preview_filename="song.mp3",
        )

        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.errors, [])
        self.assertIn((id(metadata_controller), id(tree)), result.changed_pairs)
        self.assertTrue(result.affected_preview)
        self.assertEqual(result.changed_groups, [(metadata_controller, tree, ["song.mp3"])])
        self.assertEqual(song_info.invalidated, ["music\\song.mp3"])


if __name__ == "__main__":
    unittest.main()
