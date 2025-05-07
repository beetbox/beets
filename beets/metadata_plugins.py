"""Metadata source plugin interface.

This allows beets to lookup metadata from various sources. We define
a common interface for all metadata sources which need to be
implemented as plugins.
"""

from __future__ import annotations

import abc
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Iterator,
    Literal,
    Sequence,
    TypedDict,
    TypeVar,
)

from typing_extensions import NotRequired

from .plugins import BeetsPlugin, find_plugins, notify_info_yielded, send

if TYPE_CHECKING:
    from confuse import ConfigView

    from .autotag import Distance
    from .autotag.hooks import AlbumInfo, Item, TrackInfo


def find_metadata_source_plugins() -> list[MetadataSourcePluginNext]:
    """Returns a list of MetadataSourcePluginNew subclass instances from all
    currently loaded beets plugins.
    """
    return [
        plugin
        for plugin in find_plugins()
        if isinstance(plugin, MetadataSourcePluginNext)
    ]


@notify_info_yielded("albuminfo_received")
def candidates(*args, **kwargs) -> Iterator[AlbumInfo]:
    """Return matching album candidates by using all metadata source
    plugins."""
    for plugin in find_metadata_source_plugins():
        yield from plugin.candidates(*args, **kwargs)


@notify_info_yielded("trackinfo_received")
def item_candidates(*args, **kwargs) -> Iterator[TrackInfo]:
    """Return matching track candidates by using all metadata source
    plugins."""
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


def _get_distance(
    config: ConfigView, data_source: str, info: AlbumInfo | TrackInfo
) -> Distance:
    """Returns the ``data_source`` weight and the maximum source weight
    for albums or individual tracks.
    """
    from beets.autotag.hooks import Distance

    dist = Distance()
    if info.data_source == data_source:
        dist.add("source", config["source_weight"].as_number())
    return dist


