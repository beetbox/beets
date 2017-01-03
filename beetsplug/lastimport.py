# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Rafael Bodill http://github.com/rafi
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

import pylast
from pylast import TopItem, _extract, _number
from beets import ui
from beets import dbcore
from beets import config
from beets import plugins
from beets.dbcore import types

API_URL = 'https://ws.audioscrobbler.com/2.0/'


class LastImportPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(LastImportPlugin, self).__init__()
        config['lastfm'].add({
            'user':     '',
            'api_key':  plugins.LASTFM_KEY,
        })
        config['lastfm']['api_key'].redact = True
        self.config.add({
            'per_page': 500,
            'retry_limit': 3,
        })
        self.item_types = {
            'play_count':  types.INTEGER,
        }

    def commands(self):
        cmd = ui.Subcommand('lastimport', help=u'import last.fm play-count')

        def func(lib, opts, args):
            import_lastfm(lib, self._log)

        cmd.func = func
        return [cmd]


class CustomUser(pylast.User):
    """ Custom user class derived from pylast.User, and overriding the
    _get_things method to return MBID and album. Also introduces new
    get_top_tracks_by_page method to allow access to more than one page of top
    tracks.
    """
    def __init__(self, *args, **kwargs):
        super(CustomUser, self).__init__(*args, **kwargs)

    def _get_things(self, method, thing, thing_type, params=None,
                    cacheable=True):
        """Returns a list of the most played thing_types by this thing, in a
        tuple with the total number of pages of results. Includes an MBID, if
        found.
        """
        doc = self._request(
            self.ws_prefix + "." + method, cacheable, params)

        toptracks_node = doc.getElementsByTagName('toptracks')[0]
        total_pages = int(toptracks_node.getAttribute('totalPages'))

        seq = []
        for node in doc.getElementsByTagName(thing):
            title = _extract(node, "name")
            artist = _extract(node, "name", 1)
            mbid = _extract(node, "mbid")
            playcount = _number(_extract(node, "playcount"))

            thing = thing_type(artist, title, self.network)
            thing.mbid = mbid
            seq.append(TopItem(thing, playcount))

        return seq, total_pages

    def get_top_tracks_by_page(self, period=pylast.PERIOD_OVERALL, limit=None,
                               page=1, cacheable=True):
        """Returns the top tracks played by a user, in a tuple with the total
        number of pages of results.
        * period: The period of time. Possible values:
          o PERIOD_OVERALL
          o PERIOD_7DAYS
          o PERIOD_1MONTH
          o PERIOD_3MONTHS
          o PERIOD_6MONTHS
          o PERIOD_12MONTHS
        """

        params = self._get_params()
        params['period'] = period
        params['page'] = page
        if limit:
            params['limit'] = limit

        return self._get_things(
            "getTopTracks", "track", pylast.Track, params, cacheable)


def import_lastfm(lib, log):
    user = config['lastfm']['user'].as_str()
    per_page = config['lastimport']['per_page'].get(int)

    if not user:
        raise ui.UserError(u'You must specify a user name for lastimport')

    log.info(u'Fetching last.fm library for @{0}', user)

    page_total = 1
    page_current = 0
    found_total = 0
    unknown_total = 0
    retry_limit = config['lastimport']['retry_limit'].get(int)
    # Iterate through a yet to be known page total count
    while page_current < page_total:
        log.info(u'Querying page #{0}{1}...',
                 page_current + 1,
                 '/{}'.format(page_total) if page_total > 1 else '')

        for retry in range(0, retry_limit):
            tracks, page_total = fetch_tracks(user, page_current + 1, per_page)
            if page_total < 1:
                # It means nothing to us!
                raise ui.UserError(u'Last.fm reported no data.')

            if tracks:
                found, unknown = process_tracks(lib, tracks, log)
                found_total += found
                unknown_total += unknown
                break
            else:
                log.error(u'ERROR: unable to read page #{0}',
                          page_current + 1)
                if retry < retry_limit:
                    log.info(
                        u'Retrying page #{0}... ({1}/{2} retry)',
                        page_current + 1, retry + 1, retry_limit
                    )
                else:
                    log.error(u'FAIL: unable to fetch page #{0}, ',
                              u'tried {1} times', page_current, retry + 1)
        page_current += 1

    log.info(u'... done!')
    log.info(u'finished processing {0} song pages', page_total)
    log.info(u'{0} unknown play-counts', unknown_total)
    log.info(u'{0} play-counts imported', found_total)


def fetch_tracks(user, page, limit):
    """ JSON format:
        [
            {
                "mbid": "...",
                "artist": "...",
                "title": "...",
                "playcount": "..."
            }
        ]
    """
    network = pylast.LastFMNetwork(api_key=config['lastfm']['api_key'])
    user_obj = CustomUser(user, network)
    results, total_pages =\
        user_obj.get_top_tracks_by_page(limit=limit, page=page)
    return [
        {
            "mbid": track.item.mbid if track.item.mbid else '',
            "artist": {
                "name": track.item.artist.name
            },
            "name": track.item.title,
            "playcount": track.weight
        } for track in results
    ], total_pages


def process_tracks(lib, tracks, log):
    total = len(tracks)
    total_found = 0
    total_fails = 0
    log.info(u'Received {0} tracks in this page, processing...', total)

    for num in range(0, total):
        song = None
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

        # If not, try just artist/title
        if song is None:
            log.debug(u'no album match, trying by artist/title')
            query = dbcore.AndQuery([
                dbcore.query.SubstringQuery('artist', artist),
                dbcore.query.SubstringQuery('title', title)
            ])
            song = lib.items(query).get()

        # Last resort, try just replacing to utf-8 quote
        if song is None:
            title = title.replace("'", u'\u2019')
            log.debug(u'no title match, trying utf-8 single quote')
            query = dbcore.AndQuery([
                dbcore.query.SubstringQuery('artist', artist),
                dbcore.query.SubstringQuery('title', title)
            ])
            song = lib.items(query).get()

        if song is not None:
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
        log.info(u'Acquired {0}/{1} play-counts ({2} unknown)',
                 total_found, total, total_fails)

    return total_found, total_fails
