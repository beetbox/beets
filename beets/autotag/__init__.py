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
    collapse_pat = collapse_paths = collapse_items = None

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

        # If we're currently collapsing the constituent directories in a
        # multi-disc album, check whether we should continue collapsing
        # and add the current directory. If so, just add the directory
        # and move on to the next directory. If not, stop collapsing.
        if collapse_paths:
            if collapse_paths[0] in ancestry(root) or (collapse_pat and
                    collapse_pat.match(os.path.basename(root))):
                # Still collapsing.
                collapse_paths.append(root)
                collapse_items += items
                continue
            else:
                # Collapse finished. Yield the collapsed directory and
                # proceed to process the current one.
                if collapse_items:
                    yield collapse_paths, collapse_items
                collapse_pat = collapse_paths = collapse_items = None

        # Check whether this directory looks like the *first* directory
        # in a multi-disc sequence. There are two indicators: the file
        # is named like part of a multi-disc sequence (e.g., "Title Disc
        # 1") or it contains no items but only directories that are
        # named in this way.
        start_collapsing = False
        for marker in MULTIDISC_MARKERS:
            marker_pat = re.compile(MULTIDISC_PAT_FMT % marker, re.I)

            # Is this directory the first in a flattened multi-disc album?
            match = marker_pat.match(os.path.basename(root))
            if match:
                start_collapsing = True
                # Set the current pattern to match directories with the same
                # prefix as this one, followed by a digit.
                collapse_pat = re.compile(r'^%s\d' %
                    re.escape(match.group(1)), re.I)
                break

            # Is this directory the root of a nested multi-disc album?
            elif dirs and not items:
                # Check whether all subdirectories have the same prefix.
                start_collapsing = True
                subdir_pat = None
                for subdir in dirs:
                    # The first directory dictates the pattern for
                    # the remaining directories.
                    if not subdir_pat:
                        match = marker_pat.match(subdir)
                        if match:
                            subdir_pat = re.compile(r'^%s\d' %
                                re.escape(match.group(1)), re.I)
                        else:
                            start_collapsing = False
                            break

                    # Subsequent directories must match the pattern.
                    elif not subdir_pat.match(subdir):
                        start_collapsing = False
                        break

                # If all subdirectories match, don't check other
                # markers.
                if start_collapsing:
                    break

        # If either of the above heuristics indicated that this is the
        # beginning of a multi-disc album, initialize the collapsed
        # directory and item lists and check the next directory.
        if start_collapsing:
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
