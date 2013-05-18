# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

"""Some common functionality for beets' test cases."""
import time
import sys
import os
import logging
import tempfile
import shutil

# Use unittest2 on Python < 2.7.
try:
    import unittest2 as unittest
except ImportError:
    import unittest

# Mangle the search path to include the beets sources.
sys.path.insert(0, '..')
import beets.library
from beets import importer
from beets.ui import commands
import beets

# Suppress logging output.
log = logging.getLogger('beets')
log.setLevel(logging.CRITICAL)

# Test resources/sandbox path.
RSRC = os.path.join(os.path.dirname(__file__), 'rsrc')

# Dummy item creation.
_item_ident = 0
def item():
    global _item_ident
    _item_ident += 1
    return beets.library.Item({
        'title':            u'the title',
        'artist':           u'the artist',
        'albumartist':      u'the album artist',
        'album':            u'the album',
        'genre':            u'the genre',
        'composer':         u'the composer',
        'grouping':         u'the grouping',
        'year':             1,
        'month':            2,
        'day':              3,
        'track':            4,
        'tracktotal':       5,
        'disc':             6,
        'disctotal':        7,
        'lyrics':           u'the lyrics',
        'comments':         u'the comments',
        'bpm':              8,
        'comp':             True,
        'path':             'somepath' + str(_item_ident),
        'length':           60.0,
        'bitrate':          128000,
        'format':           'FLAC',
        'mb_trackid':       'someID-1',
        'mb_albumid':       'someID-2',
        'mb_artistid':      'someID-3',
        'mb_albumartistid': 'someID-4',
        'album_id':         None,
    })

# Dummy import session.
def import_session(lib=None, logfile=None, paths=[], query=[], cli=False):
    cls = commands.TerminalImportSession if cli else importer.ImportSession
    return cls(lib, logfile, paths, query)

# A test harness for all beets tests.
# Provides temporary, isolated configuration.
class TestCase(unittest.TestCase):
    """A unittest.TestCase subclass that saves and restores beets'
    global configuration. This allows tests to make temporary
    modifications that will then be automatically removed when the test
    completes. Also provides some additional assertion methods, a
    temporary directory, and a DummyIO.
    """
    def setUp(self):
        # A "clean" source list including only the defaults.
        beets.config.sources = []
        beets.config._materialized = True
        beets.config.read(user=False, defaults=True)

        # Direct paths to a temporary directory. Tests can also use this
        # temporary directory.
        self.temp_dir = tempfile.mkdtemp()
        beets.config['statefile'] = os.path.join(self.temp_dir, 'state.pickle')
        beets.config['library'] = os.path.join(self.temp_dir, 'library.db')
        beets.config['directory'] = os.path.join(self.temp_dir, 'libdir')

        # Set $HOME, which is used by confit's `config_dir()` to create
        # directories.
        self._old_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir

        # Initialize, but don't install, a DummyIO.
        self.io = DummyIO()

    def tearDown(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.environ['HOME'] = self._old_home
        self.io.restore()

    def assertExists(self, path):
        self.assertTrue(os.path.exists(path),
                        'file does not exist: %s' % path)

    def assertNotExists(self, path):
        self.assertFalse(os.path.exists(path),
                        'file exists: %s' % path)



# Mock timing.

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


# Mock I/O.

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


# Utility.

def touch(path):
    open(path, 'a').close()

class Bag(object):
    """An object that exposes a set of fields given as keyword
    arguments. Any field not found in the dictionary appears to be None.
    Used for mocking Album objects and the like.
    """
    def __init__(self, **fields):
        self.fields = fields

    def __getattr__(self, key):
        return self.fields.get(key)
