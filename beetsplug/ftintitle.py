# This file is part of beets.
# Copyright 2013, Verrus, <github.com/Verrus/beets-plugin-featInTitle>
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

"""Moves "featured" artists to the title from the artist field.
"""
from beets.plugins import BeetsPlugin
from beets import ui
from beets.util import displayable_path
from beets import config
import re


def split_on_feat(artist):
    """Given an artist string, split the "main" artist from any artist
    on the right-hand side of a string like "feat". Return the main
    artist, which is always a string, and the featuring artist, which
    may be a string or None if none is present.
    """
    parts = re.split(
        r'[fF]t\.|[fF]eaturing|[fF]eat\.|\b[wW]ith\b|&|vs\.|and',
        artist,
        1,  # Only split on the first "feat".
    )
    parts = [s.strip() for s in parts]
    if len(parts) == 1:
        return parts[0], None
    else:
        return parts


def contains_feat(title):
    """Determine whether the title contains a "featured" marker.
    """
    return bool(re.search(
        r'[fF]t\.|[fF]eaturing|[fF]eat\.|\b[wW]ith\b|&',
        title,
    ))


def update_metadata(item, feat_part):
    """Choose how to add new artists to the title and write the new
    metadata. Also, print out messages about any changes that are made.
    """
    # In all cases, update the artist fields.
    ui.print_(u'artist: {0} -> {1}'.format(item.artist, item.albumartist))
    item.artist = item.albumartist
    item.artist_sort, _ = split_on_feat(item.artist_sort)  # Strip featured.

    # Only update the title if it does not already contain a featured
    # artist.
    if not contains_feat(item.title):
        new_title = u"{0} feat. {1}".format(item.title, feat_part)
        ui.print_(u'title: {0} -> {1}'.format(item.title, new_title))
        item.title = new_title


def ft_in_title(item):
    """Look for featured artists in the item's artist fields and move
    them to the title.
    """
    artist = item.artist.strip()
    albumartist = item.albumartist.strip()

    # Check whether there is a featured artist on this track and the
    # artist field does not exactly match the album artist field. In
    # that case, we attempt to move the featured artist to the title.
    _, featured = split_on_feat(artist)
    if featured and albumartist != artist:
        ui.print_(displayable_path(item.path))
        feat_part = None

        # Look for the album artist in the artist field. If it's not
        # present, give up.
        albumartist_split = artist.split(albumartist)
        if len(albumartist_split) <= 1:
            ui.print_('album artist not present in artist')

        # If the last element of the split (the right-hand side of the
        # album artist) is nonempty, then it probably contains the
        # featured artist.
        elif albumartist_split[-1] != '':
            # Extract the featured artist from the right-hand side.
            _, feat_part = split_on_feat(albumartist_split[-1])

        # Otherwise, if there's nothing on the right-hand side, look for a
        # featuring artist on the left-hand side.
        else:
            lhs, rhs = split_on_feat(albumartist_split[0])
            if rhs:
                feat_part = lhs

        # If we have a featuring artist, move it to the title.
        if feat_part:
            update_metadata(item, feat_part)
        else:
            ui.print_(u'no featuring artists found')

        ui.print_()


class FtInTitlePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('ftintitle',
                            help='move featured artists to the title field')
        def func(lib, opts, args):
            write = config['import']['write'].get(bool)
            for item in lib.items():
                ft_in_title(item)
                item.store()
                if write:
                    item.write()
        cmd.func = func
        return [cmd]
