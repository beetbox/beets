# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Tom Jaspers.
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

from __future__ import division, absolute_import, print_function

from contextlib import contextmanager
import os
import shutil
import tempfile
import plistlib

import six
from six.moves.urllib.parse import urlparse, unquote
from time import mktime

from beets import util
from beets.dbcore import types
from beets.library import DateType
from beets.util.confit import ConfigValueError
from beetsplug.metasync import MetaSource


@contextmanager
def create_temporary_copy(path):
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, 'temp_itunes_lib')
    shutil.copyfile(path, temp_path)
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_dir)


def _norm_itunes_path(path):
    # Itunes prepends the location with 'file://' on posix systems,
    # and with 'file://localhost/' on Windows systems.
    # The actual path to the file is always saved as posix form
    # E.g., 'file://Users/Music/bar' or 'file://localhost/G:/Music/bar'

    # The entire path will also be capitalized (e.g., '/Music/Alt-J')
    # Note that this means the path will always have a leading separator,
    # which is unwanted in the case of Windows systems.
    # E.g., '\\G:\\Music\\bar' needs to be stripped to 'G:\\Music\\bar'

    return util.bytestring_path(os.path.normpath(
        unquote(urlparse(path).path)).lstrip('\\')).lower()


class Itunes(MetaSource):

    item_types = {
        'itunes_rating':      types.INTEGER,  # 0..100 scale
        'itunes_playcount':   types.INTEGER,
        'itunes_skipcount':   types.INTEGER,
        'itunes_lastplayed':  DateType(),
        'itunes_lastskipped': DateType(),
    }

    def __init__(self, config, log):
        super(Itunes, self).__init__(config, log)

        config.add({'itunes': {
            'library': '~/Music/iTunes/iTunes Library.xml'
        }})

        # Load the iTunes library, which has to be the .xml one (not the .itl)
        library_path = config['itunes']['library'].as_filename()

        try:
            self._log.debug(
                u'loading iTunes library from {0}'.format(library_path))
            with create_temporary_copy(library_path) as library_copy:
                if six.PY2:
                    raw_library = plistlib.readPlist(library_copy)
                else:
                    with open(library_copy, 'rb') as library_copy_f:
                        raw_library = plistlib.load(library_copy_f)
        except IOError as e:
            raise ConfigValueError(u'invalid iTunes library: ' + e.strerror)
        except Exception:
            # It's likely the user configured their '.itl' library (<> xml)
            if os.path.splitext(library_path)[1].lower() != '.xml':
                hint = u': please ensure that the configured path' \
                       u' points to the .XML library'
            else:
                hint = ''
            raise ConfigValueError(u'invalid iTunes library' + hint)

        # Make the iTunes library queryable using the path
        self.collection = {_norm_itunes_path(track['Location']): track
                           for track in raw_library['Tracks'].values()
                           if 'Location' in track}

    def sync_from_source(self, item):
        result = self.collection.get(util.bytestring_path(item.path).lower())

        if not result:
            self._log.warning(u'no iTunes match found for {0}'.format(item))
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
