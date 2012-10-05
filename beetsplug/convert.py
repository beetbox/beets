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
import subprocess
import os.path
import threading
import imghdr

from beets.plugins import BeetsPlugin
from beets import ui, library, util, mediafile
from beets.util.functemplate import Template

log = logging.getLogger('beets')

def _embed(path, items):
    """Embed an image file, located at `path`, into each item.
    """
    data = open(util.syspath(path), 'rb').read()
    kindstr = imghdr.what(None, data)
    if kindstr not in ('jpeg', 'png'):
        log.error('A file of type %s is not allowed as coverart.' % kindstr)
    return
    log.debug('Embedding album art.')
    for item in items:
        try:
            f = mediafile.MediaFile(syspath(item.path))
        except mediafile.UnreadableFileError as exc:
            log.warn('Could not embed art in {0}: {1}'.format(
                repr(item.path), exc
            ))
            continue
        f.art = data
        f.save()

global sema

class encodeThread(threading.Thread):
    def __init__(self, source, dest, artpath):
        threading.Thread.__init__(self)
        self.source = source
        self.dest = dest
        self.artpath = artpath

    def run(self):
        sema.acquire()
        log.info('Started encoding '+ self.source)
        temp_dest = self.dest + "~"

        decode = subprocess.Popen(["flac", "-c", "-d", "-s", self.source], stdout=subprocess.PIPE)
        encode = subprocess.Popen(['lame', '-V2', '-', temp_dest], stdin=decode.stdout)
        decode.stdout.close()
        encode.communicate()

        os.rename(temp_dest, self.dest)
        converted_item = library.Item.from_path(self.dest)
        converted_item.read(self.source)
        converted_item.path = self.dest
        converted_item.write()
        if self.artpath:
            _embed(self.artpath,[converted_item])
        log.info('Finished encoding '+ self.source)
        sema.release()


def convert_item(lib, item, dest, artpath):
    if item.format != "FLAC":
        log.info('Skipping {0} : not FLAC'.format(item.path))
        return
    dest_path = os.path.join(dest,lib.destination(item, fragment = True))
    dest_path = os.path.splitext(dest_path)[0] + '.mp3'
    if not os.path.exists(dest_path):
        util.mkdirall(dest_path)
        thread = encodeThread(item.path, dest_path, artpath)
        thread.start()
    else:
        log.info('Skipping {0} : target file exists'.format(item.path))


def convert_func(lib, config, opts, args):
    global sema
    if not conf['dest']:
        log.error('No destination set')
        return
    sema = threading.BoundedSemaphore(opts.threads)
    if opts.album:
        fmt = '$albumartist - $album'
    else:
        fmt = '$artist - $album - $title'

    ui.commands.list_items(lib, ui.decargs(args), opts.album, False, fmt)

    if not ui.input_yn("Convert? (Y/n)"):
        return

    if opts.album:
        for album in lib.albums(ui.decargs(args)):
            for item in album.items():
                convert_item(lib, item, conf['dest'], o.artpath)
    else:
        for item in lib.items(ui.decargs(args)):
            album = lib.get_album(item)
            convert_item(lib, item, conf['dest'], album.artpath)

conf = {}

class ConvertPlugin(BeetsPlugin):
    def configure(self, config):
        conf['dest'] = ui.config_val(config, 'convert', 'path', None)

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert albums to external location')
        cmd.parser.add_option('-a', '--album', action='store_true',
                        help='choose albums instead of tracks')
        cmd.parser.add_option('-t', '--threads', action='store', type='int',
                        help='change the number of threads (default 2)', default=2)
        cmd.func = convert_func
        return [cmd]
