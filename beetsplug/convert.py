# This file is part of beets.
# Copyright 2012, Jakob Schnitzer.
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
import sys
import shutil
from subprocess import Popen, PIPE

from beets.plugins import BeetsPlugin
from beets import ui, library, util
from beetsplug.embedart import _embed

log = logging.getLogger('beets')
DEVNULL = open(os.devnull, 'wb')
conf = {}


def _cpu_count():
    """ Returns the number of CPUs in the system.
    Code was adapted from observing the soundconverter project:
    https://github.com/kassoulet/soundconverter
    """
    if sys.platform == 'win32':
        try:
            num = int(os.environ['NUMBER_OF_PROCESSORS'])
        except (ValueError, KeyError):
            num = 0
    elif sys.platform == 'darwin':
        try:
            num = int(os.popen('sysctl -n hw.ncpu').read())
        except ValueError:
            num = 0
    else:
        try:
            num = os.sysconf('SC_NPROCESSORS_ONLN')
        except (ValueError, OSError, AttributeError):
            num = 0
    if num >= 1:
        return num
    else:
        return 1


def encode(source, dest):
    log.info('Started encoding ' + source)
    temp_dest = dest + '~'

    source_ext = os.path.splitext(source)[1].lower()
    if source_ext == '.flac':
        decode = Popen([conf['flac'], '-c', '-d', '-s', source],
                       stdout=PIPE)
        encode = Popen([conf['lame']] + conf['opts'] + ['-', temp_dest],
                       stdin=decode.stdout, stderr=DEVNULL)
        decode.stdout.close()
        encode.communicate()
    elif source_ext == '.mp3':
        encode = Popen([conf['lame']] + conf['opts'] + ['--mp3input'] +
                       [source, temp_dest], close_fds=True, stderr=DEVNULL)
        encode.communicate()
    else:
        log.error('Only converting from FLAC or MP3 implemented')
        return
    if encode.returncode != 0:
        # Something went wrong (probably Ctrl+C), remove temporary files
        log.info('Encoding {0} failed. Cleaning up...'.format(source))
        util.remove(temp_dest)
        util.prune_dirs(os.path.dirname(temp_dest))
        return
    shutil.move(temp_dest, dest)
    log.info('Finished encoding ' + source)


def convert_item(lib, dest_dir):
    while True:
        item = yield
        if item.format != 'FLAC' and item.format != 'MP3':
            log.info('Skipping {0} (unsupported format)'.format(
                util.displayable_path(item.path)
            ))
            continue

        dest = os.path.join(dest_dir, lib.destination(item, fragment=True))
        dest = os.path.splitext(dest)[0] + '.mp3'

        if os.path.exists(dest):
            log.info('Skipping {0} (target file exists)'.format(
                util.displayable_path(item.path)
            ))
            continue

        util.mkdirall(dest)
        if item.format == 'MP3' and item.bitrate < 1000 * conf['max_bitrate']:
            log.info('Copying {0}'.format(util.displayable_path(item.path)))
            util.copy(item.path, dest)
            dest_item = library.Item.from_path(dest)
        else:
            encode(item.path, dest)
            dest_item = library.Item.from_path(item.path)
            dest_item.path = dest
            dest_item.write()

        artpath = lib.get_album(item).artpath
        if artpath and conf['embed']:
            _embed(artpath, [dest_item])


def convert_func(lib, config, opts, args):
    dest = opts.dest if opts.dest is not None else conf['dest']
    if not dest:
        raise ui.UserError('no convert destination set')
    threads = opts.threads if opts.threads is not None else conf['threads']

    fmt = '$albumartist - $album' if opts.album \
          else '$artist - $album - $title'
    ui.commands.list_items(lib, ui.decargs(args), opts.album, False, fmt)

    if not ui.input_yn("Convert? (Y/n)"):
        return

    if opts.album:
        items = (i for a in lib.albums(ui.decargs(args)) for i in a.items())
    else:
        items = lib.items(ui.decargs(args))
    convert = [convert_item(lib, dest) for i in range(threads)]
    pipe = util.pipeline.Pipeline([items, convert])
    pipe.run_parallel()


class ConvertPlugin(BeetsPlugin):
    def configure(self, config):
        conf['dest'] = ui.config_val(config, 'convert', 'dest', None)
        conf['threads'] = ui.config_val(config, 'convert', 'threads',
            _cpu_count())
        conf['flac'] = ui.config_val(config, 'convert', 'flac', 'flac')
        conf['lame'] = ui.config_val(config, 'convert', 'lame', 'lame')
        conf['opts'] = ui.config_val(config, 'convert',
                                     'opts', '-V2').split(' ')
        conf['max_bitrate'] = int(ui.config_val(config, 'convert',
                                                'max_bitrate', '500'))
        conf['embed'] = ui.config_val(config, 'convert', 'embed', True,
                                      vtype=bool)

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert to external location')
        cmd.parser.add_option('-a', '--album', action='store_true',
                              help='choose albums instead of tracks')
        cmd.parser.add_option('-t', '--threads', action='store', type='int',
                              help='change the number of threads, \
                              defaults to maximum availble processors ')
        cmd.parser.add_option('-d', '--dest', action='store',
                              help='set the destination directory')
        cmd.func = convert_func
        return [cmd]
