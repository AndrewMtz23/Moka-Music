import unittest
from unittest.mock import patch

from app.controllers.metadata_dialog_controller import METADATA_FIELDS, MetadataDialogController


def fake_t(key: str, **kwargs) -> str:
    return key


class MetadataDialogControllerTests(unittest.TestCase):
    def test_request_clear_uses_shared_metadata_fields(self):
        controller = MetadataDialogController(fake_t)
        song = {"title": "Track"}

        with patch("app.controllers.metadata_dialog_controller.request_clear_metadata") as request:
            request.return_value = {"title": ""}

            result = controller.request_clear("parent", song)

        self.assertEqual(result, {"title": ""})
        request.assert_called_once_with("parent", fake_t, METADATA_FIELDS, song)

    def test_request_edit_and_batch_use_shared_metadata_fields(self):
        controller = MetadataDialogController(fake_t)
        song = {"title": "Track"}

        with patch("app.controllers.metadata_dialog_controller.request_metadata_edit") as edit_request:
            edit_request.return_value = {"artist": "A"}
            edit = controller.request_edit(
                "parent",
                song,
                selected_count=3,
                is_batch_edit=True,
            )

        self.assertEqual(edit, {"artist": "A"})
        edit_request.assert_called_once_with(
            "parent",
            fake_t,
            METADATA_FIELDS,
            song,
            selected_count=3,
            is_batch_edit=True,
        )

        with patch("app.controllers.metadata_dialog_controller.request_batch_metadata") as batch_request:
            batch_request.return_value = {"album": "Album"}
            batch = controller.request_batch("parent", selected_count=2)

        self.assertEqual(batch, {"album": "Album"})
        batch_request.assert_called_once_with("parent", fake_t, METADATA_FIELDS, 2)


if __name__ == "__main__":
    unittest.main()
