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

"""Warns you about things you hate (or even blocks import)."""

import re
import logging
from beets.plugins import BeetsPlugin
from beets.importer import action
from beets.dbcore.query import AndQuery
from beets.library import query_from_strings
from beets.library import Item
from beets.library import Album


__author__ = 'baobab@heresiarch.info'
__version__ = '2.0'


class IHatePlugin(BeetsPlugin):

    _instance = None
    _log = logging.getLogger('beets')

    def __init__(self):
        super(IHatePlugin, self).__init__()
        self.register_listener('import_task_choice',
                               self.import_task_choice_event)
        self.config.add({
            'warn': {},
            'skip': {},
        })

    @classmethod
    def do_i_hate_this(cls, task, action_patterns):
        """Process group of patterns (warn or skip) and returns True if
        task is hated and not whitelisted.
        """
        if action_patterns:
            for queryString in action_patterns:
                blockQuery = None
                if task.is_album:
                    blockQuery = query_from_strings(AndQuery,Album,queryString)
                else:
                    blockQuery = query_from_strings(AndQuery,Item,queryString)
                if any(blockQuery.match(item) for item in task.items):
                    return True
        return False


    def job_to_do(self):
        """Return True if at least one pattern is defined."""
        return any(self.config[l].as_str_seq() for l in ('warn', 'skip'))

    def import_task_choice_event(self, session, task):
        if task.choice_flag == action.APPLY:
            if self.job_to_do():
                self._log.debug('[ihate] processing your hate')
                if self.do_i_hate_this(task, self.config['skip']):
                    task.choice_flag = action.SKIP
                    self._log.info(u'[ihate] skipped: {0} - {1}'
                                   .format(task.cur_artist, task.cur_album))
                    return
                if self.do_i_hate_this(task, self.config['warn']):
                    self._log.info(u'[ihate] you maybe hate this: {0} - {1}'
                                   .format(task.cur_artist, task.cur_album))
            else:
                self._log.debug('[ihate] nothing to do')
        else:
            self._log.debug('[ihate] user made a decision, nothing to do')
