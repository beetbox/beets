# This file is part of beets.
# Copyright 2015, Pedro Silva.
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

"""List duplicate tracks or albums.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import shlex

from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_, vararg_callback, Subcommand, UserError
from beets.util import command_output, displayable_path, subprocess

PLUGIN = 'duplicates'


def _process_item(item, lib, copy=False, move=False, delete=False,
                  tag=False, fmt=''):
    """Process Item `item` in `lib`.
    """
    if copy:
        item.move(basedir=copy, copy=True)
        item.store()
    if move:
        item.move(basedir=move, copy=False)
        item.store()
    if delete:
        item.remove(delete=True)
    if tag:
        try:
            k, v = tag.split('=')
        except:
            raise UserError('%s: can\'t parse k=v tag: %s' % (PLUGIN, tag))
        setattr(k, v)
        item.store()
    print_(format(item, fmt))


def _checksum(item, prog, log):
    """Run external `prog` on file path associated with `item`, cache
    output as flexattr on a key that is the name of the program, and
    return the key, checksum tuple.
    """
    args = [p.format(file=item.path) for p in shlex.split(prog)]
    key = args[0]
    checksum = getattr(item, key, False)
    if not checksum:
        log.debug(u'{0}: key {1} on item {2} not cached: computing checksum',
                  PLUGIN, key, displayable_path(item.path))
        try:
            checksum = command_output(args)
            setattr(item, key, checksum)
            item.store()
            log.debug(u'{0}: computed checksum for {1} using {2}',
                      PLUGIN, item.title, key)
        except subprocess.CalledProcessError as e:
            log.debug(u'{0}: failed to checksum {1}: {2}',
                      PLUGIN, displayable_path(item.path), e)
    else:
        log.debug(u'{0}: key {1} on item {2} cached: not computing checksum',
                  PLUGIN, key, displayable_path(item.path))
    return key, checksum


def _group_by(objs, keys, log):
    """Return a dictionary with keys arbitrary concatenations of attributes and
    values lists of objects (Albums or Items) with those keys.
    """
    import collections
    counts = collections.defaultdict(list)
    for obj in objs:
        values = [getattr(obj, k, None) for k in keys]
        values = [v for v in values if v not in (None, '')]
        if values:
            key = '\001'.join(values)
            counts[key].append(obj)
        else:
            log.debug(u'{0}: all keys {1} on item {2} are null: skipping',
                      PLUGIN, keys, displayable_path(obj.path))

    return counts


def _duplicates(objs, keys, full, log):
    """Generate triples of keys, duplicate counts, and constituent objects.
    """
    offset = 0 if full else 1
    for k, objs in _group_by(objs, keys, log).iteritems():
        if len(objs) > 1:
            yield (k, len(objs) - offset, objs[offset:])


class DuplicatesPlugin(BeetsPlugin):
    """List duplicate tracks or albums
    """
    def __init__(self):
        super(DuplicatesPlugin, self).__init__()

        self.config.add({
            'format': '',
            'count': False,
            'album': False,
            'full': False,
            'path': False,
            'keys': ['mb_trackid', 'mb_albumid'],
            'checksum': None,
            'copy': False,
            'move': False,
            'delete': False,
            'tag': False,
        })

        self._command = Subcommand('duplicates',
                                   help=__doc__,
                                   aliases=['dup'])
        self._command.parser.add_option('-c', '--count', dest='count',
                                        action='store_true',
                                        help='show duplicate counts')

        self._command.parser.add_option('-C', '--checksum', dest='checksum',
                                        action='store', metavar='PROG',
                                        help='report duplicates based on'
                                        ' arbitrary command')

        self._command.parser.add_option('-d', '--delete', dest='delete',
                                        action='store_true',
                                        help='delete items from library and '
                                        'disk')

        self._command.parser.add_option('-F', '--full', dest='full',
                                        action='store_true',
                                        help='show all versions of duplicate'
                                        ' tracks or albums')

        self._command.parser.add_option('-k', '--keys', dest='keys',
                                        action='callback', metavar='KEY1 KEY2',
                                        callback=vararg_callback,
                                        help='report duplicates based on keys')

        self._command.parser.add_option('-m', '--move', dest='move',
                                        action='store', metavar='DEST',
                                        help='move items to dest')

        self._command.parser.add_option('-o', '--copy', dest='copy',
                                        action='store', metavar='DEST',
                                        help='copy items to dest')

        self._command.parser.add_option('-t', '--tag', dest='tag',
                                        action='store',
                                        help='tag matched items with \'k=v\''
                                        ' attribute')
        self._command.parser.add_all_common_options()

    def commands(self):

        def _dup(lib, opts, args):
            self.config.set_args(opts)
            fmt = self.config['format'].get()
            album = self.config['album'].get(bool)
            full = self.config['full'].get(bool)
            keys = self.config['keys'].get()
            checksum = self.config['checksum'].get()
            copy = self.config['copy'].get()
            move = self.config['move'].get()
            delete = self.config['delete'].get(bool)
            tag = self.config['tag'].get()

            if album:
                keys = ['mb_albumid']
                items = lib.albums(decargs(args))
            else:
                items = lib.items(decargs(args))

            if self.config['path']:
                fmt = '$path'

            # Default format string for count mode.
            if self.config['count'] and not fmt:
                if album:
                    fmt = '$albumartist - $album'
                else:
                    fmt = '$albumartist - $album - $title'
                fmt += ': {0}'

            if checksum:
                if not isinstance(checksum, basestring):
                    raise UserError(
                        'duplicates: "checksum" option must be a command'
                    )
                for i in items:
                    k, _ = self._checksum(i, checksum, self._log)
                keys = [k]

            for obj_id, obj_count, objs in _duplicates(items,
                                                       keys=keys,
                                                       full=full,
                                                       log=self._log):
                if obj_id:  # Skip empty IDs.
                    for o in objs:
                        _process_item(o, lib,
                                      copy=copy,
                                      move=move,
                                      delete=delete,
                                      tag=tag,
                                      fmt=fmt.format(obj_count))

        self._command.func = _dup
        return [self._command]
