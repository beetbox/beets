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


# Additional utilities for the main interface.

def apply_item_metadata(item, track_info):
    """Set an item's metadata from its matched TrackInfo object.
    """
    for attr in track_info:
        item.__setattr__(attr, getattr(track_info, attr))

    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?


def apply_metadata(album_info, mapping):
    """Set the items' metadata to match an AlbumInfo object using a
    mapping from Items to TrackInfo objects.
    """
    for item, track_info in mapping.items():
        # Artist or artist credit.
        if config['artist_credit']:

            if 'artist_credit' in track_info:
                item.artist = track_info.artist_credit
            elif 'artist' in track_info:
                item.artist = track_info.artist
            elif 'artist_credit' in album_info:
                item.artist = album_info.artist_credit
            elif 'artist' in album_info:
                item.artist = album_info.artist

            if 'artist_credit' in album_info:
                item.albumartist = album_info.artist_credit
            elif 'artist' in album_info:
                item.albumartist = album_info.artist

        else:
            if 'artist' in track_info:
                item.artist = track_info.artist
            elif 'artist' in album_info:
                item.artist = album_info.artist

            if 'artist' in album_info:
                item.albumartist = album_info.artist

        # Album.
        if 'album' in album_info:
            item.album = album_info.album

        # Artist sort and credit names.
        if 'artist_sort' in track_info:
            item.artist_sort = track_info.artist_sort
        elif 'artist_sort' in album_info:
            item.artist_sort = album_info.artist_sort

        if 'artist_credit' in track_info:
            item.artist_credit = track_info.artist_credit
        elif 'artist_credit' in album_info:
            item.artist_credit = album_info.artist_credit

        if 'albumartist_sort' in album_info:
            item.albumartist_sort = album_info.artist_sort

        if 'albumartist_credit' in album_info:
            item.albumartist_credit = album_info.artist_credit

        # Release date.
        for prefix in '', 'original_':
            if config['original_date'] and not prefix:
                # Ignore specific release date.
                continue

            for suffix in 'year', 'month', 'day':
                key = prefix + suffix
                if key in album_info:
                    value = getattr(album_info, key)
                else:
                    value = 0

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
        if 'title' in track_info:
            item.title = track_info.title

        if config['per_disc_numbering']:
            # We want to let the track number be zero, but if the medium index
            # is not provided we need to fall back to the overall index.
            if 'medium_index' in track_info:
                item.track = track_info.medium_index
            elif 'index' in track_info:
                item.track = track_info.index
            if 'medium_total' in track_info:
                item.tracktotal = track_info.medium_total
            elif 'tracks' in album_info:
                item.tracktotal = len(album_info.tracks)
        else:
            if 'index' in track_info:
                item.track = track_info.index
            if 'tracks' in album_info:
                item.tracktotal = len(album_info.tracks)

        # Disc and disc count.
        if 'medium' in track_info:
            item.disc = track_info.medium
        if 'mediums' in album_info:
            item.disctotal = album_info.mediums

        # MusicBrainz IDs.
        if 'track_id' in track_info:
            item.mb_trackid = track_info.track_id
        if 'release_track_id' in track_info:
            item.mb_releasetrackid = track_info.release_track_id
        if 'album_id' in album_info:
            item.mb_albumid = album_info.album_id
        if 'artist_id' in track_info:
            item.mb_artistid = track_info.artist_id
        elif 'artist_id' in album_info:
            item.mb_artistid = album_info.artist_id
        if 'artist_id' in album_info:
            item.mb_albumartistid = album_info.artist_id
        if 'releasegroup_id' in album_info:
            item.mb_releasegroupid = album_info.releasegroup_id

        # Compilation flag.
        if 'va' in album_info:
            item.comp = album_info.va

        # Track alt.
        if 'track_alt' in track_info:
            item.track_alt = track_info.track_alt

        # Miscellaneous/nullable metadata.
        misc_fields = {
            'album': (
                'albumtype',
                'label',
                'asin',
                'catalognum',
                'script',
                'language',
                'country',
                'style',
                'genre',
                'discogs_albumid',
                'discogs_artistid',
                'discogs_labelid',
                'albumstatus',
                'albumdisambig',
                'releasegroupdisambig',
                'data_source',
            ),
            'track': (
                'disctitle',
                'lyricist',
                'media',
                'composer',
                'composer_sort',
                'arranger',
                'work',
                'mb_workid',
                'work_disambig',
                'bpm',
                'initial_key',
                'genre'
            )
        }

        # Don't overwrite fields with empty values unless the
        # field is explicitly allowed to be overwritten
        for field in misc_fields['album']:
            clobber = field in config['overwrite_null']['album'].as_str_seq()
            if field in album_info:
                value = getattr(album_info, field)
                if value is None and not clobber:
                    continue
                item[field] = value

        for field in misc_fields['track']:
            clobber = field in config['overwrite_null']['track'].as_str_seq()
            if field in track_info:
                value = getattr(track_info, field)
                if value is None and not clobber:
                    continue
                item[field] = value
