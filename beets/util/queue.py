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

import logging
import asyncio
from asyncio import From, Return, Future

log = logging.getLogger('beets')


class Queue(object):
    """Run all coroutines but only a specified number concurrently.::

        queue = Queue(concurrency=2)
        for coro in expensive_coroutines:
            queue.push(coro)

        for task in queue:
            result = yield From(task)

    You can attach specific data to each task. The results are then
    tuples. The first value is the return value of the coroutine and the
    rest are the data. ::

          for coro in expensive_coroutines:
              queue.push(coro, True)
          for task in queue:
              result, ran = yield From(task)

    To use the iterator you have to run it in a asyncio coroutine. If
    you don't care about that, then there is a synchronous method. ::

          for result in queue.run_sync():
              print result

    This blocks the execution of the iterator until the next result is
    available and then yields it.
    """

    def __init__(self, concurrency=1):
        self.concurrency = concurrency
        self._tasks = []
        self._futures = []
        self._futures_index = 0

    def push(self, future_or_coro, *data):
        """Add a future or coroutine to the queue.

        The result of the future and ``data`` will be yielded from the
        futures in the iterator.
        """
        self._tasks.append((future_or_coro, data))
        self._futures.append(Future())

    def __iter__(self):
        self._start()
        return self._futures.__iter__()

    def _start(self):
        """Starts the first concurrent coroutines.
        """
        for i in range(self.concurrency):
            self._queue()

    def sync(self):
        """Yield the results of the tasks as soon as they are finished.

        This runs the coroutines in the default event loop.
        """
        self._loop = asyncio.get_event_loop()
        self._start()
        for future in self._futures:
            yield self._loop.run_until_complete(future)

    def _queue(self, *_):
        """Run the first coroutine the has not been started yet.

        Connects the the result to one of the futures returned by the
        iterator.
        """
        if len(self._tasks) == 0:
            return
        task, data = self._tasks.pop(0)
        task_completed = asyncio.async(task)
        task_completed.add_done_callback(self._queue)
        task_completed.add_done_callback(self._dequeue)

    def _dequeue(self, completed):
        """Resolves the next future exposed by the iterator with the
        results from the completed future.
        """
        future = self._futures[self._futures_index]
        try:
            res = completed.result()
        except Exception as e:
            future.set_exception(e)
        else:
            future.set_result(res)
        self._futures_index += 1


class CommandQueue(Queue):
    """Spawn programs and collect there result.

    Instead of pushing coroutines to the queue we can push command line
    arguments to it. ``queue.sync()`` then runs these commands and
    collects their results.

    >>> queue = CommandQueue(concurrency=3)
    >>> queue.push(['sleep', 0.3], 'first')
    >>> queue.push(['sleep', 0.2], 'second')
    >>> queue.push(['sleep', 0.1], 'third')
    >>> for stdout, stderr, returncode, data in queue.sync():
    ...     print(data)
    third
    second
    first
    """

    def push(self, args, *data):
        """Add a command to the queue.

        ``args`` is a list of command arguments. The first value is the
        name of the command to run and the remaining are passed to the
        command.
        """
        super(CommandQueue, self).push(self.make_command(args, data))

    @asyncio.coroutine
    def make_command(self, args, data):
        args = map(str, args)
        log.debug('running {}'.format(' '.join(args)))

        process = yield From(asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        ))
        stdout, stderr = yield From(process.communicate())
        yield From(process.wait())
        raise Return(stdout, stderr, process.returncode, *data)
