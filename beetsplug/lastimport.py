# This file is part of beets.
# Copyright 2015, Rafael Bodill http://github.com/rafi
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import requests
from beets import ui
from beets import dbcore
from beets import config
from beets import plugins
from beets.dbcore import types

API_URL = 'http://ws.audioscrobbler.com/2.0/'


class LastImportPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(LastImportPlugin, self).__init__()
        config['lastfm'].add({
            'user':     '',
            'api_key':  '',
        })
        self.config.add({
            'per_page': 500,
            'retry_limit': 3,
        })
        self.item_types = {
            'play_count':  types.INTEGER,
        }

    def commands(self):
        cmd = ui.Subcommand('lastimport', help='import last.fm play-count')

        def func(lib, opts, args):
            import_lastfm(lib, self._log)

        cmd.func = func
        return [cmd]


def import_lastfm(lib, log):
    user = config['lastfm']['user']
    per_page = config['lastimport']['per_page']

    if not user:
        raise ui.UserError('You must specify a user name for lastimport')

    log.info('Fetching last.fm library for @{0}', user)

    page_total = 1
    page_current = 0
    found_total = 0
    unknown_total = 0
    retry_limit = config['lastimport']['retry_limit'].get(int)
    # Iterate through a yet to be known page total count
    while page_current < page_total:
        log.info('Querying page #{0}{1}...',
                 page_current + 1,
                 '/{}'.format(page_total) if page_total > 1 else '')

        for retry in range(0, retry_limit):
            page = fetch_tracks(user, page_current + 1, per_page)
            if 'tracks' in page:
                # Let us the reveal the holy total pages!
                page_total = int(page['tracks']['@attr']['totalPages'])
                if page_total < 1:
                    # It means nothing to us!
                    raise ui.UserError('Last.fm reported no data.')

                track = page['tracks']['track']
                found, unknown = process_tracks(lib, track, log)
                found_total += found
                unknown_total += unknown
                break
            else:
                log.error('ERROR: unable to read page #{0}',
                          page_current + 1)
                if retry < retry_limit:
                    log.info(
                        'Retrying page #{0}... ({1}/{2} retry)',
                        page_current + 1, retry + 1, retry_limit
                    )
                else:
                    log.error('FAIL: unable to fetch page #{0}, ',
                              'tried {1} times', page_current, retry + 1)
        page_current += 1

    log.info('... done!')
    log.info('finished processing {0} song pages', page_total)
    log.info('{0} unknown play-counts', unknown_total)
    log.info('{0} play-counts imported', found_total)


def fetch_tracks(user, page, limit):
    return requests.get(API_URL, params={
        'method': 'library.gettracks',
        'user': user,
        'api_key': plugins.LASTFM_KEY,
        'page': bytes(page),
        'limit': bytes(limit),
        'format': 'json',
    }).json()


def process_tracks(lib, tracks, log):
    total = len(tracks)
    total_found = 0
    total_fails = 0
    log.info('Received {0} tracks in this page, processing...', total)

    for num in xrange(0, total):
        song = ''
        trackid = tracks[num]['mbid'].strip()
        artist = tracks[num]['artist'].get('name', '').strip()
        title = tracks[num]['name'].strip()
        album = ''
        if 'album' in tracks[num]:
            album = tracks[num]['album'].get('name', '').strip()

        log.debug(u'query: {0} - {1} ({2})', artist, title, album)

        # First try to query by musicbrainz's trackid
        if trackid:
            song = lib.items(
                dbcore.query.MatchQuery('mb_trackid', trackid)
            ).get()

        # Otherwise try artist/title/album
        if not song:
            log.debug(u'no match for mb_trackid {0}, trying by '
                      u'artist/title/album', trackid)
            query = dbcore.AndQuery([
                dbcore.query.SubstringQuery('artist', artist),
                dbcore.query.SubstringQuery('title', title),
                dbcore.query.SubstringQuery('album', album)
            ])
            song = lib.items(query).get()

        # If not, try just artist/title
        if not song:
            log.debug(u'no album match, trying by artist/title')
            query = dbcore.AndQuery([
                dbcore.query.SubstringQuery('artist', artist),
                dbcore.query.SubstringQuery('title', title)
            ])
            song = lib.items(query).get()

        # Last resort, try just replacing to utf-8 quote
        if not song:
            title = title.replace("'", u'\u2019')
            log.debug(u'no title match, trying utf-8 single quote')
            query = dbcore.AndQuery([
                dbcore.query.SubstringQuery('artist', artist),
                dbcore.query.SubstringQuery('title', title)
            ])
            song = lib.items(query).get()

        if song:
            count = int(song.get('play_count', 0))
            new_count = int(tracks[num]['playcount'])
            log.debug(u'match: {0} - {1} ({2}) '
                      u'updating: play_count {3} => {4}',
                      song.artist, song.title, song.album, count, new_count)
            song['play_count'] = new_count
            song.store()
            total_found += 1
        else:
            total_fails += 1
            log.info(u'  - No match: {0} - {1} ({2})',
                     artist, title, album)

    if total_fails > 0:
        log.info('Acquired {0}/{1} play-counts ({2} unknown)',
                 total_found, total, total_fails)

    return total_found, total_fails
