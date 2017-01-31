# -*- coding: utf-8 -*-
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

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import ui
from beets import config
import musicbrainzngs

import re

SUBMISSION_CHUNK_SIZE = 200
UUID_REGEX = r'^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$'


def mb_call(func, *args, **kwargs):
    """Call a MusicBrainz API function and catch exceptions.
    """
    try:
        return func(*args, **kwargs)
    except musicbrainzngs.AuthenticationError:
        raise ui.UserError(u'authentication with MusicBrainz failed')
    except (musicbrainzngs.ResponseError, musicbrainzngs.NetworkError) as exc:
        raise ui.UserError(u'MusicBrainz API error: {0}'.format(exc))
    except musicbrainzngs.UsageError:
        raise ui.UserError(u'MusicBrainz credentials missing')


def submit_albums(collection_id, release_ids):
    """Add all of the release IDs to the indicated collection. Multiple
    requests are made if there are many release IDs to submit.
    """
    for i in range(0, len(release_ids), SUBMISSION_CHUNK_SIZE):
        chunk = release_ids[i:i + SUBMISSION_CHUNK_SIZE]
        mb_call(
            musicbrainzngs.add_releases_to_collection,
            collection_id, chunk
        )


class MusicBrainzCollectionPlugin(BeetsPlugin):
    def __init__(self):
        super(MusicBrainzCollectionPlugin, self).__init__()
        config['musicbrainz']['pass'].redact = True
        musicbrainzngs.auth(
            config['musicbrainz']['user'].as_str(),
            config['musicbrainz']['pass'].as_str(),
        )
        self.config.add({'auto': False})
        if self.config['auto']:
            self.import_stages = [self.imported]

    def commands(self):
        mbupdate = Subcommand('mbupdate',
                              help=u'Update MusicBrainz collection')
        mbupdate.func = self.update_collection
        return [mbupdate]

    def update_collection(self, lib, opts, args):
        self.update_album_list(lib.albums())

    def imported(self, session, task):
        """Add each imported album to the collection.
        """
        if task.is_album:
            self.update_album_list([task.album])

    def update_album_list(self, album_list):
        """Update the MusicBrainz colleciton from a list of Beets albums
        """
        # Get the available collections.
        collections = mb_call(musicbrainzngs.get_collections)
        if not collections['collection-list']:
            raise ui.UserError(u'no collections exist for user')

        # Get the first release collection. MusicBrainz also has event
        # collections, so we need to avoid adding to those.
        for collection in collections['collection-list']:
            if 'release-count' in collection:
                collection_id = collection['id']
                break
        else:
            raise ui.UserError(u'No collection found.')

        # Get a list of all the album IDs.
        album_ids = []
        for album in album_list:
            aid = album.mb_albumid
            if aid:
                if re.match(UUID_REGEX, aid):
                    album_ids.append(aid)
                else:
                    self._log.info(u'skipping invalid MBID: {0}', aid)

        # Submit to MusicBrainz.
        self._log.info(
            u'Updating MusicBrainz collection {0}...', collection_id
        )
        submit_albums(collection_id, album_ids)
        self._log.info(u'...MusicBrainz collection updated.')
