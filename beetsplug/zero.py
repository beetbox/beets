# This file is part of beets.
# Copyright 2013, Blemjhoo Tezoulbr <baobab@heresiarch.info>.
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

import re
import logging
from beets.plugins import BeetsPlugin
from beets.library import Item
from beets.importer import action
from beets.util import confit

__author__ = 'baobab@heresiarch.info'
__version__ = '0.10'

log = logging.getLogger('beets')


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
                log.warn(u'[zero] field \'{0}\' ignored, zeroing '
                         u'it would be dangerous'.format(field))
                continue
            if field not in Item._fields.keys():
                log.error(u'[zero] invalid field: {0}'.format(field))
                continue

            try:
                self.patterns[field] = self.config[field].as_str_seq()
            except confit.NotFoundError:
                # Matches everything
                self.patterns[field] = [u'']

    def import_task_choice_event(self, session, task):
        """Listen for import_task_choice event."""
        if task.choice_flag == action.ASIS and not self.warned:
            log.warn(u'[zero] cannot zero in \"as-is\" mode')
            self.warned = True
        # TODO request write in as-is mode

    @classmethod
    def match_patterns(cls, field, patterns):
        """Check if field (as string) is matching any of the patterns in
        the list.
        """
        for p in patterns:
            if re.search(p, unicode(field), flags=re.IGNORECASE):
                return True
        return False

    def write_event(self, item):
        """Listen for write event."""
        if not self.patterns:
            log.warn(u'[zero] no fields, nothing to do')
            return

        for field, patterns in self.patterns.items():
            try:
                value = getattr(item, field)
            except AttributeError:
                log.error(u'[zero] no such field: {0}'.format(field))
                continue

            if self.match_patterns(value, patterns):
                log.debug(u'[zero] {0}: {1} -> None'.format(field, value))
                setattr(item, field, None)
