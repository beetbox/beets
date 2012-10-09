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

"""Moves patterns in path formats (suitable for moving articles)."""

import re
import logging
from beets.plugins import BeetsPlugin
from beets import ui


__author__ = 'baobab@heresiarch.info'
__version__ = '1.1'

PATTERN_THE = u'^[the]{3}\s'
PATTERN_A = u'^[a][n]?\s'
FORMAT = u'{0}, {1}'

class ThePlugin(BeetsPlugin):

    _instance = None
    _log = logging.getLogger('beets')

    the = True
    a = True
    format = u''
    strip = False
    patterns = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ThePlugin,
                                  cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __str__(self):
        return ('[the]\n  the = {0}\n  a = {1}\n  format = {2}\n'
                '  strip = {3}\n  patterns = {4}'
                .format(self.the, self.a, self.format, self.strip,
                        self.patterns))

    def configure(self, config):
        if not config.has_section('the'):
            self._log.debug(u'[the] plugin is not configured, using defaults')
            return
        self.the = ui.config_val(config, 'the', 'the', True, bool)
        self.a = ui.config_val(config, 'the', 'a', True, bool)
        self.format = ui.config_val(config, 'the', 'format', FORMAT)
        self.strip = ui.config_val(config, 'the', 'strip', False, bool)
        self.patterns = ui.config_val(config, 'the', 'patterns', '').split()
        for p in self.patterns:
            if p:
                try:
                    re.compile(p)
                except re.error:
                    self._log.error(u'[the] invalid pattern: {0}'.format(p))
                else:
                    if not (p.startswith('^') or p.endswith('$')):
                        self._log.warn(u'[the] warning: \"{0}\" will not '
                                       'match string start/end'.format(p))
        if self.a:
            self.patterns = [PATTERN_A] + self.patterns
        if self.the:
            self.patterns = [PATTERN_THE] + self.patterns
        if not self.patterns:
            self._log.warn(u'[the] no patterns defined!')


    def unthe(self, text, pattern):
        """Moves pattern in the path format string or strips it

        text -- text to handle
        pattern -- regexp pattern (case ignore is already on)
        strip -- if True, pattern will be removed

        """
        if text:
            r = re.compile(pattern, flags=re.IGNORECASE)
            try:
                t = r.findall(text)[0]
            except IndexError:
                return text
            else:
                r = re.sub(r, '', text).strip()
                if self.strip:
                    return r
                else:
                    return self.format.format(r, t.strip()).strip()
        else:
            return u''

    def the_template_func(self, text):
        if not self.patterns:
            return text
        if text:
            for p in self.patterns:
                r = self.unthe(text, p)
                if r != text:
                    break
            self._log.debug(u'[the] \"{0}\" -> \"{1}\"'.format(text, r))
            return r
        else:
            return u''

@ThePlugin.template_func('the')
def func_the(text):
    """Provides beets template function %the"""
    return ThePlugin().the_template_func(text)
