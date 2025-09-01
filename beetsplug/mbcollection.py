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


import re

from mbzero import mbzerror

from beets import ui
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

from ._mb_interface import MbInterface, SharedMbInterface

SUBMISSION_CHUNK_SIZE = 200
FETCH_CHUNK_SIZE = 100
UUID_REGEX = r"^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$"


def mb_call(func, *args, **kwargs):
    """Call a MusicBrainz API function and catch exceptions."""
    try:
        return func(*args, **kwargs)
    except mbzerror.MbzUnauthorizedError:
        raise ui.UserError("authentication with MusicBrainz failed")
    except mbzerror.MbzWebServiceError as exc:
        raise ui.UserError(f"MusicBrainz API error: {exc}")


def submit_albums(
    mb_interface: MbInterface, collection_id: str, release_ids: list[str]
):
    """Add all of the release IDs to the indicated collection. Multiple
    requests are made if there are many release IDs to submit.
    """
    for i in range(0, len(release_ids), SUBMISSION_CHUNK_SIZE):
        chunk = release_ids[i : i + SUBMISSION_CHUNK_SIZE]
        mb_call(mb_interface.add_releases_to_collection, collection_id, chunk)


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
        self.mb_interface = (
            SharedMbInterface().require_auth_for_plugin(self.name).get()
        )
        if self.config["auto"]:
            self.import_stages = [self.imported]

    def _get_collection(self):
        collections = mb_call(self.mb_interface.get_user_collections)
        if not collections["collections"]:
            raise ui.UserError("no collections exist for user")

        # Get all collection IDs, avoiding event collections
        collection_ids = [
            x["id"]
            for x in collections["collections"]
            if x["entity-type"] == "release"
        ]
        if not collection_ids:
            raise ui.UserError("No release collection found.")

        # Check that the collection exists so we can present a nice error
        collection = self.config["collection"].as_str()
        if collection:
            if collection not in collection_ids:
                raise ui.UserError(f"invalid collection ID: {collection}")
            return collection

        # No specified collection. Just return the first collection ID
        return collection_ids[0]

    def _get_albums_in_collection(self, id):
        def _fetch(offset):
            res = mb_call(
                self.mb_interface.browse_release,
                "collection",
                id,
                limit=FETCH_CHUNK_SIZE,
                offset=offset,
            )
            return [x["id"] for x in res["releases"]], res["release-count"]

        offset = 0
        albums_in_collection, release_count = _fetch(offset)
        for i in range(0, release_count, FETCH_CHUNK_SIZE):
            albums_in_collection += _fetch(offset)[0]
            offset += FETCH_CHUNK_SIZE

        return albums_in_collection

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

    def remove_missing(self, collection_id: str, lib_albums):
        lib_ids = {x.mb_albumid for x in lib_albums}
        albums_in_collection = self._get_albums_in_collection(collection_id)
        remove_me = list(set(albums_in_collection) - lib_ids)
        for i in range(0, len(remove_me), FETCH_CHUNK_SIZE):
            chunk = remove_me[i : i + FETCH_CHUNK_SIZE]
            mb_call(
                self.mb_interface.remove_releases_from_collection,
                collection_id,
                chunk,
            )

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
        collection_id = self._get_collection()

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
        self._log.info("Updating MusicBrainz collection {}...", collection_id)
        submit_albums(self.mb_interface, collection_id, album_ids)
        if remove_missing:
            self.remove_missing(collection_id, lib.albums())
        self._log.info("...MusicBrainz collection updated.")
