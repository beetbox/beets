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
from beets import config
import logging
import re

log = logging.getLogger('beets')


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


def update_metadata(item, feat_part, drop_feat):
    """Choose how to add new artists to the title and set the new
    metadata. Also, print out messages about any changes that are made.
    If `drop_feat` is set, then do not add the artist to the title; just
    remove it from the artist field.
    """
    # In all cases, update the artist fields.
    ui.print_(u'artist: {0} -> {1}'.format(item.artist, item.albumartist))
    item.artist = item.albumartist
    if item.artist_sort:
        # Just strip the featured artist from the sort name.
        item.artist_sort, _ = split_on_feat(item.artist_sort)

    # Only update the title if it does not already contain a featured
    # artist and if we do not drop featuring information.
    if not drop_feat and not contains_feat(item.title):
        new_title = u"{0} feat. {1}".format(item.title, feat_part)
        ui.print_(u'title: {0} -> {1}'.format(item.title, new_title))
        item.title = new_title


def ft_in_title(item, drop_feat, write):
    """Look for featured artists in the item's artist fields and move
    them to the title.
    """
    artist = item.artist.strip()

    _, feat_part = split_on_feat(artist)

    if feat_part:
        update_metadata(item, feat_part, drop_feat)
    else:
        ui.print_(u'no featuring artists found')

    if write:
        item.try_write()
    item.store()


class FtInTitlePlugin(BeetsPlugin):
    def __init__(self):
        super(FtInTitlePlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'auto': True,
            'drop': False
        })

        self._command = ui.Subcommand(
            'ftintitle',
            help='move featured artists to the title field')

        self._command.parser.add_option(
            '-d', '--drop', dest='drop',
            action='store_true', default=False,
            help='drop featuring from artists and ignore title update')

    def commands(self):

        def func(lib, opts, args):
            self.config.set_args(opts)
            drop_feat = self.config['drop'].get(bool)
            write = config['import']['write'].get(bool)

            for item in lib.items(ui.decargs(args)):
                ft_in_title(item, drop_feat, write)

        self._command.func = func
        return [self._command]

    def imported(self, session, task):
        """Import hook for moving featuring artist automatically.
        """
        drop_feat = self.config['drop'].get(bool)
        write = config['import']['write'].get(bool)
        if self.config['auto'].get(bool):
            for item in task.imported_items():
                ft_in_title(item, drop_feat, write)
