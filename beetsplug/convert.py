"""Converts tracks or albums to external directory
"""
import logging
import os
import threading
import shutil
from subprocess import Popen, PIPE

import imghdr

from beets.plugins import BeetsPlugin
from beets import ui, library, util, mediafile
from beets.util.functemplate import Template

log = logging.getLogger('beets')
DEVNULL = open(os.devnull, 'wb')
conf = {}

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

class encodeThread(threading.Thread):
    def __init__(self, source, dest, artpath):
        threading.Thread.__init__(self)
        self.source = source
        self.dest = dest
        self.artpath = artpath

    def run(self):
        sema.acquire()
        self.encode()
        sema.release()

        dest_item = library.Item.from_path(self.source)
        dest_item.path = self.dest
        dest_item.write()
        if self.artpath:
            _embed(self.artpath,[dest_item])

    def encode(self):
        log.info('Started encoding '+ self.source)
        temp_dest = self.dest + '~'

        source_ext = os.path.splitext(self.source)[1].lower()
        if source_ext == '.flac':
            decode = Popen([conf['flac'], '-c', '-d', '-s', self.source],
                           stdout=PIPE)
            encode = Popen([conf['lame']] + conf['opts'] + ['-', temp_dest],
                       stdin=decode.stdout, stderr=DEVNULL)
            decode.stdout.close()
            encode.communicate()
        elif source_ext == '.mp3':
            encode = Popen([conf['lame']] + conf['opts'] + ['--mp3input'] +
                 [self.source, temp_dest], close_fds=True, stderr=DEVNULL)
            encode.communicate()
        else:
            log.error('Only converting from FLAC or MP3 implemented')
            return
        shutil.move(temp_dest, self.dest)
        log.info('Finished encoding '+ self.source)


def convert_item(lib, item, dest_dir, artpath):
    if item.format != 'FLAC' and item.format != 'MP3':
        log.info('Skipping {0} : not supported format'.format(item.path))
        return

    dest = os.path.join(dest_dir,lib.destination(item, fragment = True))
    dest = os.path.splitext(dest)[0] + '.mp3'

    if not os.path.exists(dest):
        util.mkdirall(dest)
        if item.format == 'MP3' and item.bitrate < 1000*conf['max_bitrate']:
            log.info('Copying {0}'.format(item.path))
            shutil.copy(item.path, dest)
            if artpath:
                _embed(artpath,[library.Item.from_path(dest)])
        else:
            thread = encodeThread(item.path, dest, artpath)
            thread.start()
    else:
        log.info('Skipping {0} : target file exists'.format(item.path))


def convert_func(lib, config, opts, args):
    global sema

    dest = opts.dest if opts.dest is not None else conf['dest']
    if not dest:
        log.error('No destination set')
        return
    threads = opts.threads if opts.threads is not None else conf['threads']
    sema = threading.BoundedSemaphore(threads)

    fmt = '$albumartist - $album' if opts.album \
                                  else '$artist - $album - $title'
    ui.commands.list_items(lib, ui.decargs(args), opts.album, False, fmt)

    if not ui.input_yn("Convert? (Y/n)"):
        return

    if opts.album:
        for album in lib.albums(ui.decargs(args)):
            for item in album.items():
                convert_item(lib, item, dest, album.artpath)
    else:
        for item in lib.items(ui.decargs(args)):
            convert_item(lib, item, dest, lib.get_album(item).artpath)

class ConvertPlugin(BeetsPlugin):
    def configure(self, config):
        conf['dest'] = ui.config_val(config, 'convert', 'dest', None)
        conf['threads'] = ui.config_val(config, 'convert', 'threads', 2)
        conf['flac'] = ui.config_val(config, 'convert', 'flac', 'flac')
        conf['lame'] = ui.config_val(config, 'convert', 'lame', 'lame')
        conf['opts'] = ui.config_val(config, 'convert',
                                     'opts', '-V2').split(' ')
        conf['max_bitrate'] = int(ui.config_val(config, 'convert',
                                                'max_bitrate','500'))

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert to external location')
        cmd.parser.add_option('-a', '--album', action='store_true',
                        help='choose albums instead of tracks')
        cmd.parser.add_option('-t', '--threads', action='store', type='int',
                        help='change the number of threads (default 2)')
        cmd.parser.add_option('-d', '--dest', action='store',
                        help='set the destination directory')
        cmd.func = convert_func
        return [cmd]
