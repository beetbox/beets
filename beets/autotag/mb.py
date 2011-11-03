# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
import logging

from . import musicbrainz3
import beets.autotag.hooks
import beets

SEARCH_LIMIT = 5
VARIOUS_ARTISTS_ID = '89ad4ac3-39f7-470e-963a-56509c546377'

musicbrainz3._useragent = 'beets/%s' % beets.__version__

class ServerBusyError(Exception): pass
class BadResponseError(Exception): pass

log = logging.getLogger('beets')

# We hard-code IDs for artists that can't easily be searched for.
SPECIAL_CASE_ARTISTS = {
    '!!!': 'f26c72d3-e52c-467b-b651-679c73d8e1a7',
}

RELEASE_INCLUDES = ['artists', 'media', 'recordings', 'release-groups',
                    'labels']
TRACK_INCLUDES = ['artists']

def _adapt_criteria(criteria):
    """Special-case artists in a criteria dictionary before it is passed
    to the MusicBrainz search server. The dictionary supplied is
    mutated; nothing is returned.
    """
    if 'artist' in criteria:
        for artist, artist_id in SPECIAL_CASE_ARTISTS.items():
            if criteria['artist'] == artist:
                criteria['arid'] = artist_id
                del criteria['artist']
                break

def track_info(recording):
    """Translates a MusicBrainz recording result dictionary into a beets
    ``TrackInfo`` object.
    """
    info = beets.autotag.hooks.TrackInfo(recording['title'],
                                         recording['id'])

    if 'artist-credit' in recording: # XXX: when is this not included?
        artist = recording['artist-credit'][0]['artist']
        info.artist = artist['name']
        info.artist_id = artist['id']

    if recording.get('length'):
        info.length = int(recording['length'])/(1000.0)

    return info

def album_info(release):
    """Takes a MusicBrainz release result dictionary and returns a beets
    AlbumInfo object containing the interesting data about that release.
    """
    # Basic info.
    artist = release['artist-credit'][0]['artist']
    tracks = []
    for medium in release['medium-list']:
        tracks.extend(i['recording'] for i in medium['track-list'])
    info = beets.autotag.hooks.AlbumInfo(
        release['title'],
        release['id'],
        artist['name'],
        artist['id'],
        [track_info(track) for track in tracks],
    )
    info.va = info.artist_id == VARIOUS_ARTISTS_ID
    if 'asin' in release:
        info.asin = release['asin']

    # Release type not always populated.
    reltype = release['release-group']['type']
    if reltype:
        info.albumtype = reltype.lower()

    # Release date.
    if 'date' in release: # XXX: when is this not included?
        date_str = release['date']
        if date_str:
            date_parts = date_str.split('-')
            for key in ('year', 'month', 'day'):
                if date_parts:
                    setattr(info, key, int(date_parts.pop(0)))

    # Label name.
    if release.get('label-info-list'):
        label = release['label-info-list'][0]['label']['name']
        if label != '[no label]':
            info.label = label

    return info

def match_album(artist, album, tracks=None, limit=SEARCH_LIMIT):
    """Searches for a single album ("release" in MusicBrainz parlance)
    and returns an iterator over AlbumInfo objects.

    The query consists of an artist name, an album name, and,
    optionally, a number of tracks on the album.
    """
    # Build search criteria.
    criteria = {'release': album}
    if artist is not None:
        criteria['artist'] = artist
    else:
        # Various Artists search.
        criteria['arid'] = VARIOUS_ARTISTS_ID
    if tracks is not None:
        criteria['tracks'] = str(tracks)

    _adapt_criteria(criteria)
    res = musicbrainz3.release_search(limit=limit, **criteria)
    for release in res['release-list']:
        # The search result is missing some data (namely, the tracks),
        # so we just use the ID and fetch the rest of the information.
        yield album_for_id(release['id'])

def match_track(artist, title, limit=SEARCH_LIMIT):
    """Searches for a single track and returns an iterable of TrackInfo
    objects.
    """
    criteria = {
        'artist': artist,
        'recording': title,
    }

    _adapt_criteria(criteria)
    res = musicbrainz3.recording_search(limit=limit, **criteria)
    for recording in res['recording-list']:
        yield track_info(recording)

def album_for_id(albumid):
    """Fetches an album by its MusicBrainz ID and returns an AlbumInfo
    object or None if the album is not found.
    """
    try:
        res = musicbrainz3.get_release_by_id(albumid, RELEASE_INCLUDES)
    except musicbrainz3.ResponseError:
        log.debug('Album ID match failed.')
        return None
    return album_info(res['release'])

def track_for_id(trackid):
    """Fetches a track by its MusicBrainz ID. Returns a TrackInfo object
    or None if no track is found.
    """
    try:
        res = musicbrainz3.get_recording_by_id(trackid, TRACK_INCLUDES)
    except musicbrainz3.ResponseError:
        log.debug('Track ID match failed.')
        return None
    return track_info(res['recording'])
