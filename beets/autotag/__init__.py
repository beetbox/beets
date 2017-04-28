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
    """
    for item, track_info in mapping.items():
        # Album, artist, track count.
        if track_info.artist:
            item.artist = track_info.artist
        else:
            item.artist = album_info.artist
        item.albumartist = album_info.artist
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
        item.mb_albumid = album_info.album_id
        if track_info.artist_id:
            item.mb_artistid = track_info.artist_id
        else:
            item.mb_artistid = album_info.artist_id
        item.mb_albumartistid = album_info.artist_id
        item.mb_releasegroupid = album_info.releasegroup_id

        # Compilation flag.
        item.comp = album_info.va

        # Miscellaneous metadata.
        for field in ('albumtype',
                      'label',
                      'asin',
                      'catalognum',
                      'script',
                      'language',
                      'country',
                      'albumstatus',
                      'albumdisambig',
                      'data_source',):
            value = getattr(album_info, field)
            if value is not None:
                item[field] = value
        if track_info.disctitle is not None:
            item.disctitle = track_info.disctitle

        if track_info.media is not None:
            item.media = track_info.media

        if track_info.lyricist is not None:
            item.lyricist = track_info.lyricist
        if track_info.composer is not None:
            item.composer = track_info.composer
        if track_info.composer_sort is not None:
            item.composer_sort = track_info.composer_sort
        if track_info.arranger is not None:
            item.arranger = track_info.arranger

        item.track_alt = track_info.track_alt
