# This file is part of beets.
# Copyright 2015, Tom Jaspers.
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

"""Synchronize information from iTunes's library
"""
from contextlib import contextmanager
import os
import shutil
import tempfile
from time import mktime

import plistlib
from beets import util
from beets.util.confit import ConfigValueError
from beetsplug.metasync import MetaSource


@contextmanager
def create_temporary_copy(path):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, 'temp_itunes_lib')
    shutil.copyfile(path, temp_path)
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_dir)


class ITunes(MetaSource):

    def __init__(self, config, log):
        super(ITunes, self).__init__(config, log)

        # Load the iTunes library, which has to be the .xml one (not the .itl)
        library_path = util.normpath(config['itunes']['library'].get(str))

        try:
            self._log.debug(
                u'loading iTunes library from {0}'.format(library_path))
            with create_temporary_copy(library_path) as library_copy:
                raw_library = plistlib.readPlist(library_copy)
        except IOError as e:
            raise ConfigValueError(u"invalid iTunes library: " + e.strerror)
        except Exception as e:
            # It's likely the user configured their '.itl' library (<> xml)
            if os.path.splitext(library_path)[1].lower() != '.xml':
                hint = u": please ensure that the configured path" \
                       u" points to the .XML library"
            else:
                hint = ''
            raise ConfigValueError(u"invalid iTunes library" + hint)

        # Convert the library in to something we can query more easily
        self.collection = {
            (track['Name'], track['Album'], track['Album Artist']): track
            for track in raw_library['Tracks'].values()}

    def sync_data(self, item):
        key = (item.title, item.album, item.albumartist)
        result = self.collection.get(key)

        if not all(key) or not result:
            self._log.warning(u"no iTunes match found for {0}".format(item))
            return

        item.itunes_rating = result.get('Rating')
        item.itunes_playcount = result.get('Play Count')
        item.itunes_skipcount = result.get('Skip Count')

        if result.get('Play Date UTC'):
            item.itunes_lastplayed = mktime(
                result.get('Play Date UTC').timetuple())

        if result.get('Skip Date'):
            item.itunes_lastskipped = mktime(
                result.get('Skip Date').timetuple())
