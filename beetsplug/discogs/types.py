# This file is part of beets.
# Copyright 2025, Sarunas Nejus, Henry Oberholtzer.
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

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from beets.autotag.hooks import TrackInfo


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


class TracklistInfo(TypedDict):
    index: int
    index_tracks: dict[int, str]
    tracks: list[TrackInfo]
    divisions: list[str]
    next_divisions: list[str]
    mediums: list[str | None]
    medium_indices: list[str | None]
