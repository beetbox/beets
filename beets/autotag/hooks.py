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
from typing import TYPE_CHECKING, Any, NamedTuple, TypeVar

from typing_extensions import Self

if TYPE_CHECKING:
    from beets.library import Item

    from .distance import Distance

V = TypeVar("V")


# Classes used to represent candidate options.
class AttrDict(dict[str, V]):
    """Mapping enabling attribute-style access to stored metadata values."""

    def copy(self) -> Self:
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

    def __init__(
        self,
        tracks: list[TrackInfo],
        album_id: str | None = None,
        asin: str | None = None,
        albumtype: str | None = None,
        albumtypes: list[str] | None = None,
        va: bool = False,
        year: int | None = None,
        month: int | None = None,
        day: int | None = None,
        label: str | None = None,
        barcode: str | None = None,
        mediums: int | None = None,
        releasegroup_id: str | None = None,
        release_group_title: str | None = None,
        catalognum: str | None = None,
        script: str | None = None,
        language: str | None = None,
        country: str | None = None,
        style: str | None = None,
        albumstatus: str | None = None,
        albumdisambig: str | None = None,
        releasegroupdisambig: str | None = None,
        original_year: int | None = None,
        original_month: int | None = None,
        original_day: int | None = None,
        discogs_albumid: str | None = None,
        discogs_labelid: str | None = None,
        discogs_artistid: str | None = None,
        **kwargs,
    ) -> None:
        self.album_id = album_id
        self.tracks = tracks
        self.asin = asin
        self.albumtype = albumtype
        self.albumtypes = albumtypes or []
        self.va = va
        self.year = year
        self.month = month
        self.day = day
        self.label = label
        self.barcode = barcode
        self.mediums = mediums
        self.releasegroup_id = releasegroup_id
        self.release_group_title = release_group_title
        self.catalognum = catalognum
        self.script = script
        self.language = language
        self.country = country
        self.style = style
        self.albumstatus = albumstatus
        self.albumdisambig = albumdisambig
        self.releasegroupdisambig = releasegroupdisambig
        self.original_year = original_year
        self.original_month = original_month
        self.original_day = original_day
        self.discogs_albumid = discogs_albumid
        self.discogs_labelid = discogs_labelid
        self.discogs_artistid = discogs_artistid
        super().__init__(**kwargs)


class TrackInfo(Info):
    """Metadata snapshot for a single track candidate.

    Captures identifying details and creative credits used to compare against
    a user's item. Instances often originate within an AlbumInfo but may also
    stand alone for singleton matching.
    """

    def __init__(
        self,
        title: str | None = None,
        track_id: str | None = None,
        release_track_id: str | None = None,
        length: float | None = None,
        index: int | None = None,
        medium: int | None = None,
        medium_index: int | None = None,
        medium_total: int | None = None,
        disctitle: str | None = None,
        lyricist: str | None = None,
        composer: str | None = None,
        composer_sort: str | None = None,
        arranger: str | None = None,
        track_alt: str | None = None,
        work: str | None = None,
        mb_workid: str | None = None,
        work_disambig: str | None = None,
        bpm: str | None = None,
        initial_key: str | None = None,
        **kwargs,
    ) -> None:
        self.title = title
        self.track_id = track_id
        self.release_track_id = release_track_id
        self.length = length
        self.index = index
        self.medium = medium
        self.medium_index = medium_index
        self.medium_total = medium_total
        self.disctitle = disctitle
        self.lyricist = lyricist
        self.composer = composer
        self.composer_sort = composer_sort
        self.arranger = arranger
        self.track_alt = track_alt
        self.work = work
        self.mb_workid = mb_workid
        self.work_disambig = work_disambig
        self.bpm = bpm
        self.initial_key = initial_key
        super().__init__(**kwargs)


# Structures that compose all the information for a candidate match.


class AlbumMatch(NamedTuple):
    distance: Distance
    info: AlbumInfo
    mapping: dict[Item, TrackInfo]
    extra_items: list[Item]
    extra_tracks: list[TrackInfo]


class TrackMatch(NamedTuple):
    distance: Distance
    info: TrackInfo
