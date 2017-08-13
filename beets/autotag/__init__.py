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
from .hooks import AlbumInfo, TrackInfo, AlbumMatch, TrackMatch  # noqa
from .match import tag_item, tag_album, Proposal  # noqa
from .match import Recommendation  # noqa

# Global logger.
log = logging.getLogger('beets')


# Additional utilities for the main interface.

def apply_item_metadata(item, track_info):
    """Set an item's metadata from its matched TrackInfo object.
    """
    item.artist = track_info.artist
    item.artist_sort = track_info.artist_sort
    item.artist_credit = track_info.artist_credit
    item.title = track_info.title
    item.mb_trackid = track_info.track_id
    if track_info.artist_id:
        item.mb_artistid = track_info.artist_id
    if track_info.data_source:
        item.data_source = track_info.data_source

    if track_info.lyricist is not None:
        item.lyricist = track_info.lyricist
    if track_info.composer is not None:
        item.composer = track_info.composer
    if track_info.composer_sort is not None:
        item.composer_sort = track_info.composer_sort
    if track_info.arranger is not None:
        item.arranger = track_info.arranger

    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?


def apply_metadata(album_info, mapping):
    """Set the items' metadata to match an AlbumInfo object using a
    mapping from Items to TrackInfo objects.

    :param album_info: object to match
    :type album_info: :py:class:`hooks.AlbumInfo`
    """
    # Maps item attribute to AlbumInfo key
    itemattr_to_albuminfokey = {
        'albumartist_sort': 'artist_sort',
        'albumartist_credit': 'artist_credit',
        'disctotal': 'mediums',
        'mb_albumid': 'album_id',
        'mb_albumartistid': 'artist_id',
        'mb_releasegroupid': 'releasegroup_id',
        'comp': 'va',  # Compilation flag
        'albumtype': 'albumtype',
        'label': 'label',
        'asin': 'asin',
        'catalognum': 'catalognum',
        'script': 'script',
        'language': 'language',
        'country': 'country',
        'albumstatus': 'albumstatus',
        'albumdisambig': 'albumdisambig',
        'data_source': 'data_source',
        'album': 'album',
        'albumartist': 'artist',
    }
    # Maps item attributes to the corresponding TrackInfo key
    itemattr_to_trackinfokey = {
        'title': 'title',
        'disc': 'medium',
        'mb_trackid': 'track_id',
        'track_alt': 'track_alt',
        'lyricist': 'lyricist',
        'composer': 'composer',
        'composer_sort': 'composer_sort',
        'arranger': 'arranger',
        'media': 'media',
        'disctitle': 'disctitle',
    }
    # Maps the item attribute to the corresponding key to be tried
    # first on TrackInfo and then on AlbumInfo
    itemattr_to_torainfokey = {
        'artist': 'artist',
        'artist_sort': 'artist_sort',
        'artist_credit': 'artist_credit',
        'mb_artistid': 'artist_id',
    }
    for item, track_info in mapping.items():
        def try_track_info(attr):
            """Tries to set attr to the one of ti, else uses ai"""
            return (track_info[attr] if attr in track_info.keys()
                    else album_info[attr] if attr in album_info.keys()
                    else None)

        # Info taken from AlbumInfo
        for attr, key in itemattr_to_albuminfokey.items():
            setattr(item, attr, album_info[key])

        # Info taken from TrackInfo
        for attr, key in itemattr_to_trackinfokey.items():
            setattr(item, attr, track_info[key])

        for attr, key in itemattr_to_torainfokey.items():
            setattr(item, attr, try_track_info(key))

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
