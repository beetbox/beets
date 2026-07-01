from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from beets.autotag import TrackInfo


class ReleaseFormat(TypedDict):
    name: str
    qty: int
    descriptions: list[str] | None


class Artist(TypedDict):
    name: str
    anv: str
    join: str
    role: str
    tracks: str
    id: str
    resource_url: str


class Track(TypedDict):
    position: str
    type_: str
    title: str
    duration: str
    artists: list[Artist]
    extraartists: NotRequired[list[Artist]]
    sub_tracks: NotRequired[list[Track]]


class ArtistInfo(TypedDict):
    artist: str
    artists: list[str]
    artist_credit: str
    artists_credit: list[str]
    artist_id: str
    artists_ids: list[str]
    arrangers: list[str] | None
    composers: list[str] | None
    remixers: list[str] | None
    lyricists: list[str] | None


class TracklistInfo(TypedDict):
    index: int
    index_tracks: dict[int, str]
    tracks: list[TrackInfo]
    divisions: list[str]
    next_divisions: list[str]
    mediums: list[str | None]
    medium_indices: list[str | None]
