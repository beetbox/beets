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
import tempfile

from beets.plugins import BeetsPlugin
from beets import ui, util
from beetsplug.embedart import _embed
from beets import config

log = logging.getLogger('beets')
DEVNULL = open(os.devnull, 'wb')
_fs_lock = threading.Lock()
_temp_files = []  # Keep track of temporary transcoded files for deletion.


def _destination(lib, dest_dir, item, keep_new, path_formats):
    """Return the path under `dest_dir` where the file should be placed
    (possibly after conversion).
    """
    dest = lib.destination(item, basedir=dest_dir, path_formats=path_formats)
    if keep_new:
        # When we're keeping the converted file, no extension munging
        # occurs.
        return dest
    else:
        # Otherwise, replace the extension with .mp3.
        return os.path.splitext(dest)[0] + '.mp3'


def encode(source, dest):
    log.info(u'Started encoding {0}'.format(util.displayable_path(source)))

    opts = config['convert']['opts'].get(unicode).split(u' ')
    encode = Popen([config['convert']['ffmpeg'].get(unicode), '-i',
                    source, '-y'] + opts + [dest],
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


def should_transcode(item):
    """Determine whether the item should be transcoded as part of
    conversion (i.e., its bitrate is high or it has the wrong format).
    """
    maxbr = config['convert']['max_bitrate'].get(int)
    return item.format != 'MP3' or item.bitrate >= 1000 * maxbr


def convert_item(lib, dest_dir, keep_new, path_formats):
    while True:
        item = yield
        dest = _destination(lib, dest_dir, item, keep_new, path_formats)

        if os.path.exists(util.syspath(dest)):
            log.info(u'Skipping {0} (target file exists)'.format(
                util.displayable_path(item.path)
            ))
            continue

        # Ensure that only one thread tries to create directories at a
        # time. (The existence check is not atomic with the directory
        # creation inside this function.)
        with _fs_lock:
            util.mkdirall(dest)

        # When keeping the new file in the library, we first move the
        # current (pristine) file to the destination. We'll then copy it
        # back to its old path or transcode it to a new path.
        if keep_new:
            log.info(u'Moving to {0}'.
                     format(util.displayable_path(dest)))
            util.move(item.path, dest)

        if not should_transcode(item):
            # No transcoding necessary.
            log.info(u'Copying {0}'.format(util.displayable_path(item.path)))
            if keep_new:
                util.copy(dest, item.path)
            else:
                util.copy(item.path, dest)

        else:
            if keep_new:
                item.path = os.path.splitext(item.path)[0] + '.mp3'
                encode(dest, item.path)
            else:
                encode(item.path, dest)

        # Write tags from the database to the converted file.
        if not keep_new:
            item.path = dest
        item.write()

        # If we're keeping the transcoded file, read it again (after
        # writing) to get new bitrate, duration, etc.
        if keep_new:
            item.read()
            lib.store(item)  # Store new path and audio data.

        if config['convert']['embed']:
            album = lib.get_album(item)
            if album:
                artpath = album.artpath
                if artpath:
                    _embed(artpath, [item])


def convert_on_import(lib, item):
    """Transcode a file automatically after it is imported into the
    library.
    """
    if should_transcode(item):
        fd, dest = tempfile.mkstemp('.mp3')
        os.close(fd)
        _temp_files.append(dest)  # Delete the transcode later.
        encode(item.path, dest)
        item.path = dest
        item.write()
        item.read()  # Load new audio information data.
        lib.store(item)


def convert_func(lib, opts, args):
    dest = opts.dest if opts.dest is not None else \
            config['convert']['dest'].get()
    if not dest:
        raise ui.UserError('no convert destination set')
    dest = util.bytestring_path(dest)
    threads = opts.threads if opts.threads is not None else \
            config['convert']['threads'].get(int)
    keep_new = opts.keep_new

    if not config['convert']['paths']:
        path_formats = ui.get_path_formats()
    else:
        path_formats = ui.get_path_formats(config['convert']['paths'])

    ui.commands.list_items(lib, ui.decargs(args), opts.album, None)

    if not ui.input_yn("Convert? (Y/n)"):
        return

    if opts.album:
        items = (i for a in lib.albums(ui.decargs(args)) for i in a.items())
    else:
        items = lib.items(ui.decargs(args))
    convert = [convert_item(lib, dest, keep_new, path_formats) for i in range(threads)]
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
            u'auto': False,
            u'paths': dict(),
        })
        self.import_stages = [self.auto_convert]

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert to external location')
        cmd.parser.add_option('-a', '--album', action='store_true',
                              help='choose albums instead of tracks')
        cmd.parser.add_option('-t', '--threads', action='store', type='int',
                              help='change the number of threads, \
                              defaults to maximum available processors')
        cmd.parser.add_option('-k', '--keep-new', action='store_true',
                              dest='keep_new', help='keep only the converted \
                              and move the old files')
        cmd.parser.add_option('-d', '--dest', action='store',
                              help='set the destination directory')
        cmd.func = convert_func
        return [cmd]

    def auto_convert(self, config, task):
        if self.config['auto'].get():
            if not task.is_album:
                convert_on_import(config.lib, task.item)
            else:
                for item in task.items:
                    convert_on_import(config.lib, item)


@ConvertPlugin.listen('import_task_files')
def _cleanup(task, session):
    for path in task.old_paths:
        if path in _temp_files:
            if os.path.isfile(path):
                util.remove(path)
            _temp_files.remove(path)
