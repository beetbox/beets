# This file is part of beets.
# Copyright 2012, Adrian Sampson.
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

from beets.plugins import BeetsPlugin
from beets import ui
from beets import vfs
from beets import library
from beets.util.functemplate import Template
import time

def benchmark(lib):
    # Measure path generation performance with %aunique{} included.
    lib.path_formats = [
        (library.PF_KEY_DEFAULT,
         Template('$albumartist/$album%aunique{}/$track $title')),
    ]
    start_time = time.time()
    vfs.libtree(lib)
    end_time = time.time()
    print 'With %aunique:', end_time - start_time

    # And with %aunique replaceed with a "cheap" no-op function.
    lib.path_formats = [
        (library.PF_KEY_DEFAULT,
         Template('$albumartist/$album%lower{}/$track $title')),
    ]
    start_time = time.time()
    vfs.libtree(lib)
    end_time = time.time()
    print 'Without %aunique:', end_time - start_time

class BenchmarkPlugin(BeetsPlugin):
    """A plugin for performing some simple performance benchmarks.
    """
    def commands(self):
        def bench_func(lib, config, opts, args):
            benchmark(lib)
        cmd = ui.Subcommand('bench', help='benchmark')
        cmd.func = bench_func
        return [cmd]
