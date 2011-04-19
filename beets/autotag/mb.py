# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

This is a thin layer over the official `python-musicbrainz2` module. It
abstracts away that module's object model, the server's Lucene query
syntax, and other uninteresting parts of using musicbrainz2. The
principal interface is the function `match_album`.
"""

from __future__ import with_statement # for Python 2.5
import re
import time
import logging
import musicbrainz2.webservice as mbws
from musicbrainz2.model import Release
from threading import Lock
from musicbrainz2.model import VARIOUS_ARTISTS_ID

SEARCH_LIMIT = 10
VARIOUS_ARTISTS_ID = VARIOUS_ARTISTS_ID.rsplit('/', 1)[1]

class ServerBusyError(Exception): pass

log = logging.getLogger('beets')

# We hard-code IDs for artists that can't easily be searched for.
SPECIAL_CASE_ARTISTS = {
    '!!!': 'f26c72d3-e52c-467b-b651-679c73d8e1a7',
}

RELEASE_TYPES = [
    Release.TYPE_ALBUM,
    Release.TYPE_SINGLE, 
    Release.TYPE_EP,
    Release.TYPE_COMPILATION, 
    Release.TYPE_SOUNDTRACK,
    Release.TYPE_SPOKENWORD,
    Release.TYPE_INTERVIEW,
    Release.TYPE_AUDIOBOOK,
    Release.TYPE_LIVE,
    Release.TYPE_REMIX,
    Release.TYPE_OTHER
]

# MusicBrainz requires that a client does not query the server more
# than once a second. This function enforces that limit using a
# module-global variable to keep track of the last time a query was
# sent.
MAX_QUERY_RETRY = 8
QUERY_WAIT_TIME = 1.0
last_query_time = 0.0
mb_lock = Lock()
def _query_wrap(fun, *args, **kwargs):
    """Wait until at least `QUERY_WAIT_TIME` seconds have passed since
    the last invocation of this function. Then call
    fun(*args, **kwargs). If it fails due to a "server busy" message,
    then try again. Tries up to `MAX_QUERY_RETRY` times before
    giving up.
    """
    with mb_lock:
        global last_query_time
        for i in range(MAX_QUERY_RETRY):
            since_last_query = time.time() - last_query_time
            if since_last_query < QUERY_WAIT_TIME:
                time.sleep(QUERY_WAIT_TIME - since_last_query)
            last_query_time = time.time()
            try:
                # Try the function.
                res = fun(*args, **kwargs)
            except mbws.WebServiceError, e:
                # Server busy. Retry.
                message = str(e.reason)
                for errnum in (503, 504):
                    if 'Error %i' % errnum in message:
                        break
                else:
                    # This is not the error we're looking for.
                    raise
            else:
                # Success. Return the result.
                return res
        # Gave up.
        raise ServerBusyError()
    # FIXME exponential backoff?

def get_releases(**params):
    """Given a list of parameters to ReleaseFilter, executes the
    query and yields release dicts (complete with tracks).
    """
    # Replace special cases.
    if 'artistName' in params:
        artist = params['artistName']
        if artist in SPECIAL_CASE_ARTISTS:
            del params['artistName']
            params['artistId'] = SPECIAL_CASE_ARTISTS[artist]
    
    # Issue query.
    filt = mbws.ReleaseFilter(**params)
    results = _query_wrap(mbws.Query().getReleases, filter=filt)

    # Construct results.
    for result in results:
        release = result.release
        tracks, _ = release_info(release.id)
        yield release_dict(release, tracks)

def release_info(release_id):
    """Given a MusicBrainz release ID, fetch a list of tracks on the
    release and the release group ID. If the release is not found,
    returns None.
    """
    inc = mbws.ReleaseIncludes(tracks=True, releaseGroup=True)
    release = _query_wrap(mbws.Query().getReleaseById, release_id, inc)
    if release:
        return release.getTracks(), release.getReleaseGroup().getId()
    else:
        return None

def _lucene_escape(text):
    """Escapes a string so it may be used verbatim in a Lucene query
    string.
    """
    # Regex stolen from MusicBrainz Picard.
    out = re.sub(r'([+\-&|!(){}\[\]\^"~*?:\\])', r'\\\1', text)
    return out.replace('\x00', '')

def _lucene_query(criteria):
    """Given a dictionary containing search criteria, produce a string
    that may be used as a MusicBrainz search query.
    """
    query_parts = []
    for name, value in criteria.items():
        value = _lucene_escape(value).strip().lower()
        if value:
            query_parts.append(u'%s:(%s)' % (name, value))
    return u' '.join(query_parts)

def find_releases(criteria, limit=SEARCH_LIMIT):
    """Get a list of release dictionaries from the MusicBrainz
    database that match `criteria`. The latter is a dictionary whose
    keys are MusicBrainz field names and whose values are search terms
    for those fields.

    The field names are from MusicBrainz's Lucene query syntax, which
    is detailed here:
        http://wiki.musicbrainz.org/Text_Search_Syntax
    """
    # Replace special cases.
    if 'artist' in criteria:
        artist = criteria['artist']
        if artist in SPECIAL_CASE_ARTISTS:
            del criteria['artist']
            criteria['arid'] = SPECIAL_CASE_ARTISTS[artist]
    
    # Build the filter and send the query.
    query = _lucene_query(criteria)
    log.debug('album query: %s' % query)
    return get_releases(limit=limit, query=query)

def find_tracks(criteria, limit=SEARCH_LIMIT):
    """Get a sequence of track dictionaries from MusicBrainz that match
    `criteria`, a search term dictionary similar to the one passed to
    `find_releases`.
    """
    query = _lucene_query(criteria)
    log.debug('track query: %s' % query)
    filt = mbws.TrackFilter(limit=limit, query=query)
    results = _query_wrap(mbws.Query().getTracks, filter=filt)
    for result in results:
        track = result.track
        yield track_dict(track)

def track_dict(track):
    """Produces a dictionary summarizing a MusicBrainz `Track` object.
    """
    t = {'title': track.title,
         'id': track.id.rsplit('/', 1)[1]}
    if track.artist is not None:
        # Track artists will only be present for releases with
        # multiple artists.
        t['artist'] = track.artist.name
        t['artist_id'] = track.artist.id.rsplit('/', 1)[1]
    if track.duration is not None:
        # Duration not always present.
        t['length'] = track.duration/(1000.0)
    return t

def release_dict(release, tracks=None):
    """Takes a MusicBrainz `Release` object and returns a dictionary
    containing the interesting data about that release. A list of
    `Track` objects may also be provided as `tracks`; they are then
    included in the resulting dictionary.
    """
    # Basic info.
    out = {'album':     release.title,
           'album_id':  release.id.rsplit('/', 1)[1],
           'artist':    release.artist.name,
           'artist_id': release.artist.id.rsplit('/', 1)[1],
           'asin':      release.asin,
           'albumtype': '',
          }
    out['va'] = out['artist_id'] == VARIOUS_ARTISTS_ID

    # Release type not always populated.
    for releasetype in release.types:
        if releasetype in RELEASE_TYPES:
            out['albumtype'] = releasetype.split('#')[1].lower()
            break

    # Release date.
    try:
        date_str = release.getEarliestReleaseDate()
    except:
        # The python-musicbrainz2 module has a bug that will raise an
        # exception when there is no release date to be found. In this
        # case, we just skip adding a release date to the dict.
        pass
    else:
        if date_str:
            date_parts = date_str.split('-')
            for key in ('year', 'month', 'day'):
                if date_parts:
                    out[key] = int(date_parts.pop(0))

    # Tracks.
    if tracks is not None:
        out['tracks'] = map(track_dict, tracks)

    return out

def match_album(artist, album, tracks=None, limit=SEARCH_LIMIT):
    """Searches for a single album ("release" in MusicBrainz parlance)
    and returns an iterator over dictionaries of information (as
    returned by `release_dict`).

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

    # Search for the release.
    return find_releases(criteria)

def match_track(artist, title):
    """Searches for a single track and returns an iterable of track
    info dictionaries (as returned by `track_dict`).
    """
    return find_tracks({
        'artist': artist,
        'track': title,
    })

def album_for_id(albumid):
    """Fetches an album by its MusicBrainz ID and returns an
    information dictionary. If no match is found, returns None.
    """
    query = mbws.Query()
    inc = mbws.ReleaseIncludes(artist=True, tracks=True)
    try:
        album = _query_wrap(query.getReleaseById, albumid, inc)
    except (mbws.ResourceNotFoundError, mbws.RequestError):
        return None
    return release_dict(album, album.tracks)

def track_for_id(trackid):
    """Fetches a track by its MusicBrainz ID. Returns a track info
    dictionary or None if no track is found.
    """
    query = mbws.Query()
    inc = mbws.TrackIncludes(artist=True)
    try:
        track = _query_wrap(query.getTrackById, trackid, inc)
    except (mbws.ResourceNotFoundError, mbws.RequestError):
        return None
    return track_dict(track)
