# This file is part of beets.
# Copyright 2015, Blemjhoo Tezoulbr <baobab@heresiarch.info>.
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

""" Clears tag fields in media files."""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import re
from beets.plugins import BeetsPlugin
from beets.mediafile import MediaFile
from beets.importer import action
from beets.util import confit

__author__ = 'baobab@heresiarch.info'
__version__ = '0.10'


class ZeroPlugin(BeetsPlugin):

    _instance = None

    def __init__(self):
        super(ZeroPlugin, self).__init__()

        # Listeners.
        self.register_listener('write', self.write_event)
        self.register_listener('import_task_choice',
                               self.import_task_choice_event)

        self.config.add({
            'fields': [],
        })

        self.patterns = {}
        self.warned = False

        for field in self.config['fields'].as_str_seq():
            if field in ('id', 'path', 'album_id'):
                self._log.warn(u'field \'{0}\' ignored, zeroing '
                               u'it would be dangerous', field)
                continue
            if field not in MediaFile.fields():
                self._log.error(u'invalid field: {0}', field)
                continue

            try:
                self.patterns[field] = self.config[field].as_str_seq()
            except confit.NotFoundError:
                # Matches everything
                self.patterns[field] = True

    def import_task_choice_event(self, session, task):
        """Listen for import_task_choice event."""
        if task.choice_flag == action.ASIS and not self.warned:
            self._log.warn(u'cannot zero in \"as-is\" mode')
            self.warned = True
        # TODO request write in as-is mode

    @classmethod
    def match_patterns(cls, field, patterns):
        """Check if field (as string) is matching any of the patterns in
        the list.
        """
        if patterns is True:
            return True
        for p in patterns:
            if re.search(p, unicode(field), flags=re.IGNORECASE):
                return True
        return False

    def write_event(self, item, path, tags):
        """Set values in tags to `None` if the key and value are matched
        by `self.patterns`.
        """
        if not self.patterns:
            self._log.warn(u'no fields, nothing to do')
            return

        for field, patterns in self.patterns.items():
            if field in tags:
                value = tags[field]
                match = self.match_patterns(tags[field], patterns)
            else:
                value = ''
                match = patterns is True

            if match:
                self._log.debug(u'{0}: {1} -> None', field, value)
                tags[field] = None
