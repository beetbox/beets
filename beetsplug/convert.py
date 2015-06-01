# This file is part of beets.
# Copyright 2015, Jakob Schnitzer.
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
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os
import threading
import subprocess
import tempfile
import shlex
from string import Template

from beets import ui, util, plugins, config
from beets.plugins import BeetsPlugin
from beets.util.confit import ConfigTypeError
from beets import art

_fs_lock = threading.Lock()
_temp_files = []  # Keep track of temporary transcoded files for deletion.

# Some convenient alternate names for formats.
ALIASES = {
    u'wma': u'windows media',
    u'vorbis': u'ogg',
}

LOSSLESS_FORMATS = ['ape', 'flac', 'alac', 'wav']


def replace_ext(path, ext):
    """Return the path with its extension replaced by `ext`.

    The new extension must not contain a leading dot.
    """
    return os.path.splitext(path)[0] + b'.' + ext


def get_format(fmt=None):
    """Return the command tempate and the extension from the config.
    """
    if not fmt:
        fmt = config['convert']['format'].get(unicode).lower()
    fmt = ALIASES.get(fmt, fmt)

    try:
        format_info = config['convert']['formats'][fmt].get(dict)
        command = format_info['command']
        extension = format_info['extension']
    except KeyError:
        raise ui.UserError(
            u'convert: format {0} needs "command" and "extension" fields'
            .format(fmt)
        )
    except ConfigTypeError:
        command = config['convert']['formats'][fmt].get(bytes)
        extension = fmt

    # Convenience and backwards-compatibility shortcuts.
    keys = config['convert'].keys()
    if 'command' in keys:
        command = config['convert']['command'].get(unicode)
    elif 'opts' in keys:
        # Undocumented option for backwards compatibility with < 1.3.1.
        command = u'ffmpeg -i $source -y {0} $dest'.format(
            config['convert']['opts'].get(unicode)
        )
    if 'extension' in keys:
        extension = config['convert']['extension'].get(unicode)

    return (command.encode('utf8'), extension.encode('utf8'))


def should_transcode(item, fmt):
    """Determine whether the item should be transcoded as part of
    conversion (i.e., its bitrate is high or it has the wrong format).
    """
    if config['convert']['never_convert_lossy_files'] and \
            not (item.format.lower() in LOSSLESS_FORMATS):
        return False
    maxbr = config['convert']['max_bitrate'].get(int)
    return fmt.lower() != item.format.lower() or \
        item.bitrate >= 1000 * maxbr


