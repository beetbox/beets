# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Glue between metadata sources and the matching logic."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from typing_extensions import Self

from beets import config, logging, plugins
from beets.util import cached_classproperty, unique_list
from beets.util.deprecation import (
    ALBUM_LEGACY_TO_LIST_FIELD,
    ITEM_LEGACY_TO_LIST_FIELD,
    deprecate_for_maintainers,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Album, Item

    from .distance import Distance

V = TypeVar("V")

JSONDict = dict[str, Any]

log = logging.getLogger("beets")

SYNCHRONISED_LIST_FIELDS = {
    ("albumtype", "albumtypes"),
    ("artist", "artists"),
    ("artist_id", "artists_ids"),
    ("artist_sort", "artists_sort"),
    ("artist_credit", "artists_credit"),
}


def correct_list_fields(input_data: JSONDict) -> JSONDict:
    """Synchronise single and list values for certain metadata fields.

    For fields listed in :data:`SYNCHRONISED_LIST_FIELDS`, beets stores both a
    scalar value (for example ``artist_id``) and a corresponding list value
    (for example ``artists_ids``). Under the current :class:`MediaFile`
    implementation, only the list value is actually written to files; the
    scalar is effectively mapped to the first element of the list.

    Beets, however, still treats the scalar fields as independent and stores
    them in the database. When the scalar value and the first list element
    differ (for example, ``artist_id`` != ``artists_ids[0]``), commands like
    ``beet write`` can repeatedly report changes that will never be written to
    the underlying files.

    This helper reduces such mismatches by keeping the scalar and list values
    in sync where appropriate: it usually makes sure that the scalar value is
    present (and, when necessary, first) in the corresponding list, or that an
    existing list value is copied back into the scalar field. In cases where
    the scalar value is already represented in the list (ignoring case and
    simple word ordering), the list is left unchanged.
    """
    data = deepcopy(input_data)

    def ensure_first_value(single_field: str, list_field: str) -> None:
        """Ensure the first ``list_field`` item is equal to ``single_field``."""
        list_val: list[str]
        single_val, list_val = (
            data.get(single_field) or "",
            data.get(list_field) or [],
        )
        single_val_lower = single_val.lower()
        list_val_lower = set(map(str.lower, list_val))
        if single_val not in list_val and (
            # Joined credits share words with individual list values
            set(single_val_lower.split()) & list_val_lower
            or (
                # Each of the credits in the list are in the joined credit
                len(list_val) > 1
                and all(v in single_val_lower for v in list_val_lower)
            )
        ):
            return

        if single_val:
            data[list_field] = unique_list([single_val, *list_val])
        elif list_val:
            data[single_field] = list_val[0]

    for pair in SYNCHRONISED_LIST_FIELDS:
        ensure_first_value(*pair)

    return data


# Classes used to represent candidate options.
class AttrDict(dict[str, V]):
    """Mapping enabling attribute-style access to stored metadata values."""

    def copy(self) -> Self:
        """Return a detached copy preserving subclass-specific behavior."""
        return deepcopy(self)

    def __getattr__(self, attr: str) -> V:
        if attr in self:
            return self[attr]

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{attr}'"
        )

    def __setattr__(self, key: str, value: V) -> None:
        self.__setitem__(key, value)

    def __hash__(self) -> int:  # type: ignore[override]
        return id(self)


