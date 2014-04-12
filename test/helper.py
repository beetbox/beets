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

import sys
import os
import os.path
import shutil
from tempfile import mkdtemp, mkstemp
from glob import glob
from contextlib import contextmanager
from StringIO import StringIO

import beets
from beets import config
import beets.plugins
from beets.library import Library, Item

# TODO Move this here, along with AutotagMock
from test_importer import TestImportSession
import _common


@contextmanager
def control_stdin(input=None):
    """Sends ``input`` to stdin.

    >>> with control_stdin('yes'):
    ...     input()
    'yes'
    """
    org = sys.stdin
    sys.stdin = StringIO(input)
    sys.stdin.encoding = 'utf8'
    try:
        yield sys.stdin
    finally:
        sys.stdin = org


@contextmanager
def capture_stdout():
    """Save stdout in a StringIO.

    >>> with capture_stdout() as output:
    ...     print('spam')
    ...
    >>> output.getvalue()
    'spam'
    """
    org = sys.stdout
    sys.stdout = StringIO()
    sys.stdout.encoding = 'utf8'
    try:
        yield sys.stdout
    finally:
        sys.stdout = org


class TestHelper(object):
    """Helper mixin for high-level cli and plugin tests.

    This mixin provides methods to isolate beets' global state provide
    fixtures.
    """
    # TODO automate teardown through hook registration

    def setup_beets(self, disk=False):
        """Setup pristine global configuration and library for testing.

        Sets ``beets.config`` so we can safely use any functionality
        that uses the global configuration.  All paths used are
        contained in a temporary directory

        Sets the following properties on itself.

        - ``temp_dir`` Path to a temporary directory containing all
          files specific to beets

        - ``libdir`` Path to a subfolder of ``temp_dir``, containing the
          library's media files. Same as ``config['directory']``.

        - ``config`` The global configuration used by beets.

        - ``lib`` Library instance created with the settings from
          ``config``.

        Make sure you call ``teardown_beets()`` afterwards.
        """
        self.temp_dir = mkdtemp()
        os.environ['BEETSDIR'] = self.temp_dir

        self.config = beets.config
        self.config.clear()
        self.config.read()

        self.config['plugins'] = []
        self.config['verbose'] = True
        self.config['color'] = False
        self.config['threaded'] = False

        self.libdir = os.path.join(self.temp_dir, 'libdir')
        os.mkdir(self.libdir)
        self.config['directory'] = self.libdir

        if disk:
            dbpath = self.config['library'].as_filename()
        else:
            dbpath = ':memory:'
        self.lib = Library(dbpath, self.libdir)

    def teardown_beets(self):
        del os.environ['BEETSDIR']
        # FIXME somehow close all open fd to the ilbrary
        shutil.rmtree(self.temp_dir)
        self.config.clear()

    def load_plugins(self, *plugins):
        """Load and initialize plugins by names.

        Similar setting a list of plugins in the configuration. Make
        sure you call ``unload_plugins()`` afterwards.
        """
        beets.config['plugins'] = plugins
        beets.plugins.load_plugins(plugins)
        beets.plugins.find_plugins()

    def unload_plugins(self):
        """Unload all plugins and remove the from the configuration.
        """
        beets.config['plugins'] = []
        for plugin in beets.plugins._classes:
            plugin.listeners = None
        beets.plugins._classes = set()
        beets.plugins._instances = {}

    def create_importer(self, file_count=1):
        """Returns import session with fixtures.

        Copies the specified number of files to a subdirectory of
        ``self.temp_dir`` and creates a ``TestImportSession`` for this
        path.
        """
        import_dir = os.path.join(self.temp_dir, 'import')
        if not os.path.isdir(import_dir):
            os.mkdir(import_dir)

        for i in range(file_count):
            title = 'track {0}'.format(i)
            src = os.path.join(_common.RSRC, 'full.mp3')
            dest = os.path.join(import_dir, '{0}.mp3'.format(title))
            shutil.copy(src, dest)

        config['import']['quiet'] = True
        config['import']['autotag'] = False
        config['import']['resume'] = False

        return TestImportSession(self.lib, logfile=None, query=None,
                                 paths=[import_dir])

    def add_item_fixtures(self, ext='mp3', count=1):
        items = []
        paths = glob(os.path.join(_common.RSRC, '*.' + ext))
        for path in paths[0:count]:
            item = Item.from_path(str(path))
            item.add(self.lib)
            item.move(copy=True)
            item.store()
            items.append(item)
        return items

    def create_mediafile_fixture(self, ext='mp3'):
        """Copies a fixture mediafile with the extension to a temporary
        location and returns the path.

        It keeps track of the created locations and will delete the with
        `remove_mediafile_fixtures()`
        """
        src = os.path.join(_common.RSRC, 'full.' + ext)
        handle, path = mkstemp()
        os.close(handle)
        shutil.copyfile(src, path)

        if not hasattr(self, '_mediafile_fixtures'):
            self._mediafile_fixtures = []
        self._mediafile_fixtures.append(path)

        return path

    def remove_mediafile_fixtures(self):
        if hasattr(self, '_mediafile_fixtures'):
            for path in self._mediafile_fixtures:
                os.remove(path)

    def run_command(self, *args):
        if hasattr(self, 'lib'):
            lib = self.lib
        else:
            lib = Library(':memory:')
        beets.ui._raw_main(list(args), lib)
