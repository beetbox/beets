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
import logging
import re

from beets import library, mediafile
from beets.util import sorted_walk, ancestry

# Parts of external interface.
from .hooks import AlbumInfo, TrackInfo
from .match import AutotagError
from .match import tag_item, tag_album
from .match import RECOMMEND_STRONG, RECOMMEND_MEDIUM, RECOMMEND_NONE
from .match import STRONG_REC_THRESH, MEDIUM_REC_THRESH, REC_GAP_THRESH

# Global logger.
log = logging.getLogger('beets')

# Constants for directory walker.
MULTIDISC_MARKERS = (r'part', r'volume', r'vol\.', r'disc', r'cd')
MULTIDISC_PAT_FMT = r'%s\s*\d'


# Additional utilities for the main interface.

def albums_in_dir(path, ignore=()):
    """Recursively searches the given directory and returns an iterable
    of (path, items) where path is a containing directory and items is
    a list of Items that is probably an album. Specifically, any folder
    containing any media files is an album. Directories and file names
    that match the glob patterns in ``ignore`` are skipped.
    """
    collapse_root = None
    collapse_items = None

    for root, dirs, files in sorted_walk(path, ignore):
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

        # If we're collapsing, test to see whether we should continue to
        # collapse. If so, just add to the collapsed item set;
        # otherwise, end the collapse and continue as normal.
        if collapse_root is not None:
            if collapse_root in ancestry(root):
                # Still collapsing.
                collapse_items += items
                continue
            else:
                # Collapse finished. Yield the collapsed directory and
                # proceed to process the current one.
                if collapse_items:
                    yield collapse_root, collapse_items
                collapse_root = collapse_items = None

        # Does the current directory look like a multi-disc album? If
        # so, begin collapsing here.
        if dirs and not items: # Must be only directories.
            multidisc = False
            for marker in MULTIDISC_MARKERS:
                pat = MULTIDISC_PAT_FMT % marker
                if all(re.search(pat, dirname, re.I) for dirname in dirs):
                    multidisc = True
                    break

            # This becomes True only when all directories match a
            # pattern for a single marker.
            if multidisc:
                # Start collapsing; continue to the next iteration.
                collapse_root = root
                collapse_items = []
                continue
        
        # If it's nonempty, yield it.
        if items:
            yield root, items

    # Clear out any unfinished collapse.
    if collapse_root is not None and collapse_items:
        yield collapse_root, collapse_items

def apply_item_metadata(item, track_info):
    """Set an item's metadata from its matched TrackInfo object.
    """
    item.artist = track_info.artist
    item.title = track_info.title
    item.mb_trackid = track_info.track_id
    if track_info.artist_id:
        item.mb_artistid = track_info.artist_id
    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?

def apply_metadata(items, album_info):
    """Set the items' metadata to match an AlbumInfo object. The list
    of items must be ordered.
    """
    for index, (item, track_info) in enumerate(zip(items, album_info.tracks)):
        # Album, artist, track count.
        if not item:
            continue
        if track_info.artist:
            item.artist = track_info.artist
        else:
            item.artist = album_info.artist
        item.albumartist = album_info.artist
        item.album = album_info.album
        item.tracktotal = len(items)
        
        # Release date.
        if album_info.year:
            item.year = album_info.year
        if album_info.month:
            item.month = album_info.month
        if album_info.day:
            item.day = album_info.day
        
        # Title and track index.
        item.title = track_info.title
        item.track = index + 1
        
        # MusicBrainz IDs.
        item.mb_trackid = track_info.track_id
        item.mb_albumid = album_info.album_id
        if track_info.artist_id:
            item.mb_artistid = track_info.artist_id
        else:
            item.mb_artistid = album_info.artist_id
        item.mb_albumartistid = album_info.artist_id
        item.albumtype = album_info.albumtype
        if album_info.label:
            item.label = album_info.label
        
        # Compilation flag.
        item.comp = album_info.va
