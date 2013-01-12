# This file is part of beets.
# Copyright 2012, Fabrice Laporte.
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

import logging
import subprocess
import os

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import syspath, command_output
from beets.ui import commands

log = logging.getLogger('beets')

DEFAULT_REFERENCE_LOUDNESS = 89
SAMPLE_MAX = 1 << 15

class ReplayGainError(Exception):
    """Raised when an error occurs during mp3gain/aacgain execution.
    """

def call(args):
    """Execute the command and return its output or raise a
    ReplayGainError on failure.
    """
    try:
        return command_output(args)
    except subprocess.CalledProcessError as e:
        raise ReplayGainError(
            "{0} exited with status {1}".format(args[0], e.returncode)
        )
    except UnicodeEncodeError:
        # Due to a bug in Python 2's subprocess on Windows, Unicode
        # filenames can fail to encode on that platform. See:
        # http://code.google.com/p/beets/issues/detail?id=499
        raise ReplayGainError("argument encoding failed")

def parse_tool_output(text):
    """Given the tab-delimited output from an invocation of mp3gain
    or aacgain, parse the text and return a list of dictionaries
    containing information about each analyzed file.
    """
    out = []
    for line in text.split('\n'):
        parts = line.split('\t')
        if len(parts) != 6 or parts[0] == 'File':
            continue
        out.append({
            'file': parts[0],
            'mp3gain': int(parts[1]),
            'gain': float(parts[2]),
            'peak': float(parts[3]) / SAMPLE_MAX,
            'maxgain': int(parts[4]),
            'mingain': int(parts[5]),
        })
    return out

class ReplayGainPlugin(BeetsPlugin):
    """Provides ReplayGain analysis.
    """
    def __init__(self):
        super(ReplayGainPlugin, self).__init__()
        self.import_stages = [self.imported]

    def configure(self, config):
        self.overwrite = ui.config_val(config, 'replaygain',
                                       'overwrite', False, bool)
        self.albumgain = ui.config_val(config, 'replaygain',
                                       'albumgain', False, bool)
        self.noclip = ui.config_val(config, 'replaygain',
                                    'noclip', True, bool)
        self.apply_gain = ui.config_val(config, 'replaygain',
                                        'apply_gain', False, bool)
        target_level = float(ui.config_val(config, 'replaygain',
                                           'targetlevel',
                                           DEFAULT_REFERENCE_LOUDNESS))
        self.gain_offset = int(target_level - DEFAULT_REFERENCE_LOUDNESS)
        self.automatic = ui.config_val(config, 'replaygain',
                                       'automatic', True, bool)

        self.command = ui.config_val(config,'replaygain','command', None)
        if self.command:
            # Explicit executable path.
            if not os.path.isfile(self.command):
                raise ui.UserError(
                    'replaygain command does not exist: {0}'.format(
                        self.command
                    )
                )
        else:
            # Check whether the program is in $PATH.
            for cmd in ('mp3gain', 'aacgain'):
                try:
                    call([cmd, '-v'])
                    self.command = cmd
                except OSError:
                    pass
        if not self.command:
            raise ui.UserError(
                'no replaygain command found: install mp3gain or aacgain'
            )

    def imported(self, config, task):
        """Our import stage function."""
        if not self.automatic:
            return

        if task.is_album:
            album = config.lib.get_album(task.album_id)
            items = list(album.items())
        else:
            items = [task.item]

        results = self.compute_rgain(items, task.is_album)
        if results:
            self.store_gain(config.lib, items, results,
                            album if task.is_album else None)

    def commands(self):
        """Provide a ReplayGain command."""
        def func(lib, config, opts, args):
            write = ui.config_val(config, 'beets', 'import_write',
                                  commands.DEFAULT_IMPORT_WRITE, bool)

            if opts.album:
                # Analyze albums.
                for album in lib.albums(ui.decargs(args)):
                    log.info(u'analyzing {0} - {1}'.format(album.albumartist,
                                                           album.album))
                    items = list(album.items())
                    results = self.compute_rgain(items, True)
                    if results:
                        self.store_gain(lib, items, results, album)

                    if write:
                        for item in items:
                            item.write()

            else:
                # Analyze individual tracks.
                for item in lib.items(ui.decargs(args)):
                    log.info(u'analyzing {0} - {1}'.format(item.artist,
                                                           item.title))
                    results = self.compute_rgain([item], False)
                    if results:
                        self.store_gain(lib, [item], results, None)

                    if write:
                        item.write()

        cmd = ui.Subcommand('replaygain', help='analyze for ReplayGain')
        cmd.parser.add_option('-a', '--album', action='store_true',
                              help='analyze albums instead of tracks')
        cmd.func = func
        return [cmd]

    def requires_gain(self, item, album=False):
        """Does the gain need to be computed?"""
        if 'mp3gain' in self.command and item.format != 'MP3':
            return False
        elif 'aacgain' in self.command and item.format not in ('MP3', 'AAC'):
            return False
        return self.overwrite or \
               (not item.rg_track_gain or not item.rg_track_peak) or \
               ((not item.rg_album_gain or not item.rg_album_peak) and \
                album)

    def compute_rgain(self, items, album=False):
        """Compute ReplayGain values and return a list of results
        dictionaries as given by `parse_tool_output`.
        """
        # Skip calculating gain only when *all* files don't need
        # recalculation. This way, if any file among an album's tracks
        # needs recalculation, we still get an accurate album gain
        # value.
        if all([not self.requires_gain(i, album) for i in items]):
            log.debug(u'replaygain: no gain to compute')
            return

        # Construct shell command. The "-o" option makes the output
        # easily parseable (tab-delimited). "-s s" forces gain
        # recalculation even if tags are already present and disables
        # tag-writing; this turns the mp3gain/aacgain tool into a gain
        # calculator rather than a tag manipulator because we take care
        # of changing tags ourselves.
        cmd = [self.command, '-o', '-s', 's']
        if self.noclip:
            # Adjust to avoid clipping.
            cmd = cmd + ['-k']
        else:
            # Disable clipping warning.
            cmd = cmd + ['-c']
        if self.apply_gain:
            # Lossless audio adjustment.
            cmd = cmd + ['-a' if album and self.albumgain else '-r']
        cmd = cmd + ['-d', str(self.gain_offset)]
        cmd = cmd + [syspath(i.path) for i in items]

        log.debug(u'replaygain: analyzing {0} files'.format(len(items)))
        try:
            output = call(cmd)
        except ReplayGainError as exc:
            log.warn(u'replaygain: analysis failed ({0})'.format(exc))
            return
        log.debug(u'replaygain: analysis finished')
        results = parse_tool_output(output)

        return results

    def store_gain(self, lib, items, rgain_infos, album=None):
        """Store computed ReplayGain values to the Items and the Album
        (if it is provided).
        """
        for item, info in zip(items, rgain_infos):
            item.rg_track_gain = info['gain']
            item.rg_track_peak = info['peak']
            lib.store(item)

            log.debug(u'replaygain: applied track gain {0}, peak {1}'.format(
                item.rg_track_gain,
                item.rg_track_peak
            ))

        if album and self.albumgain:
            assert len(rgain_infos) == len(items) + 1
            album_info = rgain_infos[-1]
            album.rg_album_gain = album_info['gain']
            album.rg_album_peak = album_info['peak']
            log.debug(u'replaygain: applied album gain {0}, peak {1}'.format(
                album.rg_album_gain,
                album.rg_album_peak
            ))
