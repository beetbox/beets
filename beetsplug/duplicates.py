# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Pedro Silva.
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
from __future__ import division, absolute_import, print_function

import shlex

from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_, Subcommand, UserError
from beets.util import command_output, displayable_path, subprocess, \
    bytestring_path
from beets.library import Item, Album
import six

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
            'merge': False,
            'move': '',
            'path': False,
            'tiebreak': {},
            'strict': False,
            'tag': '',
        })

        self._command = Subcommand('duplicates',
                                   help=__doc__,
                                   aliases=['dup'])
        self._command.parser.add_option(
            u'-c', u'--count', dest='count',
            action='store_true',
            help=u'show duplicate counts',
        )
        self._command.parser.add_option(
            u'-C', u'--checksum', dest='checksum',
            action='store', metavar='PROG',
            help=u'report duplicates based on arbitrary command',
        )
        self._command.parser.add_option(
            u'-d', u'--delete', dest='delete',
            action='store_true',
            help=u'delete items from library and disk',
        )
        self._command.parser.add_option(
            u'-F', u'--full', dest='full',
            action='store_true',
            help=u'show all versions of duplicate tracks or albums',
        )
        self._command.parser.add_option(
            u'-s', u'--strict', dest='strict',
            action='store_true',
            help=u'report duplicates only if all attributes are set',
        )
        self._command.parser.add_option(
            u'-k', u'--key',
            action='append', metavar='KEY',
            help=u'report duplicates based on keys (use multiple times)',
        )
        self._command.parser.add_option(
            u'-M', u'--merge', dest='merge',
            action='store_true',
            help=u'merge duplicate items',
        )
        self._command.parser.add_option(
            u'-m', u'--move', dest='move',
            action='store', metavar='DEST',
            help=u'move items to dest',
        )
        self._command.parser.add_option(
            u'-o', u'--copy', dest='copy',
            action='store', metavar='DEST',
            help=u'copy items to dest',
        )
        self._command.parser.add_option(
            u'-t', u'--tag', dest='tag',
            action='store',
            help=u'tag matched items with \'k=v\' attribute',
        )
        self._command.parser.add_all_common_options()

    def commands(self):

        def _dup(lib, opts, args):
            self.config.set_args(opts)
            album = self.config['album'].get(bool)
            checksum = self.config['checksum'].get(str)
            copy = bytestring_path(self.config['copy'].as_str())
            count = self.config['count'].get(bool)
            delete = self.config['delete'].get(bool)
            fmt = self.config['format'].get(str)
            full = self.config['full'].get(bool)
            keys = self.config['keys'].as_str_seq()
            merge = self.config['merge'].get(bool)
            move = bytestring_path(self.config['move'].as_str())
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
                fmt = u'$path'

            # Default format string for count mode.
            if count and not fmt:
                if album:
                    fmt = u'$albumartist - $album'
                else:
                    fmt = u'$albumartist - $album - $title'
                fmt += u': {0}'

            if checksum:
                for i in items:
                    k, _ = self._checksum(i, checksum)
                keys = [k]

            for obj_id, obj_count, objs in self._duplicates(items,
                                                            keys=keys,
                                                            full=full,
                                                            strict=strict,
                                                            tiebreak=tiebreak,
                                                            merge=merge):
                if obj_id:  # Skip empty IDs.
                    for o in objs:
                        self._process_item(o,
                                           copy=copy,
                                           move=move,
                                           delete=delete,
                                           tag=tag,
                                           fmt=fmt.format(obj_count))

        self._command.func = _dup
        return [self._command]

    def _process_item(self, item, copy=False, move=False, delete=False,
                      tag=False, fmt=u''):
        """Process Item `item`.
        """
        print_(format(item, fmt))
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
                raise UserError(
                    u"{}: can't parse k=v tag: {}".format(PLUGIN, tag)
                )
            setattr(item, k, v)
            item.store()

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
                            u'computing checksum',
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
                            u'not computing checksum',
                            key, displayable_path(item.path))
        return key, checksum

    def _group_by(self, objs, keys, strict):
        """Return a dictionary with keys arbitrary concatenations of attributes
        and values lists of objects (Albums or Items) with those keys.

        If strict, all attributes must be defined for a duplicate match.
        """
        import collections
        counts = collections.defaultdict(list)
        for obj in objs:
            values = [getattr(obj, k, None) for k in keys]
            values = [v for v in values if v not in (None, '')]
            if strict and len(values) < len(keys):
                self._log.debug(u'some keys {0} on item {1} are null or empty:'
                                u' skipping',
                                keys, displayable_path(obj.path))
            elif (not strict and not len(values)):
                self._log.debug(u'all keys {0} on item {1} are null or empty:'
                                u' skipping',
                                keys, displayable_path(obj.path))
            else:
                key = tuple(values)
                counts[key].append(obj)

        return counts

    def _order(self, objs, tiebreak=None):
        """Return the objects (Items or Albums) sorted by descending
        order of priority.

        If provided, the `tiebreak` dict indicates the field to use to
        prioritize the objects. Otherwise, Items are placed in order of
        "completeness" (objects with more non-null fields come first)
        and Albums are ordered by their track count.
        """
        if tiebreak:
            kind = 'items' if all(isinstance(o, Item)
                                  for o in objs) else 'albums'
            key = lambda x: tuple(getattr(x, k) for k in tiebreak[kind])
        else:
            kind = Item if all(isinstance(o, Item) for o in objs) else Album
            if kind is Item:
                def truthy(v):
                    # Avoid a Unicode warning by avoiding comparison
                    # between a bytes object and the empty Unicode
                    # string ''.
                    return v is not None and \
                        (v != '' if isinstance(v, six.text_type) else True)
                fields = kind.all_keys()
                key = lambda x: sum(1 for f in fields if truthy(getattr(x, f)))
            else:
                key = lambda x: len(x.items())

        return sorted(objs, key=key, reverse=True)

    def _merge_items(self, objs):
        """Merge Item objs by copying missing fields from items in the tail to
        the head item.

        Return same number of items, with the head item modified.
        """
        fields = Item.all_keys()
        for f in fields:
            for o in objs[1:]:
                if getattr(objs[0], f, None) in (None, ''):
                    value = getattr(o, f, None)
                    if value:
                        self._log.debug(u'key {0} on item {1} is null '
                                        u'or empty: setting from item {2}',
                                        f, displayable_path(objs[0].path),
                                        displayable_path(o.path))
                        setattr(objs[0], f, value)
                        objs[0].store()
                        break
        return objs

    def _merge_albums(self, objs):
        """Merge Album objs by copying missing items from albums in the tail
        to the head album.

        Return same number of albums, with the head album modified."""
        ids = [i.mb_trackid for i in objs[0].items()]
        for o in objs[1:]:
            for i in o.items():
                if i.mb_trackid not in ids:
                    missing = Item.from_path(i.path)
                    missing.album_id = objs[0].id
                    missing.add(i._db)
                    self._log.debug(u'item {0} missing from album {1}:'
                                    u' merging from {2} into {3}',
                                    missing,
                                    objs[0],
                                    displayable_path(o.path),
                                    displayable_path(missing.destination()))
                    missing.move(copy=True)
        return objs

    def _merge(self, objs):
        """Merge duplicate items. See ``_merge_items`` and ``_merge_albums``
        for the relevant strategies.
        """
        kind = Item if all(isinstance(o, Item) for o in objs) else Album
        if kind is Item:
            objs = self._merge_items(objs)
        else:
            objs = self._merge_albums(objs)
        return objs

    def _duplicates(self, objs, keys, full, strict, tiebreak, merge):
        """Generate triples of keys, duplicate counts, and constituent objects.
        """
        offset = 0 if full else 1
        for k, objs in self._group_by(objs, keys, strict).items():
            if len(objs) > 1:
                objs = self._order(objs, tiebreak)
                if merge:
                    objs = self._merge(objs)
                yield (k, len(objs) - offset, objs[offset:])
