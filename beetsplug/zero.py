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

""" Clears tag fields in media files.""" 

from __future__ import print_function
import sys
import re
from beets.plugins import BeetsPlugin
from beets import ui
from beets.library import ITEM_KEYS
from beets.importer import action


__author__ = 'baobab@heresiarch.info'
__version__ = '0.9'


class ZeroPlugin(BeetsPlugin):

    _instance = None

    debug = False
    fields = []
    patterns = {}
    warned = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ZeroPlugin,
                                  cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __str__(self):
        return ('[zero]\n  debug = {}\n  fields = {}\n  patterns = {}\n'
                '  warned = {}'.format(self.debug, self.fields, self.patterns, 
                                     self.warned))

    def dbg(self, *args):
        """Prints message to stderr."""
        if self.debug:
            print('[zero]', *args, file=sys.stderr)

    def configure(self, config):
        if not config.has_section('zero'):
            self.dbg('plugin is not configured')
            return
        self.debug = ui.config_val(config, 'zero', 'debug', True, bool)
        for f in ui.config_val(config, 'zero', 'fields', '').split():
            if f not in ITEM_KEYS:
                self.dbg('invalid field \"{}\" (try \'beet fields\')')
            else:
                self.fields.append(f)
                p = ui.config_val(config, 'zero', f, '').split()
                if p:
                    self.patterns[f] = p
                else:
                    self.patterns[f] = ['.']
        if self.debug:
            print(self, file=sys.stderr)

    def import_task_choice_event(self, task, config):
        """Listen for import_task_choice event."""
        if self.debug:
            self.dbg('listen: import_task_choice')
        if task.choice_flag == action.ASIS and not self.warned:
            self.dbg('cannot zero in \"as-is\" mode')
            self.warned = True
        # TODO request write in as-is mode 

    @classmethod
    def match_patterns(cls, field, patterns):
        """Check if field (as string) is matching any of the patterns in 
        the list.
        """
        for p in patterns:
            if re.findall(p, unicode(field), flags=re.IGNORECASE):
                return True
        return False

    def write_event(self, item):
        """Listen for write event."""
        if self.debug:
            self.dbg('listen: write')
        if not self.fields:
            self.dbg('no fields, nothing to do')
            return
        for fn in self.fields:
            try:
                fval = getattr(item, fn)
            except AttributeError:
                self.dbg('? no such field: {}'.format(fn))
            else:
                if not self.match_patterns(fval, self.patterns[fn]):
                    self.dbg('\"{}\" ({}) is not match any of: {}'
                             .format(fval, fn, ' '.join(self.patterns[fn])))
                    continue
                self.dbg('\"{}\" ({}) match: {}'
                         .format(fval, fn, ' '.join(self.patterns[fn])))
                setattr(item, fn, type(fval)())
                self.dbg('{}={}'.format(fn, getattr(item, fn)))


@ZeroPlugin.listen('import_task_choice')
def zero_choice(task, config):
    ZeroPlugin().import_task_choice_event(task, config)

@ZeroPlugin.listen('write')
def zero_write(item):
    ZeroPlugin().write_event(item)


# simple test
if __name__ == '__main__':
    print(ZeroPlugin().match_patterns('test', ['[0-9]']))
    print(ZeroPlugin().match_patterns('test', ['.']))
