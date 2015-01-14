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

"""Warns you about things you hate (or even blocks import)."""

import re
from beets import config
from beets.plugins import BeetsPlugin
from beets.importer import action, SingletonImportTask
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
        self.register_listener('import_task_created',
                               self.import_task_created_event)
        self.config.add({
            'warn': [],
            'skip': [],
            'path': '.*'
        })

        self.path_album_regex = \
            self.path_singleton_regex = \
            re.compile(self.config['path'].get())

        if 'album_path' in self.config:
            self.path_album_regex = re.compile(self.config['album_path'].get())

        if 'singleton_path' in self.config:
                self.path_singleton_regex = re.compile(
                    self.config['singleton_path'].get())

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

    def import_task_created_event(self, session, task):
        if task.items and len(task.items) > 0:
            items_to_import = []
            for item in task.items:
                if self.file_filter(item['path']):
                    items_to_import.append(item)
            if len(items_to_import) > 0:
                task.items = items_to_import
            else:
                task.choice_flag = action.SKIP
        elif isinstance(task, SingletonImportTask):
            if not self.file_filter(task.item['path']):
                task.choice_flag = action.SKIP

    def file_filter(self, full_path):
        """Checks if the configured regular expressions allow the import of the
        file given in full_path.
        """
        import_config = dict(config['import'])
        if 'singletons' not in import_config or not import_config[
                'singletons']:
            # Album
            return self.path_album_regex.match(full_path) is not None
        else:
            # Singleton
            return self.path_singleton_regex.match(full_path) is not None
