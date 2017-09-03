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

"""Facilities for automatically determining files' correct metadata."""

from __future__ import division, absolute_import, print_function

from beets import logging
from beets import config

# Parts of external interface.
from .hooks import AlbumInfo, TrackInfo, AlbumMatch, TrackMatch  # noqa
from .match import tag_item, tag_album, Proposal  # noqa
from .match import Recommendation  # noqa

# Global logger.
log = logging.getLogger('beets')


INFO2ITEM = {
    'track_id': 'mb_trackid',
    'artist_id': 'mb_artistid',
}
"""Translates info attributes to item attributes"""


# Additional utilities for the main interface.

def apply_item_metadata(item, track_info):
    """Set an item's metadata from its matched TrackInfo object.
    """
    for fld in track_info.keys():
        if fld in INFO2ITEM.keys():
            setattr(item, INFO2ITEM[fld], track_info[fld])
    item.artist = track_info.artist
    item.artist_sort = track_info.artist_sort
    item.artist_credit = track_info.artist_credit
    item.title = track_info.title
    item.mb_trackid = track_info.track_id
    if track_info.artist_id:
        item.mb_artistid = track_info.artist_id
    if track_info.data_source:
        item.data_source = track_info.data_source

    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?


def apply_metadata(album_info, mapping):
    """Set the metadata of item to match an AlbumInfo object using a
    mapping from Items to TrackInfo objects.

    :param album_info: object to match
    :type album_info: :py:class:`hooks.AlbumInfo`
    :param mapping: maps an :py:class:`Item` to a :py:class:`TrackInfo`
    """
    album_fields = album_info.keys()
    album_fields.remove('tracks')  # tracks is special

    for item, track_info in mapping.items():
        # First set album info
        for fld in album_fields:
            if fld in INFO2ITEM.keys():
                setattr(item, INFO2ITEM[fld], album_info[fld])
            else:
                setattr(item, fld, album_info[fld])
        # And then track info, to overwrite album info
        track_fields = track_info.keys()
        for fld in track_fields:
            if fld in INFO2ITEM.keys():
                setattr(item, INFO2ITEM[fld], track_info[fld])
            else:
                setattr(item, fld, track_info[fld])

        # Release date.
        for prefix in '', 'original_':
            if config['original_date'] and not prefix:
                # Ignore specific release date.
                continue

            for suffix in 'year', 'month', 'day':
                key = prefix + suffix
                value = album_info[key] if key in album_info.keys() else 0
                # value = getattr(album_info, key) or 0

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

        if config['per_disc_numbering']:
            # We want to let the track number be zero, but if the medium index
            # is not provided we need to fall back to the overall index.
            setattr(item, 'track',
                    (track_info['medium_index']
                     if 'medium_index' in track_info.keys()
                     else track_info['index'] if 'index' in track_info.keys()
                     else None))
            setattr(item, 'tracktotal',
                    (track_info['medium_total']
                     if 'medium_total' in track_info.keys()
                     else len(album_info['tracks'])))
        else:
            setattr(item, 'track', track_info['index'])
            setattr(item, 'tracktotal', len(album_info['tracks']))
