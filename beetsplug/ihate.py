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

"""Warns you about things you hate (or even blocks import)."""

import re
import logging
from beets.plugins import BeetsPlugin
from beets import ui
from beets.importer import action


__author__ = 'baobab@heresiarch.info'
__version__ = '1.0'


class IHatePlugin(BeetsPlugin):

    _instance = None
    _log = logging.getLogger('beets')

    warn_genre = []
    warn_artist = []
    warn_album = []
    warn_whitelist = []
    skip_genre = []
    skip_artist = []
    skip_album = []
    skip_whitelist = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(IHatePlugin,
                                  cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __str__(self):
        return ('(\n  warn_genre = {0}\n'
                '  warn_artist = {1}\n'
                '  warn_album = {2}\n'
                '  warn_whitelist = {3}\n'
                '  skip_genre = {4}\n'
                '  skip_artist = {5}\n'
                '  skip_album = {6}\n'
                '  skip_whitelist = {7} )\n'
                .format(self.warn_genre, self.warn_artist, self.warn_album, 
                        self.warn_whitelist, self.skip_genre, self.skip_artist,
                        self.skip_album, self.skip_whitelist))

    def configure(self, config):
        if not config.has_section('ihate'):
            self._log.debug('[ihate] plugin is not configured')
            return
        self.warn_genre = ui.config_val(config, 'ihate', 'warn_genre', 
                                        '').split()
        self.warn_artist = ui.config_val(config, 'ihate', 'warn_artist', 
                                         '').split()
        self.warn_album = ui.config_val(config, 'ihate', 'warn_album', 
                                        '').split()
        self.warn_whitelist = ui.config_val(config, 'ihate', 'warn_whitelist', 
                                       '').split()
        self.skip_genre = ui.config_val(config, 'ihate', 'skip_genre', 
                                        '').split()
        self.skip_artist = ui.config_val(config, 'ihate', 'skip_artist', 
                                         '').split()
        self.skip_album = ui.config_val(config, 'ihate', 'skip_album', 
                                        '').split()
        self.skip_whitelist = ui.config_val(config, 'ihate', 'skip_whitelist', 
                                       '').split()

    @classmethod
    def match_patterns(cls, s, patterns):
        """Check if string is matching any of the patterns in the list."""
        for p in patterns:
            if re.findall(p, s, flags=re.IGNORECASE):
                return True
        return False

    @classmethod
    def do_i_hate_this(cls, task, genre_patterns, artist_patterns, 
                       album_patterns, whitelist_patterns):
        """Process group of patterns (warn or skip) and returns True if
        task is hated and not whitelisted.
        """
        hate = False
        try:
            genre = task.items[0].genre
        except:
            genre = u''
        if genre and genre_patterns:
            if IHatePlugin.match_patterns(genre, genre_patterns):
                hate = True
        if not hate and task.cur_album and album_patterns:
            if IHatePlugin.match_patterns(task.cur_album, album_patterns):
                hate = True
        if not hate and task.cur_artist and artist_patterns:
            if IHatePlugin.match_patterns(task.cur_artist, artist_patterns):
                hate = True
        if hate and whitelist_patterns:
            if IHatePlugin.match_patterns(task.cur_artist, whitelist_patterns):
                hate = False
        return hate

    def job_to_do(self):
        """Return True if at least one pattern is defined."""
        return any([self.warn_genre, self.warn_artist, self.warn_album, 
                    self.skip_genre, self.skip_artist, self.skip_album])

    def import_task_choice_event(self, task, config):
        if task.choice_flag == action.APPLY:
            if self.job_to_do:
                self._log.debug('[ihate] processing your hate')
                if self.do_i_hate_this(task, self.skip_genre, self.skip_artist,
                                       self.skip_album, self.skip_whitelist):
                    task.choice_flag = action.SKIP
                    self._log.info(u'[ihate] skipped: {0} - {1}'
                                   .format(task.cur_artist, task.cur_album))
                    return
                if self.do_i_hate_this(task, self.warn_genre, self.warn_artist,
                                       self.warn_album, self.warn_whitelist):
                    self._log.info(u'[ihate] you maybe hate this: {0} - {1}'
                                   .format(task.cur_artist, task.cur_album))
            else:
                self._log.debug('[ihate] nothing to do')
        else:
            self._log.debug('[ihate] user make a decision, nothing to do')


@IHatePlugin.listen('import_task_choice')
def ihate_import_task_choice(task, config):
    IHatePlugin().import_task_choice_event(task, config)
