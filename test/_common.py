"""Some common functionality for beets' test cases."""
import time
import sys

class Timecop(object):
    """Mocks the timing system (namely time() and sleep()) for testing.
    Inspired by the Ruby timecop library.
    """
    def __init__(self):
        self.now = time.time()

    def time(self):
        return self.now
    
    def sleep(self, amount):
        self.now += amount

    def install(self):
        self.orig = {
            'time': time.time,
            'sleep': time.sleep,
        }
        time.time = self.time
        time.sleep = self.sleep

    def restore(self):
        time.time = self.orig['time']
        time.sleep = self.orig['sleep']

class InputException(Exception):
    def __init__(self, output=None):
        self.output = output
    def __str__(self):
        msg = "Attempt to read with no input provided."
        if self.output is not None:
            msg += " Output: %s" % repr(self.output)
        return msg
class DummyOut(object):
    encoding = 'utf8'
    def __init__(self):
        self.buf = []
    def write(self, s):
        self.buf.append(s)
    def get(self):
        return ''.join(self.buf)
    def clear(self):
        self.buf = []
class DummyIn(object):
    encoding = 'utf8'
    def __init__(self, out=None):
        self.buf = []
        self.reads = 0
        self.out = out
    def add(self, s):
        self.buf.append(s + '\n')
    def readline(self):
        if not self.buf:
            if self.out:
                raise InputException(self.out.get())
            else:
                raise InputException()
        self.reads += 1
        return self.buf.pop(0)
class DummyIO(object):
    """Mocks input and output streams for testing UI code."""
    def __init__(self):
        self.stdout = DummyOut()
        self.stdin = DummyIn(self.stdout)

    def addinput(self, s):
        self.stdin.add(s)

    def getoutput(self):
        res = self.stdout.get()
        self.stdout.clear()
        return res
    
    def readcount(self):
        return self.stdin.reads

    def install(self):
        sys.stdin = self.stdin
        sys.stdout = self.stdout

    def restore(self):
        sys.stdin = sys.__stdin__
        sys.stdout = sys.__stdout__
