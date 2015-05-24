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
from beets.library import Item, Album

PLUGIN = 'duplicates'


class DuplicatesPlugin(BeetsPlugin):
    """List duplicate tracks or albums
    """
    def __init__(self):
        super(DuplicatesPlugin, self).__init__()

        self.config.add({
            'album': False,
            'checksum': '',
            'copy': '',
            'count': False,
            'delete': False,
            'format': '',
            'full': False,
            'keys': [],
            'move': '',
            'path': False,
            'tiebreak': {},
            'strict': False,
            'tag': '',
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

        self._command.parser.add_option('-s', '--strict', dest='strict',
                                        action='store_true',
                                        help='report duplicates only if all'
                                        ' attributes are set')

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
            album = self.config['album'].get(bool)
            checksum = self.config['checksum'].get(str)
            copy = self.config['copy'].get(str)
            count = self.config['count'].get(bool)
            delete = self.config['delete'].get(bool)
            fmt = self.config['format'].get(str)
            full = self.config['full'].get(bool)
            keys = self.config['keys'].get(list)
            move = self.config['move'].get(str)
            path = self.config['path'].get(bool)
            tiebreak = self.config['tiebreak'].get(dict)
            strict = self.config['strict'].get(bool)
            tag = self.config['tag'].get(str)

            if album:
                if not keys:
                    keys = ['mb_albumid']
                items = lib.albums(decargs(args))
            else:
                if not keys:
                    keys = ['mb_trackid', 'mb_albumid']
                items = lib.items(decargs(args))

            if path:
                fmt = '$path'

            # Default format string for count mode.
            if count and not fmt:
                if album:
                    fmt = '$albumartist - $album'
                else:
                    fmt = '$albumartist - $album - $title'
                fmt += ': {0}'

            if checksum:
                for i in items:
                    k, _ = self._checksum(i, checksum)
                keys = [k]

            for obj_id, obj_count, objs in self._duplicates(items,
                                                            keys=keys,
                                                            full=full,
                                                            strict=strict,
                                                            tiebreak=tiebreak):
                if obj_id:  # Skip empty IDs.
                    for o in objs:
                        self._process_item(o, lib,
                                           copy=copy,
                                           move=move,
                                           delete=delete,
                                           tag=tag,
                                           fmt=fmt.format(obj_count))

        self._command.func = _dup
        return [self._command]

    def _process_item(self, item, lib, copy=False, move=False, delete=False,
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
            setattr(item, k, v)
            item.store()
        print_(format(item, fmt))

    def _checksum(self, item, prog):
        """Run external `prog` on file path associated with `item`, cache
        output as flexattr on a key that is the name of the program, and
        return the key, checksum tuple.
        """
        args = [p.format(file=item.path) for p in shlex.split(prog)]
        key = args[0]
        checksum = getattr(item, key, False)
        if not checksum:
            self._log.debug(u'key {0} on item {1} not cached:'
                            'computing checksum',
                            key, displayable_path(item.path))
            try:
                checksum = command_output(args)
                setattr(item, key, checksum)
                item.store()
                self._log.debug(u'computed checksum for {0} using {1}',
                                item.title, key)
            except subprocess.CalledProcessError as e:
                self._log.debug(u'failed to checksum {0}: {1}',
                                displayable_path(item.path), e)
        else:
            self._log.debug(u'key {0} on item {1} cached:'
                            'not computing checksum',
                            key, displayable_path(item.path))
        return key, checksum

    def _group_by(self, objs, keys, strict):
        """Return a dictionary with keys arbitrary concatenations of attributes and
        values lists of objects (Albums or Items) with those keys.

        If strict, all attributes must be defined for a duplicate match.
        """
        import collections
        counts = collections.defaultdict(list)
        for obj in objs:
            values = [getattr(obj, k, None) for k in keys]
            values = [v for v in values if v not in (None, '')]
            if strict and len(values) < len(keys):
                self._log.debug(u'some keys {0} on item {1} are null or empty:'
                                ' skipping',
                                keys, displayable_path(obj.path))
            elif (not strict and not len(values)):
                self._log.debug(u'all keys {0} on item {1} are null or empty:'
                                ' skipping',
                                keys, displayable_path(obj.path))
            else:
                key = tuple(values)
                counts[key].append(obj)

        return counts

    def _order(self, objs, tiebreak=None):
        """Return objs sorted by descending order of fields in tiebreak dict.

        Default ordering is based on attribute completeness.
        """
        if tiebreak:
            kind = 'items' if all(isinstance(o, Item)
                                  for o in objs) else 'albums'
            key = lambda x: tuple(getattr(x, k) for k in tiebreak[kind])
        else:
            kind = Item if all(isinstance(o, Item) for o in objs) else Album
            if kind is Item:
                fields = [f for sublist in kind.get_fields() for f in sublist]
                key = lambda x: len([(a, getattr(x, a, None)) for a in fields
                                     if getattr(x, a, None) not in (None, '')])
            else:
                key = lambda x: len(x.items())

        return sorted(objs, key=key, reverse=True)

    def _duplicates(self, objs, keys, full, strict, tiebreak):
        """Generate triples of keys, duplicate counts, and constituent objects.
        """
        offset = 0 if full else 1
        for k, objs in self._group_by(objs, keys, strict).iteritems():
            if len(objs) > 1:
                yield (k,
                       len(objs) - offset,
                       self._order(objs, tiebreak)[offset:])
