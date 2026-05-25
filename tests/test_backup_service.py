import json
import tempfile
import unittest
from pathlib import Path

from app.services.backup_service import (
    build_track_backup,
    decode_cover_art,
    encode_cover_art,
    iter_backup_payloads,
    safe_backup_folder_name,
    write_metadata_backup,
)


class BackupServiceTests(unittest.TestCase):
    def test_cover_art_round_trip(self):
        encoded = encode_cover_art(b"cover")
        self.assertEqual(decode_cover_art(encoded), b"cover")

    def test_safe_backup_folder_name_replaces_special_chars(self):
        self.assertEqual(safe_backup_folder_name("DENNA LA PORRI!"), "DENNA_LA_PORRI_")

    def test_write_metadata_backup_writes_expected_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            track = build_track_backup(
                filename="a.mp3",
                filepath="/music/a.mp3",
                metadata={"title": "A"},
                cover_art=b"cover",
            )

            backup_path = write_metadata_backup(
                library_folder="/music",
                applied_metadata={"artist": "New"},
                tracks=[track],
                backup_dir=backup_dir,
            )
            payload = json.loads(backup_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["library_folder"], "/music")
            self.assertEqual(payload["applied_metadata"], {"artist": "New"})
            self.assertEqual(payload["track_count"], 1)
            self.assertEqual(payload["tracks"][0]["cover_art_b64"], encode_cover_art(b"cover"))

    def test_iter_backup_payloads_skips_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            (backup_dir / "bad.json").write_text("{", encoding="utf-8")
            good = backup_dir / "good.json"
            good.write_text(json.dumps({"tracks": []}), encoding="utf-8")

            payloads = iter_backup_payloads(backup_dir)

            self.assertEqual(len(payloads), 1)
            self.assertEqual(payloads[0][0], good)


if __name__ == "__main__":
    unittest.main()
