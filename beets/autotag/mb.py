# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Searches for albums in the MusicBrainz database.
"""
from __future__ import division, absolute_import, print_function

import re
import pdb
import traceback
import musicbrainzngs
from six.moves.urllib.parse import urljoin

from beets import logging
import beets.autotag.hooks
import beets
from beets import util
from beets import config
import six

VARIOUS_ARTISTS_ID = '89ad4ac3-39f7-470e-963a-56509c546377'

if util.SNI_SUPPORTED:
    BASE_URL = 'https://musicbrainz.org/'
else:
    BASE_URL = 'http://musicbrainz.org/'

musicbrainzngs.set_useragent('beets', beets.__version__,
                             'http://beets.io/')


class MusicBrainzAPIError(util.HumanReadableException):
    """An error while talking to MusicBrainz. The `query` field is the
    parameter to the action and may have any type.
    """
    def __init__(self, reason, verb, query, tb=None):
        self.query = query
        if isinstance(reason, musicbrainzngs.WebServiceError):
            reason = u'MusicBrainz not reachable'
        super(MusicBrainzAPIError, self).__init__(reason, verb, tb)

    def get_message(self):
        return u'{0} in {1} with query {2}'.format(
            self._reasonstr(), self.verb, repr(self.query)
        )

log = logging.getLogger('beets')

RELEASE_INCLUDES = [
    'artists',
    'media',
    'recordings',
    'release-groups',
    'labels',
    'artist-credits',
    'aliases',
    'recording-level-rels',
    'work-rels',
    'discids',
    'isrcs',
    'work-level-rels',
    'artist-rels',
    'instrument-rels',
    'annotation',
    'tags',
    'user-tags',
    'area-rels',
    'label-rels',
    'place-rels',
    'event-rels',
    'recording-rels',
    'release-rels',
    'release-group-rels',
    'series-rels',
    'url-rels']
TRACK_INCLUDES = [
    'artists',
    'releases',
    'discids',
    'media',
    'artist-credits',
    'isrcs',
    'annotation',
    'aliases',
    'tags',
    'user-tags',
    'ratings',
    'user-ratings',
    'area-rels',
    'artist-rels',
    'label-rels',
    'place-rels',
    'event-rels',
    'recording-rels',
    'release-rels',
    'release-group-rels',
    'series-rels',
    'url-rels',
    'work-rels',
    'instrument-rels']
# if 'work-level-rels' in musicbrainzngs.VALID_INCLUDES['recording']:
#     TRACK_INCLUDES += ['work-level-rels', 'artist-rels']


def track_url(trackid):
    return urljoin(BASE_URL, 'recording/' + trackid)


def album_url(albumid):
    return urljoin(BASE_URL, 'release/' + albumid)


def configure():
    """Set up the python-musicbrainz-ngs module according to settings
    from the beets configuration. This should be called at startup.
    """
    hostname = config['musicbrainz']['host'].as_str()
    musicbrainzngs.set_hostname(hostname)
    musicbrainzngs.set_rate_limit(
        config['musicbrainz']['ratelimit_interval'].as_number(),
        config['musicbrainz']['ratelimit'].get(int),
    )


def _preferred_alias(aliases):
    """Given an list of alias structures for an artist credit, select
    and return the user's preferred alias alias or None if no matching
    alias is found.
    """
    if not aliases:
        return

    # Only consider aliases that have locales set.
    aliases = [a for a in aliases if 'locale' in a]

    # Search configured locales in order.
    for locale in config['import']['languages'].as_str_seq():
        # Find matching primary aliases for this locale.
        matches = [a for a in aliases
                   if a['locale'] == locale and 'primary' in a]
        # Skip to the next locale if we have no matches
        if not matches:
            continue

        return matches[0]


def _preferred_release_event(release):
    """Given a release, select and return the user's preferred release
    event as a tuple of (country, release_date). Fall back to the
    default release event if a preferred event is not found.
    """
    countries = config['match']['preferred']['countries'].as_str_seq()

    for event in release.get('release-event-list', {}):
        for country in countries:
            try:
                if country in event['area']['iso-3166-1-code-list']:
                    return country, event['date']
            except KeyError:
                pass

    return release.get('country'), release.get('date')


def _flatten_artist_credit(credit):
    """Given a list representing an ``artist-credit`` block, flatten the
    data into a triple of joined artist name strings: canonical, sort, and
    credit.

    :param list credit: the artist-credit value of a musicbrainzngs release
                        dict

    :returns: three strings appearing in tags
    :rtype: str tuple
    """
    artist_parts = []
    artist_sort_parts = []
    artist_credit_parts = []
    for el in credit:
        if isinstance(el, six.string_types):
            # Join phrase.
            artist_parts.append(el)
            artist_credit_parts.append(el)
            artist_sort_parts.append(el)

        else:
            alias = _preferred_alias(el['artist'].get('alias-list', ()))

            # An artist.
            if alias:
                cur_artist_name = alias['alias']
            else:
                cur_artist_name = el['artist']['name']
            artist_parts.append(cur_artist_name)

            # Artist sort name.
            if alias:
                artist_sort_parts.append(alias['sort-name'])
            elif 'sort-name' in el['artist']:
                artist_sort_parts.append(el['artist']['sort-name'])
            else:
                artist_sort_parts.append(cur_artist_name)

            # Artist credit.
            if 'name' in el:
                artist_credit_parts.append(el['name'])
            else:
                artist_credit_parts.append(cur_artist_name)

    return (
        ''.join(artist_parts),
        ''.join(artist_sort_parts),
        ''.join(artist_credit_parts),
    )


def _set_date_str(info, date_str, original=False):
    """Given a (possibly partial) YYYY-MM-DD string and an AlbumInfo
    object, set the object's release date fields appropriately. If
    `original`, then set the original_year, etc., fields.
    """
    if date_str:
        date_parts = date_str.split('-')
        for key in ('year', 'month', 'day'):
            if date_parts:
                date_part = date_parts.pop(0)
                try:
                    date_num = int(date_part)
                except ValueError:
                    continue

                if original:
                    key = 'original_' + key
                setattr(info, key, date_num)


def match_album(artist, album, tracks=None):
    """Searches for a single album ("release" in MusicBrainz parlance)
    and returns an iterator over AlbumInfo objects. May raise a
    MusicBrainzAPIError.

    The query consists of an artist name, an album name, and,
    optionally, a number of tracks on the album.
    """
    # Build search criteria.
    criteria = {'release': album.lower().strip()}
    if artist is not None:
        criteria['artist'] = artist.lower().strip()
    else:
        # Various Artists search.
        criteria['arid'] = VARIOUS_ARTISTS_ID
    if tracks is not None:
        criteria['tracks'] = six.text_type(tracks)

    # Abort if we have no search terms.
    if not any(criteria.values()):
        return

    try:
        log.debug(u'Searching for MusicBrainz releases with: {!r}', criteria)
        res = musicbrainzngs.search_releases(
            limit=config['musicbrainz']['searchlimit'].get(int), **criteria)
    except musicbrainzngs.MusicBrainzError as exc:
        raise MusicBrainzAPIError(exc, 'release search', criteria,
                                  traceback.format_exc())
    for release in res['release-list']:
        # The search result is missing some data (namely, the tracks),
        # so we just use the ID and fetch the rest of the information.
        albuminfo = album_for_id(release['id'])
        if albuminfo is not None:
            yield albuminfo


def match_track(artist, title):
    """Searches for a single track and returns an iterable of TrackInfo
    objects. May raise a MusicBrainzAPIError.
    """
    criteria = {
        'artist': artist.lower().strip(),
        'recording': title.lower().strip(),
    }

    if not any(criteria.values()):
        return

    try:
        res = musicbrainzngs.search_recordings(
            limit=config['musicbrainz']['searchlimit'].get(int), **criteria)
    except musicbrainzngs.MusicBrainzError as exc:
        raise MusicBrainzAPIError(exc, 'recording search', criteria,
                                  traceback.format_exc())
    for recording in res['recording-list']:
        yield beets.autotag.TrackInfo.from_mb_recording(recording)


def _parse_id(s):
    """Search for a MusicBrainz ID in the given string and return it. If
    no ID can be found, return None.
    """
    # Find the first thing that looks like a UUID/MBID.
    match = re.search(u'[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}', s)
    if match:
        return match.group()


def album_for_id(releaseid):
    """Fetches an album by its MusicBrainz ID and returns an AlbumInfo
    object or None if the album is not found. May raise a
    MusicBrainzAPIError.
    """
    log.debug(u'Requesting MusicBrainz release {}', releaseid)
    albumid = _parse_id(releaseid)
    if not albumid:
        log.debug(u'Invalid MBID ({0}).', releaseid)
        return
    try:
        res = musicbrainzngs.get_release_by_id(albumid,
                                               RELEASE_INCLUDES)
    except musicbrainzngs.ResponseError:
        log.debug(u'Album ID match failed.')
        return None
    except musicbrainzngs.MusicBrainzError as exc:
        raise MusicBrainzAPIError(exc, u'get release by ID', albumid,
                                  traceback.format_exc())
    return beets.autotag.hooks.AlbumInfo.from_mb_release(res['release'])


def track_for_id(releaseid):
    """Fetches a track by its MusicBrainz ID. Returns a TrackInfo object
    or None if no track is found. May raise a MusicBrainzAPIError.
    """
    trackid = _parse_id(releaseid)
    if not trackid:
        log.debug(u'Invalid MBID ({0}).', releaseid)
        return
    try:
        res = musicbrainzngs.get_recording_by_id(id=trackid,
                                                 includes=TRACK_INCLUDES)
    except musicbrainzngs.ResponseError:
        log.debug(u'Track ID match failed.')
        return None
    except musicbrainzngs.MusicBrainzError as exc:
        raise MusicBrainzAPIError(exc, u'get recording by ID', trackid,
                                  traceback.format_exc())
    return beets.autotag.TrackInfo.from_mb_recording(res['recording'])
