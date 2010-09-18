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
import datetime
import musicbrainz2.webservice as mbws
from threading import Lock

SEARCH_LIMIT = 10

class ServerBusyError(Exception): pass

# We hard-code IDs for artists that can't easily be searched for.
SPECIAL_CASE_ARTISTS = {
    '!!!': 'f26c72d3-e52c-467b-b651-679c73d8e1a7',
}

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
                if 'Error 503' not in str(e.reason):
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
    return re.sub(r'([+\-&|!(){}\[\]\^"~*?:\\])', r'\\\1', text)

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
    
    # Build Lucene query (the MusicBrainz 'query' filter).
    query_parts = []
    for name, value in criteria.items():
        value = _lucene_escape(value).strip().lower()
        if value:
            query_parts.append(u'%s:(%s)' % (name, value))
    query = u' '.join(query_parts)
    
    # Build the filter and send the query.
    return get_releases(limit=limit, query=query)

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
          }

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
    if tracks:
        out['tracks'] = []
        for track in tracks:
            t = {'title': track.title,
                 'id': track.id.rsplit('/', 1)[1]}
            if track.duration is not None:
                # Duration not always present.
                t['length'] = track.duration/(1000.0)
            out['tracks'].append(t)

    return out

def match_album(artist, album, tracks=None):
    """Searches for a single album ("release" in MusicBrainz parlance)
    and returns an iterator over dictionaries of information (as
    returned by `release_dict`).

    The query consists of an artist name, an album name, and,
    optionally, a number of tracks on the album.
    """
    # Build search criteria.
    criteria = {'artist':  artist, 'release': album}
    if tracks is not None:
        criteria['tracks'] = str(tracks)

    # Search for the release.
    return find_releases(criteria)

def album_for_id(albumid):
    """Fetches an album by its MusicBrainz ID and returns an
    information dictionary. If no match is found, returns None.
    """
    query = mbws.Query()
    inc = mbws.ReleaseIncludes(artist=True, tracks=True)
    try:
        album = _query_wrap(query.getReleaseById, albumid, inc)
    except mbws.ResourceNotFoundError:
        return None
    return release_dict(album, album.tracks)
