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
from beets.library import ITEM_KEYS
from beets.importer import action
from beets.util import confit

__author__ = 'baobab@heresiarch.info'
__version__ = '0.10'


class ZeroPlugin(BeetsPlugin):

    _instance = None
    _log = logging.getLogger('beets')

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

        for f in self.config['fields'].as_str_seq():
            if f not in ITEM_KEYS:
                self._log.error(u'[zero] invalid field: {0}'.format(f))
            else:
                try:
                    self.patterns[f] = self.config[f].as_str_seq()
                except confit.NotFoundError:
                    self.patterns[f] = [u'']

    def import_task_choice_event(self, session, task):
        """Listen for import_task_choice event."""
        if task.choice_flag == action.ASIS and not self.warned:
            self._log.warn(u'[zero] cannot zero in \"as-is\" mode')
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
            self._log.warn(u'[zero] no fields, nothing to do')
            return
        for fn, patterns in self.patterns.items():
            try:
                fval = getattr(item, fn)
            except AttributeError:
                self._log.error(u'[zero] no such field: {0}'.format(fn))
            else:
                if not self.match_patterns(fval, patterns):
                    self._log.debug(u'[zero] \"{0}\" ({1}) not match: {2}'
                                    .format(fval, fn, 
                                            ' '.join(patterns)))
                    continue
                self._log.debug(u'[zero] \"{0}\" ({1}) match: {2}'
                                .format(fval, fn, ' '.join(patterns)))
                new_val = None if fval is None else type(fval)()
                setattr(item, fn, new_val)
                self._log.debug(u'[zero] {0}={1}'
                                .format(fn, getattr(item, fn)))
