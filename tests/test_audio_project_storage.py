import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models.audio_edit_project import AudioEditClip, AudioEditEffect, AudioEditProject, AudioEditTrack
from app.services.audio_project_storage import load_editor_project, save_editor_project


class ProjectStorageTests(unittest.TestCase):
    def test_empty_project_is_distinct_from_missing_save(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "project.json"
            project = AudioEditProject()
            save_editor_project(path, project, [])
            self.assertEqual(load_editor_project(path), (project, []))

    def test_round_trip_preserves_mix_and_effects_without_audio_files(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "project.json"
            source = Path(folder) / "missing.wav"
            clip = AudioEditClip(source, 1, 4, timeline_start=5, gain_db=-3, effects=(AudioEditEffect("delay"),))
            project = AudioEditProject(mode="multitrack", tracks=(AudioEditTrack("a", "Track", (clip,), muted=True),))
            save_editor_project(path, project, [source])
            self.assertEqual(load_editor_project(path), (project, [source]))

    def test_relative_sources_resolve_against_project_folder(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "project.json"
            save_editor_project(path, AudioEditProject(), [])
            data = json.loads(path.read_text())
            data["sources"] = ["audio/song.wav"]
            path.write_text(json.dumps(data))
            self.assertEqual(load_editor_project(path)[1], [(Path(folder) / "audio/song.wav").resolve()])

    def test_malformed_documents_raise_value_error(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "project.json"
            for content in ("[]", "null", "{}", '{"version":true}', '{"version":99}', '{"version":1,"project":null}'):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    load_editor_project(path)
