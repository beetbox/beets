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

from os import path
import sys
import subprocess
import shutil
from setuptools.dist import Distribution
from setuptools.command.sdist import sdist as default_sdist
import warnings
from setuptools import setup, Command


class BeetsDistribution(Distribution):
    def __init__(self, *args, **kwargs):
        self.sdist_requires = None
        Distribution.__init__(self, *args, **kwargs)


class sdist(default_sdist):  # noqa: ignore=N801
    def __init__(self, *args, **kwargs):
        default_sdist.__init__(self, *args, **kwargs)

    def _build_man_pages(self):
        # Work out directories.
        setup_directory = path.dirname(__file__)
        docs_directory = path.join(setup_directory, 'docs')
        man_directory = path.join(setup_directory, 'man')
        built_man_directory = path.join(docs_directory, '_build', 'man')

        # Build man pages.
        try:
            subprocess.check_call(['make', 'man'], cwd=docs_directory)
        except OSError:
            warnings.warn('Could not build man pages')
            return

        if path.exists(man_directory):
            shutil.rmtree(man_directory)

        # Copy built man pages.
        shutil.copytree(built_man_directory, man_directory)

    def run(self, *args, **kwargs):
        sdist_requires = self.distribution.sdist_requires

        # Install sdist dependencies if needed.
        if sdist_requires:
            self.distribution.fetch_build_eggs(sdist_requires)

        self._build_man_pages()

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

        import shlex
        import tox

        args = self.tox_args
        if args:
            args = shlex.split(self.tox_args)
        errno = tox.cmdline(args=args)
        sys.exit(errno)


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
