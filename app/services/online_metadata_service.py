from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MUSICBRAINZ_SEARCH_URL = "https://musicbrainz.org/ws/2/recording/"
USER_AGENT = "MokaMusic/2.1.0 (local metadata editor)"


@dataclass(frozen=True)
class OnlineMetadataResult:
    title: str
    artist: str
    album: str = ""
    year: str = ""
    genre: str = ""
    score: int = 0
    source: str = "MusicBrainz"

    def metadata(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "title": self.title,
                "artist": self.artist,
                "album": self.album,
                "year": self.year,
                "genre": self.genre,
            }.items()
            if value
        }


class MusicBrainzClient:
    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout

    def search(self, metadata: dict[str, str], *, limit: int = 8) -> list[OnlineMetadataResult]:
        title = str(metadata.get("title", "") or "").strip()
        artist = str(metadata.get("artist", "") or "").strip()
        if not title and not artist:
            return []

        query = self._query(title=title, artist=artist)
        params = urlencode({"query": query, "fmt": "json", "limit": max(1, min(limit, 25))})
        request = Request(
            f"{MUSICBRAINZ_SEARCH_URL}?{params}",
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return parse_musicbrainz_recordings(payload)

    def _query(self, *, title: str, artist: str) -> str:
        parts: list[str] = []
        if title:
            parts.append(f'recording:"{_escape_query(title)}"')
        if artist:
            parts.append(f'artist:"{_escape_query(artist)}"')
        return " AND ".join(parts) if parts else title or artist


def parse_musicbrainz_recordings(payload: dict[str, Any]) -> list[OnlineMetadataResult]:
    results: list[OnlineMetadataResult] = []
    for recording in payload.get("recordings", []) or []:
        if not isinstance(recording, dict):
            continue
        title = str(recording.get("title", "") or "").strip()
        artist = _artist_credit_name(recording.get("artist-credit", []))
        release = _first_release(recording.get("releases", []))
        album = str(release.get("title", "") or "").strip()
        year = _year_from_date(str(release.get("date", "") or recording.get("first-release-date", "") or ""))
        genre = _first_tag_name(recording.get("tags", []) or release.get("tags", []))
        if not title and not artist:
            continue
        results.append(
            OnlineMetadataResult(
                title=title,
                artist=artist,
                album=album,
                year=year,
                genre=genre,
                score=_coerce_score(recording.get("score", 0)),
            )
        )
    return results


def _artist_credit_name(artist_credit) -> str:
    names: list[str] = []
    for credit in artist_credit or []:
        if not isinstance(credit, dict):
            continue
        artist = credit.get("artist", {})
        if isinstance(artist, dict):
            name = str(artist.get("name", "") or "").strip()
            if name:
                names.append(name)
    return ", ".join(names)


def _first_release(releases) -> dict[str, Any]:
    for release in releases or []:
        if isinstance(release, dict):
            return release
    return {}


def _year_from_date(value: str) -> str:
    match = re.match(r"^(\d{4})", value)
    return match.group(1) if match else ""


def _first_tag_name(tags) -> str:
    for tag in sorted((tag for tag in tags or [] if isinstance(tag, dict)), key=lambda item: item.get("count", 0), reverse=True):
        name = str(tag.get("name", "") or "").strip()
        if name:
            return name
    return ""


def _coerce_score(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _escape_query(value: str) -> str:
    return str(value).replace('"', '\\"')
