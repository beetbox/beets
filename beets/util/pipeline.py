# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""Simple but robust implementation of generator/coroutine-based
pipelines in Python. The pipelines may be run either sequentially
(single-threaded) or in parallel (one thread per pipeline stage).

This implementation supports pipeline bubbles (indications that the
processing for a certain item should abort). To use them, yield the
BUBBLE constant from any stage coroutine except the last.

In the parallel case, the implementation transparently handles thread
shutdown when the processing is complete and when a stage raises an
exception. KeyboardInterrupts (^C) are also handled.

When running a parallel pipeline, it is also possible to use
multiple coroutines for the same pipeline stage; this lets you speed
up a bottleneck stage by dividing its work among multiple threads.
To do so, pass an iterable of coroutines to the Pipeline constructor
in place of any single coroutine.
"""
from __future__ import with_statement # for Python 2.5
import Queue
from threading import Thread, Lock
import sys
import types

BUBBLE = '__PIPELINE_BUBBLE__'
POISON = '__PIPELINE_POISON__'

DEFAULT_QUEUE_SIZE = 16

def invalidate_queue(q):
    """Breaks a Queue such that it never blocks, always has size 1,
    and has no maximum size.
    """
    def _qsize(len=len):
        return 1
    def _put(item):
        pass
    def _get():
        return None
    with q.mutex:
        q.maxsize = 0
        q._qsize = _qsize
        q._put = _put
        q._get = _get
        q.not_empty.notify()
        q.not_full.notify()

class PipelineError(object):
    """An indication that an exception occurred in the pipeline. The
    object is passed through the pipeline to shut down all threads
    before it is raised again in the main thread.
    """
    def __init__(self, exc_info):
        self.exc_info = exc_info

class PipelineThread(Thread):
    """Abstract base class for pipeline-stage threads."""
    def __init__(self, all_threads):
        super(PipelineThread, self).__init__()
        self.abort_lock = Lock()
        self.abort_flag = False
        self.all_threads = all_threads
        self.exc_info = None

    def abort(self):
        """Shut down the thread at the next chance possible.
        """
        with self.abort_lock:
            self.abort_flag = True

        # Ensure that we are not blocking on a queue read or write.
        if hasattr(self, 'in_queue'):
            invalidate_queue(self.in_queue)
        if hasattr(self, 'out_queue'):
            invalidate_queue(self.out_queue)

    def abort_all(self, exc_info):
        """Abort all other threads in the system for an exception.
        """
        self.exc_info = exc_info
        for thread in self.all_threads:
            thread.abort()

class FirstPipelineThread(PipelineThread):
    """The thread running the first stage in a parallel pipeline setup.
    The coroutine should just be a generator.
    """
    def __init__(self, coro, out_queue, all_threads):
        super(FirstPipelineThread, self).__init__(all_threads)
        self.coro = coro
        self.out_queue = out_queue
        
        self.abort_lock = Lock()
        self.abort_flag = False
    
    def run(self):
        try:
            while True:
                # Time to abort?
                with self.abort_lock:
                    if self.abort_flag:
                        return
                
                # Get the value from the generator.
                try:
                    msg = self.coro.next()
                except StopIteration:
                    break
                
                # Send it to the next stage.
                if msg is BUBBLE:
                    continue
                self.out_queue.put(msg)

        except:
            self.abort_all(sys.exc_info())
            return

        # Generator finished; shut down the pipeline.
        self.out_queue.put(POISON)
    
class MiddlePipelineThread(PipelineThread):
    """A thread running any stage in the pipeline except the first or
    last.
    """
    def __init__(self, coro, in_queue, out_queue, all_threads):
        super(MiddlePipelineThread, self).__init__(all_threads)
        self.coro = coro
        self.in_queue = in_queue
        self.out_queue = out_queue

    def run(self):
        try:
            # Prime the coroutine.
            self.coro.next()
            
            while True:
                with self.abort_lock:
                    if self.abort_flag:
                        return

                # Get the message from the previous stage.
                msg = self.in_queue.get()
                if msg is POISON:
                    break
                
                # Invoke the current stage.
                out = self.coro.send(msg)
                
                # Send message to next stage.
                if out is BUBBLE:
                    continue
                self.out_queue.put(out)

        except:
            self.abort_all(sys.exc_info())
            return
        
        # Pipeline is shutting down normally.
        self.in_queue.put(POISON)
        self.out_queue.put(POISON)

class LastPipelineThread(PipelineThread):
    """A thread running the last stage in a pipeline. The coroutine
    should yield nothing.
    """
    def __init__(self, coro, in_queue, all_threads):
        super(LastPipelineThread, self).__init__(all_threads)
        self.coro = coro
        self.in_queue = in_queue

    def run(self):
        # Prime the coroutine.
        self.coro.next()

        try:
            while True:
                with self.abort_lock:
                    if self.abort_flag:
                        return
                    
                # Get the message from the previous stage.
                msg = self.in_queue.get()
                if msg is POISON:
                    break
                
                # Send to consumer.
                self.coro.send(msg)

        except:
            self.abort_all(sys.exc_info())
            return
        
        # Pipeline is shutting down normally.
        self.in_queue.put(POISON)

class Pipeline(object):
    """Represents a staged pattern of work. Each stage in the pipeline
    is a coroutine that receives messages from the previous stage and
    yields messages to be sent to the next stage.
    """
    def __init__(self, stages):
        """Makes a new pipeline from a list of coroutines. There must
        be at least two stages.
        """
        if len(stages) < 2:
            raise ValueError('pipeline must have at least two stages')
        self.stages = []
        for stage in stages:
            if isinstance(stage, types.GeneratorType):
                # Default to one thread per stage.
                self.stages.append((stage,))
            else:
                self.stages.append(stage)
        
    def run_sequential(self):
        """Run the pipeline sequentially in the current thread. The
        stages are run one after the other. Only the first coroutine
        in each stage is used.
        """
        coros = [stage[0] for stage in self.stages]

        # "Prime" the coroutines.
        for coro in coros:
            coro.next()
        
        # Begin the pipeline.
        for msg in coros[0]:
            for coro in coros[1:]:
                msg = coro.send(msg)
                if msg is BUBBLE:
                    # Don't continue to the next stage.
                    break
    
    def run_parallel(self, queue_size=DEFAULT_QUEUE_SIZE):
        """Run the pipeline in parallel using one thread per stage. The
        messages between the stages are stored in queues of the given
        size.
        """
        queues = [Queue.Queue(queue_size) for i in range(len(self.stages)-1)]
        threads = []

        # Set up first stage.
        for coro in self.stages[0]:
            threads.append(FirstPipelineThread(coro, queues[0], threads))


        # Middle stages.
        for i in range(1, len(self.stages)-1):
            for coro in self.stages[i]:
                threads.append(MiddlePipelineThread(
                    coro, queues[i-1], queues[i], threads
                ))

        # Last stage.
        for coro in self.stages[-1]:
            threads.append(
                LastPipelineThread(coro, queues[-1], threads)
            )
        
        # Start threads.
        for thread in threads:
            thread.start()
        
        # Wait for termination. The final thread lasts the longest.
        try:
            # Using a timeout allows us to receive KeyboardInterrupt
            # exceptions during the join().
            while threads[-1].isAlive():
                threads[-1].join(1)

        except:
            # Stop all the threads immediately.
            for thread in threads:
                thread.abort()
            raise
        
        finally:
            # Make completely sure that all the threads have finished
            # before we return. They should already be either finished,
            # in normal operation, or aborted, in case of an exception.
            for thread in threads[:-1]:
                thread.join()

        for thread in threads:
            exc_info = thread.exc_info
            if exc_info:
                # Make the exception appear as it was raised originally.
                raise exc_info[0], exc_info[1], exc_info[2]

# Smoke test.
if __name__ == '__main__':
    import time
    
    # Test a normally-terminating pipeline both in sequence and
    # in parallel.
    def produce():
        for i in range(5):
            print 'generating %i' % i
            time.sleep(1)
            yield i
    def work():
        num = yield
        while True:
            print 'processing %i' % num
            time.sleep(2)
            num = yield num*2
    def consume():
        while True:
            num = yield
            time.sleep(1)
            print 'received %i' % num
    ts_start = time.time()
    Pipeline([produce(), work(), consume()]).run_sequential()
    ts_seq = time.time()
    Pipeline([produce(), work(), consume()]).run_parallel()
    ts_par = time.time()
    Pipeline([produce(), (work(), work()), consume()]).run_parallel()
    ts_end = time.time()
    print 'Sequential time:', ts_seq - ts_start
    print 'Parallel time:', ts_par - ts_seq
    print 'Multiply-parallel time:', ts_end - ts_par
    print

    # Test a pipeline that raises an exception.
    def exc_produce():
        for i in range(10):
            print 'generating %i' % i
            time.sleep(1)
            yield i
    def exc_work():
        num = yield
        while True:
            print 'processing %i' % num
            time.sleep(3)
            if num == 3:
               raise Exception()
            num = yield num * 2
    def exc_consume():
        while True:
            num = yield
            #if num == 4:
            #   raise Exception()
            print 'received %i' % num
    Pipeline([exc_produce(), exc_work(), exc_consume()]).run_parallel(1)
