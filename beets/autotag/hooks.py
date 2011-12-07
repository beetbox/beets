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

"""Glue between metadata sources and the matching logic."""

from beets import plugins
from beets.autotag import mb

# Classes used to represent candidate options.

class AlbumInfo(object):
    """Describes a canonical release that may be used to match a release
    in the library. Consists of these data members:

    - ``album``: the release title
    - ``album_id``: MusicBrainz ID; UUID fragment only
    - ``artist``: name of the release's primary artist
    - ``artist_id``
    - ``tracks``: list of TrackInfo objects making up the release
    - ``asin``: Amazon ASIN
    - ``albumtype``: string describing the kind of release
    - ``va``: boolean: whether the release has "various artists"
    - ``year``: release year
    - ``month``: release month
    - ``day``: release day
    - ``label``: music label responsible for the release

    The fields up through ``tracks`` are required. The others are
    optional and may be None.
    """
    def __init__(self, album, album_id, artist, artist_id, tracks, asin=None,
                 albumtype=None, va=False, year=None, month=None, day=None,
                 label=None):
        self.album = album
        self.album_id = album_id
        self.artist = artist
        self.artist_id = artist_id
        self.tracks = tracks
        self.asin = asin
        self.albumtype = albumtype
        self.va = va
        self.year = year
        self.month = month
        self.day = day
        self.label = label

class TrackInfo(object):
    """Describes a canonical track present on a release. Appears as part
    of an AlbumInfo's ``tracks`` list. Consists of these data members:

    - ``title``: name of the track
    - ``track_id``: MusicBrainz ID; UUID fragment only
    - ``artist``: individual track artist name
    - ``artist_id``
    - ``length``: float: duration of the track in seconds

    Only ``title`` and ``track_id`` are required. The rest of the fields
    may be None.
    """
    def __init__(self, title, track_id, artist=None, artist_id=None,
                 length=None):
        self.title = title
        self.track_id = track_id
        self.artist = artist
        self.artist_id = artist_id
        self.length = length


# Aggregation of sources.

def _album_for_id(album_id):
    """Get an album corresponding to a MusicBrainz release ID."""
    return mb.album_for_id(album_id)

def _track_for_id(track_id):
    """Get an item for a recording MBID."""
    return mb.track_for_id(track_id)

def _album_candidates(items, artist, album, va_likely):
    """Search for album matches. ``items`` is a list of Item objects
    that make up the album. ``artist`` and ``album`` are the respective
    names (strings), which may be derived from the item list or may be
    entered by the user. ``va_likely`` is a boolean indicating whether
    the album is likely to be a "various artists" release.
    """
    out = []

    # Base candidates if we have album and artist to match.
    if artist and album:
        out.extend(mb.match_album(artist, album, len(items)))

    # Also add VA matches from MusicBrainz where appropriate.
    if va_likely and album:
        out.extend(mb.match_album(None, album, len(items)))

    # Candidates from plugins.
    out.extend(plugins.candidates(items))

    return out

def _item_candidates(item, artist, title):
    """Search for item matches. ``item`` is the Item to be matched.
    ``artist`` and ``title`` are strings and either reflect the item or
    are specified by the user.
    """
    out = []

    # MusicBrainz candidates.
    if artist and title:
        out.extend(mb.match_track(artist, title))

    # Plugin candidates.
    out.extend(plugins.item_candidates(item))

    return out
