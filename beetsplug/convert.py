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
import subprocess
import tempfile
from string import Template
import pipes

from beets import ui, util, plugins, config
from beets.plugins import BeetsPlugin
from beetsplug.embedart import embed_item
from beets.util.confit import ConfigTypeError

log = logging.getLogger('beets')
_fs_lock = threading.Lock()
_temp_files = []  # Keep track of temporary transcoded files for deletion.

# Some convenient alternate names for formats.
ALIASES = {
    u'wma': u'windows media',
    u'vorbis': u'ogg',
}


def replace_ext(path, ext):
    """Return the path with its extension replaced by `ext`.

    The new extension must not contain a leading dot.
    """
    return os.path.splitext(path)[0] + '.' + ext


def get_format(format=None):
    """Return the command tempate and the extension from the config.
    """
    if not format:
        format = config['convert']['format'].get(unicode).lower()
    format = ALIASES.get(format, format)

    try:
        format_info = config['convert']['formats'][format].get(dict)
        command = format_info['command']
        extension = format_info['extension']
    except KeyError:
        raise ui.UserError(
            u'convert: format {0} needs "command" and "extension" fields'
            .format(format)
        )
    except ConfigTypeError:
        command = config['convert']['formats'][format].get(str)
        extension = format

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


def encode(command, source, dest, pretend=False):
    """Encode `source` to `dest` using command template `command`.

    Raises `subprocess.CalledProcessError` if the command exited with a
    non-zero status code.
    """
    quiet = config['convert']['quiet'].get()

    if not quiet and not pretend:
        log.info(u'Encoding {0}'.format(util.displayable_path(source)))

    command = Template(command).safe_substitute({
        'source': pipes.quote(source),
        'dest':   pipes.quote(dest),
    })

    log.debug(u'convert: executing: {0}'
              .format(util.displayable_path(command)))

    if pretend:
        log.info(command)
        return

    try:
        util.command_output(command, shell=True)
    except subprocess.CalledProcessError:
        # Something went wrong (probably Ctrl+C), remove temporary files
        log.info(u'Encoding {0} failed. Cleaning up...'
                 .format(util.displayable_path(source)))
        util.remove(dest)
        util.prune_dirs(os.path.dirname(dest))
        raise
    except OSError as exc:
        raise ui.UserError(
            u"convert: could invoke '{0}': {0}".format(command, exc)
        )

    if not quiet and not pretend:
        log.info(u'Finished encoding {0}'.format(
            util.displayable_path(source))
        )


def should_transcode(item):
    """Determine whether the item should be transcoded as part of
    conversion (i.e., its bitrate is high or it has the wrong format).
    """
    maxbr = config['convert']['max_bitrate'].get(int)
    format_name = config['convert']['format'].get(unicode)
    return format_name.lower() != item.format.lower() or \
        item.bitrate >= 1000 * maxbr


def convert_item(dest_dir, keep_new, path_formats, command, ext,
                 pretend=False):
    while True:
        item = yield
        dest = item.destination(basedir=dest_dir, path_formats=path_formats)

        # When keeping the new file in the library, we first move the
        # current (pristine) file to the destination. We'll then copy it
        # back to its old path or transcode it to a new path.
        if keep_new:
            original = dest
            converted = replace_ext(item.path, ext)
        else:
            original = item.path
            dest = replace_ext(dest, ext)
            converted = dest

        # Ensure that only one thread tries to create directories at a
        # time. (The existence check is not atomic with the directory
        # creation inside this function.)
        if not pretend:
            with _fs_lock:
                util.mkdirall(dest)

        if os.path.exists(util.syspath(dest)):
            log.info(u'Skipping {0} (target file exists)'.format(
                util.displayable_path(item.path)
            ))
            continue

        if keep_new:
            if pretend:
                log.info(u'mv {0} {1}'.format(
                    util.displayable_path(item.path),
                    util.displayable_path(original),
                ))
            else:
                log.info(u'Moving to {0}'.format(
                    util.displayable_path(original))
                )
                util.move(item.path, original)

        if not should_transcode(item):
            if pretend:
                log.info(u'cp {0} {1}'.format(
                    util.displayable_path(original),
                    util.displayable_path(converted),
                ))
            else:
                # No transcoding necessary.
                log.info(u'Copying {0}'.format(
                    util.displayable_path(item.path))
                )
                util.copy(original, converted)
        else:
            try:
                encode(command, original, converted, pretend)
            except subprocess.CalledProcessError:
                continue

        if pretend:
            continue

        # Write tags from the database to the converted file.
        item.write(path=converted)

        if keep_new:
            # If we're keeping the transcoded file, read it again (after
            # writing) to get new bitrate, duration, etc.
            item.path = converted
            item.read()
            item.store()  # Store new path and audio data.

        if config['convert']['embed']:
            album = item.get_album()
            if album and album.artpath:
                embed_item(item, album.artpath, itempath=converted)

        plugins.send('after_convert', item=item, dest=dest, keepnew=keep_new)


def convert_on_import(lib, item):
    """Transcode a file automatically after it is imported into the
    library.
    """
    if should_transcode(item):
        command, ext = get_format()
        fd, dest = tempfile.mkstemp(ext)
        os.close(fd)
        _temp_files.append(dest)  # Delete the transcode later.
        try:
            encode(command, item.path, dest)
        except subprocess.CalledProcessError:
            return
        item.path = dest
        item.write()
        item.read()  # Load new audio information data.
        item.store()


def convert_func(lib, opts, args):
    if not opts.dest:
        opts.dest = config['convert']['dest'].get()
    if not opts.dest:
        raise ui.UserError('no convert destination set')
    opts.dest = util.bytestring_path(opts.dest)

    if not opts.threads:
        opts.threads = config['convert']['threads'].get(int)

    if config['convert']['paths']:
        path_formats = ui.get_path_formats(config['convert']['paths'])
    else:
        path_formats = ui.get_path_formats()

    if not opts.format:
        opts.format = config['convert']['format'].get(unicode).lower()

    command, ext = get_format(opts.format)

    pretend = opts.pretend if opts.pretend is not None else \
        config['convert']['pretend'].get(bool)

    if not pretend:
        ui.commands.list_items(lib, ui.decargs(args), opts.album, None)

        if not ui.input_yn("Convert? (Y/n)"):
            return

    if opts.album:
        items = (i for a in lib.albums(ui.decargs(args)) for i in a.items())
    else:
        items = iter(lib.items(ui.decargs(args)))
    convert = [convert_item(opts.dest,
                            opts.keep_new,
                            path_formats,
                            command,
                            ext,
                            pretend)
               for _ in range(opts.threads)]
    pipe = util.pipeline.Pipeline([items, convert])
    pipe.run_parallel()


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
            u'quiet': False,
            u'embed': True,
            u'paths': {},
        })
        self.import_stages = [self.auto_convert]

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert to external location')
        cmd.parser.add_option('-p', '--pretend', action='store_true',
                              help='show actions but do nothing')
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
        cmd.parser.add_option('-f', '--format', action='store', dest='format',
                              help='set the destination directory')
        cmd.func = convert_func
        return [cmd]

    def auto_convert(self, config, task):
        if self.config['auto']:
            for item in task.imported_items():
                convert_on_import(config.lib, item)


@ConvertPlugin.listen('import_task_files')
def _cleanup(task, session):
    for path in task.old_paths:
        if path in _temp_files:
            if os.path.isfile(path):
                util.remove(path)
            _temp_files.remove(path)
