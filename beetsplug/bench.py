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
import cProfile
import timeit

def benchmark(lib, prof):
    def _build_tree():
        vfs.libtree(lib)

    # Measure path generation performance with %aunique{} included.
    lib.path_formats = [
        (library.PF_KEY_DEFAULT,
         Template('$albumartist/$album%aunique{}/$track $title')),
    ]
    if prof:
        cProfile.runctx('_build_tree()', {}, {'_build_tree': _build_tree},
                        'paths.withaunique.prof')
    else:
        interval = timeit.timeit(_build_tree, number=1)
        print 'With %aunique:', interval

    # And with %aunique replaceed with a "cheap" no-op function.
    lib.path_formats = [
        (library.PF_KEY_DEFAULT,
         Template('$albumartist/$album%lower{}/$track $title')),
    ]
    if prof:
        cProfile.runctx('_build_tree()', {}, {'_build_tree': _build_tree},
                        'paths.withoutaunique.prof')
    else:
        interval = timeit.timeit(_build_tree, number=1)
        print 'Without %aunique:', interval

class BenchmarkPlugin(BeetsPlugin):
    """A plugin for performing some simple performance benchmarks.
    """
    def commands(self):
        def bench_func(lib, config, opts, args):
            benchmark(lib, opts.profile)
        bench_cmd = ui.Subcommand('bench', help='benchmark')
        bench_cmd.parser.add_option('-p', '--profile',
                                    action='store_true', default=False,
                                    help='performance profiling')
        bench_cmd.func = bench_func
        return [bench_cmd]
