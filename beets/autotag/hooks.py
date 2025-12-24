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

from beets import config
from beets.util import cached_classproperty, unique_list

if TYPE_CHECKING:
    from beets.library import Album, Item

    from .distance import Distance

V = TypeVar("V")

JSONDict = dict[str, Any]


SYNCHRONISED_LIST_FIELDS = {
    ("albumtype", "albumtypes"),
    ("artist", "artists"),
    ("artist_id", "artists_ids"),
    ("artist_sort", "artists_sort"),
    ("artist_credit", "artists_credit"),
}


def correct_list_fields(input_data: JSONDict) -> JSONDict:
    """Synchronise single and list values for the list fields that we use.

    That is, ensure the same value in the single field and the first element
    in the list.

    For context, the value we set as, say, ``mb_artistid`` is simply ignored:
    Under the current :class:`MediaFile` implementation, fields ``albumtype``,
    ``mb_artistid`` and ``mb_albumartistid`` are mapped to the first element of
    ``albumtypes``, ``mb_artistids`` and ``mb_albumartistids`` respectively.

    This means setting ``mb_artistid`` has no effect. However, beets
    functionality still assumes that ``mb_artistid`` is independent and stores
    its value in the database. If ``mb_artistid`` != ``mb_artistids[0]``,
    ``beet write`` command thinks that ``mb_artistid`` is modified and tries to
    update the field in the file. Of course nothing happens, so the same diff
    is shown every time the command is run.

    We can avoid this issue by ensuring that ``artist_id`` has the same value
    as ``artists_ids[0]``, and that's what this function does.
    """
    data = deepcopy(input_data)

    def ensure_first_value(single_field: str, list_field: str) -> None:
        """Ensure the first ``list_field`` item is equal to ``single_field``."""
        single_val, list_val = data.get(single_field), data.get(list_field, [])
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
        return self.__class__(**deepcopy(self))

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

    type: ClassVar[str]

    IGNORED_FIELDS: ClassVar[set[str]] = {"data_url"}
    MEDIA_FIELD_MAP: ClassVar[dict[str, str]] = {}

    @cached_classproperty
    def nullable_fields(cls) -> set[str]:
        return set(config["overwrite_null"][cls.type.lower()].as_str_seq())

    @cached_property
    def name(self) -> str:
        raise NotImplementedError

    @cached_property
    def raw_data(self) -> JSONDict:
        """Provide metadata with artist credits applied when configured."""
        data = self.copy()
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
        genre: str | None = None,
        media: str | None = None,
        **kwargs,
    ) -> None:
        self.album = album
        self.artist = artist
        self.artist_credit = artist_credit
        self.artist_id = artist_id
        self.artists = artists or []
        self.artists_credit = artists_credit or []
        self.artists_ids = artists_ids or []
        self.artist_sort = artist_sort
        self.artists_sort = artists_sort or []
        self.data_source = data_source
        self.data_url = data_url
        self.genre = genre
        self.media = media
        self.update(kwargs)


class AlbumInfo(Info):
    """Metadata snapshot representing a single album candidate.

    Aggregates track entries and album-wide context gathered from an external
    provider. Used during matching to evaluate similarity against a group of
    user items, and later to drive tagging decisions once selected.
    """

    type = "Album"

    IGNORED_FIELDS = {*Info.IGNORED_FIELDS, "tracks"}
    MEDIA_FIELD_MAP = {
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

    @cached_property
    def name(self) -> str:
        return self.album or ""

    @cached_property
    def raw_data(self) -> JSONDict:
        """Metadata with month and day reset to 0 when only year is present."""
        data = super().raw_data
        if data["year"]:
            data["month"] = self.month or 0
            data["day"] = self.day or 0

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
        self.albumtypes = albumtypes or []
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

    IGNORED_FIELDS = {*Info.IGNORED_FIELDS, "index", "medium_total"}
    MEDIA_FIELD_MAP = {
        **Info.MEDIA_FIELD_MAP,
        "artist_id": "mb_artistid",
        "artists_ids": "mb_artistids",
        "medium": "disc",
        "release_track_id": "mb_releasetrackid",
        "track_id": "mb_trackid",
        "medium_index": "track",
    }

    @cached_property
    def name(self) -> str:
        return self.title or ""

    @cached_property
    def raw_data(self) -> JSONDict:
        data = {
            **super().raw_data,
            "mb_releasetrackid": self.release_track_id or self.track_id,
            "track": self.index,
            "medium_index": (
                (self.medium_index or self.index)
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
        arranger: str | None = None,
        bpm: str | None = None,
        composer: str | None = None,
        composer_sort: str | None = None,
        disctitle: str | None = None,
        index: int | None = None,
        initial_key: str | None = None,
        length: float | None = None,
        lyricist: str | None = None,
        mb_workid: str | None = None,
        medium: int | None = None,
        medium_index: int | None = None,
        medium_total: int | None = None,
        release_track_id: str | None = None,
        title: str | None = None,
        track_alt: str | None = None,
        track_id: str | None = None,
        work: str | None = None,
        work_disambig: str | None = None,
        **kwargs,
    ) -> None:
        self.arranger = arranger
        self.bpm = bpm
        self.composer = composer
        self.composer_sort = composer_sort
        self.disctitle = disctitle
        self.index = index
        self.initial_key = initial_key
        self.length = length
        self.lyricist = lyricist
        self.mb_workid = mb_workid
        self.medium = medium
        self.medium_index = medium_index
        self.medium_total = medium_total
        self.release_track_id = release_track_id
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
        track = self.copy()

        for k in raw_track.keys() - {"artist_credit"}:
            if not raw_track[k] and (v := album.get(k)):
                track[k] = v

        return (
            album_info.item_data
            | {"tracktotal": len(album_info.tracks)}
            | track.item_data
        )


# Structures that compose all the information for a candidate match.
@dataclass
class Match:
    distance: Distance
    info: Info

    def apply_metadata(self) -> None:
        raise NotImplementedError

    @cached_property
    def type(self) -> str:
        return self.info.type

    @cached_property
    def from_scratch(self) -> bool:
        return bool(config["import"]["from_scratch"])


@dataclass
class AlbumMatch(Match):
    info: AlbumInfo
    mapping: dict[Item, TrackInfo]
    extra_items: list[Item] = field(default_factory=list)
    extra_tracks: list[TrackInfo] = field(default_factory=list)

    @property
    def item_info_pairs(self) -> list[tuple[Item, TrackInfo]]:
        return list(self.mapping.items())

    @property
    def items(self) -> list[Item]:
        return [i for i, _ in self.item_info_pairs]

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
        """Apply metadata to each of the items."""
        album.update(self.info.item_data)


@dataclass
class TrackMatch(Match):
    info: TrackInfo
    item: Item

    def apply_metadata(self) -> None:
        """Apply metadata to the item."""
        if self.from_scratch:
            self.item.clear()

        self.item.update(self.info.item_data)