class Info(AttrDict[Any]):
    """Container for metadata about a musical entity."""

    Identifier = tuple[str | None, str | None]

    type: ClassVar[str]

    IGNORED_FIELDS: ClassVar[set[str]] = {"data_url"}
    MEDIA_FIELD_MAP: ClassVar[dict[str, str]] = {}
    LEGACY_TO_LIST_FIELD: ClassVar[dict[str, str]]

    @cached_classproperty
    def nullable_fields(cls) -> set[str]:
        """Return fields that may be cleared when new metadata is applied."""
        return set(config["overwrite_null"][cls.type.lower()].as_str_seq())

    def __setitem__(self, key: str, value: Any) -> None:
        # handle legacy info.str_field = "abc" and info["str_field"] = "abc"
        if list_field := self.LEGACY_TO_LIST_FIELD.get(key):
            self[list_field] = self._get_list_from_string_value(
                key, list_field, value, self[list_field]
            )
        else:
            super().__setitem__(key, value)

    @property
    def id(self) -> str | None:
        """Return the provider-specific identifier for this metadata object."""
        raise NotImplementedError

    @property
    def identifier(self) -> Identifier:
        """Return a cross-provider key in ``(data_source, id)`` form."""
        return (self.data_source, self.id)

    @cached_property
    def name(self) -> str:
        raise NotImplementedError

    @cached_property
    def raw_data(self) -> JSONDict:
        """Provide metadata with artist credits applied when configured."""
        data = self.__class__(**self.copy())
        if config["artist_credit"]:
            data.update(
                artist=self.artist_credit or self.artist,
                artists=self.artists_credit or self.artists,
            )

        return correct_list_fields(data)

    @cached_property
    def item_data(self) -> JSONDict:
        """Metadata for items with field mappings and exclusions applied.

        Filters out null values and empty lists except for explicitly nullable
        fields, removes ignored fields, and applies media-specific field name
        mappings for compatibility with the item model.
        """
        data = {
            k: v
            for k, v in self.raw_data.items()
            if k not in self.IGNORED_FIELDS
            and (v not in [None, []] or k in self.nullable_fields)
        }
        for info_field, media_field in (
            (k, v) for k, v in self.MEDIA_FIELD_MAP.items() if k in data
        ):
            data[media_field] = data.pop(info_field)

        return data

    def __init__(
        self,
        album: str | None = None,
        artist_credit: str | None = None,
        artist_id: str | None = None,
        artist: str | None = None,
        artists_credit: list[str] | None = None,
        artists_ids: list[str] | None = None,
        artists: list[str] | None = None,
        artist_sort: str | None = None,
        artists_sort: list[str] | None = None,
        data_source: str | None = None,
        data_url: str | None = None,
        genres: list[str] | None = None,
        media: str | None = None,
        **kwargs,
    ) -> None:
        self.album = album
        self.artist = artist
        self.artist_credit = artist_credit
        self.artist_id = artist_id
        self.artists = artists
        self.artists_credit = artists_credit
        self.artists_ids = artists_ids
        self.artist_sort = artist_sort
        self.artists_sort = artists_sort
        self.data_source = data_source
        self.data_url = data_url
        self.genres = genres
        self.media = media
        self.update(kwargs)

    @staticmethod
    def _get_list_from_string_value(
        str_field: str,
        list_field: str,
        str_value: str | None,
        list_value: list[str] | None,
    ) -> list[str] | None:
        if str_value is not None:
            deprecate_for_maintainers(
                f"The '{str_field}' field",
                f"'{list_field}' (list)",
                stacklevel=3,
            )
            if not list_value:
                try:
                    sep = next(s for s in ["; ", ", ", " / "] if s in str_value)
                except StopIteration:
                    list_value = [str_value]
                else:
                    list_value = list(map(str.strip, str_value.split(sep)))

        return list_value


class AlbumInfo(Info):
    """Metadata snapshot representing a single album candidate.

    Aggregates track entries and album-wide context gathered from an external
    provider. Used during matching to evaluate similarity against a group of
    user items, and later to drive tagging decisions once selected.
    """

    type = "Album"

    IGNORED_FIELDS: ClassVar[set[str]] = {*Info.IGNORED_FIELDS, "tracks"}
    MEDIA_FIELD_MAP: ClassVar[dict[str, str]] = {
        **Info.MEDIA_FIELD_MAP,
        "album_id": "mb_albumid",
        "artist": "albumartist",
        "artists": "albumartists",
        "artist_id": "mb_albumartistid",
        "artists_ids": "mb_albumartistids",
        "artist_credit": "albumartist_credit",
        "artists_credit": "albumartists_credit",
        "artist_sort": "albumartist_sort",
        "artists_sort": "albumartists_sort",
        "mediums": "disctotal",
        "releasegroup_id": "mb_releasegroupid",
        "va": "comp",
    }
    LEGACY_TO_LIST_FIELD: ClassVar[dict[str, str]] = ALBUM_LEGACY_TO_LIST_FIELD

    @property
    def id(self) -> str | None:
        return self.album_id

    @cached_property
    def name(self) -> str:
        return self.album or ""

    @cached_property
    def raw_data(self) -> JSONDict:
        """Metadata with month and day reset to 0 when only year is present."""
        data = {**super().raw_data}
        if data["year"]:
            data["month"] = self.month or 0
            data["day"] = self.day or 0

        return data

    @cached_property
    def item_data(self) -> JSONDict:
        """Album metadata with optional original-date override."""
        data = {**super().item_data}
        if config["original_date"].get(bool) and (
            original_year := data.get("original_year")
        ):
            data["year"] = original_year
            data["month"] = data.get("original_month") or 0
            data["day"] = data.get("original_day") or 0

        return data

    def __init__(
        self,
        tracks: list[TrackInfo],
        *,
        album_id: str | None = None,
        albumdisambig: str | None = None,
        albumstatus: str | None = None,
        albumtype: str | None = None,
        albumtypes: list[str] | None = None,
        asin: str | None = None,
        barcode: str | None = None,
        catalognum: str | None = None,
        country: str | None = None,
        day: int | None = None,
        discogs_albumid: str | None = None,
        discogs_artistid: str | None = None,
        discogs_labelid: str | None = None,
        label: str | None = None,
        language: str | None = None,
        mediums: int | None = None,
        month: int | None = None,
        original_day: int | None = None,
        original_month: int | None = None,
        original_year: int | None = None,
        release_group_title: str | None = None,
        releasegroup_id: str | None = None,
        releasegroupdisambig: str | None = None,
        script: str | None = None,
        style: str | None = None,
        va: bool = False,
        year: int | None = None,
        **kwargs,
    ) -> None:
        self.tracks = tracks
        self.album_id = album_id
        self.albumdisambig = albumdisambig
        self.albumstatus = albumstatus
        self.albumtype = albumtype
        self.albumtypes = albumtypes
        self.asin = asin
        self.barcode = barcode
        self.catalognum = catalognum
        self.country = country
        self.day = day
        self.discogs_albumid = discogs_albumid
        self.discogs_artistid = discogs_artistid
        self.discogs_labelid = discogs_labelid
        self.label = label
        self.language = language
        self.mediums = mediums
        self.month = month
        self.original_day = original_day
        self.original_month = original_month
        self.original_year = original_year
        self.release_group_title = release_group_title
        self.releasegroup_id = releasegroup_id
        self.releasegroupdisambig = releasegroupdisambig
        self.script = script
        self.style = style
        self.va = va
        self.year = year
        super().__init__(**kwargs)


