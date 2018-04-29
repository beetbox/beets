# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Blemjhoo Tezoulbr <baobab@heresiarch.info>.
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

from __future__ import division, absolute_import, print_function

"""Warns you about things you hate (or even blocks import)."""

from beets.plugins import BeetsPlugin
from beets.importer import action
from beets.library import parse_query_string
from beets.library import Item
from beets.library import Album


__author__ = 'baobab@heresiarch.info'
__version__ = '2.0'


def summary(task):
    """Given an ImportTask, produce a short string identifying the
    object.
    """
    if task.is_album:
        return u'{0} - {1}'.format(task.cur_artist, task.cur_album)
    else:
        return u'{0} - {1}'.format(task.item.artist, task.item.title)


class IHatePlugin(BeetsPlugin):
    def __init__(self):
        super(IHatePlugin, self).__init__()
        self.register_listener('import_task_choice',
                               self.import_task_choice_event)
        self.config.add({
            'warn': [],
            'skip': [],
        })

    @classmethod
    def do_i_hate_this(cls, task, action_patterns):
        """Process group of patterns (warn or skip) and returns True if
        task is hated and not whitelisted.
        """
        if action_patterns:
            for query_string in action_patterns:
                query, _ = parse_query_string(
                    query_string,
                    Album if task.is_album else Item,
                )
                if any(query.match(item) for item in task.imported_items()):
                    return True
        return False

    def import_task_choice_event(self, session, task):
        skip_queries = self.config['skip'].as_str_seq()
        warn_queries = self.config['warn'].as_str_seq()

        if task.choice_flag == action.APPLY:
            if skip_queries or warn_queries:
                self._log.debug(u'processing your hate')
                if self.do_i_hate_this(task, skip_queries):
                    task.choice_flag = action.SKIP
                    self._log.info(u'skipped: {0}', summary(task))
                    return
                if self.do_i_hate_this(task, warn_queries):
                    self._log.info(u'you may hate this: {0}', summary(task))
            else:
                self._log.debug(u'nothing to do')
        else:
            self._log.debug(u'user made a decision, nothing to do')
