# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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

import asyncio
import logging

from _common import unittest

from beets.util import CommandQueue

log = logging.getLogger('asyncio')
log.setLevel(logging.WARNING)


class CommandQueueTest(unittest.TestCase):

    def test_run_sequential(self):
        queue = CommandQueue(concurrency=1)
        for i in range(4):
            queue.push(['printf', i])
        results = [out for out, _, _ in queue.sync()]
        self.assertEqual(results, map(str, [0, 1, 2, 3]))

    def test_run_all_parallel(self):
        queue = CommandQueue(concurrency=4)
        for i in range(4):
            queue.push(['sleep', (4 - i) * 0.04], i)
        results = [i for out, _, _, i in queue.sync()]
        self.assertEqual(results, [3, 2, 1, 0])

    def test_run_in_pairs(self):
        queue = CommandQueue(concurrency=2)
        for i in range(4):
            queue.push(['sleep', (4 - i) * 0.04], i)
        results = [i for out, _, _, i in queue.sync()]
        self.assertEqual(results, [1, 0, 3, 2])
