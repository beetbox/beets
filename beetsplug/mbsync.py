# This file is part of beets.
# Copyright 2014, Jakob Schnitzer.
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

"""Update library's tags using MusicBrainz.
"""
import logging

from beets.plugins import BeetsPlugin
from beets import autotag, library, ui, util
from beets.autotag import hooks
from beets import config
from collections import defaultdict

log = logging.getLogger('beets')


def mbsync_singletons(lib, query, move, pretend, write):
    """Retrieve and apply info from the autotagger for items matched by
    query.
    """
    for item in lib.items(query + ['singleton:true']):
        if not item.mb_trackid:
            log.info(u'Skipping singleton {0}: has no mb_trackid'
                     .format(item.title))
            continue

        # Get the MusicBrainz recording info.
        track_info = hooks.track_for_mbid(item.mb_trackid)
        if not track_info:
            log.info(u'Recording ID not found: {0}'.format(item.mb_trackid))
            continue

        # Apply.
        with lib.transaction():
            autotag.apply_item_metadata(item, track_info)
            apply_item_changes(lib, item, move, pretend, write)


def mbsync_albums(lib, query, move, pretend, write):
    """Retrieve and apply info from the autotagger for albums matched by
    query and their items.
    """
    # Process matching albums.
    for a in lib.albums(query):
        if not a.mb_albumid:
            log.info(u'Skipping album {0}: has no mb_albumid'.format(a.id))
            continue

        items = list(a.items())

        # Get the MusicBrainz album information.
        album_info = hooks.album_for_mbid(a.mb_albumid)
        if not album_info:
            log.info(u'Release ID not found: {0}'.format(a.mb_albumid))
            continue

        # Map recording MBIDs to their information. Recordings can appear
        # multiple times on a release, so each MBID maps to a list of TrackInfo
        # objects.
        track_index = defaultdict(list)
        for track_info in album_info.tracks:
            track_index[track_info.track_id].append(track_info)

        # Construct a track mapping according to MBIDs. This should work
        # for albums that have missing or extra tracks. If there are multiple
        # copies of a recording, they are disambiguated using their disc and
        # track number.
        mapping = {}
        for item in items:
            candidates = track_index[item.mb_trackid]
            if len(candidates) == 1:
                mapping[item] = candidates[0]
            else:
                for c in candidates:
                    if c.medium_index == item.track and c.medium == item.disc:
                        mapping[item] = c
                        break

        # Apply.
        with lib.transaction():
            autotag.apply_metadata(album_info, mapping)
            changed = False
            for item in items:
                item_changed = ui.show_model_changes(item)
                changed |= item_changed
                if item_changed:
                    apply_item_changes(lib, item, move, pretend, write)

            if not changed:
                # No change to any item.
                continue

            if not pretend:
                # Update album structure to reflect an item in it.
                for key in library.Album.item_keys:
                    a[key] = items[0][key]
                a.store()

                # Move album art (and any inconsistent items).
                if move and lib.directory in util.ancestry(items[0].path):
                    log.debug(u'moving album {0}'.format(a.id))
                    a.move()


def apply_item_changes(lib, item, move, pretend, write):
    """Store, move and write the item according to the arguments.
    """
    if not pretend:
        # Move the item if it's in the library.
        if move and lib.directory in util.ancestry(item.path):
            item.move(with_album=False)

        if write:
            item.try_write()
        item.store()


def mbsync_func(lib, opts, args):
    """Command handler for the mbsync function.
    """
    move = opts.move
    pretend = opts.pretend
    write = opts.write
    query = ui.decargs(args)

    mbsync_singletons(lib, query, move, pretend, write)
    mbsync_albums(lib, query, move, pretend, write)


class MBSyncPlugin(BeetsPlugin):
    def __init__(self):
        super(MBSyncPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('mbsync',
                            help='update metadata from musicbrainz')
        cmd.parser.add_option('-p', '--pretend', action='store_true',
                              help='show all changes but do nothing')
        cmd.parser.add_option('-M', '--nomove', action='store_false',
                              default=True, dest='move',
                              help="don't move files in library")
        cmd.parser.add_option('-W', '--nowrite', action='store_false',
                              default=config['import']['write'], dest='write',
                              help="don't write updated metadata to files")
        cmd.func = mbsync_func
        return [cmd]
