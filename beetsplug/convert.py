# This file is part of beets.
# Copyright 2013, Jakob Schnitzer.
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

"""Converts tracks or albums to external directory
"""
import logging
import os
import threading
from subprocess import Popen

from beets.plugins import BeetsPlugin
from beets import ui, util
from beetsplug.embedart import _embed
from beets import library
from beets import config

log = logging.getLogger('beets')
DEVNULL = open(os.devnull, 'wb')
_fs_lock = threading.Lock()


def _dest_out(lib, dest_dir, item, keep_new):
    """Path to the files outside the directory"""

    if keep_new:
        return os.path.join(dest_dir, lib.destination(item, fragment=True))

    dest = os.path.join(dest_dir, lib.destination(item, fragment=True))
    return os.path.splitext(dest)[0] + '.mp3'


def _dest_converted(lib, dest_dir, item, keep_new):
    """Path to the newly converted files"""

    if keep_new:
        dest = lib.destination(item)
        return os.path.splitext(dest)[0] + '.mp3'

    return _dest_out(lib, dest_dir, item, keep_new)


def encode(source, dest):
    log.info(u'Started encoding {0}'.format(util.displayable_path(source)))

    opts = config['convert']['opts'].get(unicode).split(u' ')
    encode = Popen([config['convert']['ffmpeg'].get(unicode), '-i', source] +
                   opts + [dest],
                   close_fds=True, stderr=DEVNULL)
    encode.wait()
    if encode.returncode != 0:
        # Something went wrong (probably Ctrl+C), remove temporary files
        log.info(u'Encoding {0} failed. Cleaning up...'
                 .format(util.displayable_path(source)))
        util.remove(dest)
        util.prune_dirs(os.path.dirname(dest))
        return
    log.info(u'Finished encoding {0}'.format(util.displayable_path(source)))


def convert_item(lib, dest_dir, keep_new):
    while True:
        item = yield

        dest_converted = _dest_converted(lib, dest_dir, item, keep_new)
        dest_out = _dest_out(lib, dest_dir, item, keep_new)

        if os.path.exists(util.syspath(dest_out)):
            log.info(u'Skipping {0} (target file exists)'.format(
                util.displayable_path(item.path)
            ))
            continue

        # Ensure that only one thread tries to create directories at a
        # time. (The existence check is not atomic with the directory
        # creation inside this function.)
        with _fs_lock:
            util.mkdirall(dest_out)

        maxbr = config['convert']['max_bitrate'].get(int)
        if item.format == 'MP3' and item.bitrate < 1000 * maxbr:
            log.info(u'Copying {0}'.format(util.displayable_path(item.path)))
            util.copy(item.path, dest_out)
        else:
            encode(item.path, dest_converted)

            if keep_new:
                log.info(u'Moving to destination {0}'.
                         format(util.displayable_path(dest_out)))
                util.move(item.path, dest_out)

        item.path = dest_converted
        item.write()

        if config['convert']['embed']:
            album = lib.get_album(item)
            if album:
                artpath = album.artpath
                if artpath:
                    _embed(artpath, [item])

        if keep_new:
            item.read()
            log.info(u'Updating new format {0}'.format(item.format))
            item.write()
            lib.store(item)


def convert_func(lib, opts, args):
    dest = opts.dest if opts.dest is not None else \
        config['convert']['dest'].get()
    if not dest:
        raise ui.UserError('no convert destination set')
    threads = opts.threads if opts.threads is not None else \
        config['convert']['threads'].get(int)

    keep_new = opts.keep_new

    ui.commands.list_items(lib, ui.decargs(args), opts.album, None)

    if not ui.input_yn("Convert? (Y/n)"):
        return

    if opts.album:
        items = (i for a in lib.albums(ui.decargs(args)) for i in a.items())
    else:
        items = lib.items(ui.decargs(args))
    convert = [convert_item(lib, dest, keep_new) for i in range(threads)]
    pipe = util.pipeline.Pipeline([items, convert])
    pipe.run_parallel()


class ConvertPlugin(BeetsPlugin):
    def __init__(self):
        super(ConvertPlugin, self).__init__()
        self.config.add({
            u'dest': None,
            u'threads': util.cpu_count(),
            u'ffmpeg': u'ffmpeg',
            u'opts': u'-aq 2',
            u'max_bitrate': 500,
            u'embed': True,
        })

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert to external location')
        cmd.parser.add_option('-a', '--album', action='store_true',
                              help='choose albums instead of tracks')
        cmd.parser.add_option('-t', '--threads', action='store', type='int',
                              help='change the number of threads, \
                              defaults to maximum availble processors ')
        cmd.parser.add_option('-k', '--keep-new', action='store_true',
                              dest='keep_new', help='keep only the converted \
                              and move the old files')
        cmd.parser.add_option('-d', '--dest', action='store',
                              help='set the destination directory')
        cmd.func = convert_func
        return [cmd]
