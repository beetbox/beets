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

import os
import os.path
import shutil
import tempfile
from glob import glob

import beets
from beets import config
import beets.plugins
from beets.library import Library

# TODO Move this here, along with AutotagMock
from test_importer import TestImportSession
import _common


class TestHelper(object):
    """Helper mixin for high-level cli and plugin tests.

    This mixin provides methods to isolate beets' global state provide
    fixtures.
    """
    # TODO automate teardown through hook registration

    def setup_beets(self):
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
        self.temp_dir = tempfile.mkdtemp()
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

        self.lib = Library(self.config['library'].as_filename(),
                           self.libdir)
    
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
        for fixture in glob(os.path.join(_common.RSRC, '*.mp3'))[0:file_count]:
            shutil.copy(fixture, import_dir)

        config['import']['quiet'] = True
        config['import']['autotag'] = False
        config['import']['resume'] = False

        return TestImportSession(self.lib, logfile=None, query=None,
                                 paths=[import_dir])
