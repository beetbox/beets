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
import errno
import traceback


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
    """Add a new coroutine thread to the scheduler."""
    def __init__(self, coro):
        self.spawned = coro

class DelegationEvent(object):
    """Suspend execution of the current thread, start a new thread and,
    once the child thread finished, return control to the parent
    thread.
    """
    def __init__(self, coro):
        self.spawned = coro

class ReturnEvent(object):
    """Return a value the current thread's delegator at the point of
    delegation. Ends the current (delegate) thread.
    """
    def __init__(self, value):
        self.value = value

class ReadEvent(WaitableEvent):
    """Reads from a file-like object."""
    def __init__(self, fd, bufsize):
        self.fd = fd
        self.bufsize = bufsize
    def waitables(self):
        return (self.fd,), (), ()
    def fire(self):
        return self.fd.read(self.bufsize)

class WriteEvent(WaitableEvent):
    """Writes to a file-like object."""
    def __init__(self, fd, data):
        self.fd = fd
        self.data = data
    def waitable(self):
        return (), (self.fd,), ()
    def fire(self):
        self.fd.write(self.data)


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
            for waitable in r:
                waitable_to_event[('r', waitable)] = event
            for waitable in w:
                waitable_to_event[('w', waitable)] = event
            for waitable in x:
                waitable_to_event[('x', waitable)] = event

    # Perform select() if we have any waitables.
    if rlist or wlist or xlist:
        rready, wready, xready = select.select(rlist, wlist, xlist)
    else:
        rready, wready, xready = (), (), ()

    # Gather ready events corresponding to the ready waitables.
    ready_events = set()
    for ready in rready:
        ready_events.add(waitable_to_event[('r', ready)])
    for ready in wready:
        ready_events.add(waitable_to_event[('w', ready)])
    for ready in xready:
        ready_events.add(waitable_to_event[('x', ready)])
    return ready_events

class ThreadException(Exception):
    def __init__(self, coro, exc_info):
        self.coro = coro
        self.exc_info = exc_info
    def reraise(self):
        raise self.exc_info[0], self.exc_info[1], self.exc_info[2]
        
def run(root_coro):
    """Schedules a coroutine, running it to completion. This
    encapsulates the Bluelet scheduler, which the root coroutine can
    add to by spawning new coroutines.
    """
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
                del delegators[coro]
        except:
            # Thread raised some other exception.
            del threads[coro]
            raise ThreadException(coro, sys.exc_info())
        else:
            if isinstance(next_event, types.GeneratorType):
                # Automatically invoke sub-coroutines.
                next_event = DelegationEvent(next_event)
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
                            del delegators[coro]
                        have_ready = True

                # Only start the select when nothing else is ready.
                if not have_ready:
                    break

            # Wait and fire.
            event2coro = dict((v,k) for k,v in threads.iteritems())
            for event in _event_select(threads.values()):
                # Run the IO operation, but catch socket errors.
                try:
                    value = event.fire()
                except socket.error, exc:
                    if isinstance(exc.args, tuple) and \
                            exc.args[0] == errno.EPIPE:
                        # Broken pipe. Remote host disconnected.
                        pass
                    else:
                        traceback.print_exc()
                    # Abort the coroutine.
                    threads[event2coro[event]] = ReturnEvent(None)
                else:
                    advance_thread(event2coro[event], value)
    
        except ThreadException, te:
            # Exception raised from inside a thread.
            event = ExceptionEvent(te.exc_info)
            if te.coro in delegators:
                # The thread is a delegate. Raise exception in its
                # delegator.
                threads[delegators[te.coro]] = event
                del delegators[te.coro]
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
    """A socket-esque object for communicating asychronously on
    network sockets.
    """
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self._buf = ''
    def close(self):
        """Close the connection."""
        self.sock.close()
    def recv(self, size):
        """Read at most size bytes of data from the socket."""
        if self._buf:
            # We already have data read previously.
            out = self._buf[:size]
            self._buf = self._buf[size:]
            return ValueEvent(out)
        else:
            return ReceiveEvent(self, size)
    def send(self, data):
        """Sends data on the socket, returning the number of bytes
        successfully sent.
        """
        return SendEvent(self, data)
    def sendall(self, data):
        """Send all of data on the socket."""
        return SendEvent(self, data, True)
    def readline(self, terminator="\n", bufsize=1024):
        """Reads a line (delimited by terminator) from the socket."""
        while True:
            if terminator in self._buf:
                line, self._buf = self._buf.split(terminator, 1)
                line += terminator
                yield ReturnEvent(line)
                break
            data = yield ReceiveEvent(self, bufsize)
            if data:
                self._buf += data
            else:
                line = self._buf
                self._buf = ''
                yield ReturnEvent(line)
                break


# Public interface for threads; each returns an event object that
# can immediately be "yield"ed.

def null():
    """Event: yield to the scheduler without doing anything special.
    """
    return ValueEvent(None)

def spawn(coro):
    """Event: add another coroutine to the scheduler. Both the parent
    and child coroutines run concurrently.
    """
    if not isinstance(coro, types.GeneratorType):
        raise ValueError('%s is not a coroutine' % str(coro))
    return SpawnEvent(coro)

def call(coro):
    """Event: delegate to another coroutine. The current coroutine
    is resumed once the sub-coroutine finishes. If the sub-coroutine
    returns a value using end(), then this event returns that value.
    """
    if not isinstance(coro, types.GeneratorType):
        raise ValueError('%s is not a coroutine' % str(coro))
    return DelegationEvent(coro)

def end(value = None):
    """Event: ends the coroutine and returns a value to its
    delegator.
    """
    return ReturnEvent(value)

def read(fd, bufsize = None):
    """Event: read from a file descriptor asynchronously."""
    if bufsize is None:
        # Read all.
        def reader():
            buf = []
            while True:
                data = yield read(fd, 1024)
                if not data:
                    break
                buf.append(data)
            yield ReturnEvent(''.join(buf))
        return DelegationEvent(reader())

    else:
        return ReadEvent(fd, bufsize)

def write(fd, data):
    """Event: write to a file descriptor asynchronously."""
    return WriteEvent(fd, data)

def connect(host, port):
    """Event: connect to a network address and return a Connection
    object for communicating on the socket.
    """
    addr = (host, port)
    sock = socket.create_connection(addr)
    return ValueEvent(Connection(sock, addr))


# Convenience function for running socket servers.

def server(host, port, func):
    """A coroutine that runs a network server. Host and port specify the
    listening address. func should be a coroutine that takes a single
    parameter, a Connection object. The coroutine is invoked for every
    incoming connection on the listening socket.
    """
    def handler(conn):
        try:
            yield func(conn)
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
