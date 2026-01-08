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

"""Adds Discogs album search support to the autotagger. Requires the
python3-discogs-client library.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import socket
import time
import traceback
from dataclasses import asdict, dataclass, field
from functools import cache
from string import ascii_lowercase
from typing import TYPE_CHECKING

import confuse
from discogs_client import Client, Master, Release
from discogs_client.exceptions import DiscogsAPIError
from requests.exceptions import ConnectionError
from typing_extensions import NotRequired, TypedDict

import beets
import beets.ui
from beets import config
from beets.autotag.distance import string_dist
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.metadata_plugins import MetadataSourcePlugin

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from beets.library import Item

USER_AGENT = f"beets/{beets.__version__} +https://beets.io/"
API_KEY = "rAzVUQYRaoFjeBjyWuWZ"
API_SECRET = "plxtUTqoCzwxZpqdPysCwGuBSmZNdZVy"

# Exceptions that discogs_client should really handle but does not.
CONNECTION_ERRORS = (
    ConnectionError,
    socket.error,
    http.client.HTTPException,
    ValueError,  # JSON decoding raises a ValueError.
    DiscogsAPIError,
)


TRACK_INDEX_RE = re.compile(
    r"""
    (.*?)   # medium: everything before medium_index.
    (\d*?)  # medium_index: a number at the end of
            # `position`, except if followed by a subtrack index.
            # subtrack_index: can only be matched if medium
            # or medium_index have been matched, and can be
    (
        (?<=\w)\.[\w]+  # a dot followed by a string (A.1, 2.A)
      | (?<=\d)[A-Z]+   # a string that follows a number (1A, B2a)
    )?
    """,
    re.VERBOSE,
)

DISAMBIGUATION_RE = re.compile(r" \(\d+\)")


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


@dataclass
class ArtistState:
    artist: str = ""
    artists: list[str] = field(default_factory=list)
    artist_credit: str = ""
    artists_credit: list[str] = field(default_factory=list)
    artist_id: str = ""
    artists_ids: list[str] = field(default_factory=list)

    @property
    def info(self) -> ArtistInfo:
        return asdict(self)  # type: ignore[return-value]

    def clone(self) -> ArtistState:
        return ArtistState(**asdict(self))

    @classmethod
    def build(
        cls,
        plugin: DiscogsPlugin,
        given_artists: list[Artist],
        given_state: ArtistState | None = None,
        for_album_artist: bool = False,
    ) -> ArtistState:
        """Iterates through a discogs result and builds
        up the artist fields. Does not contribute to
        artist_sort as Discogs does not define that.
        """
        state = given_state.clone() if given_state else cls()

        artist = ""
        artist_anv = ""
        artists: list[str] = []
        artists_anv: list[str] = []

        feat_str: str = f" {plugin.config['featured_string'].as_str()} "
        join = ""
        featured_flag = False
        for a in given_artists:
            name = plugin.strip_disambiguation(a["name"])
            discogs_id = str(a["id"])
            anv = a.get("anv", "") or name
            role = a.get("role", "").lower()
            if name.lower() == "various":
                name = config["va_name"].as_str()
                anv = name
            if "featuring" in role:
                if not featured_flag:
                    artist += feat_str
                    artist_anv += feat_str
                    artist += name
                    artist_anv += anv
                    featured_flag = True
                else:
                    artist = cls.join_artist(artist, name, join)
                    artist_anv = cls.join_artist(artist_anv, anv, join)
            elif role and "featuring" not in role:
                continue
            else:
                artist = cls.join_artist(artist, name, join)
                artist_anv = cls.join_artist(artist_anv, anv, join)
            artists.append(name)
            artists_anv.append(anv)
            if not state.artist_id:
                state.artist_id = discogs_id
            state.artists_ids.append(discogs_id)
            join = a.get("join", "")
        cls._assign_anv(
            plugin,
            state,
            artist,
            artists,
            artist_anv,
            artists_anv,
            for_album_artist,
        )
        return state

    @staticmethod
    def join_artist(base: str, artist: str, join: str) -> str:
        # Expand the artist field
        if not base:
            base = artist
        else:
            if join:
                join = join.strip()
                if join in ";,":
                    base += f"{join} "
                else:
                    base += f" {join} "
            else:
                base += ", "
            base += artist
        return base

    @staticmethod
    def _assign_anv(
        plugin: DiscogsPlugin,
        state: ArtistState,
        artist: str,
        artists: list[str],
        artist_anv: str,
        artists_anv: list[str],
        for_album_artist: bool,
    ) -> None:
        """Assign artist and variation fields based on
        configuration settings.
        """
        use_artist_anv: bool = plugin.config["anv"]["artist"].get(bool)
        use_artistcredit_anv: bool = plugin.config["anv"]["artist_credit"].get(
            bool
        )
        use_albumartist_anv: bool = plugin.config["anv"]["album_artist"].get(
            bool
        )

        if (use_artist_anv and not for_album_artist) or (
            use_albumartist_anv and for_album_artist
        ):
            state.artist += artist_anv
            state.artists += artists_anv
        else:
            state.artist += artist
            state.artists += artists

        if use_artistcredit_anv:
            state.artist_credit += artist_anv
            state.artists_credit += artists_anv
        else:
            state.artist_credit += artist
            state.artists_credit += artists


@dataclass
class TracklistState:
    index: int = 0
    index_tracks: dict[int, str] = field(default_factory=dict)
    tracks: list[TrackInfo] = field(default_factory=list)
    divisions: list[str] = field(default_factory=list)
    next_divisions: list[str] = field(default_factory=list)
    mediums: list[str | None] = field(default_factory=list)
    medium_indices: list[str | None] = field(default_factory=list)

    @property
    def info(self) -> TracklistInfo:
        return asdict(self)  # type: ignore[return-value]

    @classmethod
    def build(
        cls,
        plugin: DiscogsPlugin,
        clean_tracklist: list[Track],
        albumartistinfo: ArtistState,
    ) -> TracklistState:
        state = cls()
        for track in clean_tracklist:
            if track["position"]:
                state.index += 1
                if state.next_divisions:
                    state.divisions += state.next_divisions
                    state.next_divisions.clear()
                track_info, medium, medium_index = plugin.get_track_info(
                    track, state.index, state.divisions, albumartistinfo
                )
                track_info.track_alt = track["position"]
                state.tracks.append(track_info)
                state.mediums.append(medium or None)
                state.medium_indices.append(medium_index or None)
            else:
                state.next_divisions.append(track["title"])
                try:
                    state.divisions.pop()
                except IndexError:
                    pass
                state.index_tracks[state.index + 1] = track["title"]
        return state


class DiscogsPlugin(MetadataSourcePlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "apikey": API_KEY,
                "apisecret": API_SECRET,
                "tokenfile": "discogs_token.json",
                "user_token": "",
                "separator": ", ",
                "index_tracks": False,
                "append_style_genre": False,
                "strip_disambiguation": True,
                "featured_string": "Feat.",
                "anv": {
                    "artist_credit": True,
                    "artist": False,
                    "album_artist": False,
                },
            }
        )
        self.config["apikey"].redact = True
        self.config["apisecret"].redact = True
        self.config["user_token"].redact = True
        self.setup()

    def setup(self, session=None) -> None:
        """Create the `discogs_client` field. Authenticate if necessary."""
        c_key = self.config["apikey"].as_str()
        c_secret = self.config["apisecret"].as_str()

        # Try using a configured user token (bypassing OAuth login).
        user_token = self.config["user_token"].as_str()
        if user_token:
            # The rate limit for authenticated users goes up to 60
            # requests per minute.
            self.discogs_client = Client(USER_AGENT, user_token=user_token)
            return

        # Get the OAuth token from a file or log in.
        try:
            with open(self._tokenfile()) as f:
                tokendata = json.load(f)
        except OSError:
            # No token yet. Generate one.
            token, secret = self.authenticate(c_key, c_secret)
        else:
            token = tokendata["token"]
            secret = tokendata["secret"]

        self.discogs_client = Client(USER_AGENT, c_key, c_secret, token, secret)

    def reset_auth(self) -> None:
        """Delete token file & redo the auth steps."""
        os.remove(self._tokenfile())
        self.setup()

    def _tokenfile(self) -> str:
        """Get the path to the JSON file for storing the OAuth token."""
        return self.config["tokenfile"].get(confuse.Filename(in_app_dir=True))

    def authenticate(self, c_key: str, c_secret: str) -> tuple[str, str]:
        # Get the link for the OAuth page.
        auth_client = Client(USER_AGENT, c_key, c_secret)
        try:
            _, _, url = auth_client.get_authorize_url()
        except CONNECTION_ERRORS as e:
            self._log.debug("connection error: {}", e)
            raise beets.ui.UserError("communication with Discogs failed")

        beets.ui.print_("To authenticate with Discogs, visit:")
        beets.ui.print_(url)

        # Ask for the code and validate it.
        code = beets.ui.input_("Enter the code:")
        try:
            token, secret = auth_client.get_access_token(code)
        except DiscogsAPIError:
            raise beets.ui.UserError("Discogs authorization failed")
        except CONNECTION_ERRORS as e:
            self._log.debug("connection error: {}", e)
            raise beets.ui.UserError("Discogs token request failed")

        # Save the token for later use.
        self._log.debug("Discogs token {}, secret {}", token, secret)
        with open(self._tokenfile(), "w") as f:
            json.dump({"token": token, "secret": secret}, f)

        return token, secret

    def candidates(
        self, items: Sequence[Item], artist: str, album: str, va_likely: bool
    ) -> Iterable[AlbumInfo]:
        return self.get_albums(f"{artist} {album}" if va_likely else album)

    def get_track_from_album(
        self, album_info: AlbumInfo, compare: Callable[[TrackInfo], float]
    ) -> TrackInfo | None:
        """Return the best matching track of the release."""
        scores_and_tracks = [(compare(t), t) for t in album_info.tracks]
        score, track_info = min(scores_and_tracks, key=lambda x: x[0])
        if score > 0.3:
            return None

        track_info["artist"] = album_info.artist
        track_info["artist_id"] = album_info.artist_id
        track_info["album"] = album_info.album
        return track_info

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        albums = self.candidates([item], artist, title, False)

        def compare_func(track_info: TrackInfo) -> float:
            return string_dist(track_info.title, title)

        tracks = (self.get_track_from_album(a, compare_func) for a in albums)
        return list(filter(None, tracks))

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        """Fetches an album by its Discogs ID and returns an AlbumInfo object
        or None if the album is not found.
        """
        self._log.debug("Searching for release {}", album_id)

        discogs_id = self._extract_id(album_id)

        if not discogs_id:
            return None

        result = Release(self.discogs_client, {"id": discogs_id})
        # Try to obtain title to verify that we indeed have a valid Release
        try:
            getattr(result, "title")
        except DiscogsAPIError as e:
            if e.status_code != 404:
                self._log.debug(
                    "API Error: {} (query: {})",
                    e,
                    result.data["resource_url"],
                )
                if e.status_code == 401:
                    self.reset_auth()
                    return self.album_for_id(album_id)
            return None
        except CONNECTION_ERRORS:
            self._log.debug("Connection error in album lookup", exc_info=True)
            return None
        return self.get_album_info(result)

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        if album := self.album_for_id(track_id):
            for track in album.tracks:
                if track.track_id == track_id:
                    return track
        return None

    def get_albums(self, query: str) -> Iterable[AlbumInfo]:
        """Returns a list of AlbumInfo objects for a discogs search query."""
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        query = re.sub(r"(?u)\W+", " ", query)
        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(r"(?i)\b(CD|disc|vinyl)\s*\d+", "", query)

        try:
            results = self.discogs_client.search(query, type="release")
            results.per_page = self.config["search_limit"].get()
            releases = results.page(1)
        except CONNECTION_ERRORS:
            self._log.debug(
                "Communication error while searching for {0!r}",
                query,
                exc_info=True,
            )
            return []
        return filter(None, map(self.get_album_info, releases))

    @cache
    def get_master_year(self, master_id: str) -> int | None:
        """Fetches a master release given its Discogs ID and returns its year
        or None if the master release is not found.
        """
        self._log.debug("Getting master release {}", master_id)
        result = Master(self.discogs_client, {"id": master_id})

        try:
            return result.fetch("year")
        except DiscogsAPIError as e:
            if e.status_code != 404:
                self._log.debug(
                    "API Error: {} (query: {})",
                    e,
                    result.data["resource_url"],
                )
                if e.status_code == 401:
                    self.reset_auth()
                    return self.get_master_year(master_id)
            return None
        except CONNECTION_ERRORS:
            self._log.debug(
                "Connection error in master release lookup", exc_info=True
            )
            return None

    @staticmethod
    def get_media_and_albumtype(
        formats: list[ReleaseFormat] | None,
    ) -> tuple[str | None, str | None]:
        media = albumtype = None
        if formats and (first_format := formats[0]):
            if descriptions := first_format["descriptions"]:
                albumtype = ", ".join(descriptions)
            media = first_format["name"]

        return media, albumtype

    def get_album_info(self, result: Release) -> AlbumInfo | None:
        """Returns an AlbumInfo object for a discogs Release object."""
        # Explicitly reload the `Release` fields, as they might not be yet
        # present if the result is from a `discogs_client.search()`.
        if not result.data.get("artists"):
            try:
                result.refresh()
            except CONNECTION_ERRORS:
                self._log.debug(
                    "Connection error in release lookup: {0}",
                    result,
                )
                return None

        # Sanity check for required fields. The list of required fields is
        # defined at Guideline 1.3.1.a, but in practice some releases might be
        # lacking some of these fields. This function expects at least:
        # `artists` (>0), `title`, `id`, `tracklist` (>0)
        # https://www.discogs.com/help/doc/submission-guidelines-general-rules
        if not all(
            [
                result.data.get(k)
                for k in ["artists", "title", "id", "tracklist"]
            ]
        ):
            self._log.warning("Release does not contain the required fields")
            return None

        artist_data = [a.data for a in result.artists]
        # Information for the album artist
        albumartist = ArtistState.build(
            self, artist_data, for_album_artist=True
        )

        album = re.sub(r" +", " ", result.title)
        album_id = result.data["id"]
        # Use `.data` to access the tracklist directly instead of the
        # convenient `.tracklist` property, which will strip out useful artist
        # information and leave us with skeleton `Artist` objects that will
        # each make an API call just to get the same data back.
        tracks = self.get_tracks(
            result.data["tracklist"], ArtistState.build(self, artist_data)
        )

        # Extract information for the optional AlbumInfo fields, if possible.
        va = albumartist.artist == config["va_name"].as_str()
        year = result.data.get("year")
        mediums = [t["medium"] for t in tracks]
        country = result.data.get("country")
        data_url = result.data.get("uri")
        style = self.format(result.data.get("styles"))
        base_genre = self.format(result.data.get("genres"))

        if self.config["append_style_genre"] and style:
            genre = self.config["separator"].as_str().join([base_genre, style])
        else:
            genre = base_genre

        discogs_albumid = self._extract_id(result.data.get("uri"))

        # Extract information for the optional AlbumInfo fields that are
        # contained on nested discogs fields.
        media, albumtype = self.get_media_and_albumtype(
            result.data.get("formats")
        )

        label = catalogno = labelid = None
        if result.data.get("labels"):
            label = self.strip_disambiguation(
                result.data["labels"][0].get("name")
            )
            catalogno = result.data["labels"][0].get("catno")
            labelid = result.data["labels"][0].get("id")

        cover_art_url = self.select_cover_art(result)

        # Additional cleanups
        # (catalog number, media, disambiguation).
        if catalogno == "none":
            catalogno = None
        # Explicitly set the `media` for the tracks, since it is expected by
        # `autotag.apply_metadata`, and set `medium_total`.
        for track in tracks:
            track.media = media
            track.medium_total = mediums.count(track.medium)
            # Discogs does not have track IDs. Invent our own IDs as proposed
            # in #2336.
            track.track_id = f"{album_id}-{track.track_alt}"
            track.data_url = data_url
            track.data_source = "Discogs"

        # Retrieve master release id (returns None if there isn't one).
        master_id = result.data.get("master_id")
        # Assume `original_year` is equal to `year` for releases without
        # a master release, otherwise fetch the master release.
        original_year = self.get_master_year(master_id) if master_id else year

        return AlbumInfo(
            album=album,
            album_id=album_id,
            **albumartist.info,  # Unpacks values to satisfy the keyword arguments
            tracks=tracks,
            albumtype=albumtype,
            va=va,
            year=year,
            label=label,
            mediums=len(set(mediums)),
            releasegroup_id=master_id,
            catalognum=catalogno,
            country=country,
            style=style,
            genre=genre,
            media=media,
            original_year=original_year,
            data_source=self.data_source,
            data_url=data_url,
            discogs_albumid=discogs_albumid,
            discogs_labelid=labelid,
            discogs_artistid=albumartist.artist_id,
            cover_art_url=cover_art_url,
        )

    def select_cover_art(self, result: Release) -> str | None:
        """Returns the best candidate image, if any, from a Discogs `Release` object."""
        if result.data.get("images") and len(result.data.get("images")) > 0:
            # The first image in this list appears to be the one displayed first
            # on the release page - even if it is not flagged as `type: "primary"` - and
            # so it is the best candidate for the cover art.
            return result.data.get("images")[0].get("uri")

        return None

    def format(self, classification: Iterable[str]) -> str | None:
        if classification:
            return (
                self.config["separator"].as_str().join(sorted(classification))
            )
        else:
            return None

    def get_tracks(
        self,
        tracklist: list[Track],
        albumartistinfo: ArtistState,
    ) -> list[TrackInfo]:
        """Returns a list of TrackInfo objects for a discogs tracklist."""
        try:
            clean_tracklist: list[Track] = self._coalesce_tracks(tracklist)
        except Exception as exc:
            # FIXME: this is an extra precaution for making sure there are no
            # side effects after #2222. It should be removed after further
            # testing.
            self._log.debug("{}", traceback.format_exc())
            self._log.error("uncaught exception in _coalesce_tracks: {}", exc)
            clean_tracklist = tracklist
        t = TracklistState.build(self, clean_tracklist, albumartistinfo)
        # Fix up medium and medium_index for each track. Discogs position is
        # unreliable, but tracks are in order.
        medium = None
        medium_count, index_count, side_count = 0, 0, 0
        sides_per_medium = 1

        # If a medium has two sides (ie. vinyl or cassette), each pair of
        # consecutive sides should belong to the same medium.
        if all([medium is not None for medium in t.mediums]):
            m = sorted(
                {medium.lower() if medium else "" for medium in t.mediums}
            )
            # If all track.medium are single consecutive letters, assume it is
            # a 2-sided medium.
            if "".join(m) in ascii_lowercase:
                sides_per_medium = 2

        for i, track in enumerate(t.tracks):
            # Handle special case where a different medium does not indicate a
            # new disc, when there is no medium_index and the ordinal of medium
            # is not sequential. For example, I, II, III, IV, V. Assume these
            # are the track index, not the medium.
            # side_count is the number of mediums or medium sides (in the case
            # of two-sided mediums) that were seen before.
            medium_str = t.mediums[i]
            medium_index = t.medium_indices[i]
            medium_is_index = (
                medium_str
                and not medium_index
                and (
                    len(medium_str) != 1
                    or
                    # Not within standard incremental medium values (A, B, C, ...).
                    ord(medium_str) - 64 != side_count + 1
                )
            )

            if not medium_is_index and medium != medium_str:
                side_count += 1
                if sides_per_medium == 2:
                    if side_count % sides_per_medium:
                        # Two-sided medium changed. Reset index_count.
                        index_count = 0
                        medium_count += 1
                else:
                    # Medium changed. Reset index_count.
                    medium_count += 1
                    index_count = 0
                medium = medium_str

            index_count += 1
            medium_count = 1 if medium_count == 0 else medium_count
            track.medium, track.medium_index = medium_count, index_count

        # Get `disctitle` from Discogs index tracks. Assume that an index track
        # before the first track of each medium is a disc title.
        for track in t.tracks:
            if track.medium_index == 1:
                if track.index in t.index_tracks:
                    disctitle = t.index_tracks[track.index]
                else:
                    disctitle = None
            track.disctitle = disctitle

        return t.tracks

    def _coalesce_tracks(self, raw_tracklist: list[Track]) -> list[Track]:
        """Pre-process a tracklist, merging subtracks into a single track. The
        title for the merged track is the one from the previous index track,
        if present; otherwise it is a combination of the subtracks titles.
        """
        # Pre-process the tracklist, trying to identify subtracks.

        subtracks: list[Track] = []
        tracklist: list[Track] = []
        prev_subindex = ""
        for track in raw_tracklist:
            # Regular subtrack (track with subindex).
            if track["position"]:
                _, _, subindex = self.get_track_index(track["position"])
                if subindex:
                    if subindex.rjust(len(raw_tracklist)) > prev_subindex:
                        # Subtrack still part of the current main track.
                        subtracks.append(track)
                    else:
                        # Subtrack part of a new group (..., 1.3, *2.1*, ...).
                        self._add_merged_subtracks(tracklist, subtracks)
                        subtracks = [track]
                    prev_subindex = subindex.rjust(len(raw_tracklist))
                    continue

            # Index track with nested sub_tracks.
            if not track["position"] and "sub_tracks" in track:
                # Append the index track, assuming it contains the track title.
                tracklist.append(track)
                self._add_merged_subtracks(tracklist, track["sub_tracks"])
                continue

            # Regular track or index track without nested sub_tracks.
            if subtracks:
                self._add_merged_subtracks(tracklist, subtracks)
                subtracks = []
                prev_subindex = ""
            tracklist.append(track)

        # Merge and add the remaining subtracks, if any.
        if subtracks:
            self._add_merged_subtracks(tracklist, subtracks)

        return tracklist

    def _add_merged_subtracks(
        self,
        tracklist: list[Track],
        subtracks: list[Track],
    ) -> None:
        """Modify `tracklist` in place, merging a list of `subtracks` into
        a single track into `tracklist`."""
        # Calculate position based on first subtrack, without subindex.
        idx, medium_idx, sub_idx = self.get_track_index(
            subtracks[0]["position"]
        )
        position = f"{idx or ''}{medium_idx or ''}"

        if tracklist and not tracklist[-1]["position"]:
            # Assume the previous index track contains the track title.
            if sub_idx:
                # "Convert" the track title to a real track, discarding the
                # subtracks assuming they are logical divisions of a
                # physical track (12.2.9 Subtracks).
                tracklist[-1]["position"] = position
            else:
                # Promote the subtracks to real tracks, discarding the
                # index track, assuming the subtracks are physical tracks.
                index_track = tracklist.pop()
                # Fix artists when they are specified on the index track.
                if index_track.get("artists"):
                    for subtrack in subtracks:
                        if not subtrack.get("artists"):
                            subtrack["artists"] = index_track["artists"]
                # Concatenate index with track title when index_tracks
                # option is set
                if self.config["index_tracks"]:
                    for subtrack in subtracks:
                        subtrack["title"] = (
                            f"{index_track['title']}: {subtrack['title']}"
                        )
                tracklist.extend(subtracks)
        else:
            # Merge the subtracks, pick a title, and append the new track.
            track = subtracks[0].copy()
            track["title"] = " / ".join([t["title"] for t in subtracks])
            tracklist.append(track)

    def strip_disambiguation(self, text: str) -> str:
        """Removes discogs specific disambiguations from a string.
        Turns 'Label Name (5)' to 'Label Name' or 'Artist (1) & Another Artist (2)'
        to 'Artist & Another Artist'. Does nothing if strip_disambiguation is False."""
        if not self.config["strip_disambiguation"]:
            return text
        return DISAMBIGUATION_RE.sub("", text)

    def get_track_info(
        self,
        track: Track,
        index: int,
        divisions: list[str],
        albumartistinfo: ArtistState,
    ) -> tuple[TrackInfo, str | None, str | None]:
        """Returns a TrackInfo object for a discogs track."""

        artistinfo = albumartistinfo.clone()

        title = track["title"]
        if self.config["index_tracks"]:
            prefix = ", ".join(divisions)
            if prefix:
                title = f"{prefix}: {title}"
        track_id = None
        medium, medium_index, _ = self.get_track_index(track["position"])

        # If artists are found on the track, we will use those instead
        if artists := track.get("artists", []):
            artistinfo = ArtistState.build(self, artists)

        length = self.get_track_length(track["duration"])

        # Add featured artists
        if extraartists := track.get("extraartists", []):
            artistinfo = ArtistState.build(self, extraartists, artistinfo)

        return (
            TrackInfo(
                title=title,
                track_id=track_id,
                **artistinfo.info,
                length=length,
                index=index,
            ),
            medium,
            medium_index,
        )

    @staticmethod
    def get_track_index(
        position: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Returns the medium, medium index and subtrack index for a discogs
        track position."""
        # Match the standard Discogs positions (12.2.9), which can have several
        # forms (1, 1-1, A1, A1.1, A1a, ...).
        medium = index = subindex = None
        if match := TRACK_INDEX_RE.fullmatch(position.upper()):
            medium, index, subindex = match.groups()

            if subindex and subindex.startswith("."):
                subindex = subindex[1:]

        return medium or None, index or None, subindex or None

    def get_track_length(self, duration: str) -> int | None:
        """Returns the track length in seconds for a discogs duration."""
        try:
            length = time.strptime(duration, "%M:%S")
        except ValueError:
            return None
        return length.tm_min * 60 + length.tm_sec
