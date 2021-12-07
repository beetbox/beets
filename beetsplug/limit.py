# This file is part of beets.
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

from beets.dbcore import FieldQuery
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_
from collections import deque
from itertools import islice


def lslimit(lib, opts, args):
    """Query command with head/tail"""
    
    head = opts.head
    tail = opts.tail

    if head and tail:
        raise RuntimeError("Only use one of --head and --tail")
    
    query = decargs(args)
    if opts.album:
        objs = lib.albums(query)
    else:
        objs = lib.items(query)
    
    if head:
        objs = islice(objs, head)
    elif tail:
        objs = deque(objs, tail)

    for obj in objs:
        print_(format(obj))


lslimit_cmd = Subcommand(
    "lslimit", 
    help="query with optional head or tail"
)

lslimit_cmd.parser.add_option(
    '--head', 
    action='store', 
    type="int",
    default=None
)

lslimit_cmd.parser.add_option(
    '--tail',
    action='store', 
    type="int",
    default=None
)

lslimit_cmd.parser.add_all_common_options()
lslimit_cmd.func = lslimit


class LsLimitPlugin(BeetsPlugin):
    def commands(self):
        return [lslimit_cmd]


class HeadPlugin(BeetsPlugin):
    """Head of an arbitrary query.
    
    This allows a user to limit the results of any query to the first
    `pattern` rows. Example usage: return first 10 tracks `beet ls '<10'`.
    """
    
    def queries(self):

        class HeadQuery(FieldQuery):
            """Singleton query implementation that tracks result count."""
            n = 0
            include = True
            @classmethod
            def value_match(cls, pattern, value):
                cls.n += 1
                if cls.include:
                    cls.include = cls.n <= int(pattern)
                return cls.include
        
        return {
            "<": HeadQuery
        }