"""Extremely simple pure-Python implementation of coroutine-style
asynchronous socket I/O. Inspired by, but inferior to, Eventlet.
Bluelet can also be thought of as a less-terrible replacement for
asyncore.

Bluelet: easy concurrency without all the messy parallelism.
"""
import socket
import select
import sys
import types


# Basic events used for thread scheduling.

class Event(object):
    pass
class WaitableEvent(Event):
    def waitables(self):
        """Return "waitable" objects to pass to select. Should return
        three iterables for input readiness, output readiness, and
        exceptional conditions (i.e., the three lists passed to
        select()).
        """
        return (), (), ()
    def fire(self):
        pass

class ValueEvent(Event):
    """An event that does nothing but return a fixed value."""
    def __init__(self, value):
        self.value = value

class ExceptionEvent(Event):
    """Raise an exception at the yield point. Used internally."""
    def __init__(self, exc_info):
        self.exc_info = exc_info

class SpawnEvent(object):
    def __init__(self, coro):
        self.spawned = coro

class DelegationEvent(object):
    def __init__(self, coro):
        self.spawned = coro

class ReturnEvent(object):
    def __init__(self, value):
        self.value = value


# Core logic for executing and scheduling threads.

def _event_select(events):
    """Perform a select() over all the Events provided, returning the
    ones ready to be fired.
    """
    # Gather waitables.
    waitable_to_event = {}
    rlist, wlist, xlist = [], [], []
    for event in events:
        if isinstance(event, WaitableEvent):
            r, w, x = event.waitables()
            rlist += r
            wlist += w
            xlist += x
            for waitable in r + w + x:
                waitable_to_event[waitable] = event

    # Perform select() if we have any waitables.
    if rlist or wlist or xlist:
        rready, wready, xready = select.select(rlist, wlist, xlist)
        ready = rready + wready + xready
    else:
        ready = []

    # Gather ready events corresponding to the ready waitables.
    ready_events = set()
    for waitable in ready:
        ready_events.add(waitable_to_event[waitable])
    return ready_events

class ThreadException(Exception):
    def __init__(self, coro, exc_info):
        self.coro = coro
        self.exc_info = exc_info
    def reraise(self):
        raise self.exc_info[0], self.exc_info[1], self.exc_info[2]
        
def run(root_coro):
    # The "threads" dictionary keeps track of all the currently-
    # executing coroutines. It maps coroutines to their currenly
    # "blocking" event.
    threads = {root_coro: ValueEvent(None)}

    # When one thread delegates to another thread, its execution is
    # suspended until the delegate completes. This dictionary keeps
    # track of each running delegate's delegator.
    delegators = {}
    
    def advance_thread(coro, value, is_exc=False):
        """After an event is fired, run a given coroutine associated with
        it in the threads dict until it yields again. If the coroutine
        exits, then the thread is removed from the pool. If the coroutine
        raises an exception, it is reraised in a ThreadException. If
        is_exc is True, then the value must be an exc_info tuple and the
        exception is thrown into the coroutine.
        """
        try:
            if is_exc:
                next_event = coro.throw(*value)
            else:
                next_event = coro.send(value)
        except StopIteration:
            # Thread is done.
            del threads[coro]
            if coro in delegators:
                # Resume delegator.
                threads[delegators[coro]] = ValueEvent(None)
        except:
            # Thread raised some other exception.
            del threads[coro]
            raise ThreadException(coro, sys.exc_info())
        else:
            threads[coro] = next_event

    # Continue advancing threads until root thread exits.
    exit_te = None
    while threads:
        try:
            # Look for events that can be run immediately. Continue
            # running immediate events until nothing is ready.
            while True:
                have_ready = False
                for coro, event in threads.items():
                    if isinstance(event, SpawnEvent):
                        threads[event.spawned] = ValueEvent(None) # Spawn.
                        advance_thread(coro, None)
                        have_ready = True
                    elif isinstance(event, ValueEvent):
                        advance_thread(coro, event.value)
                        have_ready = True
                    elif isinstance(event, ExceptionEvent):
                        advance_thread(coro, event.exc_info, True)
                        have_ready = True
                    elif isinstance(event, DelegationEvent):
                        del threads[coro] # Suspend.
                        threads[event.spawned] = ValueEvent(None) # Spawn.
                        delegators[event.spawned] = coro
                        have_ready = True
                    elif isinstance(event, ReturnEvent):
                        # Thread is done.
                        del threads[coro]
                        if coro in delegators:
                            threads[delegators[coro]] = ValueEvent(event.value)
                        have_ready = True

                # Only start the select when nothing else is ready.
                if not have_ready:
                    break
            
            # Wait and fire.
            event2coro = dict((v,k) for k,v in threads.iteritems())
            for event in _event_select(threads.values()):
                value = event.fire()
                advance_thread(event2coro[event], value)
    
        except ThreadException, te:
            # Exception raised from inside a thread.
            event = ExceptionEvent(te.exc_info)
            if te.coro in delegators:
                # The thread is a delegate. Raise exception in its
                # delegator.
                threads[delegators[te.coro]] = event
            else:
                # The thread is root-level. Raise in client code.
                exit_te = te
                break
        
        except:
            # For instance, KeyboardInterrupt during select(). Raise
            # into root thread and terminate others.
            threads = {root_coro: ExceptionEvent(sys.exc_info())}

    # If any threads still remain, kill them.
    for coro in threads:
        coro.close()

    # If we're exiting with an exception, raise it in the client.
    if exit_te:
        exit_te.reraise()


