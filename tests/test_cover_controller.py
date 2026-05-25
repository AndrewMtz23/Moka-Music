import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.controllers.cover_controller import CoverController


class FakeSongInfo:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, path):
        self.invalidated.append(path)


class FakeController:
    def __init__(self, folder, *, fail=False):
        self.carpeta = str(folder)
        self.fail = fail
        self.applied = []

    def aplicar_cambios_a_archivos(self, filenames, metadata, cover_path):
        self.applied.append((filenames, metadata, cover_path))
        if self.fail:
            return 0, [f"{filenames[0]}: error"]
        return len(filenames), []


class CoverControllerTests(unittest.TestCase):
    def test_cover_targets_prefers_explicit_selection(self):
        controller = CoverController()
        selected = [("controller", "tree", ["one.mp3"])]

        targets = controller.cover_targets(
            selections=selected,
            preview_controller="preview",
            preview_filename="preview.mp3",
            tree_for_controller=lambda _controller: "preview_tree",
        )

        self.assertEqual(targets, selected)

    def test_cover_targets_falls_back_to_preview_song(self):
        controller = CoverController()

        targets = controller.cover_targets(
            selections=[],
            preview_controller="preview",
            preview_filename="preview.mp3",
            tree_for_controller=lambda _controller: "preview_tree",
        )

        self.assertEqual(targets, [("preview", "preview_tree", ["preview.mp3"])])

    def test_build_auto_cover_plan_groups_by_found_cover(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            Image.new("RGB", (20, 20), color="red").save(folder / "cover.jpg")
            controller = FakeController(folder)

            plan = CoverController().build_auto_cover_plan(
                [(controller, "tree", ["one.mp3", "two.mp3"])]
            )

            self.assertEqual(plan.planned_count, 2)
            self.assertEqual(plan.missing, [])
            self.assertEqual(plan.groups[0][0], controller)
            self.assertEqual(plan.groups[0][1], "tree")
            self.assertEqual(plan.groups[0][2], ["one.mp3", "two.mp3"])
            self.assertEqual(plan.groups[0][3], str(folder / "cover.jpg"))

    def test_apply_manual_cover_tracks_success_cache_and_preview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            controller = FakeController(folder)
            song_info = FakeSongInfo()

            result = CoverController().apply_manual_cover(
                targets=[(controller, "tree", ["one.mp3", "two.mp3"])],
                cover_path="cover.jpg",
                song_info=song_info,
                preview_controller=controller,
                preview_filename="two.mp3",
            )

            self.assertEqual(result.success_count, 2)
            self.assertEqual(result.errors, [])
            self.assertTrue(result.affected_preview)
            self.assertEqual(result.preview_cover_path, "cover.jpg")
            self.assertEqual(result.changed_pairs, {(id(controller), id("tree"))})
            self.assertEqual(
                song_info.invalidated,
                [str(folder / "one.mp3"), str(folder / "two.mp3")],
            )


if __name__ == "__main__":
    unittest.main()
