# This file is part of beets.
# Copyright 2014, Malte Ried
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
import logging
import os
import re
from beets import config
from beets.plugins import BeetsPlugin
from beets.util import syspath

log = logging.getLogger('beets')


class RegexFileFilterPlugin(BeetsPlugin):
    def __init__(self):
        super(RegexFileFilterPlugin, self).__init__()
        self.file_filters = [self.file_filter]

        self.config.add({
            'ignore_case': False,
            'invert_folder_result': False,
            'invert_file_result': False,
            'folder_name_regex': '.*',
            'file_name_regex': '.*'
        })
        flags = re.IGNORECASE if self.config['ignore_case'].get() else 0

        self.invert_folder_album_result = \
            self.invert_folder_singleton_result = \
            self.config['invert_folder_result'].get()
        self.invert_file_album_result = \
            self.invert_file_singleton_result = \
            self.config['invert_file_result'].get()
        self.folder_name_album_regex = \
            self.folder_name_singleton_regex = \
            re.compile(self.config['folder_name_regex'].get(), flags)
        self.file_name_album_regex = \
            self.file_name_singleton_regex = \
            re.compile(self.config['file_name_regex'].get(), flags)

        if 'album' in self.config:
            album_config = self.config['album']
            if 'invert_folder_result' in album_config:
                self.invert_folder_album_result = album_config['invert_folder_result'].get()
            if 'invert_file_result' in album_config:
                self.invert_file_album_result = album_config['invert_file_result'].get()
            if 'folder_name_regex' in album_config:
                self.folder_name_album_regex = re.compile(album_config['folder_name_regex'].get(), flags)
            if 'file_name_regex' in album_config:
                self.file_name_album_regex = re.compile(album_config['file_name_regex'].get(), flags)
                
        if 'singleton' in self.config:
            singleton_config = self.config['singleton']
            if 'invert_folder_result' in singleton_config:
                self.invert_folder_singleton_result = singleton_config['invert_folder_result'].get()
            if 'invert_file_result' in singleton_config:
                self.invert_file_singleton_result = singleton_config['invert_file_result'].get()
            if 'folder_name_regex' in singleton_config:
                self.folder_name_singleton_regex = re.compile(singleton_config['folder_name_regex'].get(), flags)
            if 'file_name_regex' in singleton_config:
                self.file_name_singleton_regex = re.compile(singleton_config['file_name_regex'].get(), flags)

    def file_filter(self, path, object_name):
        full_path = os.path.join(path, object_name)
        import_config = dict(config['import'])
        if not 'singletons' in import_config or not import_config['singletons']:
            if os.path.isdir(syspath(full_path)):
                matched = self.folder_name_album_regex.match(object_name) is not None
                if self.invert_folder_album_result:
                    return not matched
                return matched
            else:
                matched = self.file_name_album_regex.match(object_name) is not None
                if self.invert_file_album_result:
                    return not matched
                return matched
        else:
            if os.path.isdir(syspath(full_path)):
                matched = self.folder_name_singleton_regex.match(object_name) is not None
                if self.invert_folder_singleton_result:
                    return not matched
                return matched
            else:
                matched = self.file_name_singleton_regex.match(object_name) is not None
                if self.invert_file_singleton_result:
                    return not matched
                return matched
