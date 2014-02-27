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

log = logging.getLogger('beets')


def _print_and_apply_changes(lib, item, old_data, move, pretend, write):
    """Apply changes to an Item and preview them in the console. Return
    a boolean indicating whether any changes were made.
    """
    changed = ui.show_model_changes(item)
    if not changed:
        return False

    # If we're just pretending, then don't move or save.
    if not pretend:
        # Move the item if it's in the library.
        if move and lib.directory in util.ancestry(item.path):
            item.move(with_album=False)

        if write:
            try:
                item.write()
            except Exception as exc:
                log.error(u'could not sync {0}: {1}'.format(
                    util.displayable_path(item.path), exc))
                return False
        item.store()

    return True


def mbsync_singletons(lib, query, move, pretend, write):
    """Synchronize matching singleton items.
    """
    singletons_query = library.get_query(query, library.Item)
    singletons_query.subqueries.append(library.SingletonQuery(True))
    for s in lib.items(singletons_query):
        if not s.mb_trackid:
            log.info(u'Skipping singleton {0}: has no mb_trackid'
                     .format(s.title))
            continue

        old_data = dict(s)

        # Get the MusicBrainz recording info.
        track_info = hooks.track_for_mbid(s.mb_trackid)
        if not track_info:
            log.info(u'Recording ID not found: {0}'.format(s.mb_trackid))
            continue

        # Apply.
        with lib.transaction():
            autotag.apply_item_metadata(s, track_info)
            _print_and_apply_changes(lib, s, old_data, move, pretend, write)


def mbsync_albums(lib, query, move, pretend, write):
    """Synchronize matching albums.
    """
    # Process matching albums.
    for a in lib.albums(query):
        if not a.mb_albumid:
            log.info(u'Skipping album {0}: has no mb_albumid'.format(a.id))
            continue

        items = list(a.items())
        old_data = dict((item, dict(item)) for item in items)

        # Get the MusicBrainz album information.
        album_info = hooks.album_for_mbid(a.mb_albumid)
        if not album_info:
            log.info(u'Release ID not found: {0}'.format(a.mb_albumid))
            continue

        # Construct a track mapping according to MBIDs. This should work
        # for albums that have missing or extra tracks.
        mapping = {}
        for item in items:
            for track_info in album_info.tracks:
                if item.mb_trackid == track_info.track_id:
                    mapping[item] = track_info
                    break

        # Apply.
        with lib.transaction():
            autotag.apply_metadata(album_info, mapping)
            changed = False
            for item in items:
                changed |= _print_and_apply_changes(lib, item, old_data[item],
                                                    move, pretend, write)
            if not changed:
                # No change to any item.
                continue

            if not pretend:
                # Update album structure to reflect an item in it.
                for key in library.ALBUM_KEYS_ITEM:
                    setattr(a, key, getattr(items[0], key))

                # Move album art (and any inconsistent items).
                if move and lib.directory in util.ancestry(items[0].path):
                    log.debug(u'moving album {0}'.format(a.id))
                    a.move()


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
