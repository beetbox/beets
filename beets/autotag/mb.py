# coding=utf-8
#
# This file is part of beets.
# Copyright 2009, Adrian Sampson.
#
# Portions Copyright (C) 2006 Lukáš Lalinský
# from the MusicBrainz Picard project.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

"""Searches for albums in the MusicBrainz database.

This is a thin layer over the official `python-musicbrainz2` module. It
abstracts away that module's object model, the server's Lucene query
syntax, and other uninteresting parts of using musicbrainz2. The
principal interface is the function `match_album`.
"""

import re
import time
import datetime
import musicbrainz2.webservice as mbws

# MusicBrainz requires that a client does not query the server more
# than once a second. This function enforces that limit using a
# module-global variable to keep track of the last time a query was
# sent.
QUERY_WAIT_TIME = 1.0
last_query_time = 0.0
def _query_wait():
    """Wait until at least `QUERY_WAIT_TIME` seconds have passed since
    the last invocation of this function. This should be called (by
    this module) before any query is sent.
    """
    global last_query_time
    since_last_query = time.time() - last_query_time
    if since_last_query < QUERY_WAIT_TIME:
        time.sleep(QUERY_WAIT_TIME - since_last_query)
    last_query_time = time.time()

def _lucene_escape(text):
    """Escapes a string so it may be used verbatim in a Lucene query
    string.
    """
    # Regex stolen from MusicBrainz Picard.
    return re.sub(r'([+\-&|!(){}\[\]\^"~*?:\\])', r'\\\1', text)

# Workings of this function more or less stolen from Picard.
def find_releases(criteria, limit=25):
    """Get a list of `ReleaseResult` objects from the MusicBrainz
    database that match `criteria`. The latter is a dictionary whose
    keys are MusicBrainz field names and whose values are search terms
    for those fields.

    The field names are from MusicBrainz's Lucene query syntax, which
    is detailed here:
        http://wiki.musicbrainz.org/Text_Search_Syntax
    """
    # Build Lucene query (the MusicBrainz 'query' filter).
    query_parts = []
    for name, value in criteria.items():
        value = _lucene_escape(value).strip().lower()
        if value:
            query_parts.append(u'%s:(%s)' % (name, value))
    query = u' '.join(query_parts)
    
    # Build the filter and send the query.
    filt = mbws.ReleaseFilter(limit=limit, query=query)
    _query_wait()
    return mbws.Query().getReleases(filter=filt)

def release_dict(release, tracks=None):
    """Takes a MusicBrainz `Release` object and returns a dictionary
    containing the interesting data about that release. A list of
    `Track` objects may also be provided as `tracks`; they are then
    included in the resulting dictionary.
    """
    # Basic info.
    out = {'album':     release.title,
           'album_id':  release.id,
           'artist':    release.artist.name,
           'artist_id': release.artist.id,
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
                 'id': track.id}
            if track.duration is not None:
                # Duration not always present.
                t['length'] = track.duration/(1000.0)
            out['tracks'].append(t)

    return out

def release_tracks(release_id):
    """Given a MusicBrainz release ID, fetch a list of tracks on the
    release. If the release is not found, returns an empty list.
    """
    inc = mbws.ReleaseIncludes(tracks=True)
    _query_wait()
    release = mbws.Query().getReleaseById(release_id, inc)
    if release:
        return release.tracks
    else:
        return []

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
    results = find_releases(criteria, 10)

    for result in results:
        release = result.release
        tracks = release_tracks(release.id)
        yield release_dict(release, tracks)

def match_album_single(artist, album, tracks=None):
    """Behaves like match_album but, instead of returning an iterator,
    tries to get just a single result. Returns an info dictionary or
    None if no suitable match.
    """
    it = match_album(artist, album, tracks)
    try:
        return it.next()
    except StopIteration:
        return None

