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

    def __init__(self):
        super(IHatePlugin, self).__init__()
        self.register_listener('import_task_choice',
                               self.import_task_choice_event)
        self.config.add({
            'warn_genre': [],
            'warn_artist': [],
            'warn_album': [],
            'warn_whitelist': [],
            'skip_genre': [],
            'skip_artist': [],
            'skip_album': [],
            'skip_whitelist': [],
        })


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
            if cls.match_patterns(genre, genre_patterns):
                hate = True
        if not hate and getattr(task, 'cur_album', None) and album_patterns:
            if cls.match_patterns(task.cur_album, album_patterns):
                hate = True
        if not hate and getattr(task, 'cur_artist', None) and artist_patterns:
            if cls.match_patterns(task.cur_artist, artist_patterns):
                hate = True
        if hate and whitelist_patterns:
            if cls.match_patterns(task.cur_artist, whitelist_patterns):
                hate = False
        return hate

    def job_to_do(self):
        """Return True if at least one pattern is defined."""
        return any(self.config[l].as_str_seq() for l in
                   ('warn_genre', 'warn_artist', 'warn_album',
                    'skip_genre', 'skip_artist', 'skip_album'))

    def import_task_choice_event(self, session, task):
        if task.choice_flag == action.APPLY:
            if self.job_to_do():
                self._log.debug('[ihate] processing your hate')
                if self.do_i_hate_this(task,
                            self.config['skip_genre'].as_str_seq(),
                            self.config['skip_artist'].as_str_seq(),
                            self.config['skip_album'].as_str_seq(),
                            self.config['skip_whitelist'].as_str_seq()):
                    task.choice_flag = action.SKIP
                    self._log.info(u'[ihate] skipped: {0} - {1}'
                                   .format(task.cur_artist, task.cur_album))
                    return
                if self.do_i_hate_this(task,
                            self.config['warn_genre'].as_str_seq(),
                            self.config['warn_artist'].as_str_seq(),
                            self.config['warn_album'].as_str_seq(),
                            self.config['warn_whitelist'].as_str_seq()):
                    self._log.info(u'[ihate] you maybe hate this: {0} - {1}'
                                   .format(task.cur_artist, task.cur_album))
            else:
                self._log.debug('[ihate] nothing to do')
        else:
            self._log.debug('[ihate] user made a decision, nothing to do')