class TrackInfo(Info):
    """Metadata snapshot for a single track candidate.

    Captures identifying details and creative credits used to compare against
    a user's item. Instances often originate within an AlbumInfo but may also
    stand alone for singleton matching.
    """

    type = "Track"

    IGNORED_FIELDS: ClassVar[set[str]] = {
        *Info.IGNORED_FIELDS,
        "index",
        "medium_total",
    }
    MEDIA_FIELD_MAP: ClassVar[dict[str, str]] = {
        **Info.MEDIA_FIELD_MAP,
        "artist_id": "mb_artistid",
        "artists_ids": "mb_artistids",
        "medium": "disc",
        "release_track_id": "mb_releasetrackid",
        "track_id": "mb_trackid",
        "medium_index": "track",
    }
    LEGACY_TO_LIST_FIELD: ClassVar[dict[str, str]] = ITEM_LEGACY_TO_LIST_FIELD

    @property
    def id(self) -> str | None:
        return self.track_id

    @cached_property
    def name(self) -> str:
        return self.title or ""

    @cached_property
    def raw_data(self) -> JSONDict:
        """Provide track metadata with numbering adapted to import settings."""
        data = {
            **super().raw_data,
            "mb_releasetrackid": self.release_track_id or self.track_id,
            "track": self.index,
            "medium_index": (
                (
                    mindex
                    if (mindex := self.medium_index) is not None
                    else self.index
                )
                if config["per_disc_numbering"]
                else self.index
            ),
        }
        if config["per_disc_numbering"] and self.medium_total is not None:
            data["tracktotal"] = self.medium_total

        return data

    def __init__(
        self,
        *,
        arrangers: list[str] | None = None,
        arrangers_ids: list[str] | None = None,
        bpm: str | None = None,
        composers: list[str] | None = None,
        composer_sort: str | None = None,
        composers_ids: list[str] | None = None,
        disctitle: str | None = None,
        index: int | None = None,
        initial_key: str | None = None,
        length: float | None = None,
        lyricists: list[str] | None = None,
        lyricists_ids: list[str] | None = None,
        mb_workid: str | None = None,
        medium: int | None = None,
        medium_index: int | None = None,
        medium_total: int | None = None,
        release_track_id: str | None = None,
        remixers: list[str] | None = None,
        remixers_ids: list[str] | None = None,
        title: str | None = None,
        track_alt: str | None = None,
        track_id: str | None = None,
        work: str | None = None,
        work_disambig: str | None = None,
        **kwargs,
    ) -> None:
        self.arrangers = arrangers
        # Remove existing IDs if they are not provided by the data source
        self.arrangers_ids = arrangers_ids or []
        self.bpm = bpm
        self.composers = composers
        self.composer_sort = composer_sort
        self.composers_ids = composers_ids or []
        self.disctitle = disctitle
        self.index = index
        self.initial_key = initial_key
        self.length = length
        self.lyricists = lyricists
        self.lyricists_ids = lyricists_ids or []
        self.mb_workid = mb_workid
        self.medium = medium
        self.medium_index = medium_index
        self.medium_total = medium_total
        self.release_track_id = release_track_id
        self.remixers = remixers
        self.remixers_ids = remixers_ids or []
        self.title = title
        self.track_alt = track_alt
        self.track_id = track_id
        self.work = work
        self.work_disambig = work_disambig
        super().__init__(**kwargs)

    def merge_with_album(self, album_info: AlbumInfo) -> JSONDict:
        """Merge track metadata with album-level data as fallback.

        Combines this track's metadata with album-wide values, using album data
        to fill missing track fields while preserving track-specific artist
        credits.
        """
        album = album_info.raw_data
        raw_track = self.raw_data
        track = self.__class__(**self.copy())

        # Do not inherit album artist_credit onto tracks. When artist_credit
        # mode is enabled, raw_data() uses artist_credit to rewrite artist, and
        # inheriting the album credit here would override albumartist fallback
        # for tracks that have no track-level credit.
        for k in raw_track.keys() - {"artist_credit"}:
            if not raw_track[k] and (v := album.get(k)):
                track[k] = v

        merged = (
            album_info.item_data
            | {"tracktotal": len(album_info.tracks)}
            | track.item_data
        )
        return merged


