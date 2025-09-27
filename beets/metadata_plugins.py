"""Metadata source plugin interface.

This allows beets to lookup metadata from various sources. We define
a common interface for all metadata sources which need to be
implemented as plugins.
"""

from __future__ import annotations

import abc
import re
import warnings
from typing import TYPE_CHECKING, Generic, Literal, Sequence, TypedDict, TypeVar

import unidecode
from typing_extensions import NotRequired

from beets.util import cached_classproperty
from beets.util.id_extractors import extract_release_id

from .plugins import BeetsPlugin, find_plugins, notify_info_yielded, send

if TYPE_CHECKING:
    from collections.abc import Iterable

    from confuse import ConfigView

    from .autotag import Distance
    from .autotag.hooks import AlbumInfo, Item, TrackInfo


def find_metadata_source_plugins() -> list[MetadataSourcePlugin]:
    """Returns a list of MetadataSourcePlugin subclass instances

    Resolved from all currently loaded beets plugins.
    """

    all_plugins = find_plugins()
    metadata_plugins: list[MetadataSourcePlugin | BeetsPlugin] = []
    for plugin in all_plugins:
        if isinstance(plugin, MetadataSourcePlugin):
            metadata_plugins.append(plugin)
        elif hasattr(plugin, "data_source"):
            # TODO: Remove this in the future major release, v3.0.0
            warnings.warn(
                f"{plugin.__class__.__name__} is used as a legacy metadata source. "
                "It should extend MetadataSourcePlugin instead of BeetsPlugin. "
                "Support for this will be removed in the v3.0.0 release!",
                DeprecationWarning,
                stacklevel=2,
            )
            metadata_plugins.append(plugin)

    # typeignore: BeetsPlugin is not a MetadataSourcePlugin (legacy support)
    return metadata_plugins  # type: ignore[return-value]


@notify_info_yielded("albuminfo_received")
def candidates(*args, **kwargs) -> Iterable[AlbumInfo]:
    """Return matching album candidates from all metadata source plugins."""
    for plugin in find_metadata_source_plugins():
        yield from plugin.candidates(*args, **kwargs)


@notify_info_yielded("trackinfo_received")
def item_candidates(*args, **kwargs) -> Iterable[TrackInfo]:
    """Return matching track candidates fromm all metadata source plugins."""
    for plugin in find_metadata_source_plugins():
        yield from plugin.item_candidates(*args, **kwargs)


def album_for_id(_id: str) -> AlbumInfo | None:
    """Get AlbumInfo object for the given ID string.

    A single ID can yield just a single album, so we return the first match.
    """
    for plugin in find_metadata_source_plugins():
        if info := plugin.album_for_id(album_id=_id):
            send("albuminfo_received", info=info)
            return info

    return None


def track_for_id(_id: str) -> TrackInfo | None:
    """Get TrackInfo object for the given ID string.

    A single ID can yield just a single track, so we return the first match.
    """
    for plugin in find_metadata_source_plugins():
        if info := plugin.track_for_id(_id):
            send("trackinfo_received", info=info)
            return info

    return None


def track_distance(item: Item, info: TrackInfo) -> Distance:
    """Returns the track distance for an item and trackinfo.

    Returns a Distance object is populated by all metadata source plugins
    that implement the :py:meth:`MetadataSourcePlugin.track_distance` method.
    """
    from beets.autotag.distance import Distance

    dist = Distance()
    for plugin in find_metadata_source_plugins():
        dist.update(plugin.track_distance(item, info))
    return dist


def album_distance(
    items: Sequence[Item],
    album_info: AlbumInfo,
    mapping: dict[Item, TrackInfo],
) -> Distance:
    """Returns the album distance calculated by plugins."""
    from beets.autotag.distance import Distance

    dist = Distance()
    for plugin in find_metadata_source_plugins():
        dist.update(plugin.album_distance(items, album_info, mapping))
    return dist


