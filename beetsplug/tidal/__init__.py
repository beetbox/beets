from __future__ import annotations

import os
import re
from functools import cached_property
from typing import TYPE_CHECKING, overload

import confuse

from beets import ui
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.logging import getLogger
from beets.metadata_plugins import MetadataSourcePlugin
from beetsplug.tidal.api_types import TrackDocument

from .api import TidalAPI, TidalSession
from .authenticate import ui_auth_flow

if TYPE_CHECKING:
    import optparse
    from collections.abc import Iterable, Sequence

    from beets.library.models import Item, Library

    from .api_types import (
        AlbumAttributes,
        ResourceIdentifier,
        TidalAlbum,
        TidalArtist,
        TidalTrack,
        TrackAttributes,
    )


log = getLogger("beets.tidal")


class TidalPlugin(MetadataSourcePlugin):
    """Tidal metadata plugin.

    Allows to fetch metadata candidates from tidal.
    """

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "client_id": "mcjmpl1bPATJXcBT",
                "tokenfile": "tidal_token.json",
            }
        )
        self.config["client_id"].redact = True

        # We need to be authenticated if plugin is used to fetch metadata
        # otherwise the import cannot run.
        self.register_listener("import_begin", self.require_authentication)

    @cached_property
    def api(self) -> TidalAPI:
        return TidalAPI(
            TidalSession(
                client_id=self.config["client_id"].as_str(),
                token_path=self._tokenfile(),
            )
        )

    def _tokenfile(self) -> str:
        """Creates the token file if it doesn't exist"""
        return self.config["tokenfile"].get(confuse.Filename(in_app_dir=True))

    def require_authentication(self):
        if not os.path.isfile(self._tokenfile()):
            raise ui.UserError(
                "Please login to TIDAL"
                " using `beets tidal --auth` or disable tidal plugin"
            )

    def commands(self) -> list[ui.Subcommand]:
        tidal_cmd = ui.Subcommand(
            "tidal", help="Tidal metadata plugin commands"
        )
        tidal_cmd.parser.add_option(
            "-a",
            "--auth",
            action="store_true",
            help="Authenticate and login to Tidal",
            default=False,
        )

        def func(lib: Library, opts: optparse.Values, args: list[str]):
            if opts.auth:
                token = ui_auth_flow(self.config["client_id"].as_str())
                token.save_to(self._tokenfile())
                ui.print_(f"Saved tidal token in {self._tokenfile()}")
            else:
                tidal_cmd.print_help()

        tidal_cmd.func = func

        return [tidal_cmd]

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        if not (tidal_id := self._extract_id(album_id)):
            return None

        if album := list(self.search_albums_by_ids(ids=[tidal_id])):
            return album[0]

        log.warning("Could not find album:{0}", tidal_id)
        return None

    def albums_for_ids(self, ids: Iterable[str]) -> Iterable[AlbumInfo | None]:
        yield from self.search_albums_by_ids(ids=ids)

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        if not (tidal_id := self._extract_id(track_id)):
            return None

        if track := list(self.search_tracks_by_ids(ids=[tidal_id])):
            return track[0]

        log.warning("Could not find track:{0}", tidal_id)
        return None

    def tracks_for_ids(self, ids: Iterable[str]) -> Iterable[TrackInfo | None]:
        yield from self.search_tracks_by_ids(ids=ids)

    def candidates(
        self, items: Sequence[Item], artist: str, album: str, va_likely: bool
    ) -> Iterable[AlbumInfo]:
        breakpoint()
        return []

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        breakpoint()
        return []

    # ---------------------------------- Search ---------------------------------- #

    @overload
    def search_tracks_by_ids(
        self, *, ids: Iterable[str]
    ) -> Iterable[TrackInfo | None]: ...

    @overload
    def search_tracks_by_ids(
        self, *, isrcs: Iterable[str]
    ) -> Iterable[TrackInfo | None]: ...

    def search_tracks_by_ids(
        self,
        ids: Iterable[str] | None = None,
        isrcs: Iterable[str] | None = None,
    ) -> Iterable[TrackInfo | None]:
        tidal_ids = list(map(self._extract_id, ids or []))
        isrcs = list(isrcs or [])

        tracks_doc = self.api.get_tracks(
            ids=list(filter(None, tidal_ids)),
            isrcs=isrcs,
            include=["artists"],
        )
        track_lookup: dict[str, TidalTrack] = {
            item["id"]: item
            for item in tracks_doc.get("data", [])
            if item["type"] == "tracks"
        }
        artist_lookup: dict[str, TidalArtist] = {
            item["id"]: item
            for item in tracks_doc.get("included", [])
            if item["type"] == "artists"
        }

        # Yield for IDs first
        for tidal_id in tidal_ids:
            if tidal_id is not None and (track := track_lookup.get(tidal_id)):
                yield self._get_track_info(track, artist_lookup=artist_lookup)
            else:
                yield None

        # Then yield for ISRCs (matching by ISRC field in tracks)
        for isrc in isrcs:
            track = next(
                (t for t in track_lookup.values() if t.get("isrc") == isrc),
                None,
            )
            if track:
                yield self._get_track_info(track, artist_lookup=artist_lookup)
            else:
                yield None

    @overload
    def search_albums_by_ids(
        self, *, ids: Iterable[str]
    ) -> Iterable[AlbumInfo | None]: ...

    @overload
    def search_albums_by_ids(
        self, *, barcode_ids: Iterable[str]
    ) -> Iterable[AlbumInfo | None]: ...

    def search_albums_by_ids(
        self,
        ids: Iterable[str] | None = None,
        barcode_ids: Iterable[str] | None = None,
    ) -> Iterable[AlbumInfo | None]:
        tidal_ids = list(map(self._extract_id, ids or []))
        barcode_ids = list(barcode_ids or [])

        albums_doc = self.api.get_albums(
            ids=list(filter(None, tidal_ids)),
            barcode_ids=barcode_ids,
            include=["items.artists", "artists"],
        )
        album_lookup: dict[str, TidalAlbum] = {
            item["id"]: item
            for item in albums_doc.get("data", [])
            if item["type"] == "albums"
        }
        track_lookup: dict[str, TidalTrack] = {
            item["id"]: item
            for item in albums_doc.get("included", [])
            if item["type"] == "tracks"
        }
        artist_lookup: dict[str, TidalArtist] = {
            item["id"]: item
            for item in albums_doc.get("included", [])
            if item["type"] == "artists"
        }

        # Yield for IDs first
        for tidal_id in tidal_ids:
            if tidal_id is not None and (album := album_lookup.get(tidal_id)):
                yield self._get_album_info(
                    album,
                    track_lookup=track_lookup,
                    artist_lookup=artist_lookup,
                )
            else:
                yield None
        # Then yield for ISRCs (matching by ISRC field in tracks)
        for barcode in barcode_ids:
            album = next(
                (
                    a
                    for a in album_lookup.values()
                    if a.get("barcodeId") == barcode
                ),
                None,
            )
            if album:
                yield self._get_album_info(
                    album,
                    track_lookup=track_lookup,
                    artist_lookup=artist_lookup,
                )
            else:
                yield None

    @staticmethod
    def _item_queries(item: Item) -> Iterable[str]:
        """Search query for item.

        At the moment we only search using the title but this
        is designed to be extendable.
        """
        yield item.title

    # ---------------------------------- Parsing --------------------------------- #

    def _get_album_info(
        self,
        album: TidalAlbum,
        track_lookup: dict[str, TidalTrack],
        artist_lookup: dict[str, TidalArtist],
    ) -> AlbumInfo:

        track_infos: list[TrackInfo] = []
        for i, track_rel in enumerate(
            album["relationships"]["items"]["data"], start=1
        ):
            if track := track_lookup.get(track_rel["id"]):
                track_info = self._get_track_info(track, artist_lookup)
                track_info.index = i
                track_infos.append(track_info)

        artist_names, artist_ids = self._extract_artists(
            album["relationships"]["artists"]["data"],
            artist_lookup,
        )
        release = self._extract_release_date(album["attributes"])
        return AlbumInfo(
            # Identifier
            data_source=self.data_source,
            album_id=album["id"],
            artists_ids=artist_ids,
            data_url=self._extract_data_url(album["attributes"]),
            barcode=album["attributes"]["barcodeId"],
            # Meta
            album=self._extract_title(album["attributes"]),
            tracks=track_infos,
            artist=", ".join(artist_names),
            artists=artist_names,
            duration=self._duration_to_seconds(album["attributes"]["duration"]),
            albumtype=album["attributes"]["albumType"],
            label=self._extract_label(album["attributes"]),
            year=release[0] if release else None,
            month=release[1] if release else None,
            day=release[2] if release else None,
        )

    def _get_track_info(
        self,
        track: TidalTrack,
        artist_lookup: dict[str, TidalArtist],
    ) -> TrackInfo:
        # Artists are sorted in the track relationship
        artist_names, artist_ids = self._extract_artists(
            track["relationships"]["artists"]["data"],
            artist_lookup,
        )

        return TrackInfo(
            # Identifier
            data_source=self.data_source,
            track_id=track["id"],
            artists_ids=artist_ids,
            data_url=self._extract_data_url(track["attributes"]),
            # Meta
            title=self._extract_title(track["attributes"]),
            isrc=track["attributes"]["isrc"],
            artist=", ".join(artist_names),
            artists=artist_names,
            duration=self._duration_to_seconds(track["attributes"]["duration"]),
            label=self._extract_label(track["attributes"]),
        )

    @staticmethod
    def _extract_artists(
        artist_relationships: list[ResourceIdentifier],
        artist_lookup: dict[str, TidalArtist],
    ) -> tuple[list[str], list[str]]:
        """Extract artists from a relatninship.

        Needed as artists are sorted in the track relationship in order
        but in the included part of the response the
        """
        artist_names = []
        artist_ids = []
        for artist_rel in artist_relationships:
            if artist := artist_lookup.get(artist_rel["id"]):
                artist_ids.append(artist["id"])
                artist_names.append(artist["attributes"]["name"])
            else:
                log.warning(
                    "Artist with id %s not found in lookup",
                    artist_rel["id"],
                )

        return artist_names, artist_ids

    @staticmethod
    def _extract_title(attributes: AlbumAttributes | TrackAttributes):
        """
        Tidal normally amends the version string at the
        of the title. We do the same to be consistent
        with the tidal web ui.
        """
        if version := attributes.get("version"):
            return f"{attributes['title']} ({version})"
        else:
            return attributes["title"]

    @staticmethod
    def _extract_data_url(
        attributes: AlbumAttributes | TrackAttributes,
    ) -> str | None:
        if external_links := attributes.get("externalLinks"):
            return external_links[0].get("href")
        return None

    @staticmethod
    def _duration_to_seconds(duration: str) -> int:
        """Convert ISO 8601 duration to seconds. E.g. 'PT15M2S' -> 902."""
        match = ISO_8601_RE.match(duration)
        if not match:
            raise ValueError(f"Invalid ISO 8601 duration: {duration}")

        parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
        return (
            parts["seconds"]
            + parts["minutes"] * 60
            + parts["hours"] * 3600
            + parts["days"] * 86400
            + parts["months"] * 30 * 86400
            + parts["years"] * 365 * 86400
        )

    @staticmethod
    def _extract_label(
        attributes: AlbumAttributes | TrackAttributes,
    ) -> str | None:
        if copyright := attributes.get("copyright"):
            return copyright["text"]
        return None

    @staticmethod
    def _extract_release_date(
        attributes: AlbumAttributes,
    ) -> tuple[int, int, int] | None:
        """Returns year, month, day from iso YYYY-MM-DD"""

        if release_date := attributes.get("releaseDate"):
            parts = release_date.split("-")
            if len(parts) != 3:
                return None
            return int(parts[0]), int(parts[1]), int(parts[2])
        return None


ISO_8601_RE = re.compile(
    r"^P"
    r"(?:(?P<years>\d+)Y)?"
    r"(?:(?P<months>\d+)M)?"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)
