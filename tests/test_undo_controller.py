import unittest
from pathlib import Path

from app.controllers.undo_controller import UndoController


class UndoControllerTests(unittest.TestCase):
    def test_record_tracks_undo_and_clears_redo(self):
        controller = UndoController(limit=2)
        controller.record("one", [Path("one.json")])
        action = controller.pop_undo()
        self.assertEqual(action.label, "one")
        controller.push_redo(action)

        controller.record("two", [Path("two.json")])

        self.assertTrue(controller.can_undo())
        self.assertFalse(controller.can_redo())
        self.assertEqual(controller.undo_label(), "two")

    def test_limit_keeps_recent_actions(self):
        controller = UndoController(limit=2)

        controller.record("one", [Path("one.json")])
        controller.record("two", [Path("two.json")])
        controller.record("three", [Path("three.json")])

        self.assertEqual([action.label for action in controller.undo_stack], ["two", "three"])


if __name__ == "__main__":
    unittest.main()
