# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Jack Wilsdon <jack.wilsdon@gmail.com>
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

"""Load SQLite extensions.
"""

from __future__ import division, absolute_import, print_function

from beets.dbcore import Database
from beets.plugins import BeetsPlugin
import sqlite3


class LoadExtPlugin(BeetsPlugin):
    def __init__(self):
        super(LoadExtPlugin, self).__init__()

        if not Database.supports_extensions:
            self._log.warn('loadext is enabled but the current SQLite '
                           'installation does not support extensions')
            return

        self.register_listener('library_opened', self.library_opened)

    def library_opened(self, lib):
        for v in self.config:
            ext = v.as_filename()

            self._log.debug(u'loading extension {}', ext)

            try:
                lib.load_extension(ext)
            except sqlite3.OperationalError as e:
                self._log.error(u'failed to load extension {}: {}', ext, e)
