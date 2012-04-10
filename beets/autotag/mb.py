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
import musicbrainzngs

import beets.autotag.hooks
import beets

SEARCH_LIMIT = 5
VARIOUS_ARTISTS_ID = '89ad4ac3-39f7-470e-963a-56509c546377'

musicbrainzngs.set_useragent('beets', beets.__version__,
                             'http://beets.radbox.org/')

class ServerBusyError(Exception): pass
class BadResponseError(Exception): pass

log = logging.getLogger('beets')

RELEASE_INCLUDES = ['artists', 'media', 'recordings', 'release-groups',
                    'labels', 'artist-credits']
TRACK_INCLUDES = ['artists']

# python-musicbrainz-ngs search functions: tolerate different API versions.
if hasattr(musicbrainzngs, 'release_search'):
    # Old API names.
    _mb_release_search = musicbrainzngs.release_search
    _mb_recording_search = musicbrainzngs.recording_search
else:
    # New API names.
    _mb_release_search = musicbrainzngs.search_releases
    _mb_recording_search = musicbrainzngs.search_recordings

def track_info(recording, medium=None, medium_index=None):
    """Translates a MusicBrainz recording result dictionary into a beets
    ``TrackInfo`` object. ``medium_index``, if provided, is the track's
    index (1-based) on its medium.
    """
    info = beets.autotag.hooks.TrackInfo(recording['title'],
                                         recording['id'],
                                         medium=medium,
                                         medium_index=medium_index)

    # Get the track artist credit.
    if recording.get('artist-credit-phrase'):
        info.artist = recording['artist-credit-phrase']

    # Get the ID and sort name of the first artist.
    if 'artist-credit' in recording:
        artist = recording['artist-credit'][0]['artist']
        info.artist_id = artist['id']
        info.artist_sort = artist['sort-name']

    if recording.get('length'):
        info.length = int(recording['length'])/(1000.0)

    return info

def _set_date_str(info, date_str):
    """Given a (possibly partial) YYYY-MM-DD string and an AlbumInfo
    object, set the object's release date fields appropriately.
    """
    if date_str:
        date_parts = date_str.split('-')
        for key in ('year', 'month', 'day'):
            if date_parts:
                setattr(info, key, int(date_parts.pop(0)))

def album_info(release):
    """Takes a MusicBrainz release result dictionary and returns a beets
    AlbumInfo object containing the interesting data about that release.
    """
    # Get artist name using join phrases.
    artist_parts = []
    for el in release['artist-credit']:
        if isinstance(el, basestring):
            artist_parts.append(el)
        else:
            artist_parts.append(el['artist']['name'])
    artist_name = ''.join(artist_parts)

    # Basic info.
    track_infos = []
    for medium in release['medium-list']:
        disctitle = medium.get('title')
        for track in medium['track-list']:
            ti = track_info(track['recording'],
                            int(medium['position']),
                            int(track['position']))
            if track.get('title'):
                # Track title may be distinct from underling recording
                # title.
                ti.title = track['title']
            ti.disctitle = disctitle
            track_infos.append(ti)
    info = beets.autotag.hooks.AlbumInfo(
        release['title'],
        release['id'],
        artist_name,
        release['artist-credit'][0]['artist']['id'],
        track_infos,
        mediums=len(release['medium-list']),
        artist_sort=release['artist-credit'][0]['artist']['sort-name'],
    )
    info.va = info.artist_id == VARIOUS_ARTISTS_ID
    info.asin = release.get('asin')
    info.releasegroup_id = release['release-group']['id']
    info.albumdisambig = release['release-group'].get('disambiguation')
    info.country = release.get('country')
    info.albumstatus = release.get('status')

    # Release type not always populated.
    if 'type' in release['release-group']:
        reltype = release['release-group']['type']
        if reltype:
            info.albumtype = reltype.lower()

    # Release date.
    if 'first-release-date' in release['release-group']:
        # Try earliest release date for the entire group first.
        _set_date_str(info, release['release-group']['first-release-date'])
    elif 'date' in release:
        # Fall back to release-specific date.
        _set_date_str(info, release['date'])

    # Label name.
    if release.get('label-info-list'):
        label_info = release['label-info-list'][0]
        if label_info.get('label'):
            label = label_info['label']['name']
            if label != '[no label]':
                info.label = label
        info.catalognum = label_info.get('catalog-number')

    # Text representation data.
    if release.get('text-representation'):
        rep = release['text-representation']
        info.script = rep.get('script')
        info.language = rep.get('language')

    # Media (format).
    if release['medium-list']:
        first_medium = release['medium-list'][0]
        info.media = first_medium.get('format')

    return info

def match_album(artist, album, tracks=None, limit=SEARCH_LIMIT):
    """Searches for a single album ("release" in MusicBrainz parlance)
    and returns an iterator over AlbumInfo objects.

    The query consists of an artist name, an album name, and,
    optionally, a number of tracks on the album.
    """
    # Build search criteria.
    criteria = {'release': album.lower()}
    if artist is not None:
        criteria['artist'] = artist.lower()
    else:
        # Various Artists search.
        criteria['arid'] = VARIOUS_ARTISTS_ID
    if tracks is not None:
        criteria['tracks'] = str(tracks)

    # Abort if we have no search terms.
    if not any(criteria.itervalues()):
        return

    res = _mb_release_search(limit=limit, **criteria)
    for release in res['release-list']:
        # The search result is missing some data (namely, the tracks),
        # so we just use the ID and fetch the rest of the information.
        albuminfo = album_for_id(release['id'])
        assert albuminfo is not None
        yield albuminfo

def match_track(artist, title, limit=SEARCH_LIMIT):
    """Searches for a single track and returns an iterable of TrackInfo
    objects.
    """
    criteria = {
        'artist': artist.lower(),
        'recording': title.lower(),
    }

    if not any(criteria.itervalues()):
        return

    res = _mb_recording_search(limit=limit, **criteria)
    for recording in res['recording-list']:
        yield track_info(recording)

def album_for_id(albumid):
    """Fetches an album by its MusicBrainz ID and returns an AlbumInfo
    object or None if the album is not found.
    """
    try:
        res = musicbrainzngs.get_release_by_id(albumid, RELEASE_INCLUDES)
    except musicbrainzngs.ResponseError:
        log.debug('Album ID match failed.')
        return None
    return album_info(res['release'])

def track_for_id(trackid):
    """Fetches a track by its MusicBrainz ID. Returns a TrackInfo object
    or None if no track is found.
    """
    try:
        res = musicbrainzngs.get_recording_by_id(trackid, TRACK_INCLUDES)
    except musicbrainzngs.ResponseError:
        log.debug('Track ID match failed.')
        return None
    return track_info(res['recording'])
