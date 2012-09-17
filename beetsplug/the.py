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

from __future__ import print_function
import sys
import re
from beets.plugins import BeetsPlugin
from beets import ui


__author__ = 'baobab@heresiarch.info'
__version__ = '1.0'

PATTERN_THE = u'^[the]{3}\s'
PATTERN_A = u'^[a][n]?\s'
FORMAT = u'{0}, {1}'

the_options = {
    'debug': False,
    'the': True,
    'a': True,
    'format': FORMAT,
    'strip': False,
    'silent': False,
    'patterns': [PATTERN_THE, PATTERN_A],
}


class ThePlugin(BeetsPlugin):

    def configure(self, config):
        if not config.has_section('the'):
            print('[the] plugin is not configured, using defaults',
                  file=sys.stderr)
            return
        self.in_config = True
        the_options['debug'] = ui.config_val(config, 'the', 'debug', False,
                                             bool)
        the_options['the'] = ui.config_val(config, 'the', 'the', True, bool)
        the_options['a'] = ui.config_val(config, 'the', 'a', True, bool)
        the_options['format'] = ui.config_val(config, 'the', 'format',
                                              FORMAT)
        the_options['strip'] = ui.config_val(config, 'the', 'strip', False,
                                             bool)
        the_options['silent'] = ui.config_val(config, 'the', 'silent', False,
                                              bool)
        the_options['patterns'] = ui.config_val(config, 'the', 'patterns',
                                                '').split()
        for p in the_options['patterns']:
            if p:
                try:
                    re.compile(p)
                except re.error:
                    print(u'[the] invalid pattern: {}'.format(p),
                          file=sys.stderr)
                else:
                    if not (p.startswith('^') or p.endswith('$')):
                        if not the_options['silent']:
                            print(u'[the] warning: pattern \"{}\" will not '
                                  'match string start/end'.format(p),
                                  file=sys.stderr)
        if the_options['a']:
            the_options['patterns'] = [PATTERN_A] + the_options['patterns']
        if the_options['the']:
            the_options['patterns'] = [PATTERN_THE] + the_options['patterns']
        if not the_options['patterns'] and not the_options['silent']:
            print('[the] no patterns defined!')
        if the_options['debug']:
            print(u'[the] patterns: {}'
                  .format(' '.join(the_options['patterns'])), file=sys.stderr)


def unthe(text, pattern, strip=False):
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
            if strip:
                return r
            else:
                return the_options['format'].format(r, t.strip()).strip()
    else:
        return u''


@ThePlugin.template_func('the')
def func_the(text):
    """Provides beets template function %the"""
    if not the_options['patterns']:
        return text
    if text:
        for p in the_options['patterns']:
            r = unthe(text, p, the_options['strip'])
            if r != text:
                break
        if the_options['debug']:
            print(u'[the] \"{}\" -> \"{}\"'.format(text, r), file=sys.stderr)
        return r
    else:
        return u''


# simple tests
if __name__ == '__main__':
    print(unthe('The The', PATTERN_THE))
    print(unthe('An Apple', PATTERN_A))
    print(unthe('A Girl', PATTERN_A, strip=True))
