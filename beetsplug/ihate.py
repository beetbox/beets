# This file is part of beets.
# Copyright 2014, Blemjhoo Tezoulbr <baobab@heresiarch.info>.
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

import logging
import os
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
    _log = logging.getLogger('beets')

    def __init__(self):
        super(IHatePlugin, self).__init__()
        self.register_listener('import_task_choice',
                               self.import_task_choice_event)
        self.register_listener('import_task_created',
                               self.import_task_created_event)
        self.config.add({
            'warn': [],
            'skip': [],
            'regex_ignore_case': False,
            'regex_invert_folder_result': False,
            'regex_invert_file_result': False,
            'regex_folder_name': '.*',
            'regex_file_name': '.*'
        })

        flags = re.IGNORECASE if self.config['regex_ignore_case'].get() else 0

        self.invert_folder_album_result = \
            self.invert_folder_singleton_result = \
            self.config['regex_invert_folder_result'].get()
        self.invert_file_album_result = \
            self.invert_file_singleton_result = \
            self.config['regex_invert_file_result'].get()
        self.folder_name_album_regex = \
            self.folder_name_singleton_regex = \
            re.compile(self.config['regex_folder_name'].get(), flags)
        self.file_name_album_regex = \
            self.file_name_singleton_regex = \
            re.compile(self.config['regex_file_name'].get(), flags)

        if 'album' in self.config:
            album_config = self.config['album']
            if 'regex_invert_folder_result' in album_config:
                self.invert_folder_album_result = album_config[
                    'regex_invert_folder_result'].get()
            if 'regex_invert_file_result' in album_config:
                self.invert_file_album_result = album_config[
                    'regex_invert_file_result'].get()
            if 'regex_folder_name' in album_config:
                self.folder_name_album_regex = re.compile(
                    album_config['regex_folder_name'].get(), flags)
            if 'regex_file_name' in album_config:
                self.file_name_album_regex = re.compile(
                    album_config['regex_file_name'].get(), flags)

        if 'singleton' in self.config:
            singleton_config = self.config['singleton']
            if 'regex_invert_folder_result' in singleton_config:
                self.invert_folder_singleton_result = singleton_config[
                    'regex_invert_folder_result'].get()
            if 'regex_invert_file_result' in singleton_config:
                self.invert_file_singleton_result = singleton_config[
                    'regex_invert_file_result'].get()
            if 'regex_folder_name' in singleton_config:
                self.folder_name_singleton_regex = re.compile(
                    singleton_config['regex_folder_name'].get(), flags)
            if 'regex_file_name' in singleton_config:
                self.file_name_singleton_regex = re.compile(
                    singleton_config['regex_file_name'].get(), flags)

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
                self._log.debug(u'[ihate] processing your hate')
                if self.do_i_hate_this(task, skip_queries):
                    task.choice_flag = action.SKIP
                    self._log.info(u'[ihate] skipped: {0}'
                                   .format(summary(task)))
                    return
                if self.do_i_hate_this(task, warn_queries):
                    self._log.info(u'[ihate] you maybe hate this: {0}'
                                   .format(summary(task)))
            else:
                self._log.debug(u'[ihate] nothing to do')
        else:
            self._log.debug(u'[ihate] user made a decision, nothing to do')

    def import_task_created_event(self, session, task):
        if task.items and len(task.items) > 0:
            items_to_import = []
            for item in task.items:
                if self.file_filter(item['path'], session.paths):
                    items_to_import.append(item)
            if len(items_to_import) > 0:
                task.items = items_to_import
            else:
                task.choice_flag = action.SKIP
        elif isinstance(task, SingletonImportTask):
            if not self.file_filter(task.item['path'], session.paths):
                task.choice_flag = action.SKIP

    def file_filter(self, full_path, base_paths):
        """Checks if the configured regular expressions allow the import of the
        file given in full_path.
        """
        # The folder regex only checks the folder names starting from the
        # longest base path. Find this folder.
        matched_base_path = ''
        for base_path in base_paths:
            if full_path.startswith(base_path) and len(base_path) > len(
                    matched_base_path):
                matched_base_path = base_path
        relative_path = full_path[len(matched_base_path):]

        if os.path.isdir(full_path):
            path = relative_path
            file_name = None
        else:
            path, file_name = os.path.split(relative_path)
        path, folder_name = os.path.split(path)

        import_config = dict(config['import'])
        if 'singletons' not in import_config or not import_config[
                'singletons']:
            # Album

            # Folder
            while len(folder_name) > 0:
                matched = self.folder_name_album_regex.match(
                    folder_name) is not None
                matched = not matched if self.invert_folder_album_result else \
                    matched
                if not matched:
                    return False
                path, folder_name = os.path.split(path)

            # File
            matched = self.file_name_album_regex.match(
                file_name) is not None
            matched = not matched if self.invert_file_album_result else matched
            if not matched:
                return False
            return True
        else:
            # Singleton

            # Folder
            while len(folder_name) > 0:
                matched = self.folder_name_singleton_regex.match(
                    folder_name) is not None
                matched = not matched if \
                    self.invert_folder_singleton_result else matched
                if not matched:
                    return False
                path, folder_name = os.path.split(path)

            # File
            matched = self.file_name_singleton_regex.match(
                file_name) is not None
            matched = not matched if self.invert_file_singleton_result else \
                matched
            if not matched:
                return False
            return True
