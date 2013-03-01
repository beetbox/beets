#Copyright (c) 2011, Jeffrey Aylesworth <jeffrey@aylesworth.ca>
#
#Permission to use, copy, modify, and/or distribute this software for any
#purpose with or without fee is hereby granted, provided that the above
#copyright notice and this permission notice appear in all copies.
#
#THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from __future__ import print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import ui
from beets import config
import musicbrainzngs
from musicbrainzngs import musicbrainz

SUBMISSION_CHUNK_SIZE = 200

def mb_request(*args, **kwargs):
    """Send a MusicBrainz API request and process exceptions.
    """
    try:
        return musicbrainz._mb_request(*args, **kwargs)
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
        chunk = release_ids[i:i+SUBMISSION_CHUNK_SIZE]
        releaselist = ";".join(chunk)
        mb_request(
            "collection/%s/releases/%s" % (collection_id, releaselist),
            'PUT', True, True, body='foo'
        )
        # A non-empty request body is required to avoid a 411 "Length
        # Required" error from the MB server.

def update_collection(lib, opts, args):
    # Get the collection to modify.
    collections = mb_request('collection', 'GET', True, True)
    if not collections['collection-list']:
        raise ui.UserError('no collections exist for user')
    collection_id = collections['collection-list'][0]['id']

    # Get a list of all the albums.
    albums = [a.mb_albumid for a in lib.albums() if a.mb_albumid]

    # Submit to MusicBrainz.
    print('Updating MusicBrainz collection {0}...'.format(collection_id))
    submit_albums(collection_id, albums)
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
