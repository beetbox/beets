# Copyright (c) 2011, Jeffrey Aylesworth <jeffrey@aylesworth.ca>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from __future__ import print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import ui
from beets import config
import musicbrainzngs

import re
import logging

SUBMISSION_CHUNK_SIZE = 200
UUID_REGEX = r'^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$'

log = logging.getLogger('beets.bpd')


def mb_call(func, *args, **kwargs):
    """Call a MusicBrainz API function and catch exceptions.
    """
    try:
        return func(*args, **kwargs)
    except musicbrainzngs.AuthenticationError:
        raise ui.UserError('authentication with MusicBrainz failed')
    except musicbrainzngs.ResponseError as exc:
        raise ui.UserError('MusicBrainz API error: {0}'.format(exc))
    except musicbrainzngs.UsageError:
        raise ui.UserError('MusicBrainz credentials missing')


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


def update_collection(lib, opts, args):
    # Get the collection to modify.
    collections = mb_call(musicbrainzngs.get_collections)
    if not collections['collection-list']:
        raise ui.UserError('no collections exist for user')
    collection_id = collections['collection-list'][0]['id']

    # Get a list of all the album IDs.
    album_ids = []
    for album in lib.albums():
        aid = album.mb_albumid
        if aid:
            if re.match(UUID_REGEX, aid):
                album_ids.append(aid)
            else:
                log.info(u'skipping invalid MBID: {0}'.format(aid))

    # Submit to MusicBrainz.
    print('Updating MusicBrainz collection {0}...'.format(collection_id))
    submit_albums(collection_id, album_ids)
    print('...MusicBrainz collection updated.')

update_mb_collection_cmd = Subcommand('mbupdate',
                                      help='Update MusicBrainz collection')
update_mb_collection_cmd.func = update_collection


class MusicBrainzCollectionPlugin(BeetsPlugin):
    def __init__(self):
        super(MusicBrainzCollectionPlugin, self).__init__()
        musicbrainzngs.auth(
            config['musicbrainz']['user'].get(unicode),
            config['musicbrainz']['pass'].get(unicode),
        )

    def commands(self):
        return [update_mb_collection_cmd]
