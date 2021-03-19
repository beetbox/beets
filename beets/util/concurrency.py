# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2021, @wisp3rwind
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

"""Provides a global thread pool that can be shared among beets' core and
plugins. Every piece of work that is CPU-intensive (e.g. calling a subprocess
which performs the actual work) should block a thread on the pool.
"""

from __future__ import division, absolute_import, print_function

from concurrent.futures import ThreadPoolExecutor
import signal
from beets import logging
from beets.util import cpu_count

__all__ = ["pool"]

# Global logger.
log = logging.getLogger('beets')

pool = None


def _sigint_handler(signal, frame):
    global pool

    if pool is not None:
        pool.close(wait=True, abort=True)


signal.signal(signal.SIGINT, _sigint_handler)


class _Pool():
    def __init__(self):
        self._pool = None

    def _open(self):
        """Open the global thread pool instance lazily."""
        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=cpu_count() + 2,
                # thread_name_prefix="worker"  # not available in Python < 3.6
            )

    # FIXME: Cleanly shutdown when beets is shutting down
    # FIXME: abort on uncaught exceptions
    def close(self, wait=False, abort=False):
        """Shutdown the thread pool.

        If `abort` is `True`, all tasks that have not been started will be
        cancelled. Tasks that are already running will not be interrupted.
        """
        if self._pool is not None:
            self._pool.shutdown(wait=wait, cancel_futures=abort)
            self._pool = None

    def submit(self, transform, item):
        self._open()

        return self._pool.submit(transform, item)

    def map_iter_nowait(self, transform, items):
        """Map `transform` over `items`, yielding `Future`s.

        Apply the function `transform` to all the elements in the
        iterable `items`, like `map(transform, items)`, but in parallel.

        The parallelism uses threads (not processes), so this is only useful
        for IO-bound `transform`s.

        This yields the submitted `Future`s directly.
        """
        self._open()

        for i in items:
            yield self.submit(transform, i)

    def map_iter(self, transform, items, cancel_on_error=True):
        """Map `transform` over `items`, yielding the results.

        Apply the function `transform` to all the elements in the
        iterable `items`, like `map(transform, items)`, but in parallel.

        The parallelism uses threads (not processes), so this is only useful
        for IO-bound `transform`s.

        This yields the result of each transform as it completes.
        """
        self._open()

        # FIXME: When dropping Python 2, convert to `yield from`
        for fut in self._pool.map(transform, items):
            yield fut

    def map(self, transform, items, wait=True):
        """Map `transform` over `items`, discarding the results.

        Wrapper around `map_iter` which exhausts the iterator such that
        exceptions from threads are propagated, but discards the results.
        """
        for result in self.map_iter(transform, items, wait):
            pass


pool = _Pool()
