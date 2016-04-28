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

""" Clears tag fields in media files."""

from __future__ import division, absolute_import, print_function

import re
from beets.plugins import BeetsPlugin
from beets.mediafile import MediaFile
from beets.importer import action
import confuse

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
            'keep_fields': [],
            'update_database': False,
        })

        self.patterns = {}
        self.warned = False

        # We'll only handle `fields` or `keep_fields`, but not both.
        if self.config['fields'] and self.config['keep_fields']:
            self._log.warn(u'cannot blacklist and whitelist at the same time')

        # Blacklist mode.
        if self.config['fields']:
            self.validate_config('fields')
            for field in self.config['fields'].as_str_seq():
                self.set_pattern(field)

        # Whitelist mode.
        elif self.config['keep_fields']:
            self.validate_config('keep_fields')

            for field in MediaFile.fields():
                if field in self.config['keep_fields'].as_str_seq():
                    continue
                self.set_pattern(field)

            # These fields should always be preserved.
            for key in ('id', 'path', 'album_id'):
                if key in self.patterns:
                    del self.patterns[key]

    def validate_config(self, mode):
        """Check whether fields in the configuration are valid.

        `mode` should either be "fields" or "keep_fields", indicating
        the section of the configuration to validate.
        """
        for field in self.config[mode].as_str_seq():
            if field not in MediaFile.fields():
                self._log.error(u'invalid field: {0}', field)
                continue
            if mode == 'fields' and field in ('id', 'path', 'album_id'):
                self._log.warn(u'field \'{0}\' ignored, zeroing '
                               u'it would be dangerous', field)
                continue

    def set_pattern(self, field):
        """Set a field in `self.patterns` to a string list corresponding to
        the configuration, or `True` if the field has no specific
        configuration.
        """
        try:
            self.patterns[field] = self.config[field].as_str_seq()
        except confuse.NotFoundError:
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
                if self.config['update_database']:
                    item[field] = None