def _get_distance(
    config: ConfigView, data_source: str, info: AlbumInfo | TrackInfo
) -> Distance:
    """Returns the ``data_source`` weight and the maximum source weight
    for albums or individual tracks.
    """
    from beets.autotag.distance import Distance

    dist = Distance()
    if info.data_source == data_source:
        dist.add("source", config["source_weight"].as_number())
    return dist


class MetadataSourcePlugin(BeetsPlugin, metaclass=abc.ABCMeta):
    """A plugin that provides metadata from a specific source.

    This base class implements a contract for plugins that provide metadata
    from a specific source. The plugin must implement the methods to search for albums
    and tracks, and to retrieve album and track information by ID.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config.add(
            {
                "search_limit": 5,
                "source_weight": 0.5,
            }
        )

    @abc.abstractmethod
    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        """Return :py:class:`AlbumInfo` object or None if no matching release was
        found."""
        raise NotImplementedError

    @abc.abstractmethod
    def track_for_id(self, track_id: str) -> TrackInfo | None:
        """Return a :py:class:`TrackInfo` object or None if no matching release was
        found.
        """
        raise NotImplementedError

    # ---------------------------------- search ---------------------------------- #

    @abc.abstractmethod
    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[AlbumInfo]:
        """Return :py:class:`AlbumInfo` candidates that match the given album.

        Used in the autotag functionality to search for albums.

        :param items: List of items in the album
        :param artist: Album artist
        :param album: Album name
        :param va_likely: Whether the album is likely to be by various artists
        """
        raise NotImplementedError

    @abc.abstractmethod
    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        """Return :py:class:`TrackInfo` candidates that match the given track.

        Used in the autotag functionality to search for tracks.

        :param item: Track item
        :param artist: Track artist
        :param title: Track title
        """
        raise NotImplementedError

    def albums_for_ids(self, ids: Sequence[str]) -> Iterable[AlbumInfo | None]:
        """Batch lookup of album metadata for a list of album IDs.

        Given a list of album identifiers, yields corresponding AlbumInfo objects.
        Missing albums result in None values in the output iterator.
        Plugins may implement this for optimized batched lookups instead of
        single calls to album_for_id.
        """

        return (self.album_for_id(id) for id in ids)

    def tracks_for_ids(self, ids: Sequence[str]) -> Iterable[TrackInfo | None]:
        """Batch lookup of track metadata for a list of track IDs.

        Given a list of track identifiers, yields corresponding TrackInfo objects.
        Missing tracks result in None values in the output iterator.
        Plugins may implement this for optimized batched lookups instead of
        single calls to track_for_id.
        """

        return (self.track_for_id(id) for id in ids)

    def album_distance(
        self,
        items: Sequence[Item],
        album_info: AlbumInfo,
        mapping: dict[Item, TrackInfo],
    ) -> Distance:
        """Calculate the distance for an album based on its items and album info."""
        return _get_distance(
            data_source=self.data_source, info=album_info, config=self.config
        )

    def track_distance(
        self,
        item: Item,
        info: TrackInfo,
    ) -> Distance:
        """Calculate the distance for a track based on its item and track info."""
        return _get_distance(
            data_source=self.data_source, info=info, config=self.config
        )

    @cached_classproperty
    def data_source(cls) -> str:
        """The data source name for this plugin.

        This is inferred from the plugin name.
        """
        return cls.__name__.replace("Plugin", "")  # type: ignore[attr-defined]

    def _extract_id(self, url: str) -> str | None:
        """Extract an ID from a URL for this metadata source plugin.

        Uses the plugin's data source name to determine the ID format and
        extracts the ID from a given URL.
        """
        return extract_release_id(self.data_source, url)

    @staticmethod
    def get_artist(
        artists: Iterable[dict[str | int, str]],
        id_key: str | int = "id",
        name_key: str | int = "name",
        join_key: str | int | None = None,
    ) -> tuple[str, str | None]:
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of artist object dicts.

        For each artist, this function moves articles (such as 'a', 'an', and 'the')
        to the front. It returns a tuple containing the comma-separated string
        of all normalized artists and the ``id`` of the main/first artist.
        Alternatively a keyword can be used to combine artists together into a
        single string by passing the join_key argument.

        :param artists: Iterable of artist dicts or lists returned by API.
        :param id_key: Key or index corresponding to the value of ``id`` for
            the main/first artist. Defaults to 'id'.
        :param name_key: Key or index corresponding to values of names
            to concatenate for the artist string (containing all artists).
            Defaults to 'name'.
        :param join_key: Key or index corresponding to a field containing a
            keyword to use for combining artists into a single string, for
            example "Feat.", "Vs.", "And" or similar. The default is None
            which keeps the default behaviour (comma-separated).
        :return: Normalized artist string.
        """
        artist_id = None
        artist_string = ""
        artists = list(artists)  # In case a generator was passed.
        total = len(artists)
        for idx, artist in enumerate(artists):
            if not artist_id:
                artist_id = artist[id_key]
            name = artist[name_key]
            # Move articles to the front.
            name = re.sub(r"^(.*?), (a|an|the)$", r"\2 \1", name, flags=re.I)
            # Use a join keyword if requested and available.
            if idx < (total - 1):  # Skip joining on last.
                if join_key and artist.get(join_key, None):
                    name += f" {artist[join_key]} "
                else:
                    name += ", "
            artist_string += name

        return artist_string, artist_id