# Sockets and their associated events.

class AcceptEvent(WaitableEvent):
    def __init__(self, listener):
        self.listener = listener
    def waitables(self):
        return (self.listener.sock,), (), ()
    def fire(self):
        sock, addr = self.listener.sock.accept()
        return Connection(sock, addr)
class Listener(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(5)
    def accept(self):
        return AcceptEvent(self)
    def close(self):
        self.sock.close()

class ReceiveEvent(WaitableEvent):
    def __init__(self, conn, bufsize):
        self.conn = conn
        self.bufsize = bufsize
    def waitables(self):
        return (self.conn.sock,), (), ()
    def fire(self):
        return self.conn.sock.recv(self.bufsize)
class SendEvent(WaitableEvent):
    def __init__(self, conn, data, sendall=False):
        self.conn = conn
        self.data = data
        self.sendall = sendall
    def waitables(self):
        return (), (self.conn.sock,), ()
    def fire(self):
        if self.sendall:
            return self.conn.sock.sendall(self.data)
        else:
            return self.conn.sock.send(self.data)
class Connection(object):
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self._buf = ''
    def close(self):
        self.sock.close()
    def recv(self, size):
        if self._buf:
            # We already have data read previously.
            out = self._buf[:size]
            self._buf = self._buf[size:]
            return ValueEvent(out)
        else:
            return ReceiveEvent(self, size)
    def send(self, data):
        return SendEvent(self, data)
    def sendall(self, data):
        return SendEvent(self, data, True)
    def readline(self, terminator="\n", bufsize=1024):
        def line_reader():
            while True:
                if terminator in self._buf:
                    line, self._buf = self._buf.split(terminator, 1)
                    line += terminator
                    yield ReturnEvent(line)
                    break
                data = yield self.recv(bufsize)
                if data:
                    self._buf += data
                else:
                    line = self._buf
                    self._buf = ''
                    yield ReturnEvent(line)
                    break
        return DelegationEvent(line_reader())


# Public interface for threads; each returns an event object that
# can immediately be "yield"ed.

def null():
    return ValueEvent(None)

def spawn(coro):
    if not isinstance(coro, types.GeneratorType):
        raise ValueError('%s is not a coroutine' % str(coro))
    return SpawnEvent(coro)

def call(coro):
    if not isinstance(coro, types.GeneratorType):
        raise ValueError('%s is not a coroutine' % str(coro))
    return DelegationEvent(coro)

def end(value = None):
    return ReturnEvent(value)


# Convenience function for running socket servers.

def server(host, port, func):
    def handler(conn):
        try:
            yield call(func(conn))
        finally:
            conn.close()
            
    listener = Listener(host, port)
    try:
        while True:
            conn = yield listener.accept()
            yield spawn(handler(conn))
    except KeyboardInterrupt:
        pass
    finally:
        listener.close()
