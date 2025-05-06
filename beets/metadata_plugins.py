"""Metadata source plugin interface.

This allows beets to lookup metadata from various sources. We define
a common interface for all metadata sources which need to be
implemented as plugins.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Generic, Iterator, Sequence, TypeVar

from requests import Response

from .plugins import find_plugins, notify_info_yielded, send

if TYPE_CHECKING:
    import re

    from beets.autotag.hooks import AlbumInfo, Item, TrackInfo


def find_metadata_source_plugins() -> list[MetadataSourcePluginNew]:
    """Returns a list of MetadataSourcePluginNew subclass instances from all
    currently loaded beets plugins.
    """
    return [
        plugin
        for plugin in find_plugins()
        if isinstance(plugin, MetadataSourcePluginNew)
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
        if info := plugin.album_for_id(_id):
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


class MetadataSourcePluginNew(metaclass=abc.ABCMeta):
    """A plugin that provides metadata from a specific source.

    This base class implements a contract for plugins that provide metadata
    from a specific source. The plugin must implement the methods to search for albums
    and tracks, and to retrieve album and track information by ID.
    """

    @property
    @abc.abstractmethod
    def data_source(self) -> str:
        """The name of the data source for this plugin.

        This is used to identify the source of metadata and should be unique among
        all source plugins.
        """
        raise NotImplementedError

    @property
    def id_key(self) -> str:
        """The key used to identify external IDs in the database.

        Will normalize the data source name to alphanumeric and lowercase
        and append "_id" to it.
        """
        return (
            "".join(e for e in self.data_source if e.isalnum()).lower() + "_id"
        )

    regex_pattern: re.Pattern[str] | None = None
    # Regex pattern allowed to extract the ID from a URL or other string.

    def to_release_id(self, id_: str) -> tuple[str, str] | None:
        """Converts a raw id string (normally an url)
        to a normalized id string variant.

        Returns a tuple of (id, source) to allow plugins to also
        parse additional sources see musicbrainz plugin for reference..

        May return None if the id is not valid.
        """
        if self.regex_pattern is None:
            return (id_, self.id_key)

        if m := self.regex_pattern.search(str(id_)):
            return (m[1], self.id_key)

        return None

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

        :param item: Track item
        :param artist: Track artist
        :param title: Track title
        """
        raise NotImplementedError


R = TypeVar("R", bound=Response)


class RestApiMetadataSourcePlugin(
    Generic[R], MetadataSourcePluginNew, metaclass=abc.ABCMeta
):
    """A plugin that provides metadata from a REST API.

    This class is a base for plugins that interact with REST APIs to fetch
    metadata. It provides a common interface and some utility methods for
    handling API requests and responses.

    TODO: Needs some documentation
    """

    @property
    @abc.abstractmethod
    def album_url(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def track_url(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def search_url(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def _search_api(
        self,
        query_type: str,
        filters: dict[str, str] | None,
        keywords: str = "",
    ) -> Sequence[R]:
        raise NotImplementedError
