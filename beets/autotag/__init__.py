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

"""Facilities for automatically determining files' correct metadata.
"""

from __future__ import division, absolute_import, print_function

from beets import logging
from beets import config

# Parts of external interface.
from .hooks import (  # noqa
    AlbumInfo,
    TrackInfo,
    AlbumMatch,
    TrackMatch,
    Distance,
)
from .match import tag_item, tag_album, Proposal  # noqa
from .match import Recommendation  # noqa

# Global logger.
log = logging.getLogger('beets')

# Metadata fields that are already hardcoded, or where the tag name changes.
SPECIAL_FIELDS = {
    'album': (
        'va',
        'releasegroup_id',
        'artist_id',
        'album_id',
        'mediums',
        'tracks',
        'year',
        'month',
        'day',
        'artist',
        'artist_credit',
        'artist_sort',
        'data_url'
    ),
    'track': (
        'track_alt',
        'artist_id',
        'release_track_id',
        'medium',
        'index',
        'medium_index',
        'title',
        'artist_credit',
        'artist_sort',
        'artist',
        'track_id',
        'medium_total',
        'data_url',
        'length'
    )
}


# Additional utilities for the main interface.

def apply_item_metadata(item, track_info):
    """Set an item's metadata from its matched TrackInfo object.
    """
    item.artist = track_info.artist
    item.artist_sort = track_info.artist_sort
    item.artist_credit = track_info.artist_credit
    item.title = track_info.title
    item.mb_trackid = track_info.track_id
    item.mb_releasetrackid = track_info.release_track_id
    if track_info.artist_id:
        item.mb_artistid = track_info.artist_id

    for field, value in track_info.items():
        # We only overwrite fields that are not already hardcoded.
        if field in SPECIAL_FIELDS['track']:
            continue
        if value is None:
            continue
        item[field] = value

    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?


def apply_metadata(album_info, mapping):
    """Set the items' metadata to match an AlbumInfo object using a
    mapping from Items to TrackInfo objects.
    """
    for item, track_info in mapping.items():
        # Artist or artist credit.
        if config['artist_credit']:
            item.artist = (track_info.artist_credit or
                           track_info.artist or
                           album_info.artist_credit or
                           album_info.artist)
            item.albumartist = (album_info.artist_credit or
                                album_info.artist)
        else:
            item.artist = (track_info.artist or album_info.artist)
            item.albumartist = album_info.artist

        # Album.
        item.album = album_info.album

        # Artist sort and credit names.
        item.artist_sort = track_info.artist_sort or album_info.artist_sort
        item.artist_credit = (track_info.artist_credit or
                              album_info.artist_credit)
        item.albumartist_sort = album_info.artist_sort
        item.albumartist_credit = album_info.artist_credit

        # Release date.
        for prefix in '', 'original_':
            if config['original_date'] and not prefix:
                # Ignore specific release date.
                continue

            for suffix in 'year', 'month', 'day':
                key = prefix + suffix
                value = getattr(album_info, key) or 0

                # If we don't even have a year, apply nothing.
                if suffix == 'year' and not value:
                    break

                # Otherwise, set the fetched value (or 0 for the month
                # and day if not available).
                item[key] = value

                # If we're using original release date for both fields,
                # also set item.year = info.original_year, etc.
                if config['original_date']:
                    item[suffix] = value

        # Title.
        item.title = track_info.title

        if config['per_disc_numbering']:
            # We want to let the track number be zero, but if the medium index
            # is not provided we need to fall back to the overall index.
            if track_info.medium_index is not None:
                item.track = track_info.medium_index
            else:
                item.track = track_info.index
            item.tracktotal = track_info.medium_total or len(album_info.tracks)
        else:
            item.track = track_info.index
            item.tracktotal = len(album_info.tracks)

        # Disc and disc count.
        item.disc = track_info.medium
        item.disctotal = album_info.mediums

        # MusicBrainz IDs.
        item.mb_trackid = track_info.track_id
        item.mb_releasetrackid = track_info.release_track_id
        item.mb_albumid = album_info.album_id
        if track_info.artist_id:
            item.mb_artistid = track_info.artist_id
        else:
            item.mb_artistid = album_info.artist_id
        item.mb_albumartistid = album_info.artist_id
        item.mb_releasegroupid = album_info.releasegroup_id

        # Compilation flag.
        item.comp = album_info.va

        # Track alt.
        item.track_alt = track_info.track_alt

        # Don't overwrite fields with empty values unless the
        # field is explicitly allowed to be overwritten
        for field, value in album_info.items():
            if field in SPECIAL_FIELDS['album']:
                continue
            clobber = field in config['overwrite_null']['album'].as_str_seq()
            if value is None and not clobber:
                continue
            item[field] = value

        for field, value in track_info.items():
            if field in SPECIAL_FIELDS['track']:
                continue
            clobber = field in config['overwrite_null']['track'].as_str_seq()
            value = getattr(track_info, field)
            if value is None and not clobber:
                continue
            item[field] = value
