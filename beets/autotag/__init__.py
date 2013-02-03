# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

from beets import library, mediafile, config
from beets.util import sorted_walk, ancestry, displayable_path

# Parts of external interface.
from .hooks import AlbumInfo, TrackInfo, AlbumMatch, TrackMatch
from .match import AutotagError
from .match import tag_item, tag_album
from .match import \
    RECOMMEND_STRONG, RECOMMEND_MEDIUM, RECOMMEND_LOW, RECOMMEND_NONE

# Global logger.
log = logging.getLogger('beets')

# Constants for directory walker.
MULTIDISC_MARKERS = (r'disc', r'cd')
MULTIDISC_PAT_FMT = r'^(.*%s[\W_]*)\d'


# Additional utilities for the main interface.

def albums_in_dir(path):
    """Recursively searches the given directory and returns an iterable
    of (paths, items) where paths is a list of directories and items is
    a list of Items that is probably an album. Specifically, any folder
    containing any media files is an album.
    """
    collapse_pat = collapse_paths = collapse_items = multidisc = None

    for root, dirs, files in sorted_walk(path,
                                         ignore=config['ignore'].as_str_seq()):
        # Get a list of items in the directory.
        items = []
        for filename in files:
            try:
                i = library.Item.from_path(os.path.join(root, filename))
            except mediafile.FileTypeError:
                pass
            except mediafile.UnreadableFileError:
                log.warn(u'unreadable file: {0}'.format(
                    displayable_path(filename))
                )
            else:
                items.append(i)

        # If we're collapsing, test to see whether we should continue to
        # collapse. If so, just add to the collapsed paths and items;
        # otherwise, end the collapse and continue as normal.
        if collapse_paths:
            if collapse_paths[0] in ancestry(root) or \
                    collapse_pat.match(os.path.basename(root)):
                # Still collapsing.
                collapse_paths.append(root)
                collapse_items += items
                continue
            else:
                # Collapse finished. Yield the collapsed directory and
                # proceed to process the current one.
                if collapse_items:
                    yield collapse_paths, collapse_items
                collapse_pat = collapse_paths = collapse_items = \
                    multidisc = None

        # Does the current directory look like the start of a multi-disc
        # album? If so, begin collapsing here.
        for marker in MULTIDISC_MARKERS:
            marker_pat = re.compile(MULTIDISC_PAT_FMT % marker, re.I)
            # Is this directory the first in a flattened multi-disc album?
            match = marker_pat.match(os.path.basename(root))
            if match:
                multidisc = True
                collapse_pat = re.compile(r'^%s\d' %
                    re.escape(match.groups()[0]), re.I)
                break
            # Is this directory the root of a nested multi-disc album?
            elif dirs and not items:
                multidisc = True
                for dirname in dirs:
                    if collapse_pat:
                        if collapse_pat.match(dirname):
                            continue
                    else:
                        match = marker_pat.match(dirname)
                        if match:
                            collapse_pat = re.compile(r'^%s\d' %
                                re.escape(match.groups()[0]), re.I)
                            continue
                    multidisc = False
                    break
                if multidisc:
                    break

        # This becomes True only when all sub-directories match a
        # pattern for a single marker with a common prefix, or when
        # this directory matches a multidisc marker pattern.
        if multidisc:
            # Start collapsing; continue to the next iteration.
            collapse_paths = [root]
            collapse_items = items
            continue

        # If it's nonempty, yield it.
        if items:
            yield [root], items

    # Clear out any unfinished collapse.
    if collapse_paths and collapse_items:
        yield collapse_paths, collapse_items

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
    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?

def apply_metadata(album_info, mapping):
    """Set the items' metadata to match an AlbumInfo object using a
    mapping from Items to TrackInfo objects.
    """
    for item, track_info in mapping.iteritems():
        # Album, artist, track count.
        if track_info.artist:
            item.artist = track_info.artist
        else:
            item.artist = album_info.artist
        item.albumartist = album_info.artist
        item.album = album_info.album
        item.tracktotal = len(album_info.tracks)

        # Artist sort and credit names.
        item.artist_sort = track_info.artist_sort or album_info.artist_sort
        item.artist_credit = track_info.artist_credit or \
                             album_info.artist_credit
        item.albumartist_sort = album_info.artist_sort
        item.albumartist_credit = album_info.artist_credit

        # Release date.
        if album_info.year:
            item.year = album_info.year
        if album_info.month:
            item.month = album_info.month
        if album_info.day:
            item.day = album_info.day

        # Title.
        item.title = track_info.title

        if config['per_disc_numbering']:
            item.track = track_info.medium_index
        else:
            item.track = track_info.index

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
        item.albumtype = album_info.albumtype
        if album_info.label:
            item.label = album_info.label
        item.asin = album_info.asin
        item.catalognum = album_info.catalognum
        item.script = album_info.script
        item.language = album_info.language
        item.country = album_info.country
        item.albumstatus = album_info.albumstatus
        item.media = album_info.media
        item.albumdisambig = album_info.albumdisambig
        item.disctitle = track_info.disctitle
