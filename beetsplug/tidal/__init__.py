from __future__ import annotations

import itertools
import os
import re
import time
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar, overload

import confuse

from beets import ui
from beets.autotag import AlbumInfo, TrackInfo
from beets.dbcore import types
from beets.exceptions import UserError
from beets.logging import getLogger
from beets.metadata_plugins import MetadataSourcePlugin

from .api import TidalAPI

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
    item_types: ClassVar[dict[str, types.Type]] = {
        "tidal_track_id": types.INTEGER,
        "tidal_album_id": types.INTEGER,
        "tidal_artist_id": types.INTEGER,
        "tidal_track_popularity": types.INTEGER,
        "tidal_album_popularity": types.INTEGER,
        "tidal_updated": types.DATE,
    }

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {"client_id": "mcjmpl1bPATJXcBT", "tokenfile": "tidal_token.json"}
        )
        self.config["client_id"].redact = True

        # We need to be authenticated if plugin is used to fetch metadata
        # otherwise the import cannot run.
        self.register_listener("import_begin", self.require_authentication)

    @cached_property
    def api(self) -> TidalAPI:
        return TidalAPI(
            client_id=self.config["client_id"].as_str(),
            token_path=self._tokenfile(),
        )

    def _tokenfile(self) -> str:
        """Return the configured path to the token file in the app directory."""
        return self.config["tokenfile"].get(confuse.Filename(in_app_dir=True))

    def require_authentication(self):
        if not os.path.isfile(self._tokenfile()):
            raise UserError(
                "Please login to TIDAL"
                " using `beet tidal --auth` or disable tidal plugin"
            )

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        if not (tidal_id := self._extract_id(album_id)):
            return None

        if album := list(self.search_albums_by_ids(tidal_ids=[tidal_id])):
            return album[0]

        log.warning("Could not find album:{0}", tidal_id)
        return None

    def albums_for_ids(self, ids: Iterable[str]) -> Iterable[AlbumInfo | None]:
        yield from self.search_albums_by_ids(ids=ids)

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        if not (tidal_id := self._extract_id(track_id)):
            return None

        if track := list(self.search_tracks_by_ids(tidal_ids=[tidal_id])):
            return track[0]

        log.warning("Could not find track:{0}", tidal_id)
        return None

    def tracks_for_ids(self, ids: Iterable[str]) -> Iterable[TrackInfo | None]:
        yield from self.search_tracks_by_ids(ids=ids)

    def candidates(
        self, items: Sequence[Item], artist: str, album: str, va_likely: bool
    ) -> Iterable[AlbumInfo]:
        candidates: list[AlbumInfo] = []
        # Tidal allows to lookup via isrc and barcode (nice!)
        # We just return early here as a lookup via isrc should
        # return a 100% match
        barcodes: list[str] = list(
            filter(None, set(i.get("barcode") for i in items))
        )
        if barcodes and (
            candidates := list(
                filter(None, self.search_albums_by_ids(barcode_ids=barcodes))
            )
        ):
            return candidates

        for query in self._album_queries(items):
            candidates += self.search_albums_by_query(query)

        log.debug("Found {0} candidates", len(candidates))
        return candidates

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        candidates: list[TrackInfo] = []
        # Tidal allows to lookup via isrc and barcode (nice!)
        # We just return early here as a lookup via isrc should
        # return a 100% match
        if isrc := item.get("isrc"):
            if candidates := list(
                filter(None, self.search_tracks_by_ids(isrcs=[isrc]))
            ):
                return candidates

        for query in self._item_queries(item):
            candidates += self.search_tracks_by_query(query)

        log.debug("Found {0} candidates", len(candidates))
        return candidates

    @staticmethod
    def _item_queries(item: Item) -> Iterable[str]:
        """Search queries for items."""
        yield item.title

        if item.artist:
            yield f"{item.artist} {item.title}"

    @staticmethod
    def _album_queries(items: Sequence[Item]) -> Iterable[str]:
        """Search queries for albums."""

        album_names = set(i.album for i in items)
        artist_names = set(i.artist for i in items)

        for album, artist in itertools.product(album_names, artist_names):
            yield f"{artist} {album}"

    def search_tracks_by_query(self, query: str) -> Iterable[TrackInfo]:
        """Search for tracks given a string query."""
        search_doc = self.api.search_results(query, include=["tracks.artists"])
        track_by_id: dict[str, TidalTrack] = {
            item["id"]: item
            for item in search_doc.get("included", [])
            if item["type"] == "tracks"
        }
        artist_by_id: dict[str, TidalArtist] = {
            item["id"]: item
            for item in search_doc.get("included", [])
            if item["type"] == "artists"
        }
        for track_rel in search_doc["data"]["relationships"]["tracks"]["data"]:
            if track := track_by_id.get(track_rel["id"]):
                yield self._get_track_info(track, artist_by_id=artist_by_id)
            else:
                log.warning(
                    "Track with id {0} not found in lookup", track_rel["id"]
                )

    def search_albums_by_query(self, query: str) -> Iterable[AlbumInfo]:
        """Search for album given a string query."""
        search_doc = self.api.search_results(
            query,
            include=["albums"],
            # include="albums.items.artists" <- not supported
            # This is a bit inconvenient, but we fetch the items and artists
            # for all albums separately.
        )
        album_ids = [
            album_rel["id"]
            for album_rel in search_doc["data"]["relationships"]["albums"][
                "data"
            ]
        ]
        yield from filter(None, self.search_albums_by_ids(tidal_ids=album_ids))

    @overload
    def search_tracks_by_ids(
        self, *, ids: Iterable[str]
    ) -> Iterable[TrackInfo | None]: ...

    @overload
    def search_tracks_by_ids(
        self, *, tidal_ids: Iterable[str]
    ) -> Iterable[TrackInfo | None]: ...

    @overload
    def search_tracks_by_ids(
        self, *, isrcs: Iterable[str]
    ) -> Iterable[TrackInfo | None]: ...

    def search_tracks_by_ids(
        self,
        ids: Iterable[str] | None = None,
        tidal_ids: Iterable[str] | None = None,
        isrcs: Iterable[str] | None = None,
    ) -> Iterable[TrackInfo | None]:
        _ids: list[str | None] = list(tidal_ids or [])
        isrcs = list(isrcs or [])
        if ids:
            _ids = list(map(self._extract_id, ids))

        tracks_doc = self.api.get_tracks(
            ids=list(filter(None, _ids)), isrcs=isrcs, include=["artists"]
        )
        track_by_id: dict[str, TidalTrack] = {
            item["id"]: item
            for item in tracks_doc.get("data", [])
            if item["type"] == "tracks"
        }
        artist_by_id: dict[str, TidalArtist] = {
            item["id"]: item
            for item in tracks_doc.get("included", [])
            if item["type"] == "artists"
        }

        for _id in _ids:
            if _id is not None and (track := track_by_id.get(_id)):
                yield self._get_track_info(track, artist_by_id=artist_by_id)
            else:
                yield None

        if isrcs:
            isrc_to_track: dict[str, TidalTrack] = {
                t["attributes"]["isrc"]: t for t in track_by_id.values()
            }

            for isrc in isrcs:
                if track := isrc_to_track.get(isrc):
                    yield self._get_track_info(track, artist_by_id=artist_by_id)
                else:
                    yield None

    @overload
    def search_albums_by_ids(
        self, *, ids: Iterable[str]
    ) -> Iterable[AlbumInfo | None]: ...

    @overload
    def search_albums_by_ids(
        self, *, tidal_ids: Iterable[str]
    ) -> Iterable[AlbumInfo | None]: ...

    @overload
    def search_albums_by_ids(
        self, *, barcode_ids: Iterable[str]
    ) -> Iterable[AlbumInfo | None]: ...

    def search_albums_by_ids(
        self,
        ids: Iterable[str] | None = None,
        tidal_ids: Iterable[str] | None = None,
        barcode_ids: Iterable[str] | None = None,
    ) -> Iterable[AlbumInfo | None]:
        _ids: list[str | None] = list(tidal_ids or [])
        barcode_ids = list(barcode_ids or [])
        if ids:
            _ids = list(map(self._extract_id, ids))

        albums_doc = self.api.get_albums(
            ids=list(filter(None, _ids)),
            barcode_ids=barcode_ids,
            include=["items.artists", "artists"],
        )
        album_by_id: dict[str, TidalAlbum] = {
            item["id"]: item
            for item in albums_doc.get("data", [])
            if item["type"] == "albums"
        }
        track_by_id: dict[str, TidalTrack] = {
            item["id"]: item
            for item in albums_doc.get("included", [])
            if item["type"] == "tracks"
        }
        artist_by_id: dict[str, TidalArtist] = {
            item["id"]: item
            for item in albums_doc.get("included", [])
            if item["type"] == "artists"
        }

        for _id in _ids:
            if _id is not None and (album := album_by_id.get(_id)):
                yield self._get_album_info(
                    album, track_by_id=track_by_id, artist_by_id=artist_by_id
                )
            else:
                yield None

        if barcode_ids:
            barcode_to_album: dict[str, TidalAlbum] = {
                a["attributes"]["barcodeId"]: a for a in album_by_id.values()
            }

            for barcode in barcode_ids:
                if album := barcode_to_album.get(barcode):
                    yield self._get_album_info(
                        album,
                        track_by_id=track_by_id,
                        artist_by_id=artist_by_id,
                    )
                else:
                    yield None

    def _get_album_info(
        self,
        album: TidalAlbum,
        track_by_id: dict[str, TidalTrack],
        artist_by_id: dict[str, TidalArtist],
    ) -> AlbumInfo:
        track_infos: list[TrackInfo] = []
        for i, track_rel in enumerate(
            album["relationships"]["items"]["data"], start=1
        ):
            if track := track_by_id.get(track_rel["id"]):
                track_info = self._get_track_info(track, artist_by_id)
                track_info.index = i
                track_infos.append(track_info)

        artist_names, artist_ids = self._parse_artists(
            album["relationships"]["artists"]["data"], artist_by_id
        )
        date_parts = self._parse_release_date(album["attributes"])
        return AlbumInfo(
            # Identifier
            data_source=self.data_source,
            album_id=album["id"],
            artists_ids=artist_ids,
            data_url=self._parse_data_url(album["attributes"]),
            barcode=album["attributes"]["barcodeId"],
            # Meta
            album=self._parse_title(album["attributes"]),
            tracks=track_infos,
            artist=", ".join(artist_names),
            artists=artist_names,
            duration=self._duration_to_seconds(album["attributes"]["duration"]),
            albumtype=album["attributes"]["albumType"],
            label=self._parse_label(album["attributes"]),
            year=date_parts[0] if date_parts else None,
            month=date_parts[1] if date_parts else None,
            day=date_parts[2] if date_parts else None,
            # Flexattrs
            tidal_album_id=int(album["id"]),
            tidal_artist_id=int(artist_ids[0]) if artist_ids else None,
            tidal_album_popularity=self._parse_popularity(
                album["attributes"]
            ),
            tidal_updated=time.time(),
        )

    def _get_track_info(
        self, track: TidalTrack, artist_by_id: dict[str, TidalArtist]
    ) -> TrackInfo:
        artist_names, artist_ids = self._parse_artists(
            track["relationships"]["artists"]["data"], artist_by_id
        )

        return TrackInfo(
            # Identifier
            data_source=self.data_source,
            track_id=track["id"],
            artists_ids=artist_ids,
            data_url=self._parse_data_url(track["attributes"]),
            # Meta
            title=self._parse_title(track["attributes"]),
            isrc=track["attributes"]["isrc"],
            artist=", ".join(artist_names),
            artists=artist_names,
            duration=self._duration_to_seconds(track["attributes"]["duration"]),
            label=self._parse_label(track["attributes"]),
            # Flexattrs
            tidal_track_id=int(track["id"]),
            tidal_artist_id=int(artist_ids[0]) if artist_ids else None,
            tidal_track_popularity=self._parse_popularity(
                track["attributes"]
            ),
            tidal_updated=time.time(),
        )

    @staticmethod
    def _parse_artists(
        artist_relationships: list[ResourceIdentifier],
        artist_by_id: dict[str, TidalArtist],
    ) -> tuple[list[str], list[str]]:
        """Extract artists from a relationship.

        Artists are sorted in the track/album response relationship but not in the
        track/album responses included items.
        """
        artist_names = []
        artist_ids = []
        for artist_rel in artist_relationships:
            if artist := artist_by_id.get(artist_rel["id"]):
                artist_ids.append(artist["id"])
                artist_names.append(artist["attributes"]["name"])
            else:
                log.warning(
                    "Artist with id {0} not found in lookup", artist_rel["id"]
                )

        return artist_names, artist_ids

    @staticmethod
    def _parse_title(attributes: AlbumAttributes | TrackAttributes):
        """
        Tidal UIs append the version string at the end of the title. We do the same here
        by formatting it as ``"{title} ({version})"`` to stay consistent.
        """
        if version := attributes.get("version"):
            return f"{attributes['title']} ({version})"
        return attributes["title"]

    @staticmethod
    def _parse_data_url(
        attributes: AlbumAttributes | TrackAttributes,
    ) -> str | None:
        if external_links := attributes.get("externalLinks"):
            return external_links[0].get("href")
        return None

    @staticmethod
    def _duration_to_seconds(duration: str) -> int | None:
        """Convert ISO 8601 duration to seconds. E.g. 'PT15M2S' -> 902."""
        match = ISO_8601_RE.match(duration)
        if not match:
            log.warning("Invalid ISO 8601 duration: {0}", duration)
            return None
        parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
        return parts["seconds"] + parts["minutes"] * 60 + parts["hours"] * 3600

    @staticmethod
    def _parse_label(
        attributes: AlbumAttributes | TrackAttributes,
    ) -> str | None:
        if copyright_ := attributes.get("copyright"):
            return copyright_["text"]
        return None

    @staticmethod
    def _parse_release_date(
        attributes: AlbumAttributes,
    ) -> tuple[int, int, int] | None:
        """Returns year, month, day from iso YYYY-MM-DD"""

        if (
            (release_date := attributes.get("releaseDate"))
            and (parts := release_date.split("-"))
            and len(parts) == 3
        ):
            return int(parts[0]), int(parts[1]), int(parts[2])
        return None

    @staticmethod
    def _parse_popularity(attributes: AlbumAttributes | TrackAttributes) -> int | None:
        val = attributes.get("popularity")
        if val is None:
            return None
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val * 100)
        return None

    def tidalsync(
        self, items: Iterable[Item], write: bool, force: bool = False
    ) -> None:
        """Sync Tidal popularity data for library items."""
        items = list(items)
        self._log.info("Syncing popularity for {0} tracks", len(items))

        track_id_to_items: dict[int, list[Item]] = {}
        album_id_to_items: dict[int, list[Item]] = {}
        for item in items:
            if not force:
                track_done = item.get("tidal_track_popularity") is not None
                album_done = item.get("tidal_album_popularity") is not None
                if track_done and album_done:
                    continue

            tidal_track_id = item.get("tidal_track_id")
            if tidal_track_id is not None:
                track_id_to_items.setdefault(int(tidal_track_id), []).append(
                    item
                )
            tidal_album_id = item.get("tidal_album_id")
            if tidal_album_id is not None:
                album_id_to_items.setdefault(int(tidal_album_id), []).append(
                    item
                )

        if not track_id_to_items and not album_id_to_items:
            return

        track_popularity: dict[int, int | None] = {}
        if track_id_to_items:
            all_track_ids = [str(tid) for tid in track_id_to_items]
            for tid_str, result in zip(
                all_track_ids,
                self.search_tracks_by_ids(tidal_ids=all_track_ids),
            ):
                track_popularity[int(tid_str)] = (
                    result.tidal_track_popularity if result else None
                )

        album_popularity: dict[int, int | None] = {}
        if album_id_to_items:
            all_album_ids = [str(aid) for aid in album_id_to_items]
            for aid_str, album_result in zip(
                all_album_ids,
                self.search_albums_by_ids(tidal_ids=all_album_ids),
            ):
                album_popularity[int(aid_str)] = (
                    album_result.tidal_album_popularity if album_result else None
                )

        for item in items:
            updated = False
            tidal_track_id = item.get("tidal_track_id")
            if tidal_track_id is not None:
                pop = track_popularity.get(int(tidal_track_id))
                if pop is not None:
                    item["tidal_track_popularity"] = pop
                    updated = True

            tidal_album_id = item.get("tidal_album_id")
            if tidal_album_id is not None:
                pop = album_popularity.get(int(tidal_album_id))
                if pop is not None:
                    item["tidal_album_popularity"] = pop
                    updated = True

            if updated:
                item["tidal_updated"] = time.time()
                item.store()
                if write:
                    item.try_write()

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
        tidal_cmd.parser.add_option(
            "-f",
            "--force",
            action="store_true",
            dest="force",
            default=False,
            help="re-fetch popularity even if already present",
        )
        tidal_cmd.parser.add_option(
            "-w",
            "--write",
            action="store_true",
            dest="write",
            default=False,
            help="write updated tags to media files",
        )

        def func(lib: Library, opts: optparse.Values, args: list[str]):
            action = args[0] if args else None
            if action == "auth" or opts.auth:
                self.api.ui_authenticate_flow()
            elif action == "sync":
                query = "data_source:tidal"
                if len(args) > 1:
                    query = f"{query} {' '.join(args[1:])}"
                items = lib.items(query)
                self.tidalsync(items, write=opts.write, force=opts.force)
            else:
                tidal_cmd.print_help()

        tidal_cmd.func = func

        return [tidal_cmd]


ISO_8601_RE = re.compile(
    r"^P"
    r"T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?$"
)
