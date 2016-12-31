# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets import ui
from beets import util
from beets import config
from beets import mediafile

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


class ScrubPlugin(BeetsPlugin):
    """Removes extraneous metadata from files' tags."""
    def __init__(self):
        super(ScrubPlugin, self).__init__()
        self.config.add({
            'auto': True,
        })

        if self.config['auto']:
            self.register_listener("import_task_files", self.import_task_files)

    def commands(self):
        def scrub_func(lib, opts, args):
            # Walk through matching files and remove tags.
            for item in lib.items(ui.decargs(args)):
                self._log.info(u'scrubbing: {0}',
                               util.displayable_path(item.path))
                self._scrub_item(item, opts.write)

        scrub_cmd = ui.Subcommand('scrub', help=u'clean audio tags')
        scrub_cmd.parser.add_option(
            u'-W', u'--nowrite', dest='write',
            action='store_false', default=True,
            help=u'leave tags empty')
        scrub_cmd.func = scrub_func

        return [scrub_cmd]

    @staticmethod
    def _mutagen_classes():
        """Get a list of file type classes from the Mutagen module.
        """
        classes = []
        for modname, clsname in _MUTAGEN_FORMATS.items():
            mod = __import__('mutagen.{0}'.format(modname),
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

    def _scrub_item(self, item, restore=True):
        """Remove tags from an Item's associated file and, if `restore`
        is enabled, write the database's tags back to the file.
        """
        # Get album art if we need to restore it.
        if restore:
            try:
                mf = mediafile.MediaFile(util.syspath(item.path),
                                         config['id3v23'].get(bool))
            except mediafile.UnreadableFileError as exc:
                self._log.error(u'could not open file to scrub: {0}',
                                exc)
                return
            images = mf.images

        # Remove all tags.
        self._scrub(item.path)

        # Restore tags, if enabled.
        if restore:
            self._log.debug(u'writing new tags after scrub')
            item.try_write()
            if images:
                self._log.debug(u'restoring art')
                try:
                    mf = mediafile.MediaFile(util.syspath(item.path),
                                             config['id3v23'].get(bool))
                    mf.images = images
                    mf.save()
                except mediafile.UnreadableFileError as exc:
                    self._log.error(u'could not write tags: {0}', exc)

    def import_task_files(self, session, task):
        """Automatically scrub imported files."""
        for item in task.imported_items():
            self._log.debug(u'auto-scrubbing {0}',
                            util.displayable_path(item.path))
            self._scrub_item(item)