# Structures that compose all the information for a candidate match.
@dataclass
class Match:
    """Represent a chosen metadata candidate and its application behavior."""

    disambig_fields_key: ClassVar[str]

    distance: Distance
    info: Info

    def apply_metadata(self) -> None:
        """Apply this match's metadata to its target library objects."""
        raise NotImplementedError

    @cached_property
    def type(self) -> str:
        return self.info.type

    @cached_property
    def from_scratch(self) -> bool:
        return bool(config["import"]["from_scratch"])

    @property
    def disambig_fields(self) -> Sequence[str]:
        """Return configured disambiguation fields that exist on this match."""
        chosen_fields = config["match"][self.disambig_fields_key].as_str_seq()
        valid_fields = [f for f in chosen_fields if f in self.info]
        if missing_fields := set(chosen_fields) - set(valid_fields):
            log.warning(
                "Disambiguation string keys {} do not exist.", missing_fields
            )

        return valid_fields

    @property
    def base_disambig_data(self) -> JSONDict:
        """Return supplemental values used when formatting disambiguation."""
        return {}

    @property
    def disambig_string(self) -> str:
        """Build a display string from the candidate's disambiguation fields.

        Merges base disambiguation data with instance-specific field values,
        then formats them as a comma-separated string in field definition order.
        """
        data = {
            k: self.info[k] for k in self.disambig_fields
        } | self.base_disambig_data
        return ", ".join(str(data[k]) for k in self.disambig_fields)


@dataclass
class AlbumMatch(Match):
    """Represent an album candidate together with its item-to-track mapping."""

    disambig_fields_key = "album_disambig_fields"

    info: AlbumInfo
    mapping: dict[Item, TrackInfo]
    extra_items: list[Item] = field(default_factory=list)
    extra_tracks: list[TrackInfo] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Notify listeners when an album candidate has been matched."""
        plugins.send("album_matched", match=self)

    @property
    def item_info_pairs(self) -> list[tuple[Item, TrackInfo]]:
        """Return matched items together with their selected track metadata."""
        return list(self.mapping.items())

    @property
    def items(self) -> list[Item]:
        """Return the items that participate in this album match."""
        return [i for i, _ in self.item_info_pairs]

    @property
    def base_disambig_data(self) -> JSONDict:
        """Return album-specific values used in disambiguation displays."""
        return {
            "media": (
                f"{mediums}x{self.info.media}"
                if (mediums := self.info.mediums) and mediums > 1
                else self.info.media
            ),
        }

    @property
    def merged_pairs(self) -> list[tuple[Item, JSONDict]]:
        """Generate item-data pairs with album-level fallback values."""
        return [
            (i, ti.merge_with_album(self.info))
            for i, ti in self.item_info_pairs
        ]

    def apply_metadata(self) -> None:
        """Apply metadata to each of the items."""
        for item, data in self.merged_pairs:
            if self.from_scratch:
                item.clear()

            item.update(data)

    def apply_album_metadata(self, album: Album) -> None:
        """Apply album-level metadata to the Album object."""
        album.update(self.info.item_data)


@dataclass
class TrackMatch(Match):
    """Represent a singleton candidate and the item it updates."""

    disambig_fields_key = "singleton_disambig_fields"

    info: TrackInfo
    item: Item

    @property
    def base_disambig_data(self) -> JSONDict:
        """Return singleton-specific values used in disambiguation displays."""
        return {
            "index": f"Index {self.info.index}",
            "track_alt": f"Track {self.info.track_alt}",
            "album": (
                f"[{self.info.album}]"
                if (
                    config["import"]["singleton_album_disambig"].get()
                    and self.info.album
                )
                else ""
            ),
        }

    def apply_metadata(self) -> None:
        """Apply metadata to the item."""
        if self.from_scratch:
            self.item.clear()

        self.item.update(self.info.item_data)
