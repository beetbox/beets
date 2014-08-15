# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
from beets import config
from beets import mediafile

log = logging.getLogger('beets')

_MUTAGEN_FORMATS = {
    'asf': 'ASF',
    'apev2': 'APEv2File',
    'flac': 'FLAC',
    'id3': 'ID3FileType',
    'mp3': 'MP3',
    'mp4': 'MP4',
    'oggflac': 'OggFLAC',
    'oggspeex': 'OggSpeex',
    'oggtheora': 'OggTheora',
    'oggvorbis': 'OggVorbis',
    'oggopus': 'OggOpus',
    'trueaudio': 'TrueAudio',
    'wavpack': 'WavPack',
    'monkeysaudio': 'MonkeysAudio',
    'optimfrog': 'OptimFROG',
}


scrubbing = False


class ScrubPlugin(BeetsPlugin):
    """Removes extraneous metadata from files' tags."""
    def __init__(self):
        super(ScrubPlugin, self).__init__()
        self.config.add({
            'auto': True,
        })

    def commands(self):
        def scrub_func(lib, opts, args):
            # This is a little bit hacky, but we set a global flag to
            # avoid autoscrubbing when we're also explicitly scrubbing.
            global scrubbing
            scrubbing = True

            # Walk through matching files and remove tags.
            for item in lib.items(ui.decargs(args)):
                log.info(u'scrubbing: %s' % util.displayable_path(item.path))

                # Get album art if we need to restore it.
                if opts.write:
                    mf = mediafile.MediaFile(item.path,
                                             config['id3v23'].get(bool))
                    art = mf.art

                # Remove all tags.
                _scrub(item.path)

                # Restore tags, if enabled.
                if opts.write:
                    log.debug(u'writing new tags after scrub')
                    item.try_write()
                    if art:
                        log.info('restoring art')
                        mf = mediafile.MediaFile(item.path)
                        mf.art = art
                        mf.save()

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
        try:
            f.delete()
        except NotImplementedError:
            # Some Mutagen metadata subclasses (namely, ASFTag) do not
            # support .delete(), presumably because it is impossible to
            # remove them. In this case, we just remove all the tags.
            for tag in f.keys():
                del f[tag]
            f.save()
        except IOError as exc:
            log.error(u'could not scrub {0}: {1}'.format(
                util.displayable_path(path),
                exc,
            ))


# Automatically embed art into imported albums.
@ScrubPlugin.listen('write')
def write_item(path):
    if not scrubbing and config['scrub']['auto']:
        log.debug(u'auto-scrubbing %s' % util.displayable_path(path))
        _scrub(path)
