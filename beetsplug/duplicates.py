# This file is part of beets.
# Copyright 2013, Pedro Silva.
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
import logging

from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_obj, vararg_callback, Subcommand

PLUGIN = 'duplicates'
log = logging.getLogger('beets')


def _group_by(objs, keys):
    """Return a dictionary whose keys are arbitrary concatenations of attributes
    and whose values are lists of objects (Albums or Items) with those keys.
    """
    import collections
    counts = collections.defaultdict(list)
    for obj in objs:
        key = '\001'.join(getattr(obj, k, obj.mb_albumid) for k in keys)
        counts[key].append(obj)
    return counts


def _duplicates(objs, keys, full):
    """Generate triples of MBIDs, duplicate counts, and constituent
    objects.
    """
    offset = 0 if full else 1
    for mbid, objs in _group_by(objs, keys).iteritems():
        if len(objs) > 1:
            yield (mbid, len(objs) - offset, objs[offset:])


class DuplicatesPlugin(BeetsPlugin):
    """List duplicate tracks or albums
    """
    def __init__(self):
        super(DuplicatesPlugin, self).__init__()

        self.config.add({'format': ''})
        self.config.add({'count': False})
        self.config.add({'album': False})
        self.config.add({'full': False})
        self.config.add({'keys': ['mb_trackid', 'mb_albumid']})

        self._command = Subcommand('duplicates',
                                   help=__doc__,
                                   aliases=['dup'])

        self._command.parser.add_option('-f', '--format', dest='format',
                                        action='store', type='string',
                                        help='print with custom FORMAT',
                                        metavar='FORMAT')

        self._command.parser.add_option('-c', '--count', dest='count',
                                        action='store_true',
                                        help='count duplicate tracks or\
                                        albums')

        self._command.parser.add_option('-a', '--album', dest='album',
                                        action='store_true',
                                        help='show duplicate albums instead\
                                        of tracks')

        self._command.parser.add_option('-F', '--full', dest='full',
                                        action='store_true',
                                        help='show all versions of duplicate\
                                        tracks or albums')

        self._command.parser.add_option('-p', '--path', dest='path',
                                        action='store_true',
                                        help='print paths for matched items\
                                        or albums')

        self._command.parser.add_option('-k', '--keys', dest='keys',
                                        action='callback',
                                        callback=vararg_callback,
                                        help='report duplicates based on keys')

    def commands(self):
        def _dup(lib, opts, args):
            self.config.set_args(opts)
            fmt = self.config['format'].get()
            count = self.config['count'].get()
            album = self.config['album'].get()
            full = self.config['full'].get()
            keys = self.config['keys'].get()

            if album:
                items = lib.albums(decargs(args))
            else:
                items = lib.items(decargs(args))

            if opts.path:
                fmt = '$path'

            # Default format string for count mode.
            if count and not fmt:
                if album:
                    fmt = '$albumartist - $album'
                else:
                    fmt = '$albumartist - $album - $title'
                fmt += ': {0}'

            for obj_id, obj_count, objs in _duplicates(items,
                                                       keys=keys,
                                                       full=full):
                if obj_id:  # Skip empty IDs.
                    for o in objs:
                        print_obj(o, lib, fmt=fmt.format(obj_count))

        self._command.func = _dup
        return [self._command]
