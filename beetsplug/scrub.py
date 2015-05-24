# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets import ui
from beets import util
from beets import config
from beets import mediafile

_MUTAGEN_FORMATS = {
    b'asf': b'ASF',
    b'apev2': b'APEv2File',
    b'flac': b'FLAC',
    b'id3': b'ID3FileType',
    b'mp3': b'MP3',
    b'mp4': b'MP4',
    b'oggflac': b'OggFLAC',
    b'oggspeex': b'OggSpeex',
    b'oggtheora': b'OggTheora',
    b'oggvorbis': b'OggVorbis',
    b'oggopus': b'OggOpus',
    b'trueaudio': b'TrueAudio',
    b'wavpack': b'WavPack',
    b'monkeysaudio': b'MonkeysAudio',
    b'optimfrog': b'OptimFROG',
}


scrubbing = False


class ScrubPlugin(BeetsPlugin):
    """Removes extraneous metadata from files' tags."""
    def __init__(self):
        super(ScrubPlugin, self).__init__()
        self.config.add({
            'auto': True,
        })
        self.register_listener("write", self.write_item)

    def commands(self):
        def scrub_func(lib, opts, args):
            # This is a little bit hacky, but we set a global flag to
            # avoid autoscrubbing when we're also explicitly scrubbing.
            global scrubbing
            scrubbing = True

            # Walk through matching files and remove tags.
            for item in lib.items(ui.decargs(args)):
                self._log.info(u'scrubbing: {0}',
                               util.displayable_path(item.path))

                # Get album art if we need to restore it.
                if opts.write:
                    try:
                        mf = mediafile.MediaFile(util.syspath(item.path),
                                                 config['id3v23'].get(bool))
                    except IOError as exc:
                        self._log.error(u'could not open file to scrub: {0}',
                                        exc)
                    art = mf.art

                # Remove all tags.
                self._scrub(item.path)

                # Restore tags, if enabled.
                if opts.write:
                    self._log.debug(u'writing new tags after scrub')
                    item.try_write()
                    if art:
                        self._log.info(u'restoring art')
                        mf = mediafile.MediaFile(util.syspath(item.path))
                        mf.art = art
                        mf.save()

            scrubbing = False

        scrub_cmd = ui.Subcommand('scrub', help='clean audio tags')
        scrub_cmd.parser.add_option('-W', '--nowrite', dest='write',
                                    action='store_false', default=True,
                                    help='leave tags empty')
        scrub_cmd.func = scrub_func

        return [scrub_cmd]

    @staticmethod
    def _mutagen_classes():
        """Get a list of file type classes from the Mutagen module.
        """
        classes = []
        for modname, clsname in _MUTAGEN_FORMATS.items():
            mod = __import__(b'mutagen.{0}'.format(modname),
                             fromlist=[clsname])
            classes.append(getattr(mod, clsname))
        return classes

    def _scrub(self, path):
        """Remove all tags from a file.
        """
        for cls in self._mutagen_classes():
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
                self._log.error(u'could not scrub {0}: {1}',
                                util.displayable_path(path), exc)

    def write_item(self, item, path, tags):
        """Automatically embed art into imported albums."""
        if not scrubbing and self.config['auto']:
            self._log.debug(u'auto-scrubbing {0}', util.displayable_path(path))
            self._scrub(path)
