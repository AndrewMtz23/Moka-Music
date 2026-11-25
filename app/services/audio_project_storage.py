"""Versioned, atomic persistence for non-destructive audio editing sessions."""

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from ..models.audio_edit_project import (
    AudioEditClip,
    AudioEditEffect,
    AudioEditMarker,
    AudioEditProcessing,
    AudioEditProject,
    AudioEditTrack,
)


def save_editor_project(path, project, sources, *, document_path=None):
    path = Path(path)
    data = {"version": 1, "project": asdict(project), "sources": [str(Path(p).resolve()) for p in sources]}
    if document_path is not None:
        data["document_path"] = str(Path(document_path).resolve())
    for track in data["project"]["tracks"]:
        for clip in track["clips"]:
            clip["source_path"] = str(Path(clip["source_path"]).resolve())
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_editor_project(path):
    project, sources, _document = load_editor_session(path)
    return project, sources


def load_editor_session(path):
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _decode_project(data, path.parent)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid MokaMusic project: {exc}") from exc


def _decode_project(data, folder):
    def source_path(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Audio paths must be nonempty strings")
        candidate = Path(value)
        return candidate if candidate.is_absolute() else (folder / candidate).resolve()

    if not isinstance(data, dict) or type(data.get("version")) is not int:
        raise ValueError("Missing project version")
    if data["version"] != 1:
        raise ValueError("Unsupported editor project version")
    raw = data["project"]
    tracks = []
    for track in raw["tracks"]:
        clips = []
        for clip in track["clips"]:
            values = dict(clip)
            values["source_path"] = source_path(values["source_path"])
            values["processing"] = AudioEditProcessing(**values["processing"])
            values["effects"] = tuple(AudioEditEffect(**effect) for effect in values["effects"])
            clips.append(AudioEditClip(**values))
        if not isinstance(track.get("muted", False), bool) or not isinstance(track.get("solo", False), bool):
            raise ValueError("Track mute and solo must be boolean")
        tracks.append(AudioEditTrack(**{**track, "clips": tuple(clips)}))
    project = AudioEditProject(
        mode=raw["mode"], tracks=tuple(tracks), markers=tuple(AudioEditMarker(**marker) for marker in raw["markers"])
    )
    if project.mode == "sequence" and len(project.tracks) > 1:
        raise ValueError("Sequence projects must have at most one track")
    if not isinstance(data["sources"], list):
        raise ValueError("Sources must be a list")
    document = source_path(data["document_path"]) if data.get("document_path") is not None else None
    return project, [source_path(value) for value in data["sources"]], document