class IDResponse(TypedDict):
    """Response from the API containing an ID."""

    id: str


class SearchFilter(TypedDict):
    artist: NotRequired[str]
    album: NotRequired[str]


R = TypeVar("R", bound=IDResponse)


class SearchApiMetadataSourcePlugin(
    Generic[R], MetadataSourcePlugin, metaclass=abc.ABCMeta
):
    """Helper class to implement a metadata source plugin with an API.

    Plugins using this ABC must implement an API search method to
    retrieve album and track information by ID,
    i.e. `album_for_id` and `track_for_id`, and a search method to
    perform a search on the API. The search method should return a list
    of identifiers for the requested type (album or track).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config.add(
            {
                "search_query_ascii": False,
            }
        )

    @abc.abstractmethod
    def _search_api(
        self,
        query_type: Literal["album", "track"],
        filters: SearchFilter,
        query_string: str = "",
    ) -> Sequence[R]:
        """Perform a search on the API.

        :param query_type: The type of query to perform.
        :param filters: A dictionary of filters to apply to the search.
        :param query_string: Additional query to include in the search.

        Should return a list of identifiers for the requested type (album or track).
        """
        raise NotImplementedError

    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[AlbumInfo]:
        query_filters: SearchFilter = {}
        if album:
            query_filters["album"] = album
        if not va_likely:
            query_filters["artist"] = artist

        results = self._search_api("album", query_filters)
        if not results:
            return []

        return filter(
            None, self.albums_for_ids([result["id"] for result in results])
        )

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        results = self._search_api(
            "track", {"artist": artist}, query_string=title
        )
        if not results:
            return []

        return filter(
            None,
            self.tracks_for_ids([result["id"] for result in results if result]),
        )

    def _construct_search_query(
        self, filters: SearchFilter, query_string: str
    ) -> str:
        """Construct a query string with the specified filters and keywords to
        be provided to the spotify (or similar) search API.

        The returned format was initially designed for spotify's search API but
        we found is also useful with other APIs that support similar query structures.
        see `spotify <https://developer.spotify.com/documentation/web-api/reference/search>`_
        and `deezer <https://developers.deezer.com/api/search>`_.

        :param filters: Field filters to apply.
        :param query_string: Query keywords to use.
        :return: Query string to be provided to the search API.
        """

        components = [query_string, *(f"{k}:'{v}'" for k, v in filters.items())]
        query = " ".join(filter(None, components))

        if self.config["search_query_ascii"].get():
            query = unidecode.unidecode(query)

        return query
