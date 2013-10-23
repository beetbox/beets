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
import shlex
import logging

from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_obj, vararg_callback, Subcommand
from beets.util import command_output, displayable_path

PLUGIN = 'duplicates'
log = logging.getLogger('beets')


def _checksum(item, prog):
    """Run external `prog` on file path associated with `item`, cache
    output as flexattr on a key that is the name of the program, and
    return the key, checksum tuple.
    """
    args = shlex.split(prog.format(file=item.path))
    key = args[0]
    checksum = getattr(item, key, False)
    if not checksum:
        log.debug('%s: key %s on item %s not cached: computing checksum',
                  PLUGIN, key, displayable_path(item.path))
        try:
            checksum = command_output(args)
            setattr(item, key, checksum)
            item.store()
            log.debug('%s: computed checksum for %s using %s',
                      PLUGIN, item.title, key)
        except Exception as e:
            log.debug('%s: failed to checksum %s: %s',
                      PLUGIN, displayable_path(item.path), e)
    else:
        log.debug('%s: key %s on item %s cached: not computing checksum',
                  PLUGIN, key, displayable_path(item.path))
    return key, checksum


def _group_by(objs, keys):
    """Return a dictionary whose keys are arbitrary concatenations of attributes
    and whose values are lists of objects (Albums or Items) with those keys.
    """
    import collections
    counts = collections.defaultdict(list)
    for obj in objs:
        key = '\001'.join(getattr(obj, k, '') for k in keys)
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
        self.config.add({'path': False})
        self.config.add({'keys': ['mb_trackid', 'mb_albumid']})
        self.config.add({'checksum': 'ffmpeg -i {file} -f crc -'})

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

        self._command.parser.add_option('-C', '--checksum', dest='checksum',
                                        action='store',
                                        help='report duplicates based on\
                                        arbitrary command')

    def commands(self):
        def _dup(lib, opts, args):
            self.config.set_args(opts)
            fmt = self.config['format'].get()
            count = self.config['count'].get()
            album = self.config['album'].get()
            full = self.config['full'].get()
            keys = self.config['keys'].get()
            checksum = self.config['checksum'].get()

            if album:
                keys = ['mb_albumid']
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

            if checksum:
                for i in items:
                    k, _ = _checksum(i, checksum)
                keys = ['k']

            for obj_id, obj_count, objs in _duplicates(items,
                                                       keys=keys,
                                                       full=full):
                if obj_id:  # Skip empty IDs.
                    for o in objs:
                        print_obj(o, lib, fmt=fmt.format(obj_count))

        self._command.func = _dup
        return [self._command]
