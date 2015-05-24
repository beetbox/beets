# This file is part of beets.
# Copyright 2015, Malte Ried.
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

"""Filter imported files using a regular expression.
"""

import re
from beets import config
from beets.plugins import BeetsPlugin
from beets.importer import SingletonImportTask


class FileFilterPlugin(BeetsPlugin):
    def __init__(self):
        super(FileFilterPlugin, self).__init__()
        self.register_listener('import_task_created',
                               self.import_task_created_event)
        self.config.add({
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

    def import_task_created_event(self, session, task):
        if task.items and len(task.items) > 0:
            items_to_import = []
            for item in task.items:
                if self.file_filter(item['path']):
                    items_to_import.append(item)
            if len(items_to_import) > 0:
                task.items = items_to_import
            else:
                # Returning an empty list of tasks from the handler
                # drops the task from the rest of the importer pipeline.
                return []

        elif isinstance(task, SingletonImportTask):
            if not self.file_filter(task.item['path']):
                return []

        # If not filtered, return the original task unchanged.
        return [task]

    def file_filter(self, full_path):
        """Checks if the configured regular expressions allow the import
        of the file given in full_path.
        """
        import_config = dict(config['import'])
        if 'singletons' not in import_config or not import_config[
                'singletons']:
            # Album
            return self.path_album_regex.match(full_path) is not None
        else:
            # Singleton
            return self.path_singleton_regex.match(full_path) is not None
