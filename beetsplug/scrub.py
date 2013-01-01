# This file is part of beets.
# Copyright 2012, Adrian Sampson.
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

"""Cleans extraneous metadata from files' tags via a command or
automatically whenever tags are written.
"""
import logging

from beets.plugins import BeetsPlugin
from beets import ui
from beets import util

log = logging.getLogger('beets')

AUTOSCRUB_KEY = 'autoscrub'
_MUTAGEN_FORMATS = {
    'asf': 'ASF',
    'apev2': 'APEv2File',
    'flac': 'FLAC',
    'id3': 'ID3FileType',
    'mp3': 'MP3',
    'oggflac': 'OggFLAC',
    'oggspeex': 'OggSpeex',
    'oggtheora': 'OggTheora',
    'oggvorbis': 'OggVorbis',
    'trueaudio': 'TrueAudio',
    'wavpack': 'WavPack',
    'monkeysaudio': 'MonkeysAudio',
    'optimfrog': 'OptimFROG',
}

scrubbing = False

options = {
    AUTOSCRUB_KEY: True,
}
class ScrubPlugin(BeetsPlugin):
    """Removes extraneous metadata from files' tags."""
    def configure(self, config):
        options[AUTOSCRUB_KEY] = \
            ui.config_val(config, 'scrub', AUTOSCRUB_KEY, True, bool)

    def commands(self):
        def scrub_func(lib, config, opts, args):
            # This is a little bit hacky, but we set a global flag to
            # avoid autoscrubbing when we're also explicitly scrubbing.
            global scrubbing
            scrubbing = True

            # Walk through matching files and remove tags.
            for item in lib.items(ui.decargs(args)):
                log.info(u'scrubbing: %s' % util.displayable_path(item.path))
                _scrub(item.path)

                if opts.write:
                    log.debug(u'writing new tags after scrub')
                    item.write()

            scrubbing = False

        scrub_cmd = ui.Subcommand('scrub', help='clean audio tags')
        scrub_cmd.parser.add_option('-W', '--nowrite', dest='write',
                                    action='store_false', default=True,
                                    help='leave tags empty')
        scrub_cmd.func = scrub_func

        return [scrub_cmd]

def _mutagen_classes():
    """Get a list of file type classes from the Mutagen module.
    """
    classes = []
    for modname, clsname in _MUTAGEN_FORMATS.items():
        mod = __import__('mutagen.{0}'.format(modname),
                         fromlist=[clsname])
        classes.append(getattr(mod, clsname))
    return classes

def _scrub(path):
    """Remove all tags from a file.
    """
    for cls in _mutagen_classes():
        # Try opening the file with this type, but just skip in the
        # event of any error.
        try:
            f = cls(util.syspath(path))
        except Exception:
            continue
        if f.tags is None:
            continue

        # Remove the tag for this type.
        f.delete()
        f.save()

# Automatically embed art into imported albums.
@ScrubPlugin.listen('write')
def write_item(item):
    if not scrubbing and options[AUTOSCRUB_KEY]:
        log.debug(u'auto-scrubbing %s' % util.displayable_path(item.path))
        _scrub(item.path)
