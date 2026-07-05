from __future__ import annotations

from typing import TYPE_CHECKING, Literal

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


class AudioTrack(TypedDict):
    """Represent an audio item or logical segment in a Discogs tracklist.

    Discogs uses this shape both for independently addressable media tracks and
    for pieces rolled into one physical track. Position syntax and surrounding
    index structure determine which interpretation applies.
    """

    type_: Literal["track"]
    position: str
    title: str
    duration: str
    artists: NotRequired[list[Artist]]
    extraartists: NotRequired[list[Artist]]


class IndexTrack(TypedDict):
    """Represent a titled musical work containing related subtracks.

    The contained entries may be movements stored as separate physical tracks
    or logical divisions of one track. Their position syntax determines whether
    they remain separate or are coalesced under the work's metadata.
    """

    type_: Literal["index"]
    position: Literal[""]
    title: str
    duration: str
    sub_tracks: list[AudioTrack]
    artists: NotRequired[list[Artist]]
    extraartists: NotRequired[list[Artist]]


class HeadingTrack(TypedDict):
    """Represent descriptive tracklist structure rather than an audio item.

    A heading labels the following block but is not the title of a musical work.
    It must remain structural instead of being treated as an index container.
    """

    type_: Literal["heading"]
    position: Literal[""]
    title: str
    duration: str


Track = AudioTrack | IndexTrack | HeadingTrack


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
