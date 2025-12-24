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
from typing import TYPE_CHECKING, ClassVar

from requests.auth import HTTPDigestAuth

from beets import __version__, config, ui
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

from ._utils.musicbrainz import MusicBrainzAPI

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from requests import Response

    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Library

    from ._typing import JSONDict

UUID_PAT = re.compile(r"^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$")


@dataclass
class MusicBrainzUserAPI(MusicBrainzAPI):
    """MusicBrainz API client with user authentication.

    In order to retrieve private user collections and modify them, we need to
    authenticate the requests with the user's MusicBrainz credentials.

    See documentation for authentication details:
        https://musicbrainz.org/doc/MusicBrainz_API#Authentication

    Note that the documentation misleadingly states HTTP 'basic' authentication,
    and I had to reverse-engineer musicbrainzngs to discover that it actually
    uses HTTP 'digest' authentication.
    """

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
        """Authenticate and include required client param in all requests."""
        kwargs.setdefault("params", {})
        kwargs["params"]["client"] = f"beets-{__version__}"
        kwargs["auth"] = self.auth
        return super().request(*args, **kwargs)

    def get_collections(self) -> list[JSONDict]:
        """Get all collections for the authenticated user.

        Note that both URL parameters must be included to retrieve private
        collections.
        """
        return self.get_entity(
            "collection", editor=self.user, includes=["user-collections"]
        ).get("collections", [])


@dataclass
class MBCollection:
    """Representation of a user's MusicBrainz collection.

    Provides convenient, chunked operations for retrieving releases and updating
    the collection via the MusicBrainz web API. Fetch and submission limits are
    controlled by class-level constants to avoid oversized requests.
    """

    SUBMISSION_CHUNK_SIZE: ClassVar[int] = 200
    FETCH_CHUNK_SIZE: ClassVar[int] = 100

    data: JSONDict
    mb_api: MusicBrainzUserAPI

    @property
    def id(self) -> str:
        """Unique identifier assigned to the collection by MusicBrainz."""
        return self.data["id"]

    @property
    def release_count(self) -> int:
        """Total number of releases recorded in the collection."""
        return self.data["release-count"]

    @property
    def releases_url(self) -> str:
        """Complete API endpoint URL for listing releases in this collection."""
        return f"{self.mb_api.api_root}/collection/{self.id}/releases"

    @property
    def releases(self) -> list[JSONDict]:
        """Retrieve all releases in the collection, fetched in successive pages.

        The fetch is performed in chunks and returns a flattened sequence of
        release records.
        """
        offsets = list(range(0, self.release_count, self.FETCH_CHUNK_SIZE))
        return [r for offset in offsets for r in self.get_releases(offset)]

    def get_releases(self, offset: int) -> list[JSONDict]:
        """Fetch a single page of releases beginning at a given position."""
        return self.mb_api.get_json(
            self.releases_url,
            params={"limit": self.FETCH_CHUNK_SIZE, "offset": offset},
        )["releases"]

    @classmethod
    def get_id_chunks(cls, id_list: list[str]) -> Iterator[list[str]]:
        """Yield successive sublists of identifiers sized for safe submission.

        Splits a long sequence of identifiers into batches that respect the
        service's submission limits to avoid oversized requests.
        """
        for i in range(0, len(id_list), cls.SUBMISSION_CHUNK_SIZE):
            yield id_list[i : i + cls.SUBMISSION_CHUNK_SIZE]

    def add_releases(self, releases: list[str]) -> None:
        """Add releases to the collection in batches."""
        for chunk in self.get_id_chunks(releases):
            # Need to escape semicolons: https://github.com/psf/requests/issues/6990
            self.mb_api.put(f"{self.releases_url}/{'%3B'.join(chunk)}")

    def remove_releases(self, releases: list[str]) -> None:
        """Remove releases from the collection in chunks."""
        for chunk in self.get_id_chunks(releases):
            # Need to escape semicolons: https://github.com/psf/requests/issues/6990
            self.mb_api.delete(f"{self.releases_url}/{'%3B'.join(chunk)}")


def submit_albums(collection: MBCollection, release_ids):
    """Add all of the release IDs to the indicated collection. Multiple
    requests are made if there are many release IDs to submit.
    """
    collection.add_releases(release_ids)


class MusicBrainzCollectionPlugin(BeetsPlugin):
    def __init__(self) -> None:
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

    @cached_property
    def collection(self) -> MBCollection:
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

    def update_collection(self, lib: Library, opts, args) -> None:
        self.config.set_args(opts)
        remove_missing = self.config["remove"].get(bool)
        self.update_album_list(lib, lib.albums(), remove_missing)

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Add each imported album to the collection."""
        if task.is_album:
            self.update_album_list(
                session.lib, [task.album], remove_missing=False
            )

    def update_album_list(
        self, lib: Library, albums: Iterable[Album], remove_missing: bool
    ) -> None:
        """Update the MusicBrainz collection from a list of Beets albums"""
        collection = self.collection

        # Get a list of all the album IDs.
        album_ids = [id_ for a in albums if UUID_PAT.match(id_ := a.mb_albumid)]

        # Submit to MusicBrainz.
        self._log.info("Updating MusicBrainz collection {}...", collection.id)
        collection.add_releases(album_ids)
        if remove_missing:
            lib_ids = {x.mb_albumid for x in lib.albums()}
            albums_in_collection = {r["id"] for r in collection.releases}
            collection.remove_releases(list(albums_in_collection - lib_ids))

        self._log.info("...MusicBrainz collection updated.")
