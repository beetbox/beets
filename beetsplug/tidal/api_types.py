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


class MediaAttributes(TypedDict):
    """Describe media metadata exposed by the TIDAL API.

    Combines the core values needed to identify and present a media item with
    optional publishing, attribution, and sharing details when TIDAL provides
    them.

    While this type is not part of the original TIDAL json:api schema itself, we
    introduced it to simplify our type definitions and allow for easier reuse of
    shared attributes.
    """

    duration: str  # ISO 8601
    title: str
    explicit: bool
    mediaTags: list[str]
    popularity: float

    accessType: NotRequired[Literal["PUBLIC", "UNLISTED", "PRIVATE"]]
    copyright: NotRequired[Copyright]
    createdAt: NotRequired[str]  # ISO 8601 datetime
    externalLinks: NotRequired[list[ExternalLink]]
    version: NotRequired[str]


class AlbumAttributes(MediaAttributes):
    """Represent album-specific metadata returned by the TIDAL API.

    Extends shared media fields with release packaging details that describe how
    an album is published and how many items or volumes it contains.
    """

    # see "Albums_Attributes"
    # in https://tidal-music.github.io/tidal-api-reference/tidal-api-oas.json

    # Required
    albumType: Literal["ALBUM", "EP", "SINGLE"]
    barcodeId: str
    numberOfItems: int
    numberOfVolumes: int

    # Optional
    releaseDate: NotRequired[str]  # ISO date YYYY-MM-DD


class TrackAttributes(MediaAttributes):
    """Represent track-specific metadata returned by the TIDAL API.

    Adds the musical and catalog information needed to describe an individual
    recording, while allowing enrichment fields when TIDAL includes them.
    """

    # see "Tracks_Attributes"
    # in https://tidal-music.github.io/tidal-api-reference/tidal-api-oas.json

    # Required
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

    # Optional
    bpm: NotRequired[float]
    spotlighted: NotRequired[bool]
    toneTags: NotRequired[list[str]]


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


class FileMeta(TypedDict):
    width: int
    height: int


class ArtworkFile(TypedDict):
    href: str
    meta: FileMeta


class ArtworkAttributes(TypedDict):
    mediaType: Literal["IMAGE"]
    files: list[ArtworkFile]
    visualMetadata: NotRequired[dict[str, str]]


class TidalArtwork(TypedDict):
    id: str
    type: Literal["artworks"]
    attributes: ArtworkAttributes


class TidalSearch(TypedDict):
    id: str
    type: Literal["searchResults"]
    attributes: SearchAttributes
    relationships: dict[str, RelationshipData]


T = TypeVar("T")


class Document(TypedDict, Generic[T]):
    data: T
    included: NotRequired[
        list[TidalArtist | TidalAlbum | TidalTrack | TidalArtwork]
    ]
    links: NotRequired[dict[str, str]]


AlbumDocument = Document[list[TidalAlbum]]
TrackDocument = Document[list[TidalTrack]]
SearchDocument = Document[TidalSearch]
