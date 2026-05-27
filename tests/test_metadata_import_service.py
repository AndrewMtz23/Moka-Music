import json
import tempfile
import unittest
from pathlib import Path

from app.services.metadata_import_service import (
    extract_metadata_import_items,
    filter_import_items_for_library,
    load_metadata_import_items,
)


class MetadataImportServiceTests(unittest.TestCase):
    def test_extracts_metadata_items_from_export_payload(self):
        items = extract_metadata_import_items(
            {
                "tracks": [
                    {
                        "filename": "song.mp3",
                        "path": "C:/Music/song.mp3",
                        "metadata": {"title": "Song", "artist": "Artist", "bad": "skip"},
                    }
                ]
            }
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].filename, "song.mp3")
        self.assertEqual(items[0].metadata, {"title": "Song", "artist": "Artist"})
        self.assertEqual(items[0].source_path, "C:/Music/song.mp3")

    def test_loads_metadata_items_from_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "metadata.json"
            path.write_text(
                json.dumps({"tracks": [{"filename": "song.mp3", "metadata": {"title": "Song"}}]}),
                encoding="utf-8",
            )

            items = load_metadata_import_items(path)

            self.assertEqual(items[0].filename, "song.mp3")

    def test_filters_items_for_active_library(self):
        items = extract_metadata_import_items(
            [
                {"filename": "keep.mp3", "metadata": {"title": "Keep"}},
                {"filename": "skip.mp3", "metadata": {"title": "Skip"}},
            ]
        )

        filtered = filter_import_items_for_library(items, ["keep.mp3"])

        self.assertEqual([item.filename for item in filtered], ["keep.mp3"])


if __name__ == "__main__":
    unittest.main()
