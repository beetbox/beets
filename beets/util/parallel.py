from concurrent.futures import Executor, Future
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator
_executor = None

def executor() -> Executor:
    """Get the shared Executor.
    
    Note that this is a singleton, and the Executor is lazily created. It 
    should be shared across the Beets application and plugins to avoid creating
    unnecessary threads and their associated overhead.

    All beets library operations can safely be executed in this Executor, as
    there are safeguards in place to ensure that the connection to the physical
    database is thread-safe.

    The Executor is created with a thread name prefix of "beets" to help with
    debugging.
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(thread_name_prefix="beets")
    return _executor

def submit(fn, *args, **kwargs) -> Future:
    """Submit a function to the shared Executor."""
    return executor().submit(fn, *args, **kwargs)

def map(fn, *iterables, timeout=None, chunksize=1) -> Iterator[Future]:
    """Map a function over a number of iterables in the shared Executor."""
    return executor().map(fn, *iterables, timeout=timeout, chunksize=chunksize)