class ConvertPlugin(BeetsPlugin):
    def __init__(self):
        super(ConvertPlugin, self).__init__()
        self.config.add({
            u'dest': None,
            u'pretend': False,
            u'threads': util.cpu_count(),
            u'format': u'mp3',
            u'formats': {
                u'aac': {
                    u'command': u'ffmpeg -i $source -y -vn -acodec libfaac '
                                u'-aq 100 $dest',
                    u'extension': u'm4a',
                },
                u'alac': {
                    u'command': u'ffmpeg -i $source -y -vn -acodec alac $dest',
                    u'extension': u'm4a',
                },
                u'flac': u'ffmpeg -i $source -y -vn -acodec flac $dest',
                u'mp3': u'ffmpeg -i $source -y -vn -aq 2 $dest',
                u'opus':
                    u'ffmpeg -i $source -y -vn -acodec libopus -ab 96k $dest',
                u'ogg':
                    u'ffmpeg -i $source -y -vn -acodec libvorbis -aq 2 $dest',
                u'wma':
                    u'ffmpeg -i $source -y -vn -acodec wmav2 -vn $dest',
            },
            u'max_bitrate': 500,
            u'auto': False,
            u'tmpdir': None,
            u'quiet': False,
            u'embed': True,
            u'paths': {},
            u'never_convert_lossy_files': False,
            u'copy_album_art': False,
        })
        self.import_stages = [self.auto_convert]

        self.register_listener('import_task_files', self._cleanup)

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert to external location')
        cmd.parser.add_option('-p', '--pretend', action='store_true',
                              help='show actions but do nothing')
        cmd.parser.add_option('-t', '--threads', action='store', type='int',
                              help='change the number of threads, \
                              defaults to maximum available processors')
        cmd.parser.add_option('-k', '--keep-new', action='store_true',
                              dest='keep_new', help='keep only the converted \
                              and move the old files')
        cmd.parser.add_option('-d', '--dest', action='store',
                              help='set the destination directory')
        cmd.parser.add_option('-f', '--format', action='store', dest='format',
                              help='set the target format of the tracks')
        cmd.parser.add_option('-y', '--yes', action='store_true', dest='yes',
                              help='do not ask for confirmation')
        cmd.parser.add_album_option()
        cmd.func = self.convert_func
        return [cmd]

    def auto_convert(self, config, task):
        if self.config['auto']:
            for item in task.imported_items():
                self.convert_on_import(config.lib, item)

    # Utilities converted from functions to methods on logging overhaul

    def encode(self, command, source, dest, pretend=False):
        """Encode `source` to `dest` using command template `command`.

        Raises `subprocess.CalledProcessError` if the command exited with a
        non-zero status code.
        """
        # The paths and arguments must be bytes.
        assert isinstance(command, bytes)
        assert isinstance(source, bytes)
        assert isinstance(dest, bytes)

        quiet = self.config['quiet'].get(bool)

        if not quiet and not pretend:
            self._log.info(u'Encoding {0}', util.displayable_path(source))

        # Substitute $source and $dest in the argument list.
        args = shlex.split(command)
        for i, arg in enumerate(args):
            args[i] = Template(arg).safe_substitute({
                b'source': source,
                b'dest': dest,
            })

        if pretend:
            self._log.info(' '.join(args))
            return

        try:
            util.command_output(args)
        except subprocess.CalledProcessError as exc:
            # Something went wrong (probably Ctrl+C), remove temporary files
            self._log.info(u'Encoding {0} failed. Cleaning up...',
                           util.displayable_path(source))
            self._log.debug(u'Command {0} exited with status {1}',
                            exc.cmd.decode('utf8', 'ignore'),
                            exc.returncode)
            util.remove(dest)
            util.prune_dirs(os.path.dirname(dest))
            raise
        except OSError as exc:
            raise ui.UserError(
                u"convert: could invoke '{0}': {1}".format(
                    ' '.join(args), exc
                )
            )

        if not quiet and not pretend:
            self._log.info(u'Finished encoding {0}',
                           util.displayable_path(source))

    def convert_item(self, dest_dir, keep_new, path_formats, fmt,
                     pretend=False):
        command, ext = get_format(fmt)
        item, original, converted = None, None, None
        while True:
            item = yield (item, original, converted)
            dest = item.destination(basedir=dest_dir,
                                    path_formats=path_formats)

            # When keeping the new file in the library, we first move the
            # current (pristine) file to the destination. We'll then copy it
            # back to its old path or transcode it to a new path.
            if keep_new:
                original = dest
                converted = item.path
                if should_transcode(item, fmt):
                    converted = replace_ext(converted, ext)
            else:
                original = item.path
                if should_transcode(item, fmt):
                    dest = replace_ext(dest, ext)
                converted = dest

            # Ensure that only one thread tries to create directories at a
            # time. (The existence check is not atomic with the directory
            # creation inside this function.)
            if not pretend:
                with _fs_lock:
                    util.mkdirall(dest)

            if os.path.exists(util.syspath(dest)):
                self._log.info(u'Skipping {0} (target file exists)',
                               util.displayable_path(item.path))
                continue

            if keep_new:
                if pretend:
                    self._log.info(u'mv {0} {1}',
                                   util.displayable_path(item.path),
                                   util.displayable_path(original))
                else:
                    self._log.info(u'Moving to {0}',
                                   util.displayable_path(original))
                    util.move(item.path, original)

            if should_transcode(item, fmt):
                try:
                    self.encode(command, original, converted, pretend)
                except subprocess.CalledProcessError:
                    continue
            else:
                if pretend:
                    self._log.info(u'cp {0} {1}',
                                   util.displayable_path(original),
                                   util.displayable_path(converted))
                else:
                    # No transcoding necessary.
                    self._log.info(u'Copying {0}',
                                   util.displayable_path(item.path))
                    util.copy(original, converted)

            if pretend:
                continue

            # Write tags from the database to the converted file.
            item.try_write(path=converted)

            if keep_new:
                # If we're keeping the transcoded file, read it again (after
                # writing) to get new bitrate, duration, etc.
                item.path = converted
                item.read()
                item.store()  # Store new path and audio data.

            if self.config['embed']:
                album = item.get_album()
                if album and album.artpath:
                    art.embed_item(self._log, item, album.artpath,
                                   itempath=converted)

            if keep_new:
                plugins.send('after_convert', item=item,
                             dest=dest, keepnew=True)
            else:
                plugins.send('after_convert', item=item,
                             dest=converted, keepnew=False)

    def copy_album_art(self, album, dest_dir, path_formats, pretend=False):
        """Copies the associated cover art of the album. Album must have at
        least one track.
        """
        if not album or not album.artpath:
            return

        album_item = album.items().get()
        # Album shouldn't be empty.
        if not album_item:
            return

        # Get the destination of the first item (track) of the album, we use
        # this function to format the path accordingly to path_formats.
        dest = album_item.destination(basedir=dest_dir,
                                      path_formats=path_formats)

        # Remove item from the path.
        dest = os.path.join(*util.components(dest)[:-1])

        dest = album.art_destination(album.artpath, item_dir=dest)
        if album.artpath == dest:
            return

        if not pretend:
            util.mkdirall(dest)

        if os.path.exists(util.syspath(dest)):
            self._log.info(u'Skipping {0} (target file exists)',
                           util.displayable_path(album.artpath))
            return

        if pretend:
            self._log.info(u'cp {0} {1}',
                           util.displayable_path(album.artpath),
                           util.displayable_path(dest))
        else:
            self._log.info(u'Copying cover art to {0}',
                           util.displayable_path(dest))
            util.copy(album.artpath, dest)

    def convert_func(self, lib, opts, args):
        if not opts.dest:
            opts.dest = self.config['dest'].get()
        if not opts.dest:
            raise ui.UserError('no convert destination set')
        opts.dest = util.bytestring_path(opts.dest)

        if not opts.threads:
            opts.threads = self.config['threads'].get(int)

        if self.config['paths']:
            path_formats = ui.get_path_formats(self.config['paths'])
        else:
            path_formats = ui.get_path_formats()

        if not opts.format:
            opts.format = self.config['format'].get(unicode).lower()

        pretend = opts.pretend if opts.pretend is not None else \
            self.config['pretend'].get(bool)

        if not pretend:
            ui.commands.list_items(lib, ui.decargs(args), opts.album)

            if not (opts.yes or ui.input_yn("Convert? (Y/n)")):
                return

        if opts.album:
            albums = lib.albums(ui.decargs(args))
            items = (i for a in albums for i in a.items())
            if self.config['copy_album_art']:
                for album in albums:
                    self.copy_album_art(album, opts.dest, path_formats,
                                        pretend)
        else:
            items = iter(lib.items(ui.decargs(args)))
        convert = [self.convert_item(opts.dest,
                                     opts.keep_new,
                                     path_formats,
                                     opts.format,
                                     pretend)
                   for _ in range(opts.threads)]
        pipe = util.pipeline.Pipeline([items, convert])
        pipe.run_parallel()

    def convert_on_import(self, lib, item):
        """Transcode a file automatically after it is imported into the
        library.
        """
        fmt = self.config['format'].get(unicode).lower()
        if should_transcode(item, fmt):
            command, ext = get_format()
            tmpdir = self.config['tmpdir'].get()
            fd, dest = tempfile.mkstemp('.' + ext, dir=tmpdir)
            dest = util.bytestring_path(dest)
            os.close(fd)
            _temp_files.append(dest)  # Delete the transcode later.
            try:
                self.encode(command, item.path, dest)
            except subprocess.CalledProcessError:
                return
            item.path = dest
            item.write()
            item.read()  # Load new audio information data.
            item.store()

    def _cleanup(self, task, session):
        for path in task.old_paths:
            if path in _temp_files:
                if os.path.isfile(path):
                    util.remove(path)
                _temp_files.remove(path)
