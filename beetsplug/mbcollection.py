# This file is part of beets.
# Copyright (c) 2011, Jeffrey Aylesworth <mail@jeffrey.red>
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

import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from requests.auth import HTTPDigestAuth

from beets import __version__, config, ui
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

from ._utils.musicbrainz import MusicBrainzAPI

if TYPE_CHECKING:
    from collections.abc import Iterator

    from requests import Response

    from ._typing import JSONDict

SUBMISSION_CHUNK_SIZE = 200
FETCH_CHUNK_SIZE = 100
UUID_REGEX = r"^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$"


@dataclass
class MusicBrainzUserAPI(MusicBrainzAPI):
    auth: HTTPDigestAuth = field(init=False)

    @cached_property
    def user(self) -> str:
        return config["musicbrainz"]["user"].as_str()

    def __post_init__(self) -> None:
        super().__post_init__()
        config["musicbrainz"]["pass"].redact = True
        self.auth = HTTPDigestAuth(
            self.user, config["musicbrainz"]["pass"].as_str()
        )

    def request(self, *args, **kwargs) -> Response:
        kwargs.setdefault("params", {})
        kwargs["params"]["client"] = f"beets-{__version__}"
        kwargs["auth"] = self.auth
        return super().request(*args, **kwargs)

    def get_collections(self) -> list[JSONDict]:
        return self.get_entity(
            "collection", editor=self.user, includes=["user-collections"]
        ).get("collections", [])


@dataclass
class MBCollection:
    data: JSONDict
    mb_api: MusicBrainzUserAPI

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def release_count(self) -> int:
        return self.data["release-count"]

    @property
    def releases_url(self) -> str:
        return f"{self.mb_api.api_root}/collection/{self.id}/releases"

    @property
    def releases(self) -> list[JSONDict]:
        offsets = list(range(0, self.release_count, FETCH_CHUNK_SIZE))
        return [r for offset in offsets for r in self.get_releases(offset)]

    def get_releases(self, offset: int) -> list[JSONDict]:
        return self.mb_api.get_json(
            self.releases_url,
            params={"limit": FETCH_CHUNK_SIZE, "offset": offset},
        )["releases"]

    @staticmethod
    def get_id_chunks(id_list: list[str]) -> Iterator[list[str]]:
        for i in range(0, len(id_list), SUBMISSION_CHUNK_SIZE):
            yield id_list[i : i + SUBMISSION_CHUNK_SIZE]

    def add_releases(self, releases: list[str]) -> None:
        for chunk in self.get_id_chunks(releases):
            self.mb_api.put(f"{self.releases_url}/{'%3B'.join(chunk)}")

    def remove_releases(self, releases: list[str]) -> None:
        for chunk in self.get_id_chunks(releases):
            self.mb_api.delete(f"{self.releases_url}/{'%3B'.join(chunk)}")


def submit_albums(collection: MBCollection, release_ids):
    """Add all of the release IDs to the indicated collection. Multiple
    requests are made if there are many release IDs to submit.
    """
    collection.add_releases(release_ids)


class MusicBrainzCollectionPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "auto": False,
                "collection": "",
                "remove": False,
            }
        )
        if self.config["auto"]:
            self.import_stages = [self.imported]

    @cached_property
    def mb_api(self) -> MusicBrainzUserAPI:
        return MusicBrainzUserAPI()

    def _get_collection(self) -> MBCollection:
        if not (collections := self.mb_api.get_collections()):
            raise ui.UserError("no collections exist for user")

        # Get all release collection IDs, avoiding event collections
        if not (
            collection_by_id := {
                c["id"]: c for c in collections if c["entity-type"] == "release"
            }
        ):
            raise ui.UserError("No release collection found.")

        # Check that the collection exists so we can present a nice error
        if collection_id := self.config["collection"].as_str():
            if not (collection := collection_by_id.get(collection_id)):
                raise ui.UserError(f"invalid collection ID: {collection_id}")
        else:
            # No specified collection. Just return the first collection ID
            collection = next(iter(collection_by_id.values()))

        return MBCollection(collection, self.mb_api)

    def _get_albums_in_collection(self, collection: MBCollection) -> set[str]:
        return {r["id"] for r in collection.releases}

    def commands(self):
        mbupdate = Subcommand("mbupdate", help="Update MusicBrainz collection")
        mbupdate.parser.add_option(
            "-r",
            "--remove",
            action="store_true",
            default=None,
            dest="remove",
            help="Remove albums not in beets library",
        )
        mbupdate.func = self.update_collection
        return [mbupdate]

    def remove_missing(self, collection: MBCollection, lib_albums):
        lib_ids = {x.mb_albumid for x in lib_albums}
        albums_in_collection = self._get_albums_in_collection(collection)
        collection.remove_releases(list(albums_in_collection - lib_ids))

    def update_collection(self, lib, opts, args):
        self.config.set_args(opts)
        remove_missing = self.config["remove"].get(bool)
        self.update_album_list(lib, lib.albums(), remove_missing)

    def imported(self, session, task):
        """Add each imported album to the collection."""
        if task.is_album:
            self.update_album_list(session.lib, [task.album])

    def update_album_list(self, lib, album_list, remove_missing=False):
        """Update the MusicBrainz collection from a list of Beets albums"""
        collection = self._get_collection()

        # Get a list of all the album IDs.
        album_ids = []
        for album in album_list:
            aid = album.mb_albumid
            if aid:
                if re.match(UUID_REGEX, aid):
                    album_ids.append(aid)
                else:
                    self._log.info("skipping invalid MBID: {}", aid)

        # Submit to MusicBrainz.
        self._log.info("Updating MusicBrainz collection {}...", collection.id)
        submit_albums(collection, album_ids)
        if remove_missing:
            self.remove_missing(collection, lib.albums())
        self._log.info("...MusicBrainz collection updated.")
