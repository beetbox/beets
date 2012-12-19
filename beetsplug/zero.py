# This file is part of beets.
# Copyright 2012, Blemjhoo Tezoulbr <baobab@heresiarch.info>.
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

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ZeroPlugin,
                                  cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super(ZeroPlugin, self).__init__()

        self.config.add({
            'fields': [],
        })

        self.fields = []
        self.patterns = {}
        self.warned = False

        for f in self.config['fields'].get(list):
            if f not in ITEM_KEYS:
                self._log.error('[zero] invalid field: {0}'.format(f))
            else:
                self.fields.append(f)
                try:
                    self.patterns[f] = self.config[f].get(list)
                except confit.NotFoundError:
                    self.patterns[f] = [u'']

    def import_task_choice_event(self, task):
        """Listen for import_task_choice event."""
        if task.choice_flag == action.ASIS and not self.warned:
            self._log.warn('[zero] cannot zero in \"as-is\" mode')
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
        if not self.fields:
            self._log.warn('[zero] no fields, nothing to do')
            return
        for fn in self.fields:
            try:
                fval = getattr(item, fn)
            except AttributeError:
                self._log.error('[zero] no such field: {0}'.format(fn))
            else:
                if not self.match_patterns(fval, self.patterns[fn]):
                    self._log.debug('[zero] \"{0}\" ({1}) not match: {2}'
                                    .format(fval, fn, 
                                            ' '.join(self.patterns[fn])))
                    continue
                self._log.debug('[zero] \"{0}\" ({1}) match: {2}'
                                .format(fval, fn, ' '.join(self.patterns[fn])))
                setattr(item, fn, type(fval)())
                self._log.debug('[zero] {0}={1}'.format(fn, getattr(item, fn)))


@ZeroPlugin.listen('import_task_choice')
def zero_choice(session, task):
    ZeroPlugin().import_task_choice_event(task)

@ZeroPlugin.listen('write')
def zero_write(item):
    ZeroPlugin().write_event(item)
