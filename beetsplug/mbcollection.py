# -*- coding: utf-8 -*-
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

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import ui
from beets import config
import musicbrainzngs

import re

from rauth import OAuth2Service
import json

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
        self.config.add({
            'client_id': '',   # Needs to be generated
            'client_secret': ''
        })
        self.service = OAuth2Service(
            client_id=self.config['client_id'].as_str(),
            client_secret=self.config['secret'].as_str(),
            authorize_url="https://musicbrainz.org/oauth2/authorize",
            access_token_url="https://musicbrainz.org/oauth2/token",
            base_url="https://musicbrainz.org/"
        )
        self.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        self.params = {'response_type': 'code',
                       'redirect_uri': self.redirect_uri}

    def authorize_url(self):
        return self.service.get_authorize_url(**self.params)

    def get_token(self, code):
        session = service.get_raw_access_token(data={'code': code, 'redirect_uri': redirect_uri,
                                                     'grant_type': 'authorization_code', 'token_type': 'bearer'})
        t = session.json()
        return t['access_token'], t['refresh_token']

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


class OAuth(BeetsPlugin):
    def __init__(self):
        super(OAuth, self).__init__()
        self.client = None
        self.register_listener('import_begin', self.setup)

    def setup(self):
        client_id = self.config['client_id'].as_str()
        secret = self.config['secret'].as_str()
        try:
            with open(self.tokenfile()) as f:
                tokendata = json.load(f)
        except IOError:
            token = self.authenticate()
        else:
            token = tokendata['token']
            refresh_token = tokendata['refresh_token']

        self.client = MusicBrainzCollectionPlugin()
        return token

    def authenticate(self):
        auth_client = MusicBrainzCollectionPlugin()
        try:
            url = auth_client.authorize_url()
        except AUTH_ERRORS as e:
            self._log.debug(u'authentication error: {0}', e)
            raise beets.ui.UserError(u'Token request failed')

        beets.ui.print_(u"To authenticate, visit:")
        beets.ui.print_(url)

        data = beets.ui.input_(u"Enter the string displayed in your browser:")

        try:
            token, refresh_token = auth_client.get_token(data)
        except AUTH_ERRORS as e:
            self._log.debug(u'authentication error: {0}', e)
            raise beets.ui.UserError(u'Token request failed')

        with open(tokenfile(), 'w') as f:
            json.dump({'token': token, 'refresh_token': refresh_token}, f)

    @staticmethod
    def tokenfile():
        from os import path
        basedir = path.abspath(path.dirname(__file__))
        return "".join([basedir, '/token.json'])
