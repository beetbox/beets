from __future__ import annotations

from typing import Generic, Literal, TypedDict, TypeVar

from typing_extensions import NotRequired


class ResourceIdentifier(TypedDict):
    id: str
    type: str


class RelationshipLinks(TypedDict):
    self: NotRequired[str]
    next: NotRequired[str]


class RelationshipData(TypedDict):
    data: list[ResourceIdentifier]
    links: RelationshipLinks


class SingleRelationshipData(TypedDict):
    data: ResourceIdentifier
    links: NotRequired[RelationshipLinks]


class ExternalLink(TypedDict):
    href: str
    meta: str


class Copyright(TypedDict):
    text: str


class ArtistAttributes(TypedDict):
    name: str
    popularity: float  # 0.0 - 1.0, required
    handle: NotRequired[str]
    ownerType: NotRequired[Literal["LABEL", "USER", "MIXED"]]
    spotlighted: NotRequired[bool]


class AlbumAttributes(TypedDict):
    # see "Albums_Attributes"
    # in https://tidal-music.github.io/tidal-api-reference/tidal-api-oas.json

    # Required
    albumType: Literal["ALBUM", "EP", "SINGLE"]
    barcodeId: str
    duration: str  # ISO 8601
    explicit: bool
    mediaTags: list[str]
    numberOfItems: int
    numberOfVolumes: int
    popularity: float
    title: str

    # Optional
    accessType: NotRequired[Literal["PUBLIC", "UNLISTED", "PRIVATE"]]
    copyright: NotRequired[Copyright]
    createdAt: NotRequired[str]  # ISO 8601 datetime
    externalLinks: NotRequired[list[ExternalLink]]
    releaseDate: NotRequired[str]  # ISO date YYYY-MM-DD
    version: NotRequired[str]


class TrackAttributes(TypedDict):
    # see "Tracks_Attributes"
    # in https://tidal-music.github.io/tidal-api-reference/tidal-api-oas.json

    # Required
    title: str
    duration: str  # ISO 8601
    explicit: bool
    isrc: str
    key: Literal[
        "UNKNOWN",
        "C",
        "CSharp",
        "D",
        "Eb",
        "E",
        "F",
        "FSharp",
        "G",
        "Ab",
        "A",
        "Bb",
        "B",
    ]
    keyScale: Literal[
        "UNKNOWN",
        "MAJOR",
        "MINOR",
        "AEOLIAN",
        "BLUES",
        "DORIAN",
        "HARMONIC_MINOR",
        "LOCRIAN",
        "LYDIAN",
        "MIXOLYDIAN",
        "PENTATONIC_MAJOR",
        "PHRYGIAN",
        "MELODIC_MINOR",
        "PENTATONIC_MINOR",
    ]
    mediaTags: list[str]
    popularity: float

    # Optional
    accessType: NotRequired[Literal["PUBLIC", "UNLISTED", "PRIVATE"]]
    bpm: NotRequired[float]
    copyright: NotRequired[Copyright]
    createdAt: NotRequired[str]  # ISO 8601 datetime
    externalLinks: NotRequired[list[ExternalLink]]
    spotlighted: NotRequired[bool]
    toneTags: NotRequired[list[str]]
    version: NotRequired[str]


class SearchAttributes(TypedDict):
    didYouMean: NotRequired[str]
    trackingId: str


class TidalArtist(TypedDict):
    id: str
    type: Literal["artists"]
    attributes: ArtistAttributes


class TidalAlbum(TypedDict):
    id: str
    type: Literal["albums"]
    attributes: AlbumAttributes
    relationships: dict[str, RelationshipData]


class TidalTrack(TypedDict):
    id: str
    type: Literal["tracks"]
    attributes: TrackAttributes
    relationships: dict[str, RelationshipData]


class TidalSearch(TypedDict):
    id: str
    type: Literal["searchResults"]
    attributes: SearchAttributes
    relationships: dict[str, RelationshipData]


T = TypeVar("T")


class Document(TypedDict, Generic[T]):
    data: T
    included: NotRequired[list[TidalArtist | TidalAlbum | TidalTrack]]
    links: NotRequired[dict[str, str]]


AlbumDocument = Document[list[TidalAlbum]]
TrackDocument = Document[list[TidalTrack]]
SearchDocument = Document[TidalSearch]
