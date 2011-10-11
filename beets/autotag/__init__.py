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

"""Facilities for automatically determining files' correct metadata.
"""
import os

from beets import library, mediafile
from beets.util import sorted_walk
from . import mb

# Parts of external interface.
from .hooks import AlbumInfo, TrackInfo
from .match import tag_item, tag_album
from .match import RECOMMEND_STRONG, RECOMMEND_MEDIUM, RECOMMEND_NONE
from .match import STRONG_REC_THRESH, MEDIUM_REC_THRESH, REC_GAP_THRESH


# Additional utilities for the main interface.

def albums_in_dir(path):
    """Recursively searches the given directory and returns an iterable
    of (path, items) where path is a containing directory and items is
    a list of Items that is probably an album. Specifically, any folder
    containing any media files is an album.
    """
    for root, dirs, files in sorted_walk(path):
        # Get a list of items in the directory.
        items = []
        for filename in files:
            try:
                i = library.Item.from_path(os.path.join(root, filename))
            except mediafile.FileTypeError:
                pass
            except mediafile.UnreadableFileError:
                log.warn('unreadable file: ' + filename)
            else:
                items.append(i)
        
        # If it's nonempty, yield it.
        if items:
            yield root, items

def apply_item_metadata(item, track_data):
    """Set an item's metadata from its matched info dictionary.
    """
    item.artist = track_data['artist']
    item.title = track_data['title']
    item.mb_trackid = track_data['id']
    if 'artist_id' in track_data:
        item.mb_artistid = track_data['artist_id']
    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?

def apply_metadata(items, info):
    """Set the items' metadata to match the data given in info. The
    list of items must be ordered.
    """
    for index, (item, track_data) in enumerate(zip(items, info['tracks'])):
        # Album, artist, track count.
        if 'artist' in track_data:
            item.artist = track_data['artist']
        else:
            item.artist = info['artist']
        item.albumartist = info['artist']
        item.album = info['album']
        item.tracktotal = len(items)
        
        # Release date.
        if 'year' in info:
            item.year = info['year']
        if 'month' in info:
            item.month = info['month']
        if 'day' in info:
            item.day = info['day']
        
        # Title and track index.
        item.title = track_data['title']
        item.track = index + 1
        
        # MusicBrainz IDs.
        item.mb_trackid = track_data['id']
        item.mb_albumid = info['album_id']
        if 'artist_id' in track_data:
            item.mb_artistid = track_data['artist_id']
        else:
            item.mb_artistid = info['artist_id']
        item.mb_albumartistid = info['artist_id']
        item.albumtype = info['albumtype']
        if 'label' in info:
            item.label = info['label']
        
        # Compilation flag.
        item.comp = info['va']
