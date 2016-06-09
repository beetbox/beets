#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

import os
from os import path
import sys
import subprocess
import shutil
from setuptools.dist import Distribution
from setuptools.command.sdist import sdist as default_sdist
from distutils.errors import DistutilsExecError
from setuptools import setup, Command


class BeetsDistribution(Distribution):
    def __init__(self, *args, **kwargs):
        self.sdist_requires = None
        Distribution.__init__(self, *args, **kwargs)

    def _get_path(self, env=False):
        """Return an array of paths currently in the python path."""
        if env:
            path = os.environ.get('PYTHONPATH', '').split(':')
        else:
            path = sys.path

        return set([p for p in path if len(p) > 0])

    def export_live_eggs(self, env=False):
        """Adds all of the eggs in the current environment to PYTHONPATH."""
        path_eggs = [p for p in self._get_path(env) if p.endswith('.egg')]

        os.environ['PYTHONPATH'] = ':'.join(path_eggs)


class sdist(default_sdist):  # noqa: ignore=N801
    """Custom sdist that builds the man pages before the normal sdist build."""

    def __init__(self, *args, **kwargs):
        default_sdist.__init__(self, *args, **kwargs)
        self._setup_directory = path.dirname(__file__)
        self._docs_directory = path.join(self._setup_directory, 'docs')
        self._man_directory = path.join(self._setup_directory, 'man')
        self._built_man_directory = path.join(self._docs_directory, '_build',
                                              'man')

    def _copy_man_pages(self):
        """Copy the built man pages to the output directory."""
        if path.exists(self._man_directory):
            shutil.rmtree(self._man_directory)

        # Copy built man pages.
        shutil.copytree(self._built_man_directory, self._man_directory)

    def _build_man_pages(self):
        """Build the man pages using make."""
        # Add eggs to PYTHONPATH. We need to do this to ensure our eggs are
        # seen by the new python instance.
        self.distribution.export_live_eggs()

        try:
            # Build man pages using make.
            subprocess.check_call(['make', 'man'], cwd=self._docs_directory)
        except (subprocess.CalledProcessError, OSError):
            return False

        return True

    def run(self, *args, **kwargs):
        install_requires = self.distribution.install_requires
        sdist_requires = self.distribution.sdist_requires

        # Install install dependencies if needed.
        if install_requires:
            self.distribution.fetch_build_eggs(install_requires)

        # Install sdist dependencies if needed.
        if sdist_requires:
            self.distribution.fetch_build_eggs(sdist_requires)

        if self._build_man_pages():
            self._copy_man_pages()
        else:
            raise DistutilsExecError('could not build man pages')

        # Run the default sdist task.
        default_sdist.run(self, *args, **kwargs)


class test(Command):  # noqa: ignore=N801
    """Command to run tox."""

    description = "run tox tests"

    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        self.tox_args = ''

    def finalize_options(self):
        pass

    def run(self):
        # Install test dependencies if needed.
        if self.distribution.tests_require:
            self.distribution.fetch_build_eggs(self.distribution.tests_require)

        # Add eggs to PYTHONPATH. We need to do this to ensure our eggs are
        # seen by Tox.
        self.distribution.export_live_eggs()

        import shlex
        import tox

        parsed_args = shlex.split(self.tox_args)
        result = tox.cmdline(args=parsed_args)

        sys.exit(result)


def _read(filename):
    relative_path = path.join(path.dirname(__file__), filename)
    return open(relative_path).read()


setup(
    name='beets',
    version='1.3.19',
    description='music tagger and library organizer',
    author='Adrian Sampson',
    author_email='adrian@radbox.org',
    url='http://beets.io/',
    license='MIT',
    platforms='ALL',
    long_description=_read('README.rst'),
    include_package_data=True,  # Install plugin resources.

    packages=[
        'beets',
        'beets.ui',
        'beets.autotag',
        'beets.util',
        'beets.dbcore',
        'beetsplug',
        'beetsplug.bpd',
        'beetsplug.web',
        'beetsplug.lastgenre',
        'beetsplug.metasync',
    ],
    entry_points={
        'console_scripts': [
            'beet = beets.ui:main',
        ],
    },

    install_requires=[
        'enum34>=1.0.4',
        'mutagen>=1.27',
        'munkres',
        'unidecode',
        'musicbrainzngs>=0.4',
        'pyyaml',
        'jellyfish',
    ] + (['colorama'] if (sys.platform == 'win32') else []),

    tests_require=[
        'tox',
    ],

    sdist_requires=[
        'sphinx',
    ],

    cmdclass={
        'sdist': sdist,
        'test': test
    },

    # Plugin (optional) dependencies:
    extras_require={
        'fetchart': ['requests'],
        'chroma': ['pyacoustid'],
        'discogs': ['discogs-client>=2.1.0'],
        'lastgenre': ['pylast'],
        'mpdstats': ['python-mpd2'],
        'web': ['flask', 'flask-cors'],
        'import': ['rarfile'],
        'thumbnails': ['pathlib', 'pyxdg'],
        'metasync': ['dbus-python'],
    },
    # Non-Python/non-PyPI plugin dependencies:
    # convert: ffmpeg
    # bpd: pygst

    classifiers=[
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    distclass=BeetsDistribution
)