class MetadataSourcePluginNext(BeetsPlugin, metaclass=abc.ABCMeta):
    """A plugin that provides metadata from a specific source.

    This base class implements a contract for plugins that provide metadata
    from a specific source. The plugin must implement the methods to search for albums
    and tracks, and to retrieve album and track information by ID.

    TODO: Rename once all plugins are migrated to this interface.
    """

    data_source: str

    def __init__(self, data_source: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_source = data_source or self.__class__.__name__
        self.config.add({"source_weight": 0.5})

    # --------------------------------- id lookup -------------------------------- #

    def albums_for_ids(self, ids: Sequence[str]) -> Iterator[AlbumInfo | None]:
        """Batch lookup of album metadata for a list of album IDs.

        Given a list of album identifiers, yields corresponding AlbumInfo
        objects. Missing albums result in None values in the output iterator.
        Plugins may implement this for optimized batched lookups instead of
        single calls to album_for_id.
        """

        return iter(self.album_for_id(id) for id in ids)

    @abc.abstractmethod
    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        """Return :py:class:`AlbumInfo` object or None if no matching release was
        found."""
        raise NotImplementedError

    def tracks_for_ids(self, ids: Sequence[str]) -> Iterator[TrackInfo | None]:
        """Batch lookup of track metadata for a list of track IDs.

        Given a list of track identifiers, yields corresponding TrackInfo objects.
        Missing tracks result in None values in the output iterator. Plugins may
        implement this for optimized batched lookups instead of single calls to
        track_for_id.
        """

        return iter(self.track_for_id(id) for id in ids)

    @abc.abstractmethod
    def track_for_id(self, track_id: str) -> TrackInfo | None:
        """Return a :py:class:`AlbumInfo` object or None if no matching release was
        found.
        """
        raise NotImplementedError

    # ---------------------------------- search ---------------------------------- #

    @abc.abstractmethod
    def candidates(
        self,
        items: list[Item],
        artist: str,
        album: str,
        va_likely: bool,
        extra_tags: dict[str, Any] | None = None,
    ) -> Iterator[AlbumInfo]:
        """Return :py:class:`AlbumInfo` candidates that match the given album.

        Used in the autotag functionality to search for albums.

        :param items: List of items in the album
        :param artist: Album artist
        :param album: Album name
        :param va_likely: Whether the album is likely to be by various artists
        :param extra_tags: is a an optional dictionary of extra tags to search.
            TODO: remove:
            Currently relevant to :py:class:`MusicBrainzPlugin` autotagger and can be
            ignored by other plugins
        """
        raise NotImplementedError

    @abc.abstractmethod
    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterator[TrackInfo]:
        """Return :py:class:`TrackInfo` candidates that match the given track.

        Used in the autotag functionality to search for tracks.

        :param item: Track item
        :param artist: Track artist
        :param title: Track title
        """
        raise NotImplementedError

    # --------------------------------- distances -------------------------------- #

    def album_distance(
        self,
        items: list[Item],
        album_info: AlbumInfo,
        mapping: dict[Item, TrackInfo],
    ) -> Distance:
        return _get_distance(
            data_source=self.data_source, info=album_info, config=self.config
        )

    def track_distance(
        self,
        item: Item,
        info: TrackInfo,
    ) -> Distance:
        return _get_distance(
            data_source=self.data_source, info=info, config=self.config
        )


class IDResponse(TypedDict):
    """Response from the API containing an ID."""

    id: str


class SearchFilter(TypedDict):
    artist: NotRequired[str]
    album: NotRequired[str]


R = TypeVar("R", bound=IDResponse)


class SearchApiMetadataSourcePluginNext(
    Generic[R], MetadataSourcePluginNext, metaclass=abc.ABCMeta
):
    """Helper class to implement a metadata source plugin with an API.

    Plugins using this ABC must implement an API search method to
    retrieve album and track information by ID,
    i.e. `album_for_id` and `track_for_id`, and a search method to
    perform a search on the API. The search method should return a list
    of identifiers for the requested type (album or track).
    """

    @abc.abstractmethod
    def _search_api(
        self,
        query_type: Literal["album", "track"],
        filters: SearchFilter | None = None,
        keywords: str = "",
    ) -> Sequence[R] | None:
        """Perform a search on the API.

        :param query_type: The type of query to perform.
        :param filters: A dictionary of filters to apply to the search.
        :param keywords: Additional keywords to include in the search.

        Should return a list of identifiers for the requested type (album or track).
        """
        raise NotImplementedError

    def candidates(
        self,
        items: list[Item],
        artist: str,
        album: str,
        va_likely: bool,
        extra_tags: dict[str, Any] | None = None,
    ) -> Iterator[AlbumInfo]:
        query_filters: SearchFilter = {"album": album}
        if not va_likely:
            query_filters["artist"] = artist

        results = self._search_api("album", query_filters)
        if not results:
            return

        yield from filter(
            None, self.albums_for_ids([result["id"] for result in results])
        )

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterator[TrackInfo]:
        results = self._search_api("track", {"artist": artist}, keywords=title)
        if not results:
            return

        yield from filter(
            None, self.tracks_for_ids([result["id"] for result in results])
        )


def artists_to_artist_str(
    artists,
    id_key: str | int = "id",
    name_key: str | int = "name",
    join_key: str | int | None = None,
) -> tuple[str, str | None]:
    """Returns an artist string (all artists) and an artist_id (the main
    artist) for a list of artist object dicts.

    For each artist, this function moves articles (such as 'a', 'an',
    and 'the') to the front and strips trailing disambiguation numbers. It
    returns a tuple containing the comma-separated string of all
    normalized artists and the ``id`` of the main/first artist.
    Alternatively a keyword can be used to combine artists together into a
    single string by passing the join_key argument.

    :param artists: Iterable of artist dicts or lists returned by API.
    :type artists: list[dict] or list[list]
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
        # Strip disambiguation number.
        name = re.sub(r" \(\d+\)$", "", name)
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